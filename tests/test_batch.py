"""
Batch Transaction CSV Processing Test Suite.
Validates batch upload view, template sample CSV download, and bulk inference execution.
"""

import io
import pytest
from app.models import Transaction, Prediction

def test_batch_page_loads(analyst_client):
    res = analyst_client.get('/transactions/batch')
    assert res.status_code == 200
    assert b'Batch' in res.data and b'Sample CSV' in res.data

def test_batch_sample_csv_download(analyst_client):
    res = analyst_client.get('/transactions/batch/sample')
    assert res.status_code == 200
    assert res.mimetype == 'text/csv'
    content = res.data.decode('utf-8')
    assert 'amount' in content
    assert 'transaction_type' in content
    assert 'sender_account' in content
    assert 'receiver_account' in content
    assert 'channel' in content

def test_batch_csv_upload_and_processing(analyst_client, app):
    csv_content = (
        "amount,transaction_type,sender_account,receiver_account,channel,location,device,frequency_24h,account_age_days,previous_amount\n"
        "25.00,Payment,C101,C102,Mobile Banking,Domestic,Mobile App (Recognized),1,500,20.00\n"
        "95000.00,Transfer,C201,C202,Internet Banking,International (High-Risk),Unknown / New Device,14,3,15.00\n"
        "150.00,Purchase,C301,C302,POS,Domestic,Web Browser (Recognized),2,300,100.00\n"
    )
    data = {
        'csv_file': (io.BytesIO(csv_content.encode('utf-8')), 'test_batch.csv')
    }
    res = analyst_client.post('/transactions/batch', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert res.status_code == 200
    assert b'Batch analysis complete' in res.data

    with app.app_context():
        t1 = Transaction.query.filter_by(sender_account='C101').first()
        t2 = Transaction.query.filter_by(sender_account='C201').first()
        t3 = Transaction.query.filter_by(sender_account='C301').first()
        assert t1 is not None
        assert t2 is not None
        assert t3 is not None
        assert t1.prediction.risk_level == 'Low'
        assert t2.prediction.risk_level in ['Medium', 'High', 'Critical']

def test_batch_upload_empty_submission(analyst_client):
    res = analyst_client.post('/transactions/batch', data={}, follow_redirects=True)
    assert res.status_code == 200
    assert b'No file provided' in res.data or b'select a CSV' in res.data or b'Upload' in res.data
