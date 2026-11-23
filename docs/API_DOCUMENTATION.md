# FraudGuard AI: REST API Documentation

FraudGuard AI exposes a production-ready, versioned REST API under `/api/v1` and health monitoring at `/api/health`. All responses are formatted in strict JSON with appropriate HTTP status codes.

---

## 1. Authentication & System Health

### 1.1 Health Check Telemetry
Provides container orchestrators (Kubernetes, AWS ECS, Docker Compose, Render) with real-time operational health.

- **Endpoint:** `GET /api/health` or `GET /health`
- **Authentication:** None required
- **Success Response (200 OK):**
```json
{
  "status": "healthy",
  "database": "connected",
  "ml_model": "loaded",
  "version": "1.0.0"
}
```

### 1.2 API Client Login
Authenticates an external client or analyst service and verifies active credentials.

- **Endpoint:** `POST /api/v1/auth/login`
- **Content-Type:** `application/json`
- **Request Body:**
```json
{
  "email": "analyst@bank.com",
  "password": "AnalystPass123!"
}
```
- **Success Response (200 OK):**
```json
{
  "success": true,
  "message": "Authentication successful.",
  "user": {
    "id": 2,
    "name": "Sarah Analyst",
    "email": "analyst@bank.com",
    "role": "user"
  }
}
```
- **Error Responses:**
  - `400 Bad Request`: Missing `email` or `password`.
  - `401 Unauthorized`: Invalid credentials.
  - `403 Forbidden`: Account deactivated by administrator.

---

## 2. Machine Learning Predictions

### 2.1 Real-Time Transaction Prediction
Submits an individual transaction to the Scikit-learn Random Forest model pipeline for feature synthesis, probability calculation, risk stratification, and database persistence.

- **Endpoint:** `POST /api/v1/predict`
- **Content-Type:** `application/json`
- **Request Body:**
```json
{
  "amount": 85000.00,
  "transaction_type": "Transfer",
  "sender_account": "C9900112233",
  "receiver_account": "C4433221100",
  "channel": "Internet Banking",
  "location": "International (High-Risk)",
  "device": "Unknown / New Device",
  "frequency_24h": 12,
  "account_age_days": 2,
  "previous_amount": 10.00,
  "old_balance_orig": 85000.00,
  "new_balance_orig": 0.00
}
```

- **Field Schema:**
| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `amount` | Float | Yes | Transaction value in currency units ($> 0.00$) |
| `transaction_type` | String | No (Default: Transfer) | Transfer, Payment, Cash Withdrawal, Deposit, Purchase |
| `sender_account` | String | No | Originating account identifier |
| `receiver_account` | String | No | Beneficiary account identifier |
| `channel` | String | No (Default: Mobile Banking) | Mobile Banking, Internet Banking, ATM, POS, UPI |
| `location` | String | No (Default: Domestic) | Domestic, International (Low-Risk), International (High-Risk) |
| `device` | String | No (Default: Mobile App) | Recognized device vs. Unknown / New Device |
| `frequency_24h` | Integer | No (Default: 1) | Transaction count initiated in preceding 24 hours |
| `account_age_days` | Integer | No (Default: 365) | Age of the origin account in calendar days |
| `previous_amount` | Float | No (Default: amount) | Amount of the most recent preceding transaction |
| `old_balance_orig` | Float | No | Initial balance of origin account prior to transaction |
| `new_balance_orig` | Float | No | Resulting balance of origin account post transaction |

- **Success Response (201 Created):**
```json
{
  "success": true,
  "data": {
    "transaction_ref": "TXN-B9A1F8274C",
    "amount": 85000.0,
    "transaction_type": "Transfer",
    "prediction": {
      "is_fraud_predicted": true,
      "fraud_probability": 0.8492,
      "fraud_probability_pct": 84.92,
      "risk_level": "High",
      "recommended_action": "Freeze transaction immediately. Require step-up multi-factor biometric authentication.",
      "explanations": [
        "Complete Origin Balance Drain: 100.0% of available origin funds were extracted in this single transaction.",
        "Anomalous Transaction Ratio: Current transaction amount is 8500.0x larger than historical typical activity.",
        "Rapid Transaction Velocity: 12 transactions initiated within the last 24 hours.",
        "New Account Vulnerability: Account opened only 2 days ago.",
        "High-Risk Geo-Location & Unrecognized Device: Transaction originated from International (High-Risk) on an untrusted device."
      ],
      "model_name": "Random Forest",
      "model_version": "1.0.0"
    },
    "alert_generated": true
  }
}
```

