"""
ML Congestion Predictor
========================
Random Forest-based model that predicts transmission line congestion scores.
Provides training, evaluation, prediction, and feature importance analysis.
"""

import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib

from config import (
    ML_CONFIG, FEATURE_NAMES, TARGET_NAME,
    MODEL_DIR, DATA_DIR, RANDOM_SEED
)


class CongestionPredictor:
    """
    Random Forest model for predicting transmission line congestion.

    The model takes grid features (time, weather, load, infrastructure)
    and outputs a congestion score between 0.0 (no congestion) and 1.0 (critical).
    """

    def __init__(self):
        self.model = None
        self.feature_names = FEATURE_NAMES
        self.is_trained = False
        self.metrics = {}
        self.feature_importances = {}
        self._model_path = os.path.join(MODEL_DIR, "congestion_rf_model.joblib")

    def train(self, df: pd.DataFrame = None) -> dict:
        """
        Train the Random Forest model.

        Parameters
        ----------
        df : pd.DataFrame, optional
            Training data. If None, loads from CSV.

        Returns
        -------
        dict
            Training metrics (MSE, MAE, R²).
        """
        if df is None:
            filepath = os.path.join(DATA_DIR, "grid_data.csv")
            df = pd.read_csv(filepath)

        print("\n🤖 Training Random Forest Congestion Predictor...")
        print(f"   Dataset: {len(df)} samples, {len(self.feature_names)} features")

        # Prepare data
        X = df[self.feature_names].values
        y = df[TARGET_NAME].values

        # Train-test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=ML_CONFIG["test_size"],
            random_state=RANDOM_SEED
        )

        # Initialize and train model
        self.model = RandomForestRegressor(
            n_estimators=ML_CONFIG["n_estimators"],
            max_depth=ML_CONFIG["max_depth"],
            min_samples_split=ML_CONFIG["min_samples_split"],
            min_samples_leaf=ML_CONFIG["min_samples_leaf"],
            random_state=ML_CONFIG["random_state"],
            n_jobs=-1,
        )

        self.model.fit(X_train, y_train)

        # Evaluate
        y_pred = self.model.predict(X_test)
        self.metrics = {
            "mse": mean_squared_error(y_test, y_pred),
            "rmse": np.sqrt(mean_squared_error(y_test, y_pred)),
            "mae": mean_absolute_error(y_test, y_pred),
            "r2": r2_score(y_test, y_pred),
            "train_samples": len(X_train),
            "test_samples": len(X_test),
        }

        # Feature importance
        importances = self.model.feature_importances_
        self.feature_importances = dict(zip(self.feature_names, importances))
        self.feature_importances = dict(
            sorted(self.feature_importances.items(), key=lambda x: x[1], reverse=True)
        )

        self.is_trained = True

        # Print results
        self._print_metrics()

        return self.metrics

    def _print_metrics(self):
        """Print formatted training metrics."""
        print(f"\n   📊 Model Performance:")
        print(f"      ┌─────────────────────────────────┐")
        print(f"      │ MSE:   {self.metrics['mse']:.6f}              │")
        print(f"      │ RMSE:  {self.metrics['rmse']:.6f}              │")
        print(f"      │ MAE:   {self.metrics['mae']:.6f}              │")
        print(f"      │ R²:    {self.metrics['r2']:.6f}              │")
        print(f"      └─────────────────────────────────┘")
        print(f"\n   🔑 Feature Importances:")
        for feat, imp in self.feature_importances.items():
            bar = "█" * int(imp * 50)
            print(f"      {feat:20s} {imp:.4f} {bar}")

    def predict_congestion(self, features: dict) -> float:
        """
        Predict congestion score for a single transmission line.

        Parameters
        ----------
        features : dict
            Dictionary with keys matching FEATURE_NAMES.

        Returns
        -------
        float
            Predicted congestion score (0.0 to 1.0).
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")

        # Build feature vector in correct order
        feature_vector = np.array([
            features.get(name, 0.0) for name in self.feature_names
        ]).reshape(1, -1)

        prediction = self.model.predict(feature_vector)[0]
        return float(np.clip(prediction, 0.0, 1.0))

    def predict_batch(self, features_df: pd.DataFrame) -> np.ndarray:
        """
        Predict congestion for multiple transmission lines.

        Parameters
        ----------
        features_df : pd.DataFrame
            DataFrame with columns matching FEATURE_NAMES.

        Returns
        -------
        np.ndarray
            Array of predicted congestion scores.
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")

        X = features_df[self.feature_names].values
        predictions = self.model.predict(X)
        return np.clip(predictions, 0.0, 1.0)

    def save_model(self):
        """Save trained model to disk."""
        if not self.is_trained:
            raise RuntimeError("No trained model to save.")
        joblib.dump({
            "model": self.model,
            "metrics": self.metrics,
            "feature_importances": self.feature_importances,
        }, self._model_path)
        print(f"   💾 Model saved to {self._model_path}")

    def load_model(self) -> bool:
        """Load a previously trained model from disk."""
        if os.path.exists(self._model_path):
            data = joblib.load(self._model_path)
            self.model = data["model"]
            self.metrics = data["metrics"]
            self.feature_importances = data["feature_importances"]
            self.is_trained = True
            print(f"   📂 Model loaded from {self._model_path}")
            return True
        return False

    def get_feature_importances(self) -> dict:
        """Return feature importances as a sorted dict."""
        return self.feature_importances.copy()


if __name__ == "__main__":
    predictor = CongestionPredictor()
    predictor.train()
    predictor.save_model()

    # Test single prediction
    test_features = {
        "hour": 14.0,
        "temperature": 35.0,
        "humidity": 45.0,
        "wind_speed": 12.0,
        "solar_irradiance": 750.0,
        "historical_load": 380.0,
        "renewable_ratio": 0.25,
        "line_age_years": 30.0,
        "line_length_km": 80.0,
    }
    score = predictor.predict_congestion(test_features)
    print(f"\n🔮 Test prediction: congestion = {score:.4f}")
