import numpy as np

class FilterAnomalyDetector:
    def __init__(self, threshold_sigmas=8.0, window_size=7):
        self.threshold = threshold_sigmas
        self.window_size = window_size
        self.residuals_history = []
        
    def check_for_anomaly(self, innovation, innovation_covariance):
        """
        Checks if the filter is diverging based on the latest measurement deviating significantly from the prediction.
        """
        try:
            inv_S = np.linalg.inv(innovation_covariance)
            nis = float(innovation.T @ inv_S @ innovation)
        except np.linalg.LinAlgError:
            return False

        self.residuals_history.append(nis)
        
        # Keep rolling window
        if len(self.residuals_history) > self.window_size:
            self.residuals_history.pop(0)
            
        # 1. IMMEDIATE DETECTION of massive jumps (e.g. 5x squared threshold)
        if nis > (self.threshold ** 2) * 5.0:
            self.residuals_history = [] # Reset on detection to avoid double alarm
            return True

        # 2. Windowed detection for sustained smaller deviations
        if len(self.residuals_history) == self.window_size:
            avg_nis = np.mean(self.residuals_history)
            
            if avg_nis > self.threshold ** 2:
                self.residuals_history = []
                return True
                
        return False

class ManeuverSizer:
    """
    Estimates the velocity impulse (Delta V) required to nullify the filter innovation.
    Uses the sensitivity of the measurement to a velocity change at the previous step.
    """
    def __init__(self):
        pass

    def estimate_delta_v(self, innovation, innovation_covariance, mean_state, site_pos, dt):
        """
        Maps the measurement-space error (innovation) back to a velocity-space impulse.
        """
        if dt <= 0:
            return np.zeros(3)

        # 1. Compute H_pos (Jacobian of measurement w.r.t. position)
        r_eci = mean_state[:3]
        rho_vec = r_eci - site_pos
        rho_mag = np.linalg.norm(rho_vec)
        
        if rho_mag < 1e-3:
            return np.zeros(3)

        x, y, z = rho_vec
        rho_xy_sq = x**2 + y**2
        rho_sq = rho_mag**2

        # Singularity guard for pole crossings
        if rho_xy_sq < 1e-6:
            rho_xy_sq = 1e-6

        if len(innovation) == 3: # RA, Dec, Range
            H_pos = np.zeros((3, 3))
            H_pos[0, 0] = -y / rho_xy_sq
            H_pos[0, 1] = x / rho_xy_sq
            H_pos[1, 0] = -(x * z) / (rho_sq * np.sqrt(rho_xy_sq))
            H_pos[1, 1] = -(y * z) / (rho_sq * np.sqrt(rho_xy_sq))
            H_pos[1, 2] = np.sqrt(rho_xy_sq) / rho_sq
            H_pos[2, :] = rho_vec / rho_mag
        else: # RA, Dec only
            H_pos = np.zeros((2, 3))
            H_pos[0, 0] = -y / rho_xy_sq
            H_pos[0, 1] = x / rho_xy_sq
            H_pos[1, 0] = -(x * z) / (rho_sq * np.sqrt(rho_xy_sq))
            H_pos[1, 1] = -(y * z) / (rho_sq * np.sqrt(rho_xy_sq))
            H_pos[1, 2] = np.sqrt(rho_xy_sq) / rho_sq

        G = dt * H_pos
        
        try:
            delta_v_estimate = np.linalg.pinv(G) @ innovation
            
            # Sanity cap
            mag = np.linalg.norm(delta_v_estimate)
            if mag > 0.5: 
                delta_v_estimate = (delta_v_estimate / mag) * 0.5
                
            return delta_v_estimate
        except np.linalg.LinAlgError:
            return np.zeros(3)
