"""
Validation and Sanitization Utilities for FraudGuard -AI.
Provides strict input validation for transaction data, CSV file security,
and CSV formula injection neutralization (CWE-1236).
"""

import math
import re
from typing import Tuple, Optional, Dict, Any

# Whitelisted Transaction Domains
VALID_TRANSACTION_TYPES = {'Transfer', 'Payment', 'Cash Withdrawal', 'Deposit', 'Purchase'}
VALID_CHANNELS = {'Mobile Banking', 'Internet Banking', 'ATM', 'POS', 'UPI'}
VALID_LOCATIONS = {
    'Domestic', 'High-Risk Domestic', 'Cross-Border (Recognized)',
    'Cross-Border (Unusual)', 'International (High-Risk)'
}
VALID_DEVICES = {
    'Mobile App (Recognized)', 'Web Browser (Recognized)',
    'New / Unrecognized Device', 'Unknown / New Device', 'ATM Terminal', 'POS Terminal'
}

# Formula Injection Triggers (DDE / CSV Formula Execution in Excel / Calc / Sheets)
FORMULA_TRIGGERS = ('=', '+', '-', '@', '\t', '\r', '|')

# Binary Magic Byte Signatures Disallowed for CSV Uploads
BINARY_MAGIC_SIGNATURES = [
    (b'MZ', 'Windows PE Executable (.exe, .dll)'),
    (b'\x7fELF', 'Linux ELF Binary'),
    (b'%PDF', 'PDF Document'),
    (b'\x89PNG', 'PNG Image'),
    (b'GIF8', 'GIF Image'),
    (b'\xff\xd8\xff', 'JPEG Image'),
    (b'PK\x03\x04', 'ZIP Archive / Office Open XML Document'),
    (b'\x1f\x8b', 'GZIP Compressed File'),
    (b'7z\xbc\xaf\x27\x1c', '7-Zip Archive'),
    (b'Rar!\x1a\x07', 'RAR Archive')
]


def sanitize_csv_cell(value: Any) -> Any:
    """
    Neutralizes CSV / Spreadsheet Formula Injection (CWE-1236).
    If a string cell starts with formula execution triggers (=, +, -, @, \\t, \\r),
    prepends a single quote (') so spreadsheet applications treat it strictly as literal text.
    Preserves raw numeric int and float types.
    """
    if value is None:
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    val_str = str(value)
    if not val_str:
        return val_str

    # Direct check for leading control character triggers (tab, carriage return)
    if val_str[0] in ('\t', '\r'):
        return f"'{val_str}"

    # Examine the first meaningful (non-whitespace) character to prevent leading space bypasses
    stripped = val_str.lstrip()
    if stripped and stripped[0] in FORMULA_TRIGGERS:
        return f"'{val_str}"

    return val_str


