import numpy as np
from scipy.optimize import linear_sum_assignment

class GlobalNearestNeighbor:
    def __init__(self, gate_threshold=20.0):
        # 16.27 is the Chi-squared limit for 99.9% confidence (3 Degrees of Freedom)
        # Upgraded from 9.21 to accommodate 3D measurements (RA, Dec, Range).
        self.gate_threshold = gate_threshold

    def associate(self, tracks, measurements):
        """
        Assigns measurements to tracks using the Hungarian Algorithm.
        
        Args:
            tracks: List of Track objects
            measurements: List of Measurement objects
            
        Returns:
            assignments: List of (track_index, measurement_index) tuples
            unassigned_tracks: List of track indices
            unassigned_measurements: List of measurement indices
        """
        n_tracks = len(tracks)
        n_meas = len(measurements)
        
        if n_tracks == 0 or n_meas == 0:
            return [], list(range(n_tracks)), list(range(n_meas))
            
        # 1. Compute Cost Matrix (Mahalanobis Distance)
        # Shape: (n_tracks, n_measurements)
        cost_matrix = np.zeros((n_tracks, n_meas))
        
        for t_idx, track in enumerate(tracks):
            for m_idx, meas in enumerate(measurements):
                dist = self._compute_ensemble_distance(track, meas)
                cost_matrix[t_idx, m_idx] = dist
                
        # 2. Gating (Filter out impossible matches)
        # We set the cost to infinity for impossible matches
        valid_mask = cost_matrix < self.gate_threshold
        cost_matrix[~valid_mask] = 1e9  # Huge cost
        
        # 3. Solve Assignment Problem (Hungarian Algorithm)
        # This finds the combination that minimizes the total cost
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        
        # 4. Filter Assignments
        assignments = []
        unassigned_tracks = set(range(n_tracks))
        unassigned_meas = set(range(n_meas))
        
        for r, c in zip(row_ind, col_ind):
            if cost_matrix[r, c] < self.gate_threshold:
                assignments.append((r, c))
                unassigned_tracks.discard(r)
                unassigned_meas.discard(c)
                
        return assignments, list(unassigned_tracks), list(unassigned_meas)

    def _compute_ensemble_distance(self, track, measurement):
        """
        Computes Mahalanobis distance using the EnKF particle cloud.
        Automatically adapts to 2D (RA/Dec) or 3D (RA/Dec/Range) measurements.
        """
        # 1. Get predicted measurement from particles
        particles = track.particles
        site_pos = measurement.radar_site_eci
        
        # Check if the measurement includes valid range data
        has_range = (hasattr(measurement, 'range_km') and measurement.range_km > 0)
        
        z_preds = []
        for p in particles:
            rho = p[:3] - site_pos
            dist = np.linalg.norm(rho)
            ra = np.arctan2(rho[1], rho[0])
            # Clip handles floating point errors slightly over 1.0 or under -1.0
            dec = np.arcsin(np.clip(rho[2] / dist, -1.0, 1.0))
            
            if has_range:
                z_preds.append([ra, dec, dist])
            else:
                z_preds.append([ra, dec])
                
        z_preds = np.array(z_preds)
        
        # 2. Calculate Innovation Covariance (S) directly from particles
        z_mean = np.mean(z_preds, axis=0)
        z_dev = z_preds - z_mean
        P_zz = (z_dev.T @ z_dev) / (len(particles) - 1)
        
        # Add Measurement Noise (R)
        if has_range:
            # 3D Measurement Noise Matrix (R)
            R = np.diag([
                np.deg2rad(0.05)**2,  # RA noise (variance in rad^2)
                np.deg2rad(0.05)**2,  # Dec noise (variance in rad^2)
                5.0**2                # Range noise (variance in km^2)
            ])
            z_actual = np.array([measurement.ra_rad, measurement.dec_rad, measurement.range_km])
        else:
            # 2D Measurement Noise Matrix (R)
            # Fall back to object noise matrix if it exists, otherwise default
            if hasattr(measurement, 'noise_matrix') and measurement.noise_matrix is not None:
                R = measurement.noise_matrix
            else:
                R = np.diag([np.deg2rad(0.05)**2, np.deg2rad(0.05)**2])
            z_actual = np.array([measurement.ra_rad, measurement.dec_rad])
            
        S = P_zz + R
        
        # 3. Calculate Distance
        # Innovation (Residual)
        innovation = z_actual - z_mean
        
        # Handle Angle Wrap (Essential!)
        innovation[0] = (innovation[0] + np.pi) % (2 * np.pi) - np.pi
        
        # Mahalanobis Distance formula
        try:
            inv_S = np.linalg.inv(S)
            dist = float(innovation.T @ inv_S @ innovation)
            return dist
        except np.linalg.LinAlgError:
            return 1e9 # Singular matrix fallback