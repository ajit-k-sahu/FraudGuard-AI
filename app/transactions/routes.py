import csv
import io
from datetime import datetime
from flask import render_template, request, flash, redirect, url_for, abort, Response, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_

from app.transactions import transactions_bp
from app.extensions import db
from app.models import Transaction, Prediction, FraudAlert
from app.forms import TransactionAnalysisForm, BatchUploadForm
from app.services.prediction_service import PredictionService
from app.utils.validators import validate_csv_file, validate_transaction_payload, sanitize_csv_cell
from app import log_audit_event

@transactions_bp.route('/analyze', methods=['GET', 'POST'])
@login_required
def analyze():
    form = TransactionAnalysisForm()
    result = None

    if form.validate_on_submit():
        txn_data = {
            'amount': form.amount.data,
            'transaction_type': form.transaction_type.data,
            'sender_account': form.sender_account.data.strip(),
            'receiver_account': form.receiver_account.data.strip(),
            'channel': form.channel.data,
            'location': form.location.data,
            'device': form.device.data,
            'frequency_24h': form.frequency_24h.data,
            'account_age_days': form.account_age_days.data,
            'previous_amount': form.previous_amount.data,
            'old_balance_orig': form.amount.data * 1.5,
            'new_balance_orig': max(0.0, (form.amount.data * 1.5) - form.amount.data)
        }

        try:
            cleaned_txn, val_err = validate_transaction_payload(txn_data)
            if val_err:
                flash(val_err, "danger")
                return render_template('transactions/analyze.html', form=form)

            transaction, prediction, alert = PredictionService.predict_transaction(
                txn_data=cleaned_txn,
                user_id=current_user.id,
                is_demo=False,
                auto_commit=True
            )
            
            log_audit_event(
                'TRANSACTION_ANALYZED',
                current_user.id,
                f"Analyzed {transaction.transaction_ref}: Amount=${transaction.amount:,.2f}, Risk={prediction.risk_level} ({prediction.fraud_probability:.1%})"
            )
            
            result = {
                'transaction': transaction,
                'prediction': prediction,
                'alert': alert
            }
            flash("Transaction successfully evaluated by AI detection pipeline.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error executing AI prediction model: {str(e)}", "danger")

    return render_template('transactions/analyze.html', form=form, result=result)


@transactions_bp.route('/history')
@login_required
def history():
    page = request.args.get('page', 1, type=int)
    per_page = 12

    # Filtering parameters
    search_query = request.args.get('q', '').strip()
    t_type = request.args.get('type', '').strip()
    risk = request.args.get('risk', '').strip()
    outcome = request.args.get('outcome', '').strip()
    sort_by = request.args.get('sort', 'date_desc').strip()

    query = Transaction.query.join(Prediction)

    # Ownership check: Ordinary users only see their own transactions
    if not current_user.is_admin:
        query = query.filter(Transaction.user_id == current_user.id)

    # Search filter
    if search_query:
        query = query.filter(or_(
            Transaction.transaction_ref.ilike(f"%{search_query}%"),
            Transaction.sender_account.ilike(f"%{search_query}%"),
            Transaction.receiver_account.ilike(f"%{search_query}%")
        ))

    # Type filter
    if t_type:
        query = query.filter(Transaction.transaction_type == t_type)

    # Risk level filter
    if risk in ['Low', 'Medium', 'High']:
        query = query.filter(Prediction.risk_level == risk)

    # Outcome filter
    if outcome == 'fraud':
        query = query.filter(Prediction.is_fraud_predicted == True)
    elif outcome == 'legit':
        query = query.filter(Prediction.is_fraud_predicted == False)

    # Sorting
    if sort_by == 'amount_desc':
        query = query.order_by(Transaction.amount.desc())
    elif sort_by == 'amount_asc':
        query = query.order_by(Transaction.amount.asc())
    elif sort_by == 'prob_desc':
        query = query.order_by(Prediction.fraud_probability.desc())
    elif sort_by == 'date_asc':
        query = query.order_by(Transaction.created_at.asc())
    else:  # date_desc default
        query = query.order_by(Transaction.created_at.desc())

    transactions_paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        'transactions/history.html',
        pagination=transactions_paginated,
        transactions=transactions_paginated.items,
        search_query=search_query,
        t_type=t_type,
        risk=risk,
        outcome=outcome,
        sort_by=sort_by
    )


