import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib
import os
from src.orbital_mechanics.kepler_utils import cartesian_to_keplerian
from src.constants import RE_KM

class OrbitalRegimeClassifier:
    """
    ML Classifier for Orbital Regimes (LEO, MEO, GEO, HEO, GTO).
    Combines a Random Forest model with physics-based expert rules.
    """
    REGIMES = ["LEO", "MEO", "GEO", "HEO", "GTO"]
    
    def __init__(self, model_path=None):
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.is_trained = False
        self.model_path = model_path
        
        if model_path and os.path.exists(model_path):
            self.model = joblib.load(model_path)
            self.is_trained = True
        else:
            # Auto-train a baseline model if no model exists
            self._train_baseline()

    def _extract_features(self, r_vec, v_vec):
        """Extract features for classification."""
        a, e, i, _, _, _ = cartesian_to_keplerian(r_vec, v_vec)
        
        # Derived features
        r_p = a * (1 - e) - RE_KM # Perigee altitude
        r_a = a * (1 + e) - RE_KM # Apogee altitude
        
        return np.array([a, e, np.rad2deg(i), r_p, r_a])

    def _train_baseline(self):
        """Train a baseline model on synthetic 'ideal' regimes."""
        X_train = []
        y_train = []
        
        # Synthetic LEO: a in [6500, 8000], e < 0.1, i in [0, 100]
        for _ in range(100):
            a = 6378 + np.random.uniform(200, 1500)
            e = np.random.uniform(0, 0.05)
            i = np.random.uniform(0, np.pi)
            r_p = a*(1-e) - RE_KM
            r_a = a*(1+e) - RE_KM
            X_train.append([a, e, np.rad2deg(i), r_p, r_a])
            y_train.append(0) # LEO

        # Synthetic MEO: a in [10000, 30000], e < 0.1
        for _ in range(100):
            a = 6378 + np.random.uniform(2000, 30000)
            e = np.random.uniform(0, 0.1)
            i = np.random.uniform(0, np.pi/3)
            r_p = a*(1-e) - RE_KM
            r_a = a*(1+e) - RE_KM
            X_train.append([a, e, np.rad2deg(i), r_p, r_a])
            y_train.append(1) # MEO

        # Synthetic GEO: a ~ 42164, e < 0.01, i < 15
        for _ in range(100):
            a = 42164 + np.random.normal(0, 50)
            e = np.random.uniform(0, 0.01)
            i = np.random.uniform(0, np.deg2rad(15))
            r_p = a*(1-e) - RE_KM
            r_a = a*(1+e) - RE_KM
            X_train.append([a, e, np.rad2deg(i), r_p, r_a])
            y_train.append(2) # GEO

        # Synthetic HEO: e > 0.5
        for _ in range(100):
            a = 26000 + np.random.normal(0, 2000)
            e = np.random.uniform(0.6, 0.8)
            i = np.random.uniform(np.deg2rad(60), np.deg2rad(65))
            r_p = a*(1-e) - RE_KM
            r_a = a*(1+e) - RE_KM
            X_train.append([a, e, np.rad2deg(i), r_p, r_a])
            y_train.append(3) # HEO

        # Synthetic GTO: r_p ~ LEO, r_a ~ GEO
        for _ in range(100):
            r_p_alt = np.random.uniform(200, 600)
            r_a_alt = 35786 + np.random.normal(0, 500)
            a = (r_p_alt + r_a_alt + 2*RE_KM) / 2
            e = (r_a_alt - r_p_alt) / (r_a_alt + r_p_alt + 2*RE_KM)
            i = np.random.uniform(0, np.deg2rad(30))
            X_train.append([a, e, np.rad2deg(i), r_p_alt, r_a_alt])
            y_train.append(4) # GTO

        self.model.fit(X_train, y_train)
        self.is_trained = True

    def predict(self, r_vec, v_vec):
        """
        Predict orbital regime with physics-aware validation.
        """
        feats = self._extract_features(r_vec, v_vec)
        a, e, i_deg, r_p_alt, r_a_alt = feats
        
        # 1. ML Prediction
        probs = self.model.predict_proba([feats])[0]
        ml_idx = np.argmax(probs)
        conf = probs[ml_idx]
        regime = self.REGIMES[ml_idx]

        # 2. Physics-based Verification (Brutal Honesty)
        # We override ML if it violates hard physical boundaries
        if r_p_alt < 150:
            regime = "RE-ENTRY / SUB-ORBITAL"
        elif r_a_alt < 2000 and e < 0.2:
            regime = "LEO"
        elif 35000 < r_p_alt < 36500 and e < 0.05 and i_deg < 25:
            regime = "GEO"
        elif e > 0.5 and r_p_alt < 2000 and r_a_alt > 30000:
            regime = "GTO/HEO" # Ambiguous but high-eccentricity
        
        return {
            "regime": regime,
            "confidence": conf,
            "parameters": {
                "sma_km": a,
                "eccentricity": e,
                "inclination_deg": i_deg,
                "perigee_alt_km": r_p_alt,
                "apogee_alt_km": r_a_alt
            }
        }
