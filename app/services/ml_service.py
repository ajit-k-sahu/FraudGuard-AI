"""
ML Service for FraudGuard AI.
Loads trained scikit-learn pipeline, model metadata, and feature importances.
"""

import os
import json
import joblib
import threading

class MLService:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.pipeline = None
        self.metadata = None
        self.feature_importance = None
        self.artifacts_dir = None
        self._load_artifacts()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _load_artifacts(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.artifacts_dir = os.path.join(base_dir, 'ml', 'artifacts')
        
        pipeline_path = os.path.join(self.artifacts_dir, 'pipeline.joblib')
        metadata_path = os.path.join(self.artifacts_dir, 'model_metadata.json')
        importance_path = os.path.join(self.artifacts_dir, 'feature_importance.json')

        # Load pipeline
        if os.path.exists(pipeline_path):
            try:
                self.pipeline = joblib.load(pipeline_path)
            except Exception as e:
                print(f"[MLService] Error loading pipeline: {e}")
                self.pipeline = None
        else:
            print(f"[MLService] Pipeline artifact not found at {pipeline_path}")

        # Load metadata
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r') as f:
                    self.metadata = json.load(f)
            except Exception as e:
                print(f"[MLService] Error loading metadata: {e}")
                self.metadata = {}
        else:
            self.metadata = {
                'selected_model': 'Random Forest',
                'model_version': '1.0.0',
                'thresholds': {'low_risk_ceiling': 0.30, 'high_risk_floor': 0.70}
            }

        # Load feature importance
        if os.path.exists(importance_path):
            try:
                with open(importance_path, 'r') as f:
                    self.feature_importance = json.load(f)
            except Exception as e:
                print(f"[MLService] Error loading feature importance: {e}")
                self.feature_importance = {}
        else:
            self.feature_importance = {}

    def is_ready(self):
        return self.pipeline is not None

    def get_metadata(self):
        return self.metadata

    def get_feature_importances(self):
        return self.feature_importance
