"""flight-ecpay-return — POST /ecpay-return (ECPay ReturnURL, first charge, S2S)

The ONLY place (with ecpay_period) that sets subscription_status=active.
form-urlencoded body -> verify CheckMacValue (empty fields kept) + MerchantID
-> RtnCode=="1" and not SimulatePaid -> UpdateItem active + current_period_end
-> enqueue {event_type:"welcome"} on flight-status-queue -> reply text/plain "1|OK".
"""
import json
import os

import boto3

from ecpay import ecpay_config, parse_form_body, text_response, verify_cmv
from periods import next_period_end, now_str

TABLE = boto3.resource("dynamodb").Table("subscriptions")
_sqs = boto3.client("sqs")
STATUS_QUEUE_URL = os.environ["STATUS_QUEUE_URL"]


def activate(params, *, source):
    """Shared by return + period: flips/keeps the row active and refreshes the period end."""
    cfg = ecpay_config()
    email = (params.get("CustomField1") or "").strip().lower()
    route = (params.get("CustomField2") or "").strip()
    trade_no = params.get("MerchantTradeNo", "")
    if not email or not route:
        print(f"{source}: missing CustomField1/2, trade_no={trade_no}")
        return "0|MissingCustomFields", 400
    row = TABLE.get_item(Key={"email": email, "route": route}).get("Item") or {}
    if not row:
        print(f"{source}: no subscription row for {email}#{route} trade_no={trade_no}")
        return "1|OK", 200  # nothing to activate; ack so ECPay stops retrying
    if row.get("merchant_trade_no") and row["merchant_trade_no"] != trade_no:
        print(f"{source}: trade_no mismatch row={row['merchant_trade_no']} cb={trade_no} for {email}#{route}")
    period_type = str(row.get("period_type") or params.get("PeriodType") or "M")
    frequency = int(row.get("frequency") or params.get("Frequency") or 1)
    end, end_date = next_period_end(period_type, frequency, str(row.get("current_period_end") or ""))
    now = now_str()
    TABLE.update_item(
        Key={"email": email, "route": route},
        UpdateExpression=("SET subscription_status = :a, merchant_trade_no = :t, current_period_end = :e, "
                          "current_period_end_date = :d, last_charged_at = :n, updated_at = :n, "
                          "total_success_times = :c, failed_charges = :z"),
        ExpressionAttributeValues={":a": "active", ":t": trade_no, ":e": end, ":d": end_date, ":n": now,
                                   ":c": int(params.get("TotalSuccessTimes") or 1), ":z": 0})
    print(f"{source}: ACTIVE {email}#{route} trade_no={trade_no} period_end={end}")
    return None, (email, route, trade_no, end_date)


def handler(event, _context):
    cfg = ecpay_config()
    params = parse_form_body(event)
    trade_no = params.get("MerchantTradeNo", "")
    if not verify_cmv(params, cfg["hash_key"], cfg["hash_iv"]):
        print(f"return: CMV INVALID trade_no={trade_no} keys={sorted(params)}")
        return text_response("0|CheckMacValueInvalid", 400)
    if params.get("MerchantID") != cfg["merchant_id"]:
        print(f"return: merchant mismatch {params.get('MerchantID')}")
        return text_response("0|MerchantMismatch", 400)
    print(f"return: CMV ok trade_no={trade_no} RtnCode={params.get('RtnCode')} RtnMsg={params.get('RtnMsg')} "
          f"SimulatePaid={params.get('SimulatePaid')} TradeAmt={params.get('TradeAmt')}")
    if params.get("RtnCode") != "1":
        return text_response("1|OK")  # failed first auth: row stays pending_payment; ack
    if params.get("SimulatePaid") == "1":
        print("return: SimulatePaid=1 -> acked, NOT activating")
        return text_response("1|OK")

    email = (params.get("CustomField1") or "").strip().lower()
    route = (params.get("CustomField2") or "").strip()
    row = TABLE.get_item(Key={"email": email, "route": route}).get("Item") if email and route else None
    if row and row.get("subscription_status") == "active" and row.get("merchant_trade_no") == trade_no:
        print(f"return: already active for trade_no={trade_no} -> idempotent ack")
        return text_response("1|OK")

    err, info = activate(params, source="return")
    if err:
        return text_response(err, info)
    email, route, trade_no, end_date = info
    _sqs.send_message(QueueUrl=STATUS_QUEUE_URL, MessageBody=json.dumps(
        {"event_type": "welcome", "email": email, "route": route, "merchant_trade_no": trade_no,
         "current_period_end_date": end_date}))
    return text_response("1|OK")
