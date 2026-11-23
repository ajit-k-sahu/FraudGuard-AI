# FraudGuard AI – AI-Powered Financial Fraud Detection System

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1.3-green.svg)](https://palletsprojects.com/p/flask/)
[![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-1.8.0-orange.svg)](https://scikit-learn.org/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3.3-purple.svg)](https://getbootstrap.com/)
[![Tests](https://img.shields.io/badge/Pytest-250%20Passed%20(100%25)-brightgreen.svg)](https://pytest.org/)
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
- [Demonstration Access & Recruiter Portal](#-demonstration-access--recruiter-portal)
- [Automated Test Suite (250/250 Passing)](#-automated-test-suite-250250-passing)
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

> [!NOTE]
> **Synthetic Dataset & Evaluation Disclaimer:**
> The benchmark metrics above were measured on a held-out evaluation split of the 15,000-record PaySim-style synthetic simulation (`ml/generate_synthetic_data.py`). In this controlled benchmark environment, simulated fraud typologies (e.g. balance drains, extreme velocity spikes) follow mathematically discrete behavioral boundaries that the 120-tree Random Forest ensemble separates completely.
> **These scores reflect synthetic benchmark separation and must not be interpreted as a guarantee of identical real-world performance.** In production banking rails, real financial data exhibits severe class imbalance ($< 0.1\%$), sensor noise, partial label ambiguity, and continuous adversarial strategy shifts that necessitate human-in-the-loop triage.

---

## 🛠 Technology Stack

- **Backend:** Python 3.10–3.14, Flask 3.1.3, Flask-SQLAlchemy 3.1.1, Flask-Login 0.6.3, Flask-WTF 1.3.0, WTForms 3.3.2, Flask-Limiter 3.5.0
- **Machine Learning:** Scikit-learn 1.8.0, Pandas 3.0.2, NumPy 2.4.4, Joblib 1.5.3, Matplotlib, Seaborn
- **Database & Storage:** SQLite 3 (Development/Testing), PostgreSQL (Production with Connection Pooling), Redis (Production Distributed Rate Limiting)
- **Frontend:** Jinja2 Templates, HTML5, CSS3, Bootstrap 5.3.3, Bootstrap Icons 1.11.3, Chart.js 4.4.2
- **Testing:** Pytest 9.2.0 (250 Automated Tests across 22 Modules), Flask Test Client
- **Production Server:** Gunicorn 21.2.0 (gthread worker, Render / Container WSGI), Waitress 3.0.2 (Cross-platform)

---

## 🚀 Quick Start & Installation

### Prerequisites
- Python 3.10, 3.11, 3.12, 3.13, or 3.14
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/ajit-k-sahu/FraudGuard-AI.git
cd FraudGuard-AI
```

### 2. Create and Activate a Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv venv
# If script execution is restricted on your system, allow it for the current process:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

**Windows (Command Prompt / cmd.exe):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the template configuration file:
```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

### 5. Seed Initial Data (Model Artifacts Included)
Pre-trained model artifacts (`ml/artifacts/pipeline.joblib`, `model_metadata.json`, and `feature_importance.json`) are committed directly to the repository and ready for immediate inference. Simply run the seeding script to populate initial baseline analyst and demonstration scenarios:
```bash
python scripts/seed_demo_data.py
```

*(Optional)* If you wish to regenerate synthetic transactions and retrain the machine learning pipeline from scratch:
```bash
python ml/generate_synthetic_data.py
python ml/train_model.py
```

### 6. Run the Application
```bash
python run.py
```
Open your web browser and navigate to: **`http://127.0.0.1:5000`**

---

## 🔑 Demonstration Access & Recruiter Portal

FraudGuard AI provides a secure, isolated evaluation flow for recruiters and reviewers without requiring manual registration:

### ⚡ One-Click Instant Recruiter Demo (Recommended)
- Navigate to the login page (`/auth/login`) and click the **"Instant Recruiter Demo"** button (or navigate directly to `/auth/demo-login`).
- **Unique Ephemeral Identity:** Provisions a fresh, isolated session (`recruiter_<uuid>@demo.fraudguard.ai`).
- **Data Isolation:** Each recruiter session operates inside an isolated sandbox with dedicated transaction records, alerts, and analytics.
- **Active 2-Hour Expiration:** Sessions expire exactly 2 hours after creation using server-side UTC timestamps (`User.is_expired`), immediately revoking access to protected routes even before physical cleanup.

### 👤 Permanent Baseline Analyst Account
- For local testing and development, a seeded baseline account is provided:
  - **Email:** `analyst@bank.com`
  - **Clearances:** Analyst Portal, Real-time & Batch AI Inferences, Fraud Alerts, Executive Analytics.
  *(Password is provisioned securely during local seeding or via environment variables).*

> **Note on Administrative Security:**
> In accordance with production security standards, administrative credentials are never displayed publicly. Production and local administrative accounts are securely initialized via environment variables (`ADMIN_EMAIL`, `ADMIN_PASSWORD`) using `python scripts/create_admin.py`.

---

## 🧪 Automated Test Suite (250/250 Passing)

FraudGuard AI includes an exhaustive regression test suite covering all tiers of the application:

```bash
pytest tests/ -v
```

### Verified Test Coverage Across 22 Modules:
- **Core Application & Views:** `test_alerts.py`, `test_api.py`, `test_audit_verification.py`, `test_auth.py`, `test_batch.py`, `test_file_upload_and_validation.py`, `test_frontend_views.py`, `test_transactions.py`, `test_timezone.py`, `test_ml_prediction.py`.
- **Recruiter Demo Security & Expiration:** `test_demo_account_security.py`, `test_demo_cleanup.py`, `test_demo_expiration_and_migration.py`, `test_demo_isolation.py`, `test_one_click_demo_login.py`.
- **Infrastructure, WSGI & Production Security:** `test_free_tier_hosting.py`, `test_gunicorn_and_proxy.py`, `test_postgres_config.py`, `test_production_secrets_hardening.py`, `test_rate_limiting.py`, `test_redis_ratelimit.py`, `test_security_headers_and_csrf.py`.

**Test Execution Result:** **250 Passed, 0 Failed (100% Pass Rate).**

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

### 1. Docker Compose (Web App + PostgreSQL + Redis)
Run the entire production-like stack in isolated Docker containers:
```bash
docker-compose up -d --build
```
Access the application at `http://localhost:5000`. Container health checks monitor database connectivity, Redis shared rate limiting, and ML pipeline memory residency.

### 2. Standalone Docker Container
```bash
docker build -t fraudguard-ai:latest .
docker run -p 5000:5000 --env-file .env fraudguard-ai:latest
```

### 3. Deploy to Render (Free-Tier Stack)
The repository includes a ready-to-use [`render.yaml`](render.yaml) blueprint configured for free-tier hosting:
- **Web Service:** Render Free Web Service (512MB RAM, Gunicorn WSGI with `WEB_CONCURRENCY=2` and `GUNICORN_THREADS=2`).
- **Database:** External free PostgreSQL (such as [Neon.tech](https://neon.tech/)).
- **Rate Limiting / Cache:** External free Redis (such as [Upstash.com](https://upstash.com/)).

**Deployment Steps:**
1. In [Render Dashboard](https://dashboard.render.com/), select **New +** > **Blueprint**.
2. Connect your `FraudGuard-AI` repository.
3. When prompted for environment variables marked `sync: false`, provide:
   - `DATABASE_URL`: Your Neon PostgreSQL connection string (with `?sslmode=require`).
   - `REDIS_URL`: Your Upstash Redis TLS connection string (`rediss://...`).
   - `ADMIN_PASSWORD`: A secure password ($\ge 12$ characters) to initialize the administrator account.
4. Render automatically generates a cryptographically secure `SECRET_KEY`, installs `requirements.txt`, seeds baseline demo scenarios (reusing pre-trained model artifacts without retraining), and attaches health monitoring (`/api/health`).

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
