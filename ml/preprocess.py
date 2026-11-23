"""
Preprocessing and Feature Engineering Pipeline for FraudGuard AI.
Transforms raw transaction dictionaries or DataFrames into model-ready features.
"""

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.pipeline import Pipeline

NUMERICAL_FEATURES = [
    'amount',
    'log_amount',
    'amount_to_prev_ratio',
    'frequency_24h',
    'account_age_days',
    'previous_amount',
    'old_balance_orig',
    'new_balance_orig',
    'balance_orig_drain_ratio',
    'is_high_frequency',
    'is_new_account'
]

CATEGORICAL_FEATURES = [
    'transaction_type',
    'channel',
    'location',
    'device'
]

class FeatureEngineer(BaseEstimator, TransformerMixin):
    """Calculates domain-specific financial fraud risk indicators."""
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        df = X.copy()
        if not isinstance(df, pd.DataFrame):
            df = pd.DataFrame(df)

        # Fill default balances if missing (e.g. from single-form input)
        if 'old_balance_orig' not in df.columns:
            df['old_balance_orig'] = df['amount'] * 1.5
        if 'new_balance_orig' not in df.columns:
            df['new_balance_orig'] = np.maximum(0.0, df['old_balance_orig'] - df['amount'])
        if 'previous_amount' not in df.columns:
            df['previous_amount'] = df['amount']

        # Ensure correct numeric types
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        df['previous_amount'] = pd.to_numeric(df['previous_amount'], errors='coerce').fillna(0.0)
        df['frequency_24h'] = pd.to_numeric(df['frequency_24h'], errors='coerce').fillna(1)
        df['account_age_days'] = pd.to_numeric(df['account_age_days'], errors='coerce').fillna(365)
        df['old_balance_orig'] = pd.to_numeric(df['old_balance_orig'], errors='coerce').fillna(df['amount'] * 1.5)
        df['new_balance_orig'] = pd.to_numeric(df['new_balance_orig'], errors='coerce').fillna(0.0)

        # 1. Log transform amount to handle skewness
        df['log_amount'] = np.log1p(np.maximum(0.0, df['amount']))

        # 2. Ratio of current amount to historical previous amount
        df['amount_to_prev_ratio'] = df['amount'] / (df['previous_amount'] + 1.0)

        # 3. Drain ratio (amount relative to total starting balance)
        df['balance_orig_drain_ratio'] = df['amount'] / (df['old_balance_orig'] + 1.0)

        # 4. Behavioral indicator flags
        df['is_high_frequency'] = (df['frequency_24h'] >= 8).astype(int)
        df['is_new_account'] = (df['account_age_days'] <= 30).astype(int)

        return df

def build_preprocessor():
    """Builds a scikit-learn ColumnTransformer for scaling & one-hot encoding."""
    numeric_transformer = Pipeline(steps=[
        ('scaler', StandardScaler())
    ])

    categorical_transformer = Pipeline(steps=[
        ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ('num', numeric_transformer, NUMERICAL_FEATURES),
            ('cat', categorical_transformer, CATEGORICAL_FEATURES)
        ],
        remainder='drop'
    )

    return preprocessor

def create_full_pipeline(classifier):
    """Combines FeatureEngineer, ColumnTransformer, and Classifier into a single end-to-end Pipeline."""
    return Pipeline(steps=[
        ('engineer', FeatureEngineer()),
        ('preprocessor', build_preprocessor()),
        ('classifier', classifier)
    ])
