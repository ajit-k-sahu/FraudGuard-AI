# FraudGuard AI – AI-Powered Financial Fraud Detection System

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1.3-green.svg)](https://palletsprojects.com/p/flask/)
[![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-1.8.0-orange.svg)](https://scikit-learn.org/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3.3-purple.svg)](https://getbootstrap.com/)
[![Tests](https://img.shields.io/badge/Pytest-40%20Passed%20(100%25)-brightgreen.svg)](https://pytest.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)

**FraudGuard AI** is an enterprise-grade financial transaction fraud detection platform engineered with **Python**, **Flask**, **SQLAlchemy**, and **Scikit-learn**. The application provides real-time transaction risk scoring, multi-tier fraud stratification, actionable forensic explainability, CSV batch evaluation, dynamic Chart.js analytics, role-based access control (RBAC), and immutable security audit logging.

Built as an academic capstone and high-impact portfolio system, FraudGuard AI is completely end-to-end: every KPI card, gauge, distribution chart, alert, and prediction is driven by real database records and calibrated inferences from a trained 120-tree Random Forest ensemble pipeline (`pipeline.joblib`).

---

## 📑 Table of Contents
- [Architecture & Data Flow](#-system-architecture)
- [Key Capabilities & Features](#-key-capabilities)
- [Machine Learning Pipeline & Forensic Typologies](#-machine-learning-pipeline)
- [Technology Stack](#-technology-stack)
- [Quick Start & Installation](#-quick-start--installation)
- [Demo Credentials](#-demo-credentials)
- [Automated Test Suite (40/40 Passing)](#-automated-test-suite)
- [REST API Reference & cURL Examples](#-rest-api-reference)
- [Docker & Production Deployment](#-docker--production-deployment)
- [Project Documentation & Academic Reports](#-project-documentation)
- [License & Disclaimer](#-license--disclaimer)

---

## 🏛 System Architecture

FraudGuard AI adopts a clean, layered Model-View-Controller (MVC) and Service-Oriented pattern:

```mermaid
flowchart TD
    subgraph Client Tier
        Browser["Modern Browser (Desktop / Tablet / Mobile)"]
        APIClient["External Financial Rail / REST Consumer"]
    end

    subgraph Controller & Routing Tier
        ReverseProxy["WSGI Server (Waitress / Gunicorn)"]
        CSRF["CSRF & Session Security Layer"]
        BPAuth["/auth - Authentication & Password Security"]
        BPDash["/ - Real-Time Executive Dashboard"]
        BPTxn["/transactions - Real-time & Batch Analysis"]
        BPAlert["/alerts - Fraud Incident Management"]
        BPAnalytics["/analytics - Trend & Risk Distributions"]
        BPAdmin["/admin - User Control & Security Audit Logs"]
        BPProfile["/profile - Security & Credentials"]
        BPAPI["/api/v1 - REST API & Health Telemetry"]
    end

    subgraph Service Layer (Business Logic)
        PredService["PredictionService (Pipeline Orchestrator)"]
        AnalyticsService["AnalyticsService (SQL Aggregator)"]
        MLService["MLService (Singleton Model Manager)"]
        AuditLogger["log_audit_event() (Security Trail)"]
    end

    subgraph Machine Learning Tier
        PipelineArtifact["pipeline.joblib (120-Tree Random Forest)"]
        FeatureEngine["Custom Feature Synthesizer & Preprocessor"]
        ModelMeta["model_metadata.json & Feature Importances"]
    end

    subgraph Persistence Layer
        DB[("Relational Database (SQLite / PostgreSQL)")]
        Users["users"]
        Transactions["transactions"]
        Predictions["predictions"]
        Alerts["fraud_alerts"]
        AuditLogs["audit_logs"]
    end

    Browser --> ReverseProxy
    APIClient --> ReverseProxy
    ReverseProxy --> CSRF
    CSRF --> BPAuth & BPDash & BPTxn & BPAlert & BPAnalytics & BPAdmin & BPProfile & BPAPI

    BPTxn --> PredService
    BPAPI --> PredService
    BPDash --> AnalyticsService
    BPAnalytics --> AnalyticsService
    BPAdmin --> AnalyticsService & MLService

    PredService --> MLService
    MLService --> PipelineArtifact & FeatureEngine & ModelMeta

    PredService --> DB
    AnalyticsService --> DB
    AuditLogger --> DB

    DB --> Users & Transactions & Predictions & Alerts & AuditLogs
```

---

## ⚡ Key Capabilities

### 1. Real-Time AI Transaction Prediction
- **Interactive Form:** Submit transaction amount, transaction type (Transfer, Payment, Cash Withdrawal, Deposit, Purchase), channel (Mobile Banking, Internet Banking, ATM, POS, UPI), sender/receiver account numbers, device fingerprint, frequency velocity, and account age.
- **Scenario Presets:** One-click automated form autofill for real-world scenarios:
  - *Normal Retail Purchase* (Low Risk $\approx 5.8\%$)
  - *Sudden Velocity Burst* (Medium/High Risk $\approx 65\%–75\%$)
  - *Full Account Takeover Drain* (Critical Risk $\approx 85\%–92\%$)
- **Calibrated Probability Gauge:** Displays continuous probability from $0.0\%$ to $100.0\%$.
- **Multi-Tier Risk Stratification:**
  - 🟢 **Low Risk** ($< 30\%$): Automatic transaction approval.
  - 🟡 **Medium Risk** ($30\% - 69.9\%$): Step-up OTP or biometric MFA challenge.
  - 🔴 **High Risk** ($70\% - 89.9\%$): Immediate transaction freeze and compliance alert.
  - 🟣 **Critical Risk** ($\ge 90\%$): Automatic account lock, transaction rejection, and emergency SMS/email.
- **Explainable AI (XAI) Forensic Factor Cards:** Synthesizes clear, bulleted reasons detailing why the transaction was flagged (e.g. *"Complete Origin Balance Drain: 100.0% of available origin funds extracted in this single transaction"*).

### 2. Multi-Record Batch CSV Processing
- Upload multi-row CSV files (up to 500 records per upload) for bulk inference.
- One-click **Download Sample Template CSV** button.
- Live summary counters: Total Records Evaluated, Legitimate Count, Flagged Fraud / Suspicious Count, and Row-level outcome badges.

### 3. Executive Analytics & Dynamic Dashboard
- Aggregated KPI cards: Total Transactions Analyzed, Legitimate Inferences, Fraudulent Flags, Overall Fraud Detection Rate, and Total Capital Protected.
- Interactive **Chart.js** data visualizations:
  - 7-Day Ingestion & Fraud Volume Area/Line Trend
  - Channel Volume Distribution (Donut Chart)
  - Risk Tier Breakdown (Bar Chart)
  - Transaction Type Proportions (Doughnut Chart)

### 4. Audit History & CSV Export
- Searchable transaction table with full-text search across reference codes, sender accounts, and receiver accounts.
- Granular multi-filter parameters: Transaction Type, Risk Level, and Outcome.
- Server-side pagination with clean URL parameter preservation.
- **One-Click CSV Export:** Streams filtered transaction records with timestamps, risk probabilities, and outcomes.

### 5. Fraud Alert Incident Center
- Automatic generation of `FraudAlert` entities whenever an inference crosses the High-Risk threshold ($70\%+$).
- Filter alerts by severity (`Medium`, `High`, `Critical`) and status (`unread` vs. `read`).
- Resolve individual alerts or perform bulk **Mark All as Read** operations.

### 6. Administrator Command Center & RBAC
- **Strict Role-Based Authorization:** Non-admin users are strictly blocked from `/admin` (HTTP 403 Forbidden).
- **User Management:** View all registered analysts and toggle account activation status (deactivated accounts are immediately blocked from logging in).
- **Security Audit Logs:** Comprehensive immutable log tracking login events, failed logins, account deactivations, batch processing, and unauthorized admin access attempts with client IP addresses.
- **Model Telemetry & Diagnostics:** Live inspection of model metadata, accuracy, precision, recall, F1, ROC-AUC, and relative Gini feature importance bars.

---

## 🧠 Machine Learning Pipeline

### Forensic Fraud Typologies Injected (15,000 Transactions Dataset)
1. **Account Takeover / Balance Drain:** Sudden transfer extracting $90\%–100\%$ of available sender balance.
2. **Velocity Burst:** Spike of $\ge 10$ rapid transactions in 24 hours from an unrecognized device.
3. **New Account Extraction:** High-value transfer originating from an account opened $< 5$ days prior.
4. **Historical Ratio Spike:** Transaction amount exceeding $25\times$ historical median.
5. **Cross-Border Exploitation:** High-value withdrawal or transfer in an international high-risk terminal.
6. **Micro-Testing:** Rapid micro-transactions ($\le \$5$) executed prior to high-value extraction attempts.

### Champion Model Benchmark Performance (`Random Forest`)
| Metric | Performance Score |
| :--- | :---: |
| **Accuracy** | **100.0%** |
| **Precision** | **100.0%** |
| **Recall** | **100.0%** |
| **F1-Score** | **1.000** |
| **ROC-AUC** | **1.000** |
| **PR-AUC** | **1.000** |
| **Inference Latency** | **$\approx 3.1$ ms** |

---

## 🛠 Technology Stack

- **Backend:** Python 3.10–3.14, Flask 3.1.3, Flask-SQLAlchemy 3.1.1, Flask-Login 0.6.3, Flask-WTF 1.3.0, WTForms 3.3.2
- **Machine Learning:** Scikit-learn 1.8.0, Pandas 3.0.2, NumPy 2.4.4, Joblib 1.5.3, Matplotlib, Seaborn
- **Database:** SQLite 3 (Development/Testing), PostgreSQL (Production-Ready)
- **Frontend:** Jinja2 Templates, HTML5, CSS3, Bootstrap 5.3.3, Bootstrap Icons 1.11.3, Chart.js 4.4.2
- **Testing:** Pytest 9.2.0, Flask Test Client
- **Production Server:** Waitress 3.0.2, Gunicorn

---

## 🚀 Quick Start & Installation

### Prerequisites
- Python 3.10, 3.11, 3.12, 3.13, or 3.14
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/fraudguard-ai.git
cd fraudguard-ai
```

### 2. Create and Activate a Virtual Environment
```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the sample environment file:
```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

### 5. Generate ML Dataset, Train Model & Seed Demo Data
Run the automated initialization pipeline:
```bash
# Generate 15,000 synthetic transaction records
python ml/generate_synthetic_data.py

# Train and evaluate models, persisting pipeline.joblib
python ml/train_model.py

# Seed administrator, analyst accounts, and demo scenarios
python scripts/seed_demo_data.py
```

### 6. Run the Application
```bash
python run.py
```
Open your web browser and navigate to: **`http://127.0.0.1:5000`**

---

## 🔑 Demo Credentials

| Role | Email Address | Password | Clearances |
| :--- | :--- | :--- | :--- |
| **Recruiter / Financial Analyst Demo** | `analyst@bank.com` | `AnalystPass123!` | Full Analyst Portal, Single & Batch AI Inference, Fraud Alerts, Analytics |

> **Note on Administrative Security:**
> In accordance with production security standards, administrative credentials are never displayed on public pages or documentation. Production and local administrative accounts are securely provisioned via environment variables (`ADMIN_EMAIL`, `ADMIN_PASSWORD`) using `python scripts/create_admin.py`.

---

## 🧪 Automated Test Suite

FraudGuard AI includes an exhaustive automated test suite covering all tiers of the application:

```bash
pytest tests/ -v
```

### Test Suite Execution Output (40/40 Passing):
```text
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Users\Welcome\Downloads\FraudGuard- AI
collected 40 items

tests/test_alerts.py::test_alert_generation_and_list_view PASSED         [  2%]
tests/test_api.py::test_api_health_endpoint PASSED                       [  5%]
tests/test_api.py::test_api_auth_login PASSED                            [  7%]
tests/test_api.py::test_api_predict_endpoint_valid PASSED                [ 10%]
tests/test_api.py::test_api_predict_missing_amount_error PASSED          [ 12%]
tests/test_api.py::test_api_predict_batch_endpoint PASSED                [ 15%]
tests/test_api.py::test_api_transactions_and_stats PASSED                [ 17%]
tests/test_api.py::test_api_model_info_diagnostics PASSED                [ 20%]
tests/test_audit_verification.py::test_app_initialization PASSED         [ 22%]
tests/test_audit_verification.py::test_user_authentication_and_password_security PASSED [ 25%]
tests/test_audit_verification.py::test_ml_service_and_artifacts PASSED   [ 27%]
tests/test_audit_verification.py::test_prediction_engine_low_and_high_risk PASSED [ 30%]
tests/test_audit_verification.py::test_api_health_endpoint PASSED        [ 32%]
tests/test_audit_verification.py::test_api_predict_endpoint PASSED       [ 35%]
tests/test_auth.py::test_registration_success PASSED                     [ 37%]
tests/test_auth.py::test_registration_duplicate_email PASSED             [ 40%]
tests/test_auth.py::test_registration_password_mismatch PASSED           [ 42%]
tests/test_auth.py::test_login_success_and_logout PASSED                 [ 45%]
tests/test_auth.py::test_login_invalid_password PASSED                   [ 47%]
tests/test_auth.py::test_login_deactivated_account PASSED                [ 50%]
tests/test_auth.py::test_protected_routes_require_authentication PASSED  [ 52%]
tests/test_batch.py::test_batch_page_loads PASSED                        [ 55%]
tests/test_batch.py::test_batch_sample_csv_download PASSED               [ 57%]
tests/test_batch.py::test_batch_csv_upload_and_processing PASSED         [ 60%]
tests/test_batch.py::test_batch_upload_empty_submission PASSED           [ 62%]
tests/test_frontend_views.py::test_public_pages PASSED                   [ 65%]
tests/test_frontend_views.py::test_login_and_logout_flow PASSED          [ 67%]
tests/test_frontend_views.py::test_transaction_views PASSED              [ 70%]
tests/test_frontend_views.py::test_alerts_and_analytics_views PASSED     [ 72%]
tests/test_frontend_views.py::test_rbac_admin_security PASSED            [ 75%]
tests/test_ml_prediction.py::test_ml_service_singleton_and_artifacts PASSED [ 77%]
tests/test_ml_prediction.py::test_prediction_low_risk_retail_transaction PASSED [ 80%]
tests/test_ml_prediction.py::test_prediction_high_risk_account_takeover PASSED [ 82%]
tests/test_ml_prediction.py::test_explainability_and_recommended_actions PASSED [ 85%]
tests/test_transactions.py::test_analyze_page_get PASSED                 [ 87%]
tests/test_transactions.py::test_analyze_page_submission_legitimate PASSED [ 90%]
tests/test_transactions.py::test_analyze_page_submission_high_risk PASSED [ 92%]
tests/test_transactions.py::test_history_filtering_and_search PASSED     [ 95%]
tests/test_transactions.py::test_transaction_detail_access_control PASSED [ 97%]
tests/test_transactions.py::test_transaction_csv_export PASSED           [100%]

====================== 40 passed in 26.44s ======================
```

---

## 📡 REST API Reference

FraudGuard AI provides a JSON REST API for external banking rail integration.

### Health Telemetry
```bash
curl -X GET http://127.0.0.1:5000/api/health
```
```json
{
  "status": "healthy",
  "database": "connected",
  "ml_model": "loaded",
  "version": "1.0.0"
}
```

### Real-Time Transaction Prediction
```bash
curl -X POST http://127.0.0.1:5000/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 95000.00,
    "transaction_type": "Transfer",
    "channel": "Internet Banking",
    "location": "International (High-Risk)",
    "device": "Unknown / New Device",
    "frequency_24h": 15,
    "account_age_days": 2,
    "previous_amount": 10.00,
    "old_balance_orig": 95000.00,
    "new_balance_orig": 0.00
  }'
```
```json
{
  "success": true,
  "data": {
    "transaction_ref": "TXN-E7480C24B1",
    "amount": 95000.0,
    "transaction_type": "Transfer",
    "prediction": {
      "is_fraud_predicted": true,
      "fraud_probability": 0.8492,
      "fraud_probability_pct": 84.92,
      "risk_level": "High",
      "recommended_action": "Freeze transaction immediately. Require step-up multi-factor biometric authentication.",
      "explanations": [
        "Complete Origin Balance Drain: 100.0% of available origin funds were extracted in this single transaction.",
        "Anomalous Transaction Ratio: Current transaction amount is 9500.0x larger than historical typical activity.",
        "Rapid Transaction Velocity: 15 transactions initiated within the last 24 hours.",
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

---

## 🐳 Docker & Production Deployment

### 1. Docker Compose (Web App + PostgreSQL)
Run the entire stack in isolated Docker containers:
```bash
docker-compose up -d --build
```
Access the application at `http://localhost:5000`. Container health checks monitor database connectivity and ML pipeline memory residency.

### 2. Standalone Docker Container
```bash
docker build -t fraudguard-ai:latest .
docker run -p 5000:5000 --env-file .env fraudguard-ai:latest
```

### 3. Deploy to Render / Cloud PaaS
The repository includes a ready-to-use [`render.yaml`](render.yaml) specification and [`Procfile`](Procfile) for zero-configuration cloud deployment:
1. Connect your GitHub repository to [Render.com](https://render.com/).
2. Select **Blueprint** deployment.
3. Render automatically provisions the Python environment, executes `requirements.txt`, trains the pipeline, seeds demo accounts, and attaches health monitoring.

---

## 📚 Project Documentation

Comprehensive academic specifications and architectural documentation are available in the [`docs/`](docs/) directory:
- [📄 Formal Academic Project Report](docs/PROJECT_REPORT.md)
- [🏗 System Architecture & Data Flow Diagrams](docs/ARCHITECTURE.md)
- [📡 Complete REST API Documentation](docs/API_DOCUMENTATION.md)
- [🗄 Relational Database Design & ERD Specification](docs/DATABASE_DESIGN.md)
- [🔬 Machine Learning Model Evaluation & Forensic Diagnostics](docs/ML_MODEL_REPORT.md)

---

## ⚖️ License & Educational Disclaimer

This project is released under the **MIT License**.

> [!IMPORTANT]
> **Educational & Portfolio Prototype Notice:** FraudGuard AI is an educational machine learning prototype engineered for demonstration, placement portfolios, and academic evaluation. Model inferences represent statistical probability estimates and should not be construed as definitive certified banking fraud determinations without human oversight.
