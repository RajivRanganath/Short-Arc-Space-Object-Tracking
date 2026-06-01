import numpy as np
from src.constants import MU, get_logger
from typing import Dict, Optional, Tuple

logger = get_logger("TLECatalog")

class TLECatalog:
    """
    Simulates correlation against a TLE catalog like CelesTrak.
    Given a state vector (r, v), it calculates the mean Keplerian elements
    and compares them to known objects in the database.
    """
    def __init__(self):
        self.mu = MU
        # For demonstration, a static dictionary of known objects (ID -> elements)
        # Elements: [a (km), e, i (rad), RAAN (rad), arg_per (rad)]
        self.catalog: Dict[int, Dict[str, float]] = {
            25544: {"name": "ISS", "a": 6790.0, "e": 0.0005, "i": np.deg2rad(51.6), "raan": np.deg2rad(150.0)},
            48274: {"name": "CSS (Tiangong)", "a": 6760.0, "e": 0.0002, "i": np.deg2rad(41.5), "raan": np.deg2rad(200.0)},
            # Add some dummy debris candidates that might match test scenarios
            99991: {"name": "Debris Alpha", "a": 7128.0, "e": 0.01, "i": np.deg2rad(98.0), "raan": np.deg2rad(10.0)},
        }

    def correlate_track(self, r_vec: np.ndarray, v_vec: np.ndarray) -> Optional[Tuple[int, str, float]]:
        """
        Calculates the mean orbital elements and compares against the catalog.
        Returns the (object_id, name, confidence) of the best match, or None.
        """
        try:
            r_mag = np.linalg.norm(r_vec)
            v_mag = np.linalg.norm(v_vec)

            # Specific energy
            energy = 0.5 * v_mag**2 - self.mu / r_mag
            if energy >= 0:
                return None  # Unbound orbit

            # Semi-major axis
            a = -self.mu / (2.0 * energy)

            # Eccentricity
            h_vec = np.cross(r_vec, v_vec)
            h_mag = np.linalg.norm(h_vec)
            e_sq = 1.0 - (h_mag**2) / (self.mu * a)
            e = np.sqrt(max(0.0, e_sq))

            # Inclination
            i = np.arccos(h_vec[2] / h_mag)

            NODE_vec = np.cross(np.array([0, 0, 1]), h_vec)
            NODE_mag = np.linalg.norm(NODE_vec)
            if NODE_mag < 1e-6:
                raan = 0.0
            else:
                raan = np.arccos(NODE_vec[0] / NODE_mag)
                if NODE_vec[1] < 0:
                    raan = 2 * np.pi - raan

            best_match = None
            best_score = float('inf')

            # Tolerances for matching
            TOL_A = 20.0       # km
            TOL_E = 0.005      # unitless
            TOL_I = np.deg2rad(2.0) # radians
            TOL_RAAN = np.deg2rad(5.0) # radians

            for obj_id, data in self.catalog.items():
                da = abs(a - data["a"])
                de = abs(e - data["e"])
                di = abs(i - data["i"])
                
                # RAAN difference wrapping at 2pi
                draan = abs(raan - data["raan"])
                if draan > np.pi:
                    draan = 2 * np.pi - draan

                if da < TOL_A and de < TOL_E and di < TOL_I and draan < TOL_RAAN:
                    # Simple distance/score metric
                    score = (da / TOL_A) + (de / TOL_E) + (di / TOL_I) + (draan / TOL_RAAN)
                    if score < best_score:
                        best_score = score
                        # Confidence metric [0, 1]
                        confidence = max(0.0, 1.0 - (score / 4.0))
                        best_match = (obj_id, data["name"], confidence)

            return best_match
            
        except Exception as e:
            logger.debug(f"Failed to correlate to catalog: {e}")
            return None
