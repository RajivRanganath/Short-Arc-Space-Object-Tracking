import numpy as np
from src.constants import MU, RE_KM, J2, OMEGA_EARTH, get_logger

logger = get_logger("PerturbationEngine")

class PerturbationEngine:
    def __init__(self):
        # Gravity Constants
        self.mu = MU
        self.J2 = J2
        self.Re = RE_KM
        
        # Earth rotation rate (rad/s)
        self.omega_earth = np.array(OMEGA_EARTH)
        
        # Satellite physical properties (Defaults for debris)
        self.Cd = 2.2               # Drag coefficient (approx for boxy shape)
        self.Cr = 1.2               # Reflectivity coefficient (0=absorb, 1=reflect, 2=specular)
        self.area = 1.0             # Cross-sectional area (m^2)
        self.mass = 100.0           # Mass (kg)
        
        # Solar Radiation Pressure constant Near Earth
        # P_sr ~ 4.56e-6 N/m^2 = 4.56e-6 kg*m/s^2 / m^2 = 4.56e-9 kg*km/s^2 / m^2
        self.P_sr_km = 4.56e-9

        # Segmented atmosphere model data (US Standard Atmosphere 1976 approx)
        # Tuples of (base_altitude_km, base_density_kg_m3, scale_height_km)
        self.atmosphere_bands = [
            (0,    1.225,       7.249),
            (25,   3.899e-2,   6.349),
            (30,   1.774e-2,   6.682),
            (40,   3.972e-3,   7.554),
            (50,   1.057e-3,   8.382),
            (70,   8.754e-5,   6.582),
            (100,  5.297e-7,   5.927),
            (150,  1.821e-9,   23.63),
            (200,  2.789e-10,  37.11),
            (250,  7.248e-11,  45.55),
            (300,  2.418e-11,  53.63),
            (400,  3.725e-12,  64.45),
            (500,  6.967e-13,  71.84),
            (600,  1.454e-13,  76.54),
            (700,  3.614e-14,  85.50),
            (800,  1.170e-14,  101.40),
            (900,  5.245e-15,  120.37),
            (1000, 3.019e-15,  139.14)
        ]

    def compute_j2_acceleration(self, position):
        """Computes J2 Gravity Perturbation"""
        r_vec = position
        r = np.linalg.norm(r_vec)
        x, y, z = r_vec
        
        factor = (1.5 * self.J2 * self.mu * self.Re**2) / (r**5)
        z_sq = (z / r)**2
        
        ax = factor * x * (5 * z_sq - 1)
        ay = factor * y * (5 * z_sq - 1)
        az = factor * z * (5 * z_sq - 3)
        
        return np.array([ax, ay, az])

    def compute_srp_acceleration(self, position, current_time=None):
        """
        Computes Solar Radiation Pressure (SRP) Acceleration using a cannonball model.
        Assumes Sun is roughly at +X axis for simplicity without full ephemeris.
        """
        # Simplistic Sun vector (can be improved with true ephemeris)
        r_sun_hat = np.array([1.0, 0.0, 0.0])
        
        # Simple cylindrical shadow model
        r_mag = np.linalg.norm(position)
        dot_product = np.dot(position, r_sun_hat)
        
        # If the satellite is behind the Earth (dot product < 0) 
        # and its perpendicular distance to the Sun line is less than Earth's radius, it's in shadow
        if dot_product < 0:
            perp_dist_sq = r_mag**2 - dot_product**2
            if perp_dist_sq < self.Re**2:
                return np.array([0.0, 0.0, 0.0]) # No SRP in eclipse
        
        # a_srp = - (P_sr * (1 + Cr) * A) / m * r_sun_hat
        factor = -(self.P_sr_km * (1.0 + self.Cr) * self.area) / self.mass
        
        a_srp = factor * r_sun_hat
        return a_srp

    def compute_drag_acceleration(self, position, velocity):
        """
        Computes Atmospheric Drag Acceleration using a segmented exponential 
        atmosphere model and relative velocity (accounting for Earth rotation).
        """
        r = np.linalg.norm(position)
        h = r - self.Re # Altitude in km
        
        if h < 0: h = 0 # Clamp for safety
        
        # Beyond 1500 km, drag is truly negligible
        if h > 1500:
            return np.array([0.0, 0.0, 0.0])

        # Find the correct atmosphere band
        rho0, h0, H = self.atmosphere_bands[0][1], self.atmosphere_bands[0][0], self.atmosphere_bands[0][2]
        for band_h, band_rho, band_scale in reversed(self.atmosphere_bands):
            if h >= band_h:
                h0 = band_h
                rho0 = band_rho
                H = band_scale
                break
                
        # Calculate density (kg/m^3)
        rho = rho0 * np.exp(-(h - h0) / H)
        
        # Calculate relative velocity accounting for Earth's rotation
        # v_rel = v_inertial - (omega_earth x r)
        v_atm = np.cross(self.omega_earth, position) # km/s
        v_rel = velocity - v_atm                     # km/s
        
        v_rel_m = v_rel * 1000.0 # Convert to m/s
        v_mag_m = np.linalg.norm(v_rel_m)
        
        if v_mag_m < 1e-6:
            return np.array([0.0, 0.0, 0.0])
            
        # Accel in m/s^2 = 0.5 * rho * v^2 * (Cd * A / m)
        acc_drag_mag = 0.5 * rho * (v_mag_m**2) * (self.Cd * self.area / self.mass)
        
        # Direction is opposite to relative velocity
        acc_drag_vec_m = -acc_drag_mag * (v_rel_m / v_mag_m)
        
        return acc_drag_vec_m / 1000.0 # Convert back to km/s^2

    def compute_j2_acceleration_batch(self, positions):
        """Computes J2 Gravity Perturbation for an array of positions (N, 3)"""
        r_mag = np.linalg.norm(positions, axis=1, keepdims=True)
        x = positions[:, 0:1]
        y = positions[:, 1:2]
        z = positions[:, 2:3]
        
        factor = (1.5 * self.J2 * self.mu * self.Re**2) / (r_mag**5)
        z_sq = (z / r_mag)**2
        
        ax = factor * x * (5 * z_sq - 1)
        ay = factor * y * (5 * z_sq - 1)
        az = factor * z * (5 * z_sq - 3)
        
        return np.concatenate([ax, ay, az], axis=1)

    def compute_srp_acceleration_batch(self, positions, current_time=None):
        """
        Computes Solar Radiation Pressure (SRP) for a batch of positions (N, 3).
        """
        r_sun_hat = np.array([1.0, 0.0, 0.0])
        factor = -(self.P_sr_km * (1.0 + self.Cr) * self.area) / self.mass
        
        # Base acceleration vector
        a_srp_base = factor * r_sun_hat
        a_srp = np.tile(a_srp_base, (positions.shape[0], 1))
        
        # Cylindrical shadow model (batch)
        dot_products = np.dot(positions, r_sun_hat)
        r_mag_sq = np.sum(positions**2, axis=1)
        perp_dist_sq = r_mag_sq - dot_products**2
        
        in_shadow = (dot_products < 0) & (perp_dist_sq < self.Re**2)
        
        # Zero out acceleration for particles in eclipse
        a_srp[in_shadow] = 0.0
        
        return a_srp

    def compute_drag_acceleration_batch(self, positions, velocities):
        """
        Computes Atmospheric Drag Acceleration for (N, 3) positions and velocities.
        """
        r_mag = np.linalg.norm(positions, axis=1, keepdims=True)
        h = r_mag - self.Re
        h = np.maximum(h, 0) # Clamp for safety
        
        accel = np.zeros_like(positions)
        valid_idx = (h < 1500).flatten()
        if not np.any(valid_idx):
            return accel
            
        h_valid = h[valid_idx]
        pos_valid = positions[valid_idx]
        vel_valid = velocities[valid_idx]
        
        band_h = np.array([b[0] for b in self.atmosphere_bands])
        band_rho = np.array([b[1] for b in self.atmosphere_bands])
        band_H = np.array([b[2] for b in self.atmosphere_bands])
        
        idx = np.searchsorted(band_h, h_valid.flatten(), side='right') - 1
        idx = np.clip(idx, 0, len(band_h) - 1)
        
        h0 = band_h[idx].reshape(-1, 1)
        rho0 = band_rho[idx].reshape(-1, 1)
        H = band_H[idx].reshape(-1, 1)
        
        rho = rho0 * np.exp(-(h_valid - h0) / H)
        
        v_atm = np.cross(self.omega_earth, pos_valid)
        v_rel = vel_valid - v_atm
        
        v_rel_m = v_rel * 1000.0
        v_mag_m = np.linalg.norm(v_rel_m, axis=1, keepdims=True)
        
        v_mask = (v_mag_m > 1e-6).flatten()
        if not np.any(v_mask):
            return accel
            
        rho_v = rho[v_mask]
        v_mag_m_v = v_mag_m[v_mask]
        v_rel_m_v = v_rel_m[v_mask]
        
        acc_drag_mag = 0.5 * rho_v * (v_mag_m_v**2) * (self.Cd * self.area / self.mass)
        acc_drag_vec_m = -acc_drag_mag * (v_rel_m_v / v_mag_m_v)
        
        final_idx = np.where(valid_idx)[0][v_mask]
        accel[final_idx] = acc_drag_vec_m / 1000.0
        
        return accel
