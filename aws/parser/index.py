"""flight-parser — one route per invocation.

Event: {"origin": "TPE", "destination": "TYO", "route": "TPE-TYO"}
1. read Travelpayouts token from Secrets Manager (flight/travelpayouts)
2. fetch cheapest fare for next month in TWD (the gate) and USD (best-effort)
3. scan `subscriptions` for this route; every subscriber whose target_price >= cheapest TWD
   gets a message on flight-fare-queue. M1: no subscription_status filter.
"""
import datetime
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr

UA = "Mozilla/5.0 (compatible; flight-notifier/1.0)"
SECRET_ID = os.environ.get("TRAVELPAYOUTS_SECRET", "flight/travelpayouts")
QUEUE_URL = os.environ["QUEUE_URL"]

_sm = boto3.client("secretsmanager")
_sqs = boto3.client("sqs")
_table = boto3.resource("dynamodb").Table("subscriptions")
_token_cache = {}


def _token():
    if "token" not in _token_cache:
        s = json.loads(_sm.get_secret_value(SecretId=SECRET_ID)["SecretString"])
        _token_cache["token"] = s["token"]
    return _token_cache["token"]


def next_month(today=None):
    d = today or datetime.date.today()
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return f"{y:04d}-{m:02d}"


def fetch_cheapest(origin, destination, month, token, currency):
    q = urllib.parse.urlencode({"origin": origin, "destination": destination,
                                "depart_date": month, "currency": currency, "token": token})
    req = urllib.request.Request(f"https://api.travelpayouts.com/v1/prices/cheap?{q}",
                                 headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = json.loads(r.read())
    except urllib.error.HTTPError as ex:
        print(f"travelpayouts HTTP {ex.code} for {origin}-{destination} {currency}")
        return None
    except Exception as ex:  # timeout / network
        print(f"travelpayouts error for {origin}-{destination} {currency}: {ex}")
        return None
    if not body.get("success") or not body.get("data"):
        return None
    offers = body["data"].get(destination, {})
    if not offers:
        return None
    best = min(offers.values(), key=lambda o: o["price"])
    return {"price": best["price"], "currency": currency.upper(), "airline": best.get("airline"),
            "depart_date": best.get("departure_at"), "return_date": best.get("return_at")}


def handler(event, _context):
    origin = event["origin"]
    destination = event["destination"]
    route = event.get("route") or f"{origin}-{destination}"
    month = event.get("month") or next_month()
    token = _token()

    tw = fetch_cheapest(origin, destination, month, token, "twd")
    if not tw:
        print(f"no TWD fare for {route} {month} (empty/429) - skipping")
        return {"ok": True, "route": route, "month": month, "matched": 0}
    us = fetch_cheapest(origin, destination, month, token, "usd")  # may be None - never block on it
    print(f"{route} {month} cheapest {tw['price']} TWD ({tw['airline']}) usd={us['price'] if us else None}")

    cheapest_twd = Decimal(str(tw["price"]))
    matched = 0
    skipped = {"unpaid": 0, "expired": 0, "below_target": 0}
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    scan_kwargs = {"FilterExpression": Attr("route").eq(route)}
    while True:
        res = _table.scan(**scan_kwargs)
        for it in res.get("Items", []):
            # M2 paywall gate: serve active, and cancelled rows still inside their paid period;
            # lazily expire cancelled rows whose period has lapsed. pending_payment/expired/legacy never.
            status = it.get("subscription_status")
            period_end = str(it.get("current_period_end") or "")
            if status == "cancelled" and period_end < now:
                _table.update_item(Key={"email": it["email"], "route": route},
                                   UpdateExpression="SET subscription_status = :x, updated_at = :n",
                                   ExpressionAttributeValues={":x": "expired", ":n": now})
                print(f"expired {it['email']} (cancelled, period ended {period_end})")
                skipped["expired"] += 1
                continue
            if not (status == "active" or (status == "cancelled" and period_end >= now)):
                skipped["unpaid"] += 1
                continue
            tp = Decimal(str(it.get("target_price", 0)))
            if tp < cheapest_twd:
                skipped["below_target"] += 1
                continue
            body = {"email": it["email"], "route": route, "plan_name": it.get("plan_name"),
                    "target_price": int(tp),
                    "cheapest": {"price": tw["price"], "currency": "TWD", "airline": tw["airline"],
                                 "depart_date": tw["depart_date"], "return_date": tw["return_date"]}}
            if us:
                body["cheapest_usd"] = {"price": us["price"], "currency": "USD", "airline": us["airline"],
                                        "depart_date": us["depart_date"], "return_date": us["return_date"]}
            _sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps(body))
            matched += 1
            print(f"match {it['email']} target={tp} cheapest={cheapest_twd} -> enqueued")
        if "LastEvaluatedKey" not in res:
            break
        scan_kwargs["ExclusiveStartKey"] = res["LastEvaluatedKey"]

    print(f"{route}: matched={matched} skipped={skipped}")
    return {"ok": True, "route": route, "month": month, "cheapest_twd": tw["price"], "matched": matched, "skipped": skipped}