### 2.2 Batch Prediction
Evaluates up to 100 transactions in a single batch request.

- **Endpoint:** `POST /api/v1/predict/batch`
- **Content-Type:** `application/json`
- **Request Body:**
```json
{
  "transactions": [
    {
      "amount": 25.50,
      "transaction_type": "Purchase",
      "channel": "POS",
      "frequency_24h": 1
    },
    {
      "amount": 95000.00,
      "transaction_type": "Transfer",
      "channel": "Internet Banking",
      "location": "International (High-Risk)",
      "frequency_24h": 15,
      "account_age_days": 1
    }
  ]
}
```
- **Success Response (200 OK):**
```json
{
  "success": true,
  "total": 2,
  "results": [
    {
      "index": 0,
      "status": "success",
      "transaction_ref": "TXN-A19F883E12",
      "amount": 25.50,
      "is_fraud_predicted": false,
      "fraud_probability": 0.0583,
      "risk_level": "Low"
    },
    {
      "index": 1,
      "status": "success",
      "transaction_ref": "TXN-E7480C24B1",
      "amount": 95000.00,
      "is_fraud_predicted": true,
      "fraud_probability": 0.8492,
      "risk_level": "High"
    }
  ]
}
```

---

## 3. Data Ingestion & Analytics Endpoints

### 3.1 Paginated Transaction Listing
- **Endpoint:** `GET /api/v1/transactions?page=1&limit=20`
- **Success Response (200 OK):**
```json
{
  "success": true,
  "page": 1,
  "total_pages": 1,
  "total_items": 10,
  "transactions": [
    {
      "id": 1,
      "transaction_ref": "TXN-DEMO-001",
      "amount": 25.50,
      "transaction_type": "Purchase",
      "channel": "POS",
      "location": "Domestic",
      "device": "Mobile App (Recognized)",
      "created_at": "2026-11-20 18:30:00",
      "is_demo": true,
      "prediction": {
        "fraud_probability": 0.058,
        "risk_level": "Low",
        "is_fraud_predicted": false
      }
    }
  ]
}
```

### 3.2 High-Level Statistics
- **Endpoint:** `GET /api/v1/stats`
- **Success Response (200 OK):**
```json
{
  "success": true,
  "statistics": {
    "total_transactions": 10,
    "legitimate_count": 5,
    "fraud_count": 3,
    "suspicious_count": 2,
    "fraud_rate": 30.0,
    "total_volume_flagged": 279500.00,
    "active_alerts_count": 3
  }
}
```

### 3.3 Visual Analytics Chart Data
- **Endpoint:** `GET /api/v1/analytics`
- **Success Response (200 OK):** Returns pre-aggregated series data for Chart.js (type distribution, risk tier breakdowns, 7-day volume trends).

### 3.4 Model Telemetry & Diagnostics
- **Endpoint:** `GET /api/v1/model-info`
- **Success Response (200 OK):**
```json
{
  "success": true,
  "model_status": "ready",
  "metadata": {
    "selected_model": "Random Forest",
    "model_version": "1.0.0",
    "dataset": "PaySim-style Synthetic Benchmark (15,000 transactions)",
    "all_models_evaluation": {
      "Random Forest": {
        "accuracy": 1.0,
        "precision": 1.0,
        "recall": 1.0,
        "f1_score": 1.0,
        "roc_auc": 1.0
      }
    }
  },
  "top_feature_importance": {
    "balance_orig_drain_ratio": 0.1632,
    "device_New / Unrecognized Device": 0.1345,
    "amount_to_prev_ratio": 0.1319,
    "amount": 0.1175
  }
}
```
