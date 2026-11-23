"""
Tests for Phase A, Task 4: File Upload Security & Strict Input Validation Hardening.
Verifies:
- Strict CSV extension and byte-level magic signature validation.
- Rejection of empty, disguised binary (PE, ELF, PDF, ZIP), null-byte, and oversized files.
- Batch row limits (500 for web, 10 for demo API, 100 for auth API).
- Strict input validation (amount bounds, NaN/Inf rejection, whitelist constraints).
- CSV Formula Injection defense (CWE-1236) in exported data.
- Database atomicity and transaction rollback upon batch errors.
- 413 Payload Too Large error handling.
"""

import io
import pytest
from app.models import User, Transaction
from app.services.prediction_service import PredictionService
from app.utils.validators import sanitize_csv_cell, validate_transaction_payload, validate_csv_file


# ============================================================================
# 1. UNIT TESTS: SANITIZATION & VALIDATORS
# ============================================================================

def test_sanitize_csv_cell_formula_injection():
    """Formula injection triggers (=, +, -, @, |, tab, cr) and leading whitespace variants must be neutralized."""
    # Direct triggers
    assert sanitize_csv_cell("=1+1") == "'=1+1"
    assert sanitize_csv_cell("+SUM(A1:A5)") == "'+SUM(A1:A5)"
    assert sanitize_csv_cell("-1+2") == "'-1+2"
    assert sanitize_csv_cell("@SUM(A1:A5)") == "'@SUM(A1:A5)"
    
    # Leading whitespace followed by formula triggers (FG-SEC-04-01 remediation)
    assert sanitize_csv_cell(" =1+1") == "' =1+1"
    assert sanitize_csv_cell("   @SUM(A1)") == "'   @SUM(A1)"
    assert sanitize_csv_cell("  +2+5") == "'  +2+5"
    assert sanitize_csv_cell(" -cmd") == "' -cmd"
    
    # Tab and Carriage Return control characters
    assert sanitize_csv_cell("\t=1+1") == "'\t=1+1"
    assert sanitize_csv_cell("\tDDE_LINK") == "'\tDDE_LINK"
    assert sanitize_csv_cell("\r+cmd") == "'\r+cmd"
    assert sanitize_csv_cell("\rMALICIOUS") == "'\rMALICIOUS"
    
    # Pipe-prefixed suspicious content
    assert sanitize_csv_cell("|cmd|' /C calc'!A0") == "'|cmd|' /C calc'!A0"
    assert sanitize_csv_cell(" |cmd|' /C calc'!A0") == "' |cmd|' /C calc'!A0"
    
    # Safe values must remain untouched
    assert sanitize_csv_cell("Normal Text") == "Normal Text"
    assert sanitize_csv_cell("ACC-12345") == "ACC-12345"
    assert sanitize_csv_cell(1234.56) == 1234.56
    assert sanitize_csv_cell(-50.0) == -50.0
    assert sanitize_csv_cell(100) == 100
    assert sanitize_csv_cell(0) == 0
    assert sanitize_csv_cell("") == ""
    assert sanitize_csv_cell(None) == ""


def test_validate_csv_file_disguised_binaries():
    """validate_csv_file must inspect content bytes and reject executables, archives, and binaries."""
    # Empty
    is_valid, err, _ = validate_csv_file(io.BytesIO(b""))
    assert not is_valid
    assert "empty" in err.lower()

    # Disguised Windows PE executable
    pe_file = io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00")
    is_valid, err, _ = validate_csv_file(pe_file)
    assert not is_valid
    assert "Windows PE Executable" in err

    # Disguised Linux ELF binary
    elf_file = io.BytesIO(b"\x7fELF\x02\x01\x01\x00")
    is_valid, err, _ = validate_csv_file(elf_file)
    assert not is_valid
    assert "Linux ELF" in err

    # Disguised PDF
    pdf_file = io.BytesIO(b"%PDF-1.7\r\n1 0 obj")
    is_valid, err, _ = validate_csv_file(pdf_file)
    assert not is_valid
    assert "PDF Document" in err

    # Disguised ZIP
    zip_file = io.BytesIO(b"PK\x03\x04\x14\x00\x00\x00")
    is_valid, err, _ = validate_csv_file(zip_file)
    assert not is_valid
    assert "ZIP Archive" in err

    # Binary with null bytes
    null_file = io.BytesIO(b"amount,type\n100,Transfer\x00evil")
    is_valid, err, _ = validate_csv_file(null_file)
    assert not is_valid
    assert "null bytes" in err.lower()

    # Valid CSV
    valid_csv = io.BytesIO(b"amount,transaction_type\n150.00,Transfer\n")
    is_valid, err, enc = validate_csv_file(valid_csv)
    assert is_valid
    assert err is None
    assert enc in ('utf-8', 'utf-8-sig', 'latin-1')


