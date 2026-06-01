import numpy as np
from scipy.integrate import solve_ivp
from datetime import timedelta
from src.orbital_mechanics.perturbations import PerturbationEngine

class OrbitPropagator:
    def __init__(self):
        self.physics = PerturbationEngine()
        
    def propagate_state(self, initial_state, start_time, duration_hours):
        """
        Predicts the position of a satellite N hours into the future.
        """
        # Convert hours to seconds
        dt_seconds = duration_hours * 3600.0
        
        # Define the physics function (same as your Filter, but deterministic)
        def dynamics(t, y):
            r_vec = y[:3]
            v_vec = y[3:]
            
            # 1. Keplerian Gravity
            r_norm = np.linalg.norm(r_vec)
            acc_kepler = -self.physics.mu / (r_norm**3) * r_vec
            
            # 2. J2 Perturbation
            acc_j2 = self.physics.compute_j2_acceleration(r_vec)
            
            # 3. Atmospheric Drag (Assume standard mass/area for prediction)
            acc_drag = self.physics.compute_drag_acceleration(r_vec, v_vec)
            
            # 4. Solar Radiation Pressure (SRP)
            acc_srp = self.physics.compute_srp_acceleration(r_vec)
            
            return np.concatenate((v_vec, acc_kepler + acc_j2 + acc_drag + acc_srp))
            
        # Integrate!
        # We use a high-precision method (DOP853) for long-term predictions
        sol = solve_ivp(dynamics, [0, dt_seconds], initial_state, method='DOP853', rtol=1e-9)
        
        final_state = sol.y[:, -1]
        final_time = start_time + timedelta(seconds=dt_seconds)
        
        return final_state, final_time
