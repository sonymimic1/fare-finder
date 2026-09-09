"""flight-cancel-subscription — POST /cancel  body {"email","route"}

Calls ECPay CreditCardPeriodAction Action=Cancel (stops future charges), then marks the
row `cancelled` (NOT expired) keeping current_period_end so the parser keeps serving the
already-paid period, and enqueues {event_type:"cancel"} on flight-status-queue.
"""
import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal

import boto3

from ecpay import ecpay_config, gen_cmv, json_response
from periods import next_period_end, now_str

TABLE = boto3.resource("dynamodb").Table("subscriptions")
_sqs = boto3.client("sqs")
STATUS_QUEUE_URL = os.environ["STATUS_QUEUE_URL"]
UA = "Mozilla/5.0 (compatible; flight-notifier/1.0)"


def _plain(item):
    return {k: (int(v) if isinstance(v, Decimal) else v) for k, v in item.items()}


def ecpay_cancel(cfg, trade_no):
    params = {"MerchantID": cfg["merchant_id"], "MerchantTradeNo": trade_no,
              "Action": "Cancel", "TimeStamp": str(int(time.time()))}
    params["CheckMacValue"] = gen_cmv(params, cfg["hash_key"], cfg["hash_iv"])
    req = urllib.request.Request(cfg["period_action_url"], data=urllib.parse.urlencode(params).encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as ex:
        body = f"HTTP {ex.code}: " + ex.read().decode("utf-8", "replace")
    except Exception as ex:
        body = f"error: {ex}"
    resp = dict(urllib.parse.parse_qsl(body, keep_blank_values=True)) if "=" in body else {"raw": body}
    print(f"cancel: ECPay CreditCardPeriodAction trade_no={trade_no} -> {resp}")
    return resp


def handler(event, _context):
    try:
        raw = event.get("body") or "{}"
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw).decode("utf-8")
        data = json.loads(raw)
    except Exception:
        return json_response({"error": "invalid JSON body"}, 400)
    email = str(data.get("email") or "").strip().lower()
    route = str(data.get("route") or "").strip()
    if "@" not in email or not route:
        return json_response({"error": "email and route required"}, 400)

    row = TABLE.get_item(Key={"email": email, "route": route}).get("Item")
    if not row:
        return json_response({"error": "subscription not found"}, 404)
    status = row.get("subscription_status")
    if status in ("cancelled", "expired"):
        return json_response({"ok": True, "subscription": _plain(row), "note": f"already {status}"})
    if status != "active":
        return json_response({"error": f"cannot cancel a subscription in status {status or 'pending_payment'}"}, 400)

    cfg = ecpay_config()
    ecpay_resp = ecpay_cancel(cfg, str(row.get("merchant_trade_no") or "")) if row.get("merchant_trade_no") else {"raw": "no merchant_trade_no on row"}

    now = now_str()
    period_end = str(row.get("current_period_end") or "")
    period_end_date = str(row.get("current_period_end_date") or "")
    if not period_end:  # legacy active row without period tracking -> grace of one period from now
        period_end, period_end_date = next_period_end(str(row.get("period_type") or "M"), int(row.get("frequency") or 1))
    res = TABLE.update_item(
        Key={"email": email, "route": route},
        UpdateExpression=("SET subscription_status = :c, current_period_end = :e, current_period_end_date = :d, "
                          "cancelled_at = :n, updated_at = :n, ecpay_cancel_rtn = :r"),
        ExpressionAttributeValues={":c": "cancelled", ":e": period_end, ":d": period_end_date, ":n": now,
                                   ":r": str(ecpay_resp.get("RtnCode", "")) + "|" + str(ecpay_resp.get("RtnMsg", ecpay_resp.get("raw", "")))[:80]},
        ReturnValues="ALL_NEW")
    print(f"cancel: {email}#{route} -> cancelled, service until {period_end}")
    _sqs.send_message(QueueUrl=STATUS_QUEUE_URL, MessageBody=json.dumps(
        {"event_type": "cancel", "email": email, "route": route,
         "merchant_trade_no": row.get("merchant_trade_no"), "current_period_end_date": period_end_date}))
    return json_response({"ok": True, "subscription": _plain(res["Attributes"])})
