"""flight-ecpay-period — POST /ecpay-period (ECPay PeriodReturnURL, 2nd charge onwards)

Verify CheckMacValue; RtnCode=="1" -> keep active + push current_period_end one period
further. A failed renewal is only counted (ECPay retries; it auto-terminates after 6
consecutive failures) — expiry happens lazily in the parser when the paid period lapses.
Always reply "1|OK".
"""
import os

import boto3

from ecpay import ecpay_config, parse_form_body, text_response, verify_cmv
from periods import next_period_end, now_str

TABLE = boto3.resource("dynamodb").Table("subscriptions")


def handler(event, _context):
    cfg = ecpay_config()
    params = parse_form_body(event)
    trade_no = params.get("MerchantTradeNo", "")
    if not verify_cmv(params, cfg["hash_key"], cfg["hash_iv"]):
        print(f"period: CMV INVALID trade_no={trade_no} keys={sorted(params)}")
        return text_response("0|CheckMacValueInvalid", 400)
    if params.get("MerchantID") != cfg["merchant_id"]:
        return text_response("0|MerchantMismatch", 400)
    print(f"period: CMV ok trade_no={trade_no} RtnCode={params.get('RtnCode')} RtnMsg={params.get('RtnMsg')} "
          f"TotalSuccessTimes={params.get('TotalSuccessTimes')} Amount={params.get('Amount')} "
          f"SimulatePaid={params.get('SimulatePaid')}")
    if params.get("SimulatePaid") == "1":
        print("period: SimulatePaid=1 -> acked, no ledger change")
        return text_response("1|OK")

    email = (params.get("CustomField1") or "").strip().lower()
    route = (params.get("CustomField2") or "").strip()
    if not email or not route:
        return text_response("1|OK")
    row = TABLE.get_item(Key={"email": email, "route": route}).get("Item") or {}
    if not row:
        print(f"period: no row for {email}#{route}")
        return text_response("1|OK")
    now = now_str()

    if params.get("RtnCode") == "1":
        if row.get("subscription_status") == "cancelled":
            # user cancelled locally but ECPay still charged (cancel call failed?) - keep grace bookkeeping
            print(f"period: charge on cancelled row {email}#{route}; extending period only")
        period_type = str(row.get("period_type") or params.get("PeriodType") or "M")
        frequency = int(row.get("frequency") or params.get("Frequency") or 1)
        end, end_date = next_period_end(period_type, frequency, str(row.get("current_period_end") or ""))
        new_status = "cancelled" if row.get("subscription_status") == "cancelled" else "active"
        TABLE.update_item(
            Key={"email": email, "route": route},
            UpdateExpression=("SET subscription_status = :s, current_period_end = :e, current_period_end_date = :d, "
                              "last_charged_at = :n, updated_at = :n, total_success_times = :c, failed_charges = :z"),
            ExpressionAttributeValues={":s": new_status, ":e": end, ":d": end_date, ":n": now,
                                       ":c": int(params.get("TotalSuccessTimes") or 0), ":z": 0})
        print(f"period: renewed {email}#{route} -> {new_status} period_end={end}")
    else:
        res = TABLE.update_item(
            Key={"email": email, "route": route},
            UpdateExpression="SET failed_charges = if_not_exists(failed_charges, :z) + :one, last_charge_error = :m, updated_at = :n",
            ExpressionAttributeValues={":z": 0, ":one": 1, ":m": str(params.get("RtnMsg") or params.get("RtnCode")), ":n": now},
            ReturnValues="ALL_NEW")
        print(f"period: FAILED charge {email}#{route} failed_charges={res['Attributes'].get('failed_charges')} (not expiring; parser expires when period lapses)")
    return text_response("1|OK")