@transactions_bp.route('/<int:txn_id>')
@login_required
def detail(txn_id):
    transaction = Transaction.query.get_or_404(txn_id)

    # Ensure user can only view their own transaction unless authorized as admin
    if not current_user.is_admin and transaction.user_id != current_user.id:
        log_audit_event('UNAUTHORIZED_ACCESS_ATTEMPT', current_user.id, f"Attempted to view transaction {txn_id} owned by user {transaction.user_id}")
        abort(403)

    prediction = transaction.prediction
    alerts = transaction.alerts.all()

    return render_template(
        'transactions/detail.html',
        transaction=transaction,
        prediction=prediction,
        alerts=alerts
    )


@transactions_bp.route('/batch', methods=['GET', 'POST'])
@login_required
def batch():
    form = BatchUploadForm()
    batch_results = []
    errors = []
    summary = {'total': 0, 'processed': 0, 'failed': 0, 'fraud_flagged': 0}

    if form.validate_on_submit():
        file = form.csv_file.data
        is_valid, err_msg, encoding = validate_csv_file(file)
        if not is_valid:
            flash(err_msg, "danger")
            return render_template(
                'transactions/batch.html',
                form=form,
                batch_results=batch_results,
                errors=errors,
                summary=summary
            )

        try:
            raw_bytes = file.stream.read()
            text_content = raw_bytes.decode(encoding or "utf-8-sig", errors="replace")
            stream = io.StringIO(text_content, newline=None)
            reader = csv.DictReader(stream)
            
            required_cols = {'amount', 'transaction_type', 'channel'}
            if not reader.fieldnames or not required_cols.issubset(set(reader.fieldnames)):
                flash("CSV file is missing required columns: 'amount', 'transaction_type', 'channel'.", "danger")
                return render_template(
                    'transactions/batch.html',
                    form=form,
                    batch_results=batch_results,
                    errors=errors,
                    summary=summary
                )

            rows = list(reader)
            if not rows:
                flash("The uploaded CSV file contains no data rows.", "danger")
                return render_template(
                    'transactions/batch.html',
                    form=form,
                    batch_results=batch_results,
                    errors=errors,
                    summary=summary
                )

            summary['total'] = len(rows)

            if len(rows) > 500:
                flash("Batch upload limit is 500 transactions per submission. Please reduce file size.", "warning")
                return render_template(
                    'transactions/batch.html',
                    form=form,
                    batch_results=batch_results,
                    errors=errors,
                    summary=summary
                )

            # Atomicity: validate all rows before executing predictions or database mutations
            validated_rows = []
            for idx, row in enumerate(rows, 1):
                cleaned_data, val_err = validate_transaction_payload(row)
                if val_err:
                    summary['failed'] += 1
                    errors.append(f"Row {idx}: {val_err}")
                else:
                    validated_rows.append((idx, cleaned_data))

            if errors:
                db.session.rollback()
                flash(f"Batch validation failed on {len(errors)} row(s): {errors[0]}. No transactions were saved.", "danger")
                return render_template(
                    'transactions/batch.html',
                    form=form,
                    batch_results=batch_results,
                    errors=errors,
                    summary=summary
                )

            for idx, cleaned_data in validated_rows:
                txn, pred, alert = PredictionService.predict_transaction(
                    txn_data=cleaned_data,
                    user_id=current_user.id,
                    is_demo=False,
                    auto_commit=False
                )
                
                summary['processed'] += 1
                if pred.is_fraud_predicted or pred.risk_level in ['High', 'Medium']:
                    summary['fraud_flagged'] += 1

                batch_results.append({
                    'row': idx,
                    'ref': txn.transaction_ref,
                    'amount': txn.amount,
                    'type': txn.transaction_type,
                    'risk_level': pred.risk_level,
                    'probability': f"{pred.fraud_probability:.1%}",
                    'is_fraud': pred.is_fraud_predicted,
                    'status': 'Processed'
                })

            db.session.commit()
            log_audit_event(
                'BATCH_PREDICTION',
                current_user.id,
                f"Batch processed: Total={summary['total']}, Succeeded={summary['processed']}, Flagged={summary['fraud_flagged']}, Failed={summary['failed']}"
            )
            flash(f"Batch analysis complete: {summary['processed']} records evaluated, {summary['fraud_flagged']} flagged as suspicious/high-risk.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Failed to process CSV batch file: {str(e)}", "danger")

    return render_template(
        'transactions/batch.html',
        form=form,
        batch_results=batch_results,
        errors=errors,
        summary=summary
    )


