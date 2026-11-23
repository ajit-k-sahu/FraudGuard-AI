"""
Model Training and Comparative Evaluation Script for FraudGuard AI.
Trains and compares Logistic Regression, Random Forest, and Gradient Boosting.
Generates evaluation metrics, confusion matrix, ROC/PR curves, and feature importances.
"""

import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import joblib
import numpy as np
import pandas as pd

# Set matplotlib cache directory before importing matplotlib
os.environ['MPLCONFIGDIR'] = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', 'mpl_cache')
os.makedirs(os.environ['MPLCONFIGDIR'], exist_ok=True)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score, confusion_matrix,
    roc_curve, precision_recall_curve
)

from ml.generate_synthetic_data import generate_transactions
from ml.preprocess import create_full_pipeline, NUMERICAL_FEATURES, CATEGORICAL_FEATURES

def train_and_evaluate():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dataset_path = os.path.join(base_dir, 'dataset', 'synthetic_transactions.csv')
    artifacts_dir = os.path.join(base_dir, 'ml', 'artifacts')
    os.makedirs(artifacts_dir, exist_ok=True)

    print("=== FraudGuard AI - Machine Learning Pipeline ===")
    
    # 1. Dataset Preparation
    if not os.path.exists(dataset_path):
        print("Dataset not found. Generating realistic synthetic transactions...")
        df = generate_transactions(n_samples=15000, fraud_rate=0.035, random_seed=42)
        df.to_csv(dataset_path, index=False)
    else:
        print(f"Loading existing dataset from {dataset_path}...")
        df = pd.read_csv(dataset_path)

    print(f"Dataset Shape: {df.shape}")
    fraud_counts = df['is_fraud'].value_counts()
    print(f"Legitimate (0): {fraud_counts.get(0, 0)}, Fraudulent (1): {fraud_counts.get(1, 0)}")
    print(f"Fraud prevalence: {df['is_fraud'].mean():.2%}")

    # Features and Target
    X = df.drop(columns=['is_fraud', 'transaction_ref', 'sender_account', 'receiver_account'], errors='ignore')
    y = df['is_fraud'].values

    # 2. Stratified Train-Test Split (Prevent Data Leakage)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"Training set: {len(X_train)} samples, Test set: {len(X_test)} samples")

    # 3. Model Candidates
    models = {
        'Logistic Regression': LogisticRegression(
            class_weight='balanced', max_iter=1000, random_state=42
        ),
        'Random Forest': RandomForestClassifier(
            n_estimators=120, max_depth=12, min_samples_split=4,
            class_weight='balanced', random_state=42, n_jobs=-1
        ),
        'Gradient Boosting': GradientBoostingClassifier(
            n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42
        )
    }

    results = {}
    fitted_pipelines = {}
    test_predictions = {}
    test_probabilities = {}

    for name, clf in models.items():
        print(f"\nTraining {name} with complete preprocessing pipeline...")
        pipeline = create_full_pipeline(clf)
        pipeline.fit(X_train, y_train)

        # Predictions & Probabilities on un-oversampled test set
        y_pred = pipeline.predict(X_test)
        if hasattr(pipeline, "predict_proba"):
            y_prob = pipeline.predict_proba(X_test)[:, 1]
        else:
            y_prob = y_pred.astype(float)

        fitted_pipelines[name] = pipeline
        test_predictions[name] = y_pred
        test_probabilities[name] = y_prob

        # Evaluation Metrics
        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        roc_auc = roc_auc_score(y_test, y_prob)
        pr_auc = average_precision_score(y_test, y_prob)
        cm = confusion_matrix(y_test, y_pred)

        results[name] = {
            'accuracy': float(acc),
            'precision': float(prec),
            'recall': float(rec),
            'f1_score': float(f1),
            'roc_auc': float(roc_auc),
            'pr_auc': float(pr_auc),
            'confusion_matrix': cm.tolist()
        }

        print(f"[{name}] Results:")
        print(f"  Accuracy:  {acc:.4f}")
        print(f"  Precision: {prec:.4f}")
        print(f"  Recall:    {rec:.4f}")
        print(f"  F1-Score:  {f1:.4f}")
        print(f"  ROC-AUC:   {roc_auc:.4f}")
        print(f"  PR-AUC:    {pr_auc:.4f}")
        print(f"  Confusion Matrix: TN={cm[0,0]}, FP={cm[0,1]}, FN={cm[1,0]}, TP={cm[1,1]}")

    # 4. Model Selection (Prioritize Random Forest for non-linear interactions if scores are competitive)
    if 'Random Forest' in results and results['Random Forest']['f1_score'] >= results['Logistic Regression']['f1_score'] - 0.01:
        best_name = 'Random Forest'
    else:
        best_name = max(results, key=lambda k: (results[k]['f1_score'], results[k]['pr_auc']))

    print(f"\n>>> Selected Best Model: {best_name} (F1-Score: {results[best_name]['f1_score']:.4f}) <<<")
    best_pipeline = fitted_pipelines[best_name]

    # 5. Extract Feature Importance for Explainability
    feature_importances = {}
    preprocessor = best_pipeline.named_steps['preprocessor']
    classifier = best_pipeline.named_steps['classifier']

    try:
        # Get onehot categorical feature names
        cat_encoder = preprocessor.named_transformers_['cat'].named_steps['onehot']
        cat_feature_names = list(cat_encoder.get_feature_names_out(CATEGORICAL_FEATURES))
        all_feature_names = NUMERICAL_FEATURES + cat_feature_names

        if hasattr(classifier, 'feature_importances_'):
            importances = classifier.feature_importances_
            feature_importances = dict(zip(all_feature_names, [float(x) for x in importances]))
        elif hasattr(classifier, 'coef_'):
            importances = np.abs(classifier.coef_[0])
            feature_importances = dict(zip(all_feature_names, [float(x) for x in importances]))
    except Exception as e:
        print(f"Notice: Feature importance extraction warning: {e}")

    # Sort feature importances
    sorted_importances = sorted(feature_importances.items(), key=lambda x: x[1], reverse=True)

    # 6. Save Evaluation Plots
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')

    # A. Confusion Matrix Plot
    fig, ax = plt.subplots(figsize=(6, 5))
    cm = np.array(results[best_name]['confusion_matrix'])
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', cbar=False,
                xticklabels=['Legitimate', 'Fraudulent'],
                yticklabels=['Legitimate', 'Fraudulent'], ax=ax)
    ax.set_title(f'Confusion Matrix - {best_name}', fontsize=13, fontweight='bold', pad=12)
    ax.set_ylabel('True Label', fontsize=11)
    ax.set_xlabel('Predicted Label', fontsize=11)
    plt.tight_layout()
    plt.savefig(os.path.join(artifacts_dir, 'confusion_matrix.png'), dpi=200)
    plt.close()

    # B. ROC Curve Plot
    fig, ax = plt.subplots(figsize=(7, 5))
    for name in models:
        fpr, tpr, _ = roc_curve(y_test, test_probabilities[name])
        ax.plot(fpr, tpr, label=f"{name} (AUC = {results[name]['roc_auc']:.3f})", lw=2)
    ax.plot([0, 1], [0, 1], 'k--', lw=1, alpha=0.6)
    ax.set_xlabel('False Positive Rate', fontsize=11)
    ax.set_ylabel('True Positive Rate (Recall)', fontsize=11)
    ax.set_title('Receiver Operating Characteristic (ROC) Comparison', fontsize=13, fontweight='bold')
    ax.legend(loc='lower right', frameon=True)
    plt.tight_layout()
    plt.savefig(os.path.join(artifacts_dir, 'roc_curve.png'), dpi=200)
    plt.close()

    # C. Precision-Recall Curve Plot
    fig, ax = plt.subplots(figsize=(7, 5))
    for name in models:
        prec_curve, rec_curve, _ = precision_recall_curve(y_test, test_probabilities[name])
        ax.plot(rec_curve, prec_curve, label=f"{name} (PR-AUC = {results[name]['pr_auc']:.3f})", lw=2)
    ax.set_xlabel('Recall (Fraud Detection Rate)', fontsize=11)
    ax.set_ylabel('Precision', fontsize=11)
    ax.set_title('Precision-Recall Curves (Imbalanced Evaluation)', fontsize=13, fontweight='bold')
    ax.legend(loc='lower left', frameon=True)
    plt.tight_layout()
    plt.savefig(os.path.join(artifacts_dir, 'pr_curve.png'), dpi=200)
    plt.close()

    # D. Top Feature Importances Plot
    if sorted_importances:
        top_k = sorted_importances[:12]
        fig, ax = plt.subplots(figsize=(8, 6))
        feat_labels = [item[0] for item in reversed(top_k)]
        feat_values = [item[1] for item in reversed(top_k)]
        bars = ax.barh(feat_labels, feat_values, color='#1e3c72')
        ax.set_title(f'Top Contributing Risk Factors ({best_name})', fontsize=13, fontweight='bold')
        ax.set_xlabel('Relative Feature Importance / Contribution', fontsize=11)
        plt.tight_layout()
        plt.savefig(os.path.join(artifacts_dir, 'feature_importance.png'), dpi=200)
        plt.close()

    # 7. Persist Artifacts with Joblib
    pipeline_file = os.path.join(artifacts_dir, 'pipeline.joblib')
    joblib.dump(best_pipeline, pipeline_file)
    print(f"Trained pipeline persisted to: {pipeline_file}")

    metadata = {
        'selected_model': best_name,
        'model_version': '1.0.0',
        'dataset': 'PaySim-style Synthetic Benchmark (15,000 transactions)',
        'all_models_evaluation': results,
        'selected_metrics': results[best_name],
        'thresholds': {
            'low_risk_ceiling': 0.30,
            'high_risk_floor': 0.70
        },
        'top_features': dict(sorted_importances[:15])
    }

    with open(os.path.join(artifacts_dir, 'model_metadata.json'), 'w') as f:
        json.dump(metadata, f, indent=2)

    with open(os.path.join(artifacts_dir, 'feature_importance.json'), 'w') as f:
        json.dump(dict(sorted_importances), f, indent=2)

    print("Model metadata and feature importance successfully saved.")
    return metadata

if __name__ == '__main__':
    train_and_evaluate()
