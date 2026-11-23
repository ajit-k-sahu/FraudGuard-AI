"""
Standalone Evaluation & Inspection Tool for FraudGuard AI ML Models.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import joblib
import pandas as pd

def print_model_report():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    metadata_path = os.path.join(base_dir, 'ml', 'artifacts', 'model_metadata.json')
    
    if not os.path.exists(metadata_path):
        print("Model metadata not found. Please train the model first by running `python ml/train_model.py`.")
        return

    with open(metadata_path, 'r') as f:
        meta = json.load(f)

    print("\n" + "="*50)
    print("      FRAUDGUARD AI - MODEL PERFORMANCE REPORT")
    print("="*50)
    print(f"Active Model:    {meta['selected_model']} (v{meta['model_version']})")
    print(f"Dataset:         {meta['dataset']}")
    print(f"Evaluation Metrics:")
    metrics = meta['selected_metrics']
    print(f"  - Accuracy:     {metrics['accuracy']:.2%}")
    print(f"  - Precision:    {metrics['precision']:.2%}")
    print(f"  - Recall:       {metrics['recall']:.2%}")
    print(f"  - F1-Score:     {metrics['f1_score']:.4f}")
    print(f"  - ROC-AUC:      {metrics['roc_auc']:.4f}")
    print(f"  - PR-AUC:       {metrics['pr_auc']:.4f}")
    
    cm = metrics['confusion_matrix']
    print(f"\nConfusion Matrix:")
    print(f"  True Negatives (Legit correct):   {cm[0][0]}")
    print(f"  False Positives (False alarms):   {cm[0][1]}")
    print(f"  False Negatives (Missed fraud):   {cm[1][0]}")
    print(f"  True Positives (Fraud detected):  {cm[1][1]}")

    print("\nModel Risk Stratification Thresholds:")
    print(f"  Low Risk:     < {meta['thresholds']['low_risk_ceiling'] * 100:.0f}% probability")
    print(f"  Medium Risk:  {meta['thresholds']['low_risk_ceiling'] * 100:.0f}% to {meta['thresholds']['high_risk_floor'] * 100:.0f}% probability")
    print(f"  High Risk:    >= {meta['thresholds']['high_risk_floor'] * 100:.0f}% probability")

    print("\nTop Contributing Predictive Features:")
    for i, (feat, score) in enumerate(list(meta.get('top_features', {}).items())[:8], 1):
        print(f"  {i}. {feat:<28} (Importance: {score:.4f})")
    print("="*50 + "\n")

if __name__ == '__main__':
    print_model_report()