def test_validate_transaction_payload_edge_cases():
    """validate_transaction_payload strictly rejects NaN, Inf, non-whitelisted enums, and bounds."""
    # Missing amount
    cleaned, err = validate_transaction_payload({'transaction_type': 'Transfer'})
    assert err is not None
    assert "amount" in err.lower()

    # Zero or negative amount
    cleaned, err = validate_transaction_payload({'amount': 0})
    assert err is not None
    cleaned, err = validate_transaction_payload({'amount': -50.0})
    assert err is not None

    # NaN and Infinity string or float representations
    for bad_amt in ['nan', 'NaN', 'inf', '-inf', 'Infinity', float('nan'), float('inf')]:
        cleaned, err = validate_transaction_payload({'amount': bad_amt})
        assert err is not None
        assert "nan or infinity" in err.lower() or "numeric" in err.lower()

    # Amount > $10,000,000
    cleaned, err = validate_transaction_payload({'amount': 10_000_001.0})
    assert err is not None
    assert "maximum" in err.lower()

    # Invalid transaction type
    cleaned, err = validate_transaction_payload({'amount': 100, 'transaction_type': 'INVALID_TYPE'})
    assert err is not None
    assert "transaction_type" in err.lower()

    # Invalid channel
    cleaned, err = validate_transaction_payload({'amount': 100, 'channel': 'PIGEON_CARRIER'})
    assert err is not None
    assert "channel" in err.lower()

    # Valid payload normalizes successfully
    cleaned, err = validate_transaction_payload({
        'amount': 250.50,
        'transaction_type': 'Transfer',
        'channel': 'Mobile Banking',
        'frequency_24h': 3,
        'account_age_days': 400
    })
    assert err is None
    assert cleaned['amount'] == 250.50
    assert cleaned['transaction_type'] == 'Transfer'
    assert cleaned['channel'] == 'Mobile Banking'


# ============================================================================
# 2. WEB BATCH UPLOAD SECURITY TESTS
# ============================================================================

