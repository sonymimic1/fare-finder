"""flight-list-subscriptions — GET /subscriptions?email=...

Returns all subscription rows for one email.
Security note: trusts the client-supplied email (no auth) — acceptable for the
M1 course build; production would verify the Supabase JWT first.
"""
import json
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

TABLE = boto3.resource("dynamodb").Table("subscriptions")
HEADERS = {"content-type": "application/json"}


def _plain(v):
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_plain(x) for x in v]
    return v


def _resp(status, body):
    return {"statusCode": status, "headers": HEADERS, "body": json.dumps(body, ensure_ascii=False)}


def handler(event, _context):
    params = event.get("queryStringParameters") or {}
    email = str(params.get("email") or "").strip().lower()
    if "@" not in email:
        return _resp(400, {"error": "email query parameter required"})

    res = TABLE.query(KeyConditionExpression=Key("email").eq(email))
    items = [_plain(i) for i in res.get("Items", [])]
    return _resp(200, {"ok": True, "email": email, "subscriptions": items})
