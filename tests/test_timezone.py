"""
Unit and integration tests for FraudGuard AI timezone handling (UTC storage to Asia/Kolkata IST display).
"""

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from app.utils.timezone import to_ist, format_ist, LOCAL_TIMEZONE
from app.models import Transaction, FraudAlert, AuditLog

def test_timezone_constant():
    assert LOCAL_TIMEZONE.key == "Asia/Kolkata"

def test_to_ist_with_naive_utc():
    naive_utc = datetime(2026, 11, 21, 14, 44, 0)
    ist_dt = to_ist(naive_utc)
    assert ist_dt.tzinfo is not None
    assert ist_dt.tzinfo.key == "Asia/Kolkata"
    # IST is UTC+05:30 -> 14:44 UTC is 20:14 IST
    assert ist_dt.year == 2026
    assert ist_dt.month == 11
    assert ist_dt.day == 21
    assert ist_dt.hour == 20
    assert ist_dt.minute == 14

def test_to_ist_with_aware_utc():
    aware_utc = datetime(2026, 11, 21, 14, 44, 0, tzinfo=timezone.utc)
    ist_dt = to_ist(aware_utc)
    assert ist_dt.hour == 20
    assert ist_dt.minute == 14

def test_to_ist_idempotent():
    first_ist = to_ist(datetime(2026, 11, 21, 14, 44, 0))
    second_ist = to_ist(first_ist)
    assert second_ist.hour == 20
    assert second_ist.minute == 14
    assert second_ist == first_ist

def test_to_ist_none():
    assert to_ist(None) is None

def test_format_ist_default_formatting():
    dt = datetime(2026, 11, 21, 14, 44, 0)
    formatted = format_ist(dt)
    assert formatted == "21 Nov 2026, 08:14 PM IST"

def test_format_ist_custom_formatting():
    dt = datetime(2026, 11, 21, 14, 44, 0)
    formatted = format_ist(dt, "%d %b %Y")
    assert formatted == "21 Nov 2026"

def test_format_ist_none():
    assert format_ist(None) == "N/A"
    assert format_ist(None, default="--") == "--"

def test_model_properties_and_dictionary():
    dt = datetime(2026, 11, 21, 14, 44, 0)
    txn = Transaction(
        transaction_ref="TXN-TZ-TEST-001",
        amount=500.0,
        transaction_type="Transfer",
        channel="Mobile Banking",
        location="Domestic",
        device="Mobile App",
        created_at=dt
    )
    assert txn.created_at_ist.hour == 20
    assert txn.created_at_ist.minute == 14
    assert txn.formatted_ist == "21 Nov 2026, 08:14 PM IST"
    d = txn.to_dict()
    assert d['created_at_ist'] == "21 Nov 2026, 08:14 PM IST"

def test_history_page_ist_display(analyst_client):
    res = analyst_client.get('/transactions/history')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Timestamp (IST)' in html
    assert 'IST' in html