def validate_csv_file(file_storage, max_size: int = 16 * 1024 * 1024) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Performs deep content and extension validation on an uploaded file.
    - Verifies extension ends with .csv
    - Checks for non-empty content
    - Rejects binary magic bytes (executables, images, archives)
    - Rejects null bytes in text
    - Identifies valid text encoding (utf-8-sig, utf-8, latin-1)
    - Restores stream position to 0 upon completion.
    Returns (is_valid, error_message, detected_encoding).
    """
    if not file_storage:
        return False, "No file was provided for upload.", None

    filename = getattr(file_storage, 'filename', None)
    if filename is not None:
        filename = filename.strip()
        if not filename.lower().endswith('.csv'):
            return False, "Invalid file extension: Only .csv files are supported.", None
        if '\x00' in filename or filename == '.csv':
            return False, "Malformed or invalid filename.", None

    # Read leading bytes to inspect magic header
    stream = getattr(file_storage, 'stream', file_storage)
    initial_pos = stream.tell() if hasattr(stream, 'tell') else 0
    header_bytes = stream.read(2048)

    if not header_bytes or len(header_bytes) == 0:
        if hasattr(stream, 'seek'):
            stream.seek(initial_pos)
        return False, "The uploaded CSV file is empty. Please provide a valid transaction batch.", None

    # Check for binary / executable magic byte signatures
    for magic, desc in BINARY_MAGIC_SIGNATURES:
        if header_bytes.startswith(magic):
            if hasattr(stream, 'seek'):
                stream.seek(initial_pos)
            return False, f"Invalid file content: {desc} files disguised as CSV are strictly prohibited.", None

    # Check for null bytes (indicative of binary files)
    if b'\x00' in header_bytes:
        if hasattr(stream, 'seek'):
            stream.seek(initial_pos)
        return False, "Invalid file content: Binary data or null bytes detected in CSV file.", None

    # Test text encodings
    detected_encoding = None
    for enc in ('utf-8-sig', 'utf-8', 'latin-1'):
        try:
            header_bytes.decode(enc)
            detected_encoding = enc
            break
        except (UnicodeDecodeError, Exception):
            continue

    if not detected_encoding:
        if hasattr(stream, 'seek'):
            stream.seek(initial_pos)
        return False, "Unsupported file encoding. Please ensure the CSV file is encoded in UTF-8.", None

    # Reset stream pointer
    if hasattr(stream, 'seek'):
        stream.seek(0)

    return True, None, detected_encoding


def validate_transaction_payload(data: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Performs strict validation and type sanitization on a transaction payload.
    Guarantees:
    - Amount is a finite, positive number greater than zero and not NaN or Infinity.
    - Transaction type and channel match system whitelists.
    - Frequency, account age, and balance values are non-negative and finite.
    - Identifiers are trimmed, bounded in length (max 64 chars), and sanitized.
    Returns (cleaned_dict, error_message or None).
    """
    if not isinstance(data, dict):
        return None, "Transaction data must be a valid JSON object or key-value dictionary."

    # 1. Amount validation
    if 'amount' not in data or data['amount'] is None:
        return None, "Missing required field: 'amount'."

    amount_raw = data['amount']
    # Reject strings like 'NaN', 'inf', '-infinity'
    if isinstance(amount_raw, str):
        cleaned_raw = amount_raw.strip().lower()
        if cleaned_raw in ('nan', 'inf', '-inf', '+inf', 'infinity', '-infinity'):
            return None, "Invalid 'amount': Value cannot be NaN or Infinity."

    try:
        amount = float(amount_raw)
        if math.isnan(amount) or math.isinf(amount):
            return None, "Invalid 'amount': Value cannot be NaN or Infinity."
        if amount <= 0:
            return None, "Invalid 'amount': Amount must be a positive number greater than zero."
        if amount > 10_000_000.0:
            return None, "Invalid 'amount': Amount exceeds maximum transaction limit of $10,000,000."
    except (ValueError, TypeError):
        return None, "Invalid 'amount': Must be a valid finite numeric value."

    # 2. Transaction Type validation
    t_type_raw = str(data.get('transaction_type', 'Transfer')).strip()
    if t_type_raw not in VALID_TRANSACTION_TYPES:
        allowed = ", ".join(sorted(VALID_TRANSACTION_TYPES))
        return None, f"Invalid 'transaction_type' '{t_type_raw}'. Supported types: {allowed}."

    # 3. Channel validation
    channel_raw = str(data.get('channel', 'Mobile Banking')).strip()
    if channel_raw not in VALID_CHANNELS:
        allowed = ", ".join(sorted(VALID_CHANNELS))
        return None, f"Invalid 'channel' '{channel_raw}'. Supported channels: {allowed}."

    # 4. Location validation
    location_raw = str(data.get('location', 'Domestic')).strip()
    location = location_raw if location_raw in VALID_LOCATIONS else 'Domestic'

    # 5. Device validation
    device_raw = str(data.get('device', 'Mobile App (Recognized)')).strip()
    device = device_raw if device_raw in VALID_DEVICES else 'Mobile App (Recognized)'

    # 6. Frequency 24h validation
    freq_raw = data.get('frequency_24h', 1)
    if isinstance(freq_raw, str) and freq_raw.strip().lower() in ('nan', 'inf', '-inf'):
        return None, "Invalid 'frequency_24h': Value cannot be NaN or Infinity."
    try:
        freq = int(float(freq_raw))
        if freq < 0 or freq > 1000:
            return None, "Invalid 'frequency_24h': Must be an integer between 0 and 1000."
    except (ValueError, TypeError):
        return None, "Invalid 'frequency_24h': Must be a valid integer."

    # 7. Account Age Days validation
    age_raw = data.get('account_age_days', 365)
    if isinstance(age_raw, str) and age_raw.strip().lower() in ('nan', 'inf', '-inf'):
        return None, "Invalid 'account_age_days': Value cannot be NaN or Infinity."
    try:
        age = int(float(age_raw))
        if age < 0 or age > 30000:
            return None, "Invalid 'account_age_days': Must be an integer between 0 and 30000."
    except (ValueError, TypeError):
        return None, "Invalid 'account_age_days': Must be a valid integer."

    # 8. Previous Amount validation
    prev_raw = data.get('previous_amount', 0.0)
    if isinstance(prev_raw, str) and prev_raw.strip().lower() in ('nan', 'inf', '-inf'):
        return None, "Invalid 'previous_amount': Value cannot be NaN or Infinity."
    try:
        prev_amount = float(prev_raw)
        if math.isnan(prev_amount) or math.isinf(prev_amount) or prev_amount < 0:
            return None, "Invalid 'previous_amount': Must be a non-negative finite number."
    except (ValueError, TypeError):
        return None, "Invalid 'previous_amount': Must be a valid numeric value."

    # 9. Balances validation
    try:
        old_bal = float(data.get('old_balance_orig', amount * 1.5))
        if math.isnan(old_bal) or math.isinf(old_bal) or old_bal < 0:
            old_bal = amount * 1.5
    except (ValueError, TypeError):
        old_bal = amount * 1.5

    try:
        new_bal = float(data.get('new_balance_orig', 0.0))
        if math.isnan(new_bal) or math.isinf(new_bal) or new_bal < 0:
            new_bal = 0.0
    except (ValueError, TypeError):
        new_bal = 0.0

    # 10. Account Identifiers (strip, sanitize, bounded length)
    sender = str(data.get('sender_account', 'ACC-SENDER')).strip()[:64]
    receiver = str(data.get('receiver_account', 'ACC-RECEIVER')).strip()[:64]
    if not sender:
        sender = 'ACC-SENDER'
    if not receiver:
        receiver = 'ACC-RECEIVER'

    cleaned = {
        'amount': round(amount, 2),
        'transaction_type': t_type_raw,
        'sender_account': sender,
        'receiver_account': receiver,
        'channel': channel_raw,
        'location': location,
        'device': device,
        'frequency_24h': freq,
        'account_age_days': age,
        'previous_amount': round(prev_amount, 2),
        'old_balance_orig': round(old_bal, 2),
        'new_balance_orig': round(new_bal, 2)
    }

    if 'transaction_ref' in data and data['transaction_ref']:
        cleaned['transaction_ref'] = str(data['transaction_ref']).strip()[:64]

    if 'old_balance_dest' in data and data['old_balance_dest'] is not None:
        try:
            cleaned['old_balance_dest'] = float(data['old_balance_dest'])
        except (ValueError, TypeError):
            cleaned['old_balance_dest'] = 0.0

    if 'new_balance_dest' in data and data['new_balance_dest'] is not None:
        try:
            cleaned['new_balance_dest'] = float(data['new_balance_dest'])
        except (ValueError, TypeError):
            cleaned['new_balance_dest'] = 0.0

    return cleaned, None
