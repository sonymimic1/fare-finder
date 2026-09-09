"""flight-status-notification — SQS consumer for flight-status-queue.

ONE consumer for subscription lifecycle mail, branched on message["event_type"]:
  "welcome" -> subscription activated;  "cancel" -> cancellation confirmed.
Idempotent per (event_type, merchant_trade_no) via notification_history rows
(pk = "status#{email}#{route}"). Sends via Resend; 429/5xx re-raise, 4xx drop.
"""
import datetime
import json
import os
import urllib.error
import urllib.request

import boto3
from boto3.dynamodb.conditions import Key

UA = "Mozilla/5.0 (compatible; flight-notifier/1.0)"
RESEND_SECRET = os.environ.get("RESEND_SECRET", "flight/resend")
SITE_URL = os.environ.get("SITE_URL", "").strip().rstrip("/")
ROUTE_NAMES = {"TPE-TYO": "台北 → 東京", "TPE-SEL": "台北 → 首爾"}

_sm = boto3.client("secretsmanager")
_history = boto3.resource("dynamodb").Table("notification_history")
_cfg = {}


class TransientSendError(Exception):
    pass


def _resend_cfg():
    if not _cfg:
        _cfg.update(json.loads(_sm.get_secret_value(SecretId=RESEND_SECRET)["SecretString"]))
    return _cfg


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _already_sent(pk, event_type, trade_no):
    res = _history.query(KeyConditionExpression=Key("pk").eq(pk), ScanIndexForward=False, Limit=10)
    return any(i.get("event_type") == event_type and i.get("merchant_trade_no") == trade_no for i in res.get("Items", []))


def render(event_type, route, end_date):
    name = ROUTE_NAMES.get(route, route)
    app = f"{SITE_URL}/app" if SITE_URL else ""
    if event_type == "welcome":
        subject = f"✅ 訂閱已啟用：{name} 降價通知"
        text = (f"你的 {name} 機票降價通知已啟用。\n"
                f"票價低於你設定的目標價時，我們會寄 email 通知你。\n"
                f"本期有效至 {end_date}，之後每月自動續訂，可隨時取消。\n\n"
                f"管理訂閱：{app}\n\nFlight Price Notifier")
        html = (f'<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;max-width:520px;margin:0 auto;padding:24px;color:#111">'
                f'<p style="margin:0 0 4px;font-size:14px;color:#666">Flight Price Notifier</p>'
                f'<h1 style="margin:0 0 12px;font-size:20px">訂閱已啟用 / Subscription active</h1>'
                f'<p style="margin:0 0 8px">你的 <strong>{name}</strong> 機票降價通知已啟用。票價低於目標價時會寄 email 通知你。</p>'
                f'<p style="margin:0 0 16px;color:#444;font-size:14px">本期有效至 {end_date}，之後每月自動續訂，可隨時取消。</p>'
                + (f'<p style="margin:0"><a href="{app}" style="display:inline-block;background:#6d28d9;color:#fff;text-decoration:none;padding:12px 20px;border-radius:8px;font-weight:600">管理訂閱 / Manage</a></p>' if app else "")
                + '</div>')
    else:
        subject = f"取消確認：{name} 降價通知將於 {end_date} 停止"
        text = (f"我們已收到你取消 {name} 降價通知的請求。\n"
                f"不會再自動扣款。已付費的本期服務保留至 {end_date}，在那之前仍會收到通知。\n\n"
                f"想恢復訂閱可以隨時回到：{app}\n\nFlight Price Notifier")
        html = (f'<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;max-width:520px;margin:0 auto;padding:24px;color:#111">'
                f'<p style="margin:0 0 4px;font-size:14px;color:#666">Flight Price Notifier</p>'
                f'<h1 style="margin:0 0 12px;font-size:20px">已取消訂閱 / Subscription cancelled</h1>'
                f'<p style="margin:0 0 8px">已收到你取消 <strong>{name}</strong> 降價通知的請求，不會再自動扣款。</p>'
                f'<p style="margin:0 0 16px;color:#444;font-size:14px">已付費的本期服務保留至 {end_date}，在那之前仍會收到通知。</p>'
                + (f'<p style="margin:0"><a href="{app}" style="color:#6d28d9">恢復訂閱 / Resubscribe</a></p>' if app else "")
                + '</div>')
    return subject, html, text


def send_email(cfg, to, subject, html, text):
    body = {"from": cfg["from"], "to": to, "subject": subject, "html": html, "text": text}
    req = urllib.request.Request("https://api.resend.com/emails", data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + cfg["api_key"],
                                          "Content-Type": "application/json", "User-Agent": UA}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as ex:
        return ex.code, ex.read().decode()


def _handle(msg):
    event_type = msg.get("event_type")
    email, route = msg["email"], msg["route"]
    trade_no = msg.get("merchant_trade_no") or ""
    end_date = msg.get("current_period_end_date") or "-"
    if event_type not in ("welcome", "cancel"):
        print(f"unknown event_type {event_type!r} -> dropped")
        return "dropped"
    pk = f"status#{email}#{route}"
    if _already_sent(pk, event_type, trade_no):
        print(f"skipped (already sent) {event_type} {pk} trade_no={trade_no}")
        return "skipped"
    subject, html, text = render(event_type, route, end_date)
    status, resp = send_email(_resend_cfg(), email, subject, html, text)
    if 200 <= status < 300:
        _history.put_item(Item={"pk": pk, "sent_at": _now_iso(), "email": email, "route": route,
                                "event_type": event_type, "merchant_trade_no": trade_no})
        print(f"RESEND_OK {status} {event_type} {pk} {resp}")
        return "sent"
    if status == 429 or status >= 500:
        print(f"RESEND_TRANSIENT {status} {pk}: {resp}")
        raise TransientSendError(f"resend {status}")
    print(f"RESEND_DROP {status} {event_type} {pk}: {resp}")
    return "dropped"


def handler(event, _context):
    return {"ok": True, "results": [_handle(json.loads(r["body"])) for r in event.get("Records", [])]}
