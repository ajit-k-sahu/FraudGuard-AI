# FraudGuard AI - Dataset Documentation

## Overview

FraudGuard AI is designed to analyze financial transaction streams to detect potential fraud.

### Public Reference Dataset
- **Name:** PaySim Synthetic Financial Datasets for Fraud Detection
- **Source:** [Kaggle PaySim Dataset](https://www.kaggle.com/datasets/ealaxi/paysim1)
- **Description:** PaySim simulates mobile money transactions based on a sample of real financial logs from a mobile money service in an African country.

### Local Development Dataset
To enable immediate local development, reproducible academic evaluation, and continuous integration testing without requiring manual downloads of multi-gigabyte files, FraudGuard AI includes a dedicated synthetic generator:
- **Script:** `ml/generate_synthetic_data.py`
- **Output:** `dataset/synthetic_transactions.csv`
- **Typologies Modeled:**
  1. **Account Takeover / Rapid Drain:** Large transfers draining originating account balance to zero.
  2. **Sudden Velocity Spikes:** Abnormal transaction counts within a 24-hour window.
  3. **New Account High-Value Transfer:** Accounts under 14 days old initiating unusually large payments.
  4. **Spending Discrepancies:** Transactions whose amounts deviate dramatically (>20x) from historical averages.
  5. **High-Risk Channel / Device Pairings:** Unrecognized devices paired with cross-border routes during off-peak hours.
- **Labeling:** All records generated locally are transparently flagged with source provenance (`synthetic_dev_benchmark`).
