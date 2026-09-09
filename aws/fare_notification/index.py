"""flight-fare-notification — SQS consumer for flight-fare-queue.

Per message: dedup against notification_history (pk = "{email}#{route}"),
render the alert (NT$ headline + optional 約 US$ + 立即訂購 link), POST to Resend,
and only after a 2xx write the history row.

Failure classes (no DLQ): 429/5xx -> raise (SQS redelivers); 403/422/other 4xx -> log + drop.
"""
import datetime
import json
import os
import urllib.error
import urllib.request
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

UA = "Mozilla/5.0 (compatible; flight-notifier/1.0)"
RESEND_SECRET = os.environ.get("RESEND_SECRET", "flight/resend")
NOTIFY_FLOOR_HOURS = float(os.environ.get("NOTIFY_FLOOR_HOURS", "24"))
REALERT_PCT = float(os.environ.get("REALERT_PCT", "20"))
REALERT_ABS_TWD = float(os.environ.get("REALERT_ABS_TWD", "2000"))

ROUTE_NAMES = {"TPE-TYO": ("台北", "東京"), "TPE-SEL": ("台北", "首爾")}
CITY_EN = {"TPE": "Taipei", "TYO": "Tokyo", "SEL": "Seoul"}

_sm = boto3.client("secretsmanager")
_history = boto3.resource("dynamodb").Table("notification_history")
_secret_cache = {}


class TransientSendError(Exception):
    """Raised for 429/5xx so SQS redelivers the message."""


def _resend_cfg():
    if not _secret_cache:
        _secret_cache.update(json.loads(_sm.get_secret_value(SecretId=RESEND_SECRET)["SecretString"]))
    return _secret_cache


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(s):
    return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)


def _ddmm(iso_ts):
    """'2026-10-31T17:15:00+08:00' -> '3110'"""
    return iso_ts[8:10] + iso_ts[5:7]


def _ymd(iso_ts):
    return iso_ts[:10]


def _route_names(route):
    zh = ROUTE_NAMES.get(route)
    if zh:
        return zh
    o, d = route.split("-")
    return (o, d)


def _fmt_twd(n):
    return f"NT${int(round(float(n))):,}"


def booking_url(route, cheapest, marker=None):
    origin, dest = route.split("-")
    seg = f"{origin}{_ddmm(cheapest['depart_date'])}{dest}"
    if cheapest.get("return_date"):
        seg += _ddmm(cheapest["return_date"])
    url = f"https://www.aviasales.com/search/{seg}1?currency=twd"
    if marker:
        url += f"&marker={marker}"
    return url


def subject(route, cheapest):
    o, d = _route_names(route)
    return f"✈️ {o} → {d} 降價通知！{_fmt_twd(cheapest['price'])} 已達標"


def _lines(route, cheapest, target_price, usd_price):
    o, d = _route_names(route)
    origin, dest = route.split("-")
    head = f"{o} → {d}（{CITY_EN.get(origin, origin)} → {CITY_EN.get(dest, dest)}）"
    price = _fmt_twd(cheapest["price"])
    usd = f"約 US${int(round(float(usd_price))):,}" if usd_price is not None else None
    dates = f"{_ymd(cheapest['depart_date'])} 出發"
    if cheapest.get("return_date"):
        dates += f"、{_ymd(cheapest['return_date'])} 回程"
    airline = cheapest.get("airline") or "-"
    return head, price, usd, dates, airline


def render_text(route, cheapest, target_price, marker=None, usd_price=None):
    head, price, usd, dates, airline = _lines(route, cheapest, target_price, usd_price)
    out = [f"{head} 最低票價 {price}" + (f"（{usd}）" if usd else ""),
           f"你的目標價：{_fmt_twd(target_price)}",
           f"{dates}，航空公司 {airline}",
           "",
           f"立即訂購：{booking_url(route, cheapest, marker)}",
           "",
           "Flight Price Notifier — 票價低於你的目標價時通知你。"]
    return "\n".join(out)


