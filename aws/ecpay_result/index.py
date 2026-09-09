"""flight-ecpay-result — ANY /ecpay-result (ECPay OrderResultURL, browser POST)

ECPay sends the shopper's browser back with a POST; a static SPA answers 405.
This Lambda only turns that POST into a 302 to the app. It never activates anything
(the S2S ReturnURL is the source of truth).
"""
import os

from ecpay import parse_form_body

SITE_URL = os.environ["SITE_URL"].strip().rstrip("/")


def handler(event, _context):
    try:
        params = parse_form_body(event)
    except Exception:
        params = {}
    ok = params.get("RtnCode") == "1"
    print(f"result: RtnCode={params.get('RtnCode')} trade_no={params.get('MerchantTradeNo')} -> {'success' if ok else 'failed'}")
    return {"statusCode": 302,
            "headers": {"Location": f"{SITE_URL}/app?purchase={'success' if ok else 'failed'}",
                        "cache-control": "no-store"},
            "body": ""}