def test_web_batch_upload_valid_csv(app, analyst_client):
    """Authenticated analyst can upload a valid CSV batch."""
    csv_content = (
        "amount,transaction_type,channel,location,device,frequency_24h,account_age_days,previous_amount,old_balance_orig,new_balance_orig,sender_account,receiver_account\n"
        "125.00,Transfer,Mobile Banking,Domestic,Mobile App (Recognized),1,365,100.00,1000.00,875.00,ACC-S1,ACC-R1\n"
        "250.00,Payment,Mobile Banking,Domestic,Mobile App (Recognized),2,365,125.00,875.00,625.00,ACC-S1,ACC-R2\n"
    )
    data = {
        'csv_file': (io.BytesIO(csv_content.encode('utf-8')), 'test_batch.csv')
    }
    res = analyst_client.post('/transactions/batch', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert res.status_code == 200
    assert b"Batch analysis complete" in res.data


def test_web_batch_upload_empty_csv_rejected(analyst_client):
    """Empty CSV file upload is rejected with a clear error."""
    data = {
        'csv_file': (io.BytesIO(b""), 'empty.csv')
    }
    res = analyst_client.post('/transactions/batch', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert res.status_code == 200
    assert b"empty" in res.data.lower() or b"no file" in res.data.lower()


def test_web_batch_upload_disguised_executable_rejected(analyst_client):
    """Executable disguised as CSV is rejected by magic byte inspection."""
    pe_bytes = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"
    data = {
        'csv_file': (io.BytesIO(pe_bytes), 'malicious.csv')
    }
    res = analyst_client.post('/transactions/batch', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert res.status_code == 200
    assert b"prohibited" in res.data.lower() or b"executable" in res.data.lower()


def test_web_batch_upload_wrong_extension_rejected(analyst_client):
    """Non-CSV file extension is rejected."""
    data = {
        'csv_file': (io.BytesIO(b"some content"), 'payload.sh')
    }
    res = analyst_client.post('/transactions/batch', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert res.status_code == 200
    assert b"Only .csv files are supported" in res.data or b"invalid" in res.data.lower()


def test_web_batch_upload_row_limit_enforced(analyst_client):
    """Batch uploads exceeding the 500-row limit are rejected before processing."""
    header = "amount,transaction_type,channel,location,device,frequency_24h,account_age_days,previous_amount,old_balance_orig,new_balance_orig,sender_account,receiver_account\n"
    rows = "\n".join(["10.00,Payment,Mobile Banking,Domestic,Mobile App (Recognized),1,365,10.00,100.00,90.00,ACC-S,ACC-R"] * 505)
    data = {
        'csv_file': (io.BytesIO((header + rows).encode('utf-8')), 'huge_batch.csv')
    }
    res = analyst_client.post('/transactions/batch', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert res.status_code == 200
    assert b"Batch upload limit is 500 transactions" in res.data


def test_web_batch_upload_atomicity_on_row_failure(app, analyst_client):
    """If any row in the batch is corrupted/invalid, the entire batch is rolled back atomically."""
    with app.app_context():
        analyst = User.query.filter_by(email='analyst@test.com').first()
        initial_count = Transaction.query.filter_by(user_id=analyst.id).count()

    # Batch with 3 rows: row 2 has negative amount
    csv_content = (
        "amount,transaction_type,channel,location,device,frequency_24h,account_age_days,previous_amount,old_balance_orig,new_balance_orig,sender_account,receiver_account\n"
        "50.00,Payment,Mobile Banking,Domestic,Mobile App (Recognized),1,365,50.00,500.00,450.00,ACC-S,ACC-R\n"
        "-999.00,Payment,Mobile Banking,Domestic,Mobile App (Recognized),1,365,50.00,500.00,450.00,ACC-S,ACC-R\n"
        "75.00,Payment,Mobile Banking,Domestic,Mobile App (Recognized),1,365,50.00,500.00,425.00,ACC-S,ACC-R\n"
    )
    data = {
        'csv_file': (io.BytesIO(csv_content.encode('utf-8')), 'corrupted_batch.csv')
    }
    res = analyst_client.post('/transactions/batch', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert res.status_code == 200
    assert b"Batch validation failed on 1 row(s)" in res.data

    # Verify atomic rollback: no rows from this batch were saved
    with app.app_context():
        post_count = Transaction.query.filter_by(user_id=analyst.id).count()
        assert post_count == initial_count


# ============================================================================
# 3. CSV FORMULA INJECTION DEFENSE IN EXPORT (CWE-1236)
# ============================================================================

def test_csv_export_formula_injection_sanitization(app, analyst_client):
    """Exported CSV cells starting with formula triggers (=, +, -, @, |) and leading spaces are neutralized."""
    with app.app_context():
        analyst = User.query.filter_by(email='analyst@test.com').first()
        # Seed transactions with formula injection payloads in string fields
        txn1, _, _ = PredictionService.predict_transaction({
            'amount': 333.33,
            'transaction_type': 'Transfer',
            'channel': 'Mobile Banking',
            'sender_account': '=cmd|\' /C calc\'!A0',
            'receiver_account': '+1234567890',
            'location': 'Domestic'
        }, user_id=analyst.id, auto_commit=True)

        txn2, _, _ = PredictionService.predict_transaction({
            'amount': 444.44,
            'transaction_type': 'Payment',
            'channel': 'Mobile Banking',
            'sender_account': ' =1+1',
            'receiver_account': '   @SUM(A1:A5)',
            'location': 'Domestic'
        }, user_id=analyst.id, auto_commit=True)

        txn3, _, _ = PredictionService.predict_transaction({
            'amount': 555.55,
            'transaction_type': 'Purchase',
            'channel': 'POS',
            'sender_account': '|cmd|\' /C calc\'!A0',
            'receiver_account': '\t=1+1',
            'location': 'Domestic'
        }, user_id=analyst.id, auto_commit=True)

    res = analyst_client.get('/transactions/export')
    assert res.status_code == 200
    csv_text = res.data.decode('utf-8')

    # Direct triggers neutralized
    assert "'=cmd|" in csv_text
    assert "'+1234567890" in csv_text

    # Leading whitespace formula triggers neutralized through input sanitization & CSV quoting
    assert "'=1+1" in csv_text
    assert "'@SUM(A1:A5)" in csv_text

    # Pipe and tab triggers neutralized
    assert "'|cmd|" in csv_text

    # Legitimate numeric amounts must remain unquoted and accurately formatted
    assert "333.33" in csv_text
    assert "444.44" in csv_text
    assert "555.55" in csv_text


# ============================================================================
# 4. REST API INPUT VALIDATION & BATCH ATOMICITY
# ============================================================================

def test_api_predict_rejects_nan_and_infinity(analyst_client):
    """API endpoint /api/v1/predict rejects NaN and Infinity in amount."""
    for bad in ['NaN', 'inf', '-infinity', float('nan')]:
        res = analyst_client.post('/api/v1/predict', json={'amount': bad})
        assert res.status_code == 400
        data = res.get_json()
        assert data['success'] is False
        assert "amount" in data['error'].lower()


def test_api_predict_rejects_invalid_type_and_channel(analyst_client):
    """API endpoint /api/v1/predict rejects non-whitelisted transaction_type or channel."""
    res_type = analyst_client.post('/api/v1/predict', json={'amount': 100, 'transaction_type': 'ILLEGAL_WIRE'})
    assert res_type.status_code == 400
    assert "transaction_type" in res_type.get_json()['error'].lower()

    res_chan = analyst_client.post('/api/v1/predict', json={'amount': 100, 'channel': 'DARK_WEB'})
    assert res_chan.status_code == 400
    assert "channel" in res_chan.get_json()['error'].lower()


def test_api_predict_batch_demo_limit(client):
    """Unauthenticated demo batch > 10 items is rejected to protect against DoS."""
    demo_payload = {'transactions': [{'amount': 100}] * 11}
    res_demo = client.post('/api/v1/predict/batch', json=demo_payload)
    assert res_demo.status_code == 401
    data = res_demo.get_json()
    assert data['success'] is False
    assert 'limited to 10 transactions' in data['error']


def test_api_predict_batch_authenticated_limit_and_atomicity(app, analyst_client):
    """API batch endpoint enforces batch size limit (100) and rollback on validation failure."""
    # 1. Authenticated batch > 100 items is rejected
    huge_payload = {'transactions': [{'amount': 100}] * 101}
    res_huge = analyst_client.post('/api/v1/predict/batch', json=huge_payload)
    assert res_huge.status_code == 400

    # 2. Authenticated batch atomicity: if an item has invalid data, DB is rolled back
    with app.app_context():
        analyst = User.query.filter_by(email='analyst@test.com').first()
        count_before = Transaction.query.filter_by(user_id=analyst.id).count()

    invalid_batch = {
        'transactions': [
            {'amount': 50.0, 'transaction_type': 'Transfer'},
            {'amount': -999.0, 'transaction_type': 'Transfer'},  # Invalid row
            {'amount': 75.0, 'transaction_type': 'Transfer'}
        ]
    }
    res_batch = analyst_client.post('/api/v1/predict/batch', json=invalid_batch)
    assert res_batch.status_code == 200
    data = res_batch.get_json()
    assert data['success'] is False
    assert any(r['status'] == 'error' for r in data['results'])

    # Verify no partial rows were committed to database
    with app.app_context():
        count_after = Transaction.query.filter_by(user_id=analyst.id).count()
        assert count_after == count_before


# ============================================================================
# 5. 413 REQUEST ENTITY TOO LARGE HANDLER
# ============================================================================

def test_request_entity_too_large_413_handling(client):
    """Application 413 error handler formats responses cleanly for API and web clients."""
    with client.application.test_request_context():
        from werkzeug.exceptions import RequestEntityTooLarge
        from flask import current_app
        
        handler = current_app.error_handler_spec[None][413][RequestEntityTooLarge]
        
        # 1. Simulate API JSON request
        with current_app.test_request_context('/api/v1/upload', headers={'Accept': 'application/json'}):
            res = handler(RequestEntityTooLarge())
            resp_obj, status_code = res
            assert status_code == 413
            data = resp_obj.get_json()
            assert data['success'] is False
            assert '16 mb' in data['error'].lower()

        # 2. Simulate browser upload request
        with current_app.test_request_context('/transactions/batch', headers={'Accept': 'text/html'}):
            web_res = handler(RequestEntityTooLarge())
            assert web_res.status_code == 302
            assert '/transactions/batch' in web_res.headers['Location']