def render_html(route, cheapest, target_price, marker=None, usd_price=None):
    head, price, usd, dates, airline = _lines(route, cheapest, target_price, usd_price)
    usd_line = f'<p style="margin:0 0 12px;color:#666;font-size:14px">{usd}</p>' if usd else ""
    return f"""<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;max-width:520px;margin:0 auto;padding:24px;color:#111">
<p style="margin:0 0 4px;font-size:14px;color:#666">Flight Price Notifier</p>
<h1 style="margin:0 0 12px;font-size:20px">{head}</h1>
<p style="margin:0 0 4px;font-size:32px;font-weight:700">{price}</p>
{usd_line}
<p style="margin:0 0 4px;font-size:14px">你的目標價：{_fmt_twd(target_price)}</p>
<p style="margin:0 0 20px;font-size:14px;color:#444">{dates}，航空公司 {airline}</p>
<p style="margin:0 0 24px"><a href="{booking_url(route, cheapest, marker)}" style="display:inline-block;background:#6d28d9;color:#fff;text-decoration:none;padding:12px 20px;border-radius:8px;font-weight:600">立即訂購 / Book now</a></p>
<p style="margin:0;font-size:12px;color:#888">票價為 Travelpayouts 回報的最低價，實際價格以訂票網站為準。Fare reported by Travelpayouts; final price on the booking site.</p>
</div>"""


def _last_alert(pk):
    res = _history.query(KeyConditionExpression=Key("pk").eq(pk), ScanIndexForward=False, Limit=1)
    items = res.get("Items", [])
    return items[0] if items else None


def _should_send(last, new_price):
    if not last:
        return True, "first alert"
    age_h = (_now() - _parse_iso(last["sent_at"])).total_seconds() / 3600
    if age_h >= NOTIFY_FLOOR_HOURS:
        return True, f"last alert {age_h:.1f}h ago >= floor {NOTIFY_FLOOR_HOURS}h"
    last_price = float(last.get("price", 0))
    if new_price <= last_price * (1 - REALERT_PCT / 100):
        return True, f"drop >= {REALERT_PCT}% vs last {last_price}"
    if (last_price - new_price) >= REALERT_ABS_TWD:
        return True, f"drop >= NT${REALERT_ABS_TWD:.0f} vs last {last_price}"
    return False, f"within floor ({age_h:.1f}h) and drop too small vs last {last_price}"


def send_email(cfg, to, subj, html, text):
    body = {"from": cfg["from"], "to": to, "subject": subj, "html": html, "text": text}
    req = urllib.request.Request("https://api.resend.com/emails", data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + cfg["api_key"],
                                          "Content-Type": "application/json", "User-Agent": UA},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as ex:
        return ex.code, ex.read().decode()


def _handle_message(msg):
    email = msg["email"]
    route = msg["route"]
    cheapest = msg["cheapest"]
    usd = (msg.get("cheapest_usd") or {}).get("price")
    target_price = msg.get("target_price", 0)
    new_price = float(cheapest["price"])
    pk = f"{email}#{route}"

    ok, why = _should_send(_last_alert(pk), new_price)
    if not ok:
        print(f"skipped (deduped) {pk} price={new_price}: {why}")
        return "skipped"

    cfg = _resend_cfg()
    marker = cfg.get("marker")
    status, resp = send_email(cfg, email, subject(route, cheapest),
                              render_html(route, cheapest, target_price, marker, usd),
                              render_text(route, cheapest, target_price, marker, usd))
    if 200 <= status < 300:
        _history.put_item(Item={"pk": pk, "sent_at": _iso(_now()), "email": email, "route": route,
                                "price": Decimal(str(cheapest["price"])), "currency": "TWD",
                                "target_price": Decimal(str(target_price))})
        print(f"RESEND_OK {status} {pk} price={new_price} ({why}) {resp}")
        return "sent"
    if status == 429 or status >= 500:
        print(f"RESEND_TRANSIENT {status} {pk}: {resp}")
        raise TransientSendError(f"resend {status}")
    print(f"RESEND_DROP {status} {pk}: {resp}")
    return "dropped"


def handler(event, _context):
    results = []
    for rec in event.get("Records", []):
        msg = json.loads(rec["body"])
        results.append(_handle_message(msg))
    return {"ok": True, "results": results}
