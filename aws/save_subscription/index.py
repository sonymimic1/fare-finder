"""flight-save-subscription — POST /subscribe

Body: {"email": str, "plan_name": "tokyo"|"seoul", "target_price": number (TWD)}
Writes one row to DynamoDB `subscriptions` (PK email, SK route).
M1: no subscription_status / payment fields.
"""
import base64
import json
import time
from decimal import Decimal

import boto3

PLANS = {
    "tokyo": {"origin": "TPE", "destination": "TYO"},
    "seoul": {"origin": "TPE", "destination": "SEL"},
}
TABLE = boto3.resource("dynamodb").Table("subscriptions")
HEADERS = {"content-type": "application/json"}


def _resp(status, body):
    return {"statusCode": status, "headers": HEADERS, "body": json.dumps(body, ensure_ascii=False)}


def _parse_body(event):
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    return json.loads(raw)


def handler(event, _context):
    try:
        data = _parse_body(event)
    except Exception:
        return _resp(400, {"error": "invalid JSON body"})

    email = str(data.get("email") or "").strip().lower()
    plan_name = str(data.get("plan_name") or "").strip().lower()
    target_price = data.get("target_price")

    if "@" not in email or len(email) > 254:
        return _resp(400, {"error": "invalid email"})
    if plan_name not in PLANS:
        return _resp(400, {"error": "plan_name must be one of: " + ", ".join(PLANS)})
    try:
        tp = Decimal(str(target_price))
    except Exception:
        return _resp(400, {"error": "target_price must be a number"})
    if not tp.is_finite() or tp <= 0 or tp > 1_000_000:
        return _resp(400, {"error": "target_price out of range"})

    plan = PLANS[plan_name]
    route = f"{plan['origin']}-{plan['destination']}"
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    existing = TABLE.get_item(Key={"email": email, "route": route}).get("Item")
    item = {
        "email": email,
        "route": route,
        "plan_name": plan_name,
        "origin": plan["origin"],
        "destination": plan["destination"],
        "target_price": tp,
        "currency": "TWD",
        "created_at": existing["created_at"] if existing else now,
        "updated_at": now,
    }
    TABLE.put_item(Item=item)
    print(f"saved subscription email={email} route={route} target_price={tp}")

    item["target_price"] = int(tp)
    return _resp(200, {"ok": True, "subscription": item})
