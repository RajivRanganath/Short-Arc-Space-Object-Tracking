import numpy as np

class RobustIOD:
    def __init__(self, mu=398600.4418, r_earth=6378.137):
        self.mu = mu
        self.r_earth = r_earth

    def solve(self, obs1, obs2, obs3):
        return self.estimate_state([obs1, obs2, obs3])

    def estimate_state(self, observations):
        """
        Initialize orbit state (position, velocity) using angular rate 
        and physical LEO constraints over a short arc of observations.
        """
        if len(observations) < 2:
            raise ValueError("Need at least 2 observations to estimate angular rate.")

        obs_start = observations[0]
        obs_end = observations[-1]
        dt_total = obs_end['time'] - obs_start['time']

        if dt_total <= 0:
             # Fallback if timestamps are identical
             dt_total = 1.0

        # Line-of-sight unit vectors
        L_start = self._radec_to_vector(obs_start['ra'], obs_start['dec'])
        L_end = self._radec_to_vector(obs_end['ra'], obs_end['dec'])

        # Angular separation calculation
        cos_angle = np.dot(L_start, L_end)
        angle_sep = np.arccos(np.clip(cos_angle, -1.0, 1.0))
        angular_rate = angle_sep / dt_total  # rad/s

        # Use middle observation for the base position estimate
        mid_idx = len(observations) // 2
        obs_mid = observations[mid_idx]
        site_pos = np.array(obs_mid.get('site_eci', obs_mid.get('site_ecef', [0,0,0])))
        L_mid = self._radec_to_vector(obs_mid['ra'], obs_mid['dec'])

        # --- Estimate range based on typical LEO kinetics ---
        # For LEO, velocity is typically ~7.5 km/s. 
        # Angular rate ~ velocity_perpendicular / range.
        # Assuming most velocity is perpendicular near culmination:
        if angular_rate > 1e-6:
            estimated_range = 7.5 / angular_rate  # km
            # Constrain to a plausible LEO radar detection envelope
            estimated_range = np.clip(estimated_range, 400.0, 3000.0)
        else:
            estimated_range = 1000.0  # Safe fallback for very slow angular rates

        # --- Determine Initial Position ---
        r_init = site_pos + estimated_range * L_mid
        r_mag = np.linalg.norm(r_init)
        altitude = r_mag - self.r_earth

        # Enforce physical constraints: must be in space
        if altitude < 150.0:
            # Rescale the position vector along the line-of-sight to reach a minimum viable altitude
            # The exact math to solve |R_site + rho * L| = R_earth + h is a quadratic, 
            # but for a quick robust proxy we just push the state up.
            r_init = r_init / r_mag * (self.r_earth + 500.0)
            r_mag = np.linalg.norm(r_init)

        # --- Determine Initial Velocity ---
        # Assume nearly circular orbit: v = sqrt(mu / r)
        v_circular = np.sqrt(self.mu / r_mag)

        r_normalized = r_init / r_mag
        
        # Determine the orbital plane roughly by crossing r with Z-axis
        # This implies a prograde, eastward orbit.
        h_dir = np.cross(r_normalized, np.array([0.0, 0.0, 1.0]))
        
        # Handle near-polar singularity
        if np.linalg.norm(h_dir) < 0.1:
            h_dir = np.cross(r_normalized, np.array([1.0, 0.0, 0.0]))
            
        h_dir = h_dir / np.linalg.norm(h_dir)
        v_dir = np.cross(h_dir, r_normalized)
        
        v_init = v_dir * v_circular

        return np.concatenate([r_init, v_init])

    def _radec_to_vector(self, ra, dec):
        return np.array([
            np.cos(dec) * np.cos(ra),
            np.cos(dec) * np.sin(ra),
            np.sin(dec)
        ])
