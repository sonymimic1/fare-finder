"""Billing-period helpers shared by the ECPay callback / cancel Lambdas.

All timestamps are fixed-width UTC strings `%Y-%m-%dT%H:%M:%SZ` so DynamoDB string
comparison (used by the parser's grace-period gate) orders correctly.
"""
import calendar
import datetime

FMT = "%Y-%m-%dT%H:%M:%SZ"


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def now_str():
    return now_utc().strftime(FMT)


def parse(s):
    return datetime.datetime.strptime(s, FMT).replace(tzinfo=datetime.timezone.utc)


def add_period(dt, period_type="M", frequency=1):
    """Advance dt by one billing period. M = calendar months (clamped to month end), D = days, Y = years."""
    n = int(frequency or 1)
    if period_type == "D":
        return dt + datetime.timedelta(days=n)
    if period_type == "Y":
        n *= 12
    month0 = dt.month - 1 + n
    year = dt.year + month0 // 12
    month = month0 % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def next_period_end(period_type="M", frequency=1, from_str=None):
    """Return (current_period_end, current_period_end_date) one period after `from_str` (or now)."""
    base = now_utc()
    if from_str:
        try:
            prev = parse(from_str)
            if prev > base:
                base = prev  # renewal: extend from the current paid-through date
        except Exception:
            pass
    end = add_period(base, period_type, frequency)
    return end.strftime(FMT), end.strftime("%Y-%m-%d")
