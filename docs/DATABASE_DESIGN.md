# FraudGuard AI: Database Design & Schema Specification

FraudGuard AI utilizes a fully normalized relational database schema managed via **SQLAlchemy ORM**. The data tier supports local file-based SQLite development and seamless migration to enterprise PostgreSQL in production.

---

## 1. Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    users ||--o{ transactions : "creates"
    users ||--o{ fraud_alerts : "receives"
    users ||--o{ audit_logs : "triggers"
    transactions ||--|| predictions : "evaluated_by"
    transactions ||--o{ fraud_alerts : "escalates_to"

    users {
        int id PK
        string name "User full name"
        string email UK "Indexed unique email"
        string password_hash "Scrypt cryptographic hash"
        string role "user | admin"
        boolean is_active_account "Account activation toggle"
        datetime created_at
        datetime updated_at
    }

    transactions {
        int id PK
        string transaction_ref UK "Indexed unique reference (TXN-...)"
        int user_id FK "References users.id (CASCADE)"
        float amount "Transaction currency amount"
        string transaction_type "Payment, Transfer, etc."
        string sender_account "Origin account ID"
        string receiver_account "Beneficiary account ID"
        string channel "Mobile Banking, ATM, POS, etc."
        string location "Domestic, International (High-Risk)"
        string device "Device fingerprint metadata"
        int frequency_24h "Velocity count in last 24 hours"
        int account_age_days "Age of account in days"
        float previous_amount "Historical transaction amount"
        float old_balance_orig "Balance prior to transaction"
        float new_balance_orig "Balance after transaction"
        boolean is_demo "Identifies demo scenario data"
        datetime created_at "Indexed timestamp"
    }

    predictions {
        int id PK
        int transaction_id FK, UK "1-to-1 unique FK to transactions.id"
        string model_name "Algorithm (Random Forest)"
        string model_version "Model release version"
        float fraud_probability "Calibrated probability [0.0 - 1.0]"
        boolean is_fraud_predicted "Binary prediction"
        string risk_level "Low | Medium | High | Critical"
        text explanation_summary "JSON serialized forensic factors"
        text recommended_action "Prescribed compliance protocol"
        datetime created_at
    }

    fraud_alerts {
        int id PK
        int transaction_id FK "References transactions.id (CASCADE)"
        int user_id FK "References users.id (CASCADE)"
        string severity "Medium | High | Critical"
        string title "Alert header"
        text message "Forensic alert justification"
        boolean is_read "Indexed read/resolved boolean"
        datetime created_at "Indexed timestamp"
    }

    audit_logs {
        int id PK
        int user_id FK "Nullable FK to users.id"
        string action "Indexed action code (e.g., LOGIN_SUCCESS)"
        string ip_address "Remote IP address"
        text details "Structured context"
        datetime created_at "Indexed timestamp"
    }
```

---

## 2. Table Dictionaries & Schema Definitions

### 2.1 Table: `users`
Stores user identity, role-based authorization attributes, and cryptographic credentials.
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Unique surrogate key |
| `name` | `VARCHAR(100)` | `NOT NULL` | Full legal or display name |
| `email` | `VARCHAR(120)` | `NOT NULL, UNIQUE, INDEX` | Unique email identifier (lowercase normalized) |
| `password_hash` | `VARCHAR(255)` | `NOT NULL` | Salted Scrypt hash string |
| `role` | `VARCHAR(20)` | `NOT NULL, DEFAULT 'user'` | Access control role (`'user'` or `'admin'`) |
| `is_active_account` | `BOOLEAN` | `NOT NULL, DEFAULT TRUE` | Administrative killswitch for user access |
| `created_at` | `DATETIME` | `NOT NULL, DEFAULT utcnow` | Account creation timestamp |
| `updated_at` | `DATETIME` | `NOT NULL, DEFAULT utcnow` | Last profile update timestamp |

### 2.2 Table: `transactions`
Records financial transaction attributes, account metadata, and channel provenance.
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Unique transaction ID |
| `transaction_ref`| `VARCHAR(64)` | `NOT NULL, UNIQUE, INDEX` | Human-readable reference code (`TXN-...`) |
| `user_id` | `INTEGER` | `FOREIGN KEY (users.id) ON DELETE CASCADE, INDEX` | Associated analyst or customer ID |
| `amount` | `FLOAT` | `NOT NULL` | Transaction amount ($> 0.00$) |
| `transaction_type` | `VARCHAR(32)` | `NOT NULL` | Payment, Transfer, Cash Withdrawal, Deposit, Purchase |
| `sender_account`| `VARCHAR(64)` | `NOT NULL` | Originating bank account or wallet ID |
| `receiver_account`| `VARCHAR(64)` | `NOT NULL` | Beneficiary bank account or merchant ID |
| `channel` | `VARCHAR(32)` | `NOT NULL` | Mobile Banking, Internet Banking, ATM, POS, UPI |
| `location` | `VARCHAR(64)` | `NOT NULL, DEFAULT 'Domestic'` | Geographic risk profile |
| `device` | `VARCHAR(64)` | `NOT NULL` | Device fingerprint and trust classification |
| `frequency_24h`| `INTEGER` | `NOT NULL, DEFAULT 1` | Velocity count of transactions in last 24h |
| `account_age_days`| `INTEGER` | `NOT NULL, DEFAULT 365` | Age of origin account in days |
| `previous_amount`| `FLOAT` | `NOT NULL` | Historical transaction baseline amount |
| `old_balance_orig`| `FLOAT` | `NULLABLE` | Balance of sender prior to debit |
| `new_balance_orig`| `FLOAT` | `NULLABLE` | Balance of sender post debit |
| `is_demo` | `BOOLEAN` | `NOT NULL, DEFAULT FALSE` | Flag for seeded portfolio demo records |
| `created_at` | `DATETIME` | `NOT NULL, DEFAULT utcnow, INDEX`| Creation timestamp |

### 2.3 Table: `predictions`
Stores model inferences, calibrated probabilities, risk tiers, and explainability factors.
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Unique prediction ID |
| `transaction_id`| `INTEGER` | `FOREIGN KEY (transactions.id) ON DELETE CASCADE, UNIQUE` | 1-to-1 relationship with transaction |
| `model_name` | `VARCHAR(64)` | `NOT NULL` | Name of model (e.g. `Random Forest`) |
| `model_version` | `VARCHAR(32)` | `NOT NULL, DEFAULT '1.0.0'` | Model version identifier |
| `fraud_probability`| `FLOAT` | `NOT NULL` | Calibrated continuous score $[0.0, 1.0]$ |
| `is_fraud_predicted`| `BOOLEAN` | `NOT NULL` | Binary decision threshold |
| `risk_level` | `VARCHAR(20)` | `NOT NULL` | Stratified tier (`Low`, `Medium`, `High`, `Critical`) |
| `explanation_summary`| `TEXT` | `NULLABLE` | JSON array of forensic justification strings |
| `recommended_action`| `TEXT` | `NULLABLE` | Operational compliance guidance |
| `created_at` | `DATETIME` | `NOT NULL, DEFAULT utcnow` | Prediction timestamp |

### 2.4 Table: `fraud_alerts`
Tracks actionable security alerts triggered by High or Critical risk inferences.
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Unique alert ID |
| `transaction_id`| `INTEGER` | `FOREIGN KEY (transactions.id) ON DELETE CASCADE, INDEX` | Linked high-risk transaction |
| `user_id` | `INTEGER` | `FOREIGN KEY (users.id) ON DELETE CASCADE, INDEX` | Owner of transaction |
| `severity` | `VARCHAR(20)` | `NOT NULL` | `Medium`, `High`, or `Critical` |
| `title` | `VARCHAR(128)`| `NOT NULL` | Alert title |
| `message` | `TEXT` | `NOT NULL` | Forensic justification details |
| `is_read` | `BOOLEAN` | `NOT NULL, DEFAULT FALSE, INDEX` | Status flag (`False` = unread/active) |
| `created_at` | `DATETIME` | `NOT NULL, DEFAULT utcnow, INDEX`| Alert creation timestamp |

### 2.5 Table: `audit_logs`
Provides an immutable security trail for administrative and compliance auditing.
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Unique log entry ID |
| `user_id` | `INTEGER` | `FOREIGN KEY (users.id), NULLABLE, INDEX` | Actor user ID (null for anonymous attempts) |
| `action` | `VARCHAR(64)` | `NOT NULL, INDEX` | Action code (`LOGIN_SUCCESS`, `ALERT_READ`, etc.) |
| `ip_address` | `VARCHAR(45)` | `NOT NULL, DEFAULT '127.0.0.1'` | Client IP address (IPv4 or IPv6) |
| `details` | `TEXT` | `NULLABLE` | Contextual metadata |
| `created_at` | `DATETIME` | `NOT NULL, DEFAULT utcnow, INDEX`| Event timestamp |

---

## 3. Database Indexes & Query Optimization

To guarantee sub-10ms response times for high-volume dashboard queries and transaction filtering:
1. `users.email`: Unique B-Tree index for $O(1)$ authentication lookups.
2. `transactions.transaction_ref`: Unique B-Tree index for quick reference searches.
3. `transactions.created_at`: Descending index for rapid pagination of newest records.
4. `transactions.user_id`: Foreign key index to enforce multi-tenant customer isolation without full-table scans.
5. `fraud_alerts.is_read` & `fraud_alerts.user_id`: Composite index powering instantaneous unread alert count badge queries (`inject_global_data` context processor).
6. `audit_logs.action` & `audit_logs.created_at`: Filtered administrative index for audit inspection.