@transactions_bp.route('/batch/sample')
@login_required
def download_sample_csv():
    """Provides a sample CSV template with valid test records for batch evaluation."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'amount', 'transaction_type', 'sender_account', 'receiver_account',
        'channel', 'location', 'device', 'frequency_24h', 'account_age_days', 'previous_amount'
    ])
    sample_rows = [
        [150.00, 'Payment', 'C1029384', 'M8472910', 'Mobile Banking', 'Domestic', 'Mobile App (Recognized)', 2, 450, 120.00],
        [45.50, 'Purchase', 'C3849102', 'M1928374', 'POS', 'Domestic', 'POS Terminal', 1, 600, 50.00],
        [35000.00, 'Transfer', 'C9281726', 'C5519283', 'Internet Banking', 'Cross-Border (Unusual)', 'New / Unrecognized Device', 18, 12, 100.00],
        [12500.00, 'Cash Withdrawal', 'C7728192', 'C1182938', 'Internet Banking', 'High-Risk Domestic', 'New / Unrecognized Device', 8, 45, 250.00],
        [85.00, 'Payment', 'C4491029', 'M3391827', 'UPI', 'Domestic', 'Mobile App (Recognized)', 3, 300, 80.00]
    ]
    for row in sample_rows:
        writer.writerow(row)

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=fraudguard_sample_transactions.csv"}
    )


@transactions_bp.route('/export')
@login_required
def export_csv():
    """Allows authenticated users to download their evaluated transactions and risk scores as CSV."""
    query = Transaction.query.join(Prediction)
    if not current_user.is_admin:
        query = query.filter(Transaction.user_id == current_user.id)
    
    txns = query.order_by(Transaction.created_at.desc()).all()

    from app.utils.timezone import format_ist
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Transaction_Ref', 'Timestamp_IST', 'Amount', 'Type', 'Sender', 'Receiver',
        'Channel', 'Location', 'Device', 'Fraud_Probability', 'Risk_Level',
        'Prediction', 'Recommended_Action'
    ])

    for t in txns:
        pred = t.prediction
        writer.writerow([
            sanitize_csv_cell(t.transaction_ref),
            sanitize_csv_cell(format_ist(t.created_at)),
            t.amount,
            sanitize_csv_cell(t.transaction_type),
            sanitize_csv_cell(t.sender_account),
            sanitize_csv_cell(t.receiver_account),
            sanitize_csv_cell(t.channel),
            sanitize_csv_cell(t.location),
            sanitize_csv_cell(t.device),
            f"{pred.fraud_probability:.4f}" if pred else 'N/A',
            sanitize_csv_cell(pred.risk_level if pred else 'N/A'),
            'Fraudulent' if pred and pred.is_fraud_predicted else 'Legitimate',
            sanitize_csv_cell(pred.recommended_action if pred else 'N/A')
        ])

    output.seek(0)
    filename = f"fraudguard_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )
