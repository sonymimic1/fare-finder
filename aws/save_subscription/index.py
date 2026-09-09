"""flight-save-subscription — POST /subscribe (M2: ECPay recurring checkout)

Body: {"email": str, "plan_name": "tokyo"|"seoul", "target_price": number (TWD)}

- Row already active, or cancelled and still inside its paid period -> update target_price
  in place, keep status, return JSON.
- Otherwise (new / pending_payment / expired / legacy M1 row without status) -> write
  subscription_status=pending_payment + a fresh MerchantTradeNo, build the ECPay
  credit-card recurring (定期定額) AIO form signed with CheckMacValue and return it as
  text/html (auto-submit). Only the ReturnURL callback may ever set `active`.
"""
import base64
import datetime
import html
import json
import os
import time
import uuid
from decimal import Decimal

import boto3

from ecpay import ecpay_config, gen_cmv, json_response

PLANS = {
    "tokyo": {"origin": "TPE", "destination": "TYO"},
    "seoul": {"origin": "TPE", "destination": "SEL"},
}
TABLE = boto3.resource("dynamodb").Table("subscriptions")
API_BASE = os.environ["API_BASE"].strip().rstrip("/")
SITE_URL = os.environ["SITE_URL"].strip().rstrip("/")
PERIOD_TYPE = os.environ.get("PERIOD_TYPE", "M").strip()      # M (monthly); set D for renewal testing
FREQUENCY = os.environ.get("FREQUENCY", "1").strip()
EXEC_TIMES = os.environ.get("EXEC_TIMES", "999").strip()       # ECPay requires >= 2; 999 ~ "indefinite"
TPE = datetime.timezone(datetime.timedelta(hours=8))


def _now_utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _parse_body(event):
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    return json.loads(raw)


def _plain(item):
    return {k: (int(v) if isinstance(v, Decimal) else v) for k, v in item.items()}


def _new_trade_no():
    return ("FN" + uuid.uuid4().hex.upper())[:20]  # <= 20 chars, alphanumeric


def _build_checkout(cfg, email, route, trade_no):
    amount = str(int(Decimal(str(cfg.get("amount", "300")))))
    params = {
        "MerchantID": cfg["merchant_id"],
        "MerchantTradeNo": trade_no,
        "MerchantTradeDate": datetime.datetime.now(TPE).strftime("%Y/%m/%d %H:%M:%S"),
        "PaymentType": "aio",
        "TotalAmount": amount,
        "TradeDesc": "Flight Price Notifier monthly subscription",
        "ItemName": "Flight Price Notifier monthly plan",
        "ReturnURL": f"{API_BASE}/ecpay-return",
        "ChoosePayment": "Credit",
        "EncryptType": "1",
        "PeriodAmount": amount,
        "PeriodType": PERIOD_TYPE,
        "Frequency": FREQUENCY,
        "ExecTimes": EXEC_TIMES,
        "PeriodReturnURL": f"{API_BASE}/ecpay-period",
        "OrderResultURL": f"{API_BASE}/ecpay-result",
        "ClientBackURL": f"{SITE_URL}/app",
        "CustomField1": email,
        "CustomField2": route,
    }
    params["CheckMacValue"] = gen_cmv(params, cfg["hash_key"], cfg["hash_iv"])
    inputs = "\n".join(
        f'<input type="hidden" name="{html.escape(k)}" value="{html.escape(str(v), quote=True)}">'
        for k, v in params.items())
    return f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><title>Redirecting to ECPay…</title></head>
<body style="font-family:sans-serif;padding:2rem;text-align:center">
<p>正在前往綠界付款頁… / Redirecting to ECPay checkout…</p>
<form id="ecpay" action="{cfg['cashier_url']}" method="post">
{inputs}
<noscript><button type="submit">前往付款 / Continue to payment</button></noscript>
</form>
<script>document.forms[0].submit()</script>
</body></html>"""


def handler(event, _context):
    try:
        data = _parse_body(event)
    except Exception:
        return json_response({"error": "invalid JSON body"}, 400)

    email = str(data.get("email") or "").strip().lower()
    plan_name = str(data.get("plan_name") or "").strip().lower()
    try:
        tp = Decimal(str(data.get("target_price")))
    except Exception:
        return json_response({"error": "target_price must be a number"}, 400)
    if "@" not in email or len(email) > 254:
        return json_response({"error": "invalid email"}, 400)
    if plan_name not in PLANS:
        return json_response({"error": "plan_name must be one of: " + ", ".join(PLANS)}, 400)
    if not tp.is_finite() or tp <= 0 or tp > 1_000_000:
        return json_response({"error": "target_price out of range"}, 400)

    plan = PLANS[plan_name]
    route = f"{plan['origin']}-{plan['destination']}"
    now = _now_utc()
    existing = TABLE.get_item(Key={"email": email, "route": route}).get("Item") or {}
    status = existing.get("subscription_status")
    in_grace = status == "cancelled" and str(existing.get("current_period_end", "")) >= now

    if status == "active" or in_grace:
        # paid user: update the target in place, never bounce them back to pending_payment
        res = TABLE.update_item(
            Key={"email": email, "route": route},
            UpdateExpression="SET target_price = :tp, updated_at = :now",
            ExpressionAttributeValues={":tp": tp, ":now": now},
            ReturnValues="ALL_NEW")
        print(f"updated target email={email} route={route} status={status} target={tp}")
        return json_response({"ok": True, "subscription": _plain(res["Attributes"])})

    # new / pending_payment / expired / legacy row -> (re)start checkout
    cfg = ecpay_config()
    trade_no = _new_trade_no()
    item = {
        "email": email, "route": route, "plan_name": plan_name,
        "origin": plan["origin"], "destination": plan["destination"],
        "target_price": tp, "currency": "TWD",
        "subscription_status": "pending_payment",
        "merchant_trade_no": trade_no,
        "period_type": PERIOD_TYPE, "frequency": int(FREQUENCY),
        "created_at": existing.get("created_at", now), "updated_at": now,
    }
    TABLE.put_item(Item=item)
    print(f"pending_payment email={email} route={route} target={tp} trade_no={trade_no}")
    return {"statusCode": 200, "headers": {"content-type": "text/html; charset=utf-8"},
            "body": _build_checkout(cfg, email, route, trade_no)}
