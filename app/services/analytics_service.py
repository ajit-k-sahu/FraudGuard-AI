"""
Analytics Service for FraudGuard AI.
Aggregates database metrics, risk distributions, temporal trends, and comparative telemetry.
"""

from datetime import datetime, timedelta
from sqlalchemy import func
from app.extensions import db
from app.models import Transaction, Prediction, FraudAlert, User

class AnalyticsService:
    @staticmethod
    def get_dashboard_summary(user_id=None, is_admin=False):
        """Generates key statistical summary cards for the user or administrator."""
        query = db.session.query(Transaction).join(Prediction)
        
        # Non-admins only see their own transactions + demo transactions if no user_id or explicitly enabled
        if not is_admin and user_id is not None:
            query = query.filter(Transaction.user_id == user_id)

        total_txns = query.count()
        if total_txns == 0:
            return {
                'total_analyzed': 0,
                'legitimate_count': 0,
                'fraud_count': 0,
                'suspicious_count': 0,
                'fraud_rate': 0.0,
                'total_volume': 0.0,
                'high_risk_count': 0,
                'medium_risk_count': 0,
                'low_risk_count': 0,
                'has_data': False
            }

        legit_count = query.filter(Prediction.is_fraud_predicted == False).count()
        fraud_count = query.filter(Prediction.is_fraud_predicted == True).count()
        suspicious_count = query.filter(Prediction.risk_level == 'Medium').count()
        high_risk_count = query.filter(Prediction.risk_level == 'High').count()
        low_risk_count = query.filter(Prediction.risk_level == 'Low').count()

        total_volume = query.with_entities(func.sum(Transaction.amount)).scalar() or 0.0
        fraud_rate = (fraud_count / total_txns * 100) if total_txns > 0 else 0.0

        return {
            'total_analyzed': total_txns,
            'legitimate_count': legit_count,
            'fraud_count': fraud_count,
            'suspicious_count': suspicious_count,
            'high_risk_count': high_risk_count,
            'medium_risk_count': suspicious_count,
            'low_risk_count': low_risk_count,
            'fraud_rate': round(fraud_rate, 2),
            'total_volume': round(total_volume, 2),
            'has_data': True
        }

    @staticmethod
    def get_chart_data(user_id=None, is_admin=False):
        """Prepares JSON-serializable chart data for Chart.js dashboards."""
        query = db.session.query(Transaction).join(Prediction)
        if not is_admin and user_id is not None:
            query = query.filter(Transaction.user_id == user_id)

        # 1. Transaction Type Distribution
        type_counts = db.session.query(
            Transaction.transaction_type, func.count(Transaction.id)
        ).join(Prediction)
        if not is_admin and user_id is not None:
            type_counts = type_counts.filter(Transaction.user_id == user_id)
        type_data = dict(type_counts.group_by(Transaction.transaction_type).all())

        all_types = ['Transfer', 'Payment', 'Cash Withdrawal', 'Deposit', 'Purchase']
        type_chart = {
            'labels': all_types,
            'values': [type_data.get(t, 0) for t in all_types]
        }

        # 2. Risk Level Distribution
        risk_counts = db.session.query(
            Prediction.risk_level, func.count(Prediction.id)
        ).join(Transaction)
        if not is_admin and user_id is not None:
            risk_counts = risk_counts.filter(Transaction.user_id == user_id)
        risk_dict = dict(risk_counts.group_by(Prediction.risk_level).all())

        risk_chart = {
            'labels': ['Low Risk', 'Medium Risk', 'High Risk'],
            'values': [risk_dict.get('Low', 0), risk_dict.get('Medium', 0), risk_dict.get('High', 0)]
        }

        # 3. Legitimate vs Fraudulent Breakdown
        legit_total = query.filter(Prediction.is_fraud_predicted == False).count()
        fraud_total = query.filter(Prediction.is_fraud_predicted == True).count()
        outcome_chart = {
            'labels': ['Legitimate', 'Predicted Fraud'],
            'values': [legit_total, fraud_total]
        }

        # 4. Temporal Trends (Last 7 Days in Asia/Kolkata)
        from app.utils.timezone import to_ist
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        trend_query = query.filter(Transaction.created_at >= seven_days_ago).all()

        ist_now = to_ist(datetime.utcnow())
        date_map = {}
        for d in range(7):
            day_str = (ist_now - timedelta(days=6-d)).strftime('%b %d')
            date_map[day_str] = {'total': 0, 'fraud': 0, 'volume': 0.0}

        for txn in trend_query:
            day_str = to_ist(txn.created_at).strftime('%b %d')
            if day_str in date_map:
                date_map[day_str]['total'] += 1
                date_map[day_str]['volume'] += txn.amount
                if txn.prediction and txn.prediction.is_fraud_predicted:
                    date_map[day_str]['fraud'] += 1

        trend_chart = {
            'labels': list(date_map.keys()),
            'total_txns': [date_map[d]['total'] for d in date_map],
            'fraud_txns': [date_map[d]['fraud'] for d in date_map],
            'volumes': [round(date_map[d]['volume'], 2) for d in date_map]
        }

        # 5. Average Amount by Outcome
        avg_legit = query.filter(Prediction.is_fraud_predicted == False).with_entities(func.avg(Transaction.amount)).scalar() or 0.0
        avg_fraud = query.filter(Prediction.is_fraud_predicted == True).with_entities(func.avg(Transaction.amount)).scalar() or 0.0
        amount_comparison = {
            'labels': ['Avg Legitimate Amount ($)', 'Avg Fraudulent Amount ($)'],
            'values': [round(avg_legit, 2), round(avg_fraud, 2)]
        }

        return {
            'type_distribution': type_chart,
            'risk_distribution': risk_chart,
            'outcome_distribution': outcome_chart,
            'trend_data': trend_chart,
            'amount_comparison': amount_comparison
        }

    @staticmethod
    def get_recent_transactions(limit=10, user_id=None, is_admin=False):
        query = Transaction.query.order_by(Transaction.created_at.desc())
        if not is_admin and user_id is not None:
            query = query.filter(Transaction.user_id == user_id)
        return query.limit(limit).all()

    @staticmethod
    def get_recent_high_risk(limit=5, user_id=None, is_admin=False):
        query = Transaction.query.join(Prediction).filter(
            Prediction.risk_level.in_(['High', 'Medium'])
        ).order_by(Transaction.created_at.desc())
        if not is_admin and user_id is not None:
            query = query.filter(Transaction.user_id == user_id)
        return query.limit(limit).all()
