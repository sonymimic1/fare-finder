"""ECPay (綠界) helpers shared by the M2 Lambdas — stdlib only.

- CheckMacValue (SHA256, EncryptType=1) per the official ecpayUrlEncode rules
- form-urlencoded body parsing for API Gateway HTTP API v2 events (keeps empty-string fields)
- flight/ecpay secret loader
"""
import base64
import hashlib
import json
import os
import urllib.parse

import boto3

ECPAY_SECRET = os.environ.get("ECPAY_SECRET", "flight/ecpay")
STAGE_CASHIER = "https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5"
PROD_CASHIER = "https://payment.ecpay.com.tw/Cashier/AioCheckOut/V5"
STAGE_PERIOD_ACTION = "https://payment-stage.ecpay.com.tw/Cashier/CreditCardPeriodAction"
PROD_PERIOD_ACTION = "https://payment.ecpay.com.tw/Cashier/CreditCardPeriodAction"

_cache = {}


def ecpay_url_encode(s):
    e = urllib.parse.quote_plus(str(s)).replace("~", "%7E")  # quote_plus leaves ~ literal
    e = e.lower()
    for old, new in (("%2d", "-"), ("%5f", "_"), ("%2e", "."), ("%21", "!"),
                     ("%2a", "*"), ("%28", "("), ("%29", ")")):
        e = e.replace(old, new)
    return e


def gen_cmv(params, hash_key, hash_iv):
    items = {k: v for k, v in params.items() if k != "CheckMacValue"}  # KEEP "" values
    body = "&".join(f"{k}={items[k]}" for k in sorted(items, key=str.lower))
    raw = f"HashKey={hash_key}&{body}&HashIV={hash_iv}"
    return hashlib.sha256(ecpay_url_encode(raw).encode("utf-8")).hexdigest().upper()


def verify_cmv(params, hash_key, hash_iv):
    return str(params.get("CheckMacValue", "")).upper() == gen_cmv(params, hash_key, hash_iv)


def ecpay_config():
    """{merchant_id, hash_key, hash_iv, env, amount, cashier_url, period_action_url}"""
    if not _cache:
        s = json.loads(boto3.client("secretsmanager").get_secret_value(SecretId=ECPAY_SECRET)["SecretString"])
        prod = str(s.get("env", "stage")).lower() == "prod"
        s["cashier_url"] = PROD_CASHIER if prod else STAGE_CASHIER
        s["period_action_url"] = PROD_PERIOD_ACTION if prod else STAGE_PERIOD_ACTION
        _cache.update(s)
    return _cache


def parse_form_body(event):
    """API Gateway v2 event -> dict of form fields (first value each), keeping blank values."""
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    return {k: v[0] for k, v in urllib.parse.parse_qs(raw, keep_blank_values=True).items()}


def text_response(body, status=200):
    return {"statusCode": status, "headers": {"content-type": "text/plain; charset=utf-8"}, "body": body}


def json_response(body, status=200):
    return {"statusCode": status, "headers": {"content-type": "application/json"},
            "body": json.dumps(body, ensure_ascii=False)}
