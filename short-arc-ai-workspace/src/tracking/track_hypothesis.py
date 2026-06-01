import numpy as np
from dataclasses import dataclass
from datetime import datetime
from src.orbit_determination.ensemble_kalman_filter import EnsembleKalmanFilter
from src.tracking.maneuver import FilterAnomalyDetector, ManeuverSizer
from src.classification.regime_classifier import OrbitalRegimeClassifier

@dataclass
class Measurement:
    time: datetime
    radar_site_eci: np.ndarray
    range_m: float
    ra_rad: float
    dec_rad: float
    noise_matrix: np.ndarray
    range_km: float = 0.0
    true_object_id: int = -1  # For ground-truth validation


class Track:
    def __init__(self, track_id, initial_measurement):
        self.id = track_id
        self.last_update_time = initial_measurement.time
        self.missed_detections = 0
        self.total_frames = 1
        self.matched_frames = 1
        self.nis_sum = 0.0

        self.filter = EnsembleKalmanFilter(n_particles=200)
        self._initialize_filter(initial_measurement)

        # Raised threshold: real debris doesn't maneuver
        self.anomaly_detector = FilterAnomalyDetector(threshold_sigmas=8.0)
        self.maneuver_sizer = ManeuverSizer()
        self.last_dt = 0.0
        
        # Simulation/UI attributes
        self.last_manuever_dv = 0.0
        
        # ML Regime Classifier
        self.classifier = OrbitalRegimeClassifier()
        self.regime_info = None

    # ------------------------------------------------------------------
    # INITIALISATION
    # ------------------------------------------------------------------
    def _initialize_filter(self, obs):
        """
        Smart track initialisation.

        Strategy
        --------
        1. Build the Line-Of-Sight (LOS) unit vector from RA/Dec.
        2. Decide on a slant-range estimate:
             a) Use the measured range if it places the satellite in LEO.
             b) Otherwise solve the quadratic that puts the satellite at
                a default altitude of 750 km along the LOS direction.
        3. Compute a circular-orbit velocity at that position.
        4. Initialise the EnKF particle cloud.
        """

        # --- Step 1: Line-Of-Sight unit vector (ECI) ---
        L_vec = np.array([
            np.cos(obs.dec_rad) * np.cos(obs.ra_rad),
            np.cos(obs.dec_rad) * np.sin(obs.ra_rad),
            np.sin(obs.dec_rad)
        ])

        R_site  = np.array(obs.radar_site_eci)   # Station ECI position (km)
        Re      = 6378.137                         # Earth radius (km)
        mu      = 398600.4418                      # GM  (km³/s²)

        # --- Step 2: Estimate slant range ---
        range_km    = getattr(obs, 'range_km', 0.0)
        use_measured = False

        if range_km > 0:
            # Quickly check whether this range puts us in LEO
            r_test = R_site + range_km * L_vec
            alt_test = np.linalg.norm(r_test) - Re
            if 300 < alt_test < 2000:
                estimated_range = range_km
                use_measured    = True
                print(f"   Track {self.id}: "
                      f"Using measured range {estimated_range:.1f} km  "
                      f"(alt approx {alt_test:.0f} km)")

        if not use_measured:
            # Solve  |R_site + ρ·L|² = (Re + h_target)²
            # → ρ² + 2(R·L)ρ + (|R|² - (Re+h)²) = 0
            h_target = 750.0          # desired altitude (km)
            target_r = Re + h_target

            a_c =  1.0
            b_c =  2.0 * float(np.dot(R_site, L_vec))
            c_c =  float(np.dot(R_site, R_site)) - target_r ** 2

            disc = b_c ** 2 - 4.0 * a_c * c_c

            if disc >= 0:
                rho1 = (-b_c + np.sqrt(disc)) / 2.0
                rho2 = (-b_c - np.sqrt(disc)) / 2.0
                # Pick the positive root that is smallest (front intersection)
                candidates = [r for r in (rho1, rho2) if r > 0]
                estimated_range = min(candidates) if candidates else 1500.0
            else:
                estimated_range = 1500.0   # fallback

            # Clamp to a sensible window
            estimated_range = float(np.clip(estimated_range, 300.0, 6000.0))
            print(f"   Track {self.id}: "
                  f"Geometric range estimate {estimated_range:.1f} km  "
                  f"(target alt {h_target:.0f} km)")

        # --- Step 3: Satellite position in ECI ---
        r_guess = R_site + estimated_range * L_vec
        r_mag   = float(np.linalg.norm(r_guess))
        alt     = r_mag - Re

        # Safety clamp: if still out of LEO band, rescale along LOS
        if not (300 < alt < 2000):
            print(f"   WARNING Track {self.id}: "
                  f"Alt {alt:.0f} km still outside LEO - rescaling to 750 km")
            r_guess = r_guess / r_mag * (Re + 750.0)
            r_mag   = float(np.linalg.norm(r_guess))
            alt     = r_mag - Re

        # --- Step 4: Circular-orbit velocity ---
        v_circular = float(np.sqrt(mu / r_mag))   # km/s

        # Prograde direction: v = h × r_hat,  h = r_hat × z
        r_hat = r_guess / r_mag
        z_hat = np.array([0.0, 0.0, 1.0])
        h_dir = np.cross(r_hat, z_hat)

        if np.linalg.norm(h_dir) < 0.1:          # near-polar edge case
            h_dir = np.cross(r_hat, np.array([1.0, 0.0, 0.0]))

        h_dir  = h_dir / np.linalg.norm(h_dir)
        v_dir  = np.cross(h_dir, r_hat)
        v_guess = v_dir * v_circular

        initial_state = np.concatenate([r_guess, v_guess])

        # --- Step 5: Initial covariance ---
        # Tighter when we have a real range measurement
        if use_measured:
            P = np.diag([
                100.0**2, 100.0**2, 100.0**2,   # position  (km)
                  1.0**2,   1.0**2,   1.0**2     # velocity  (km/s)
            ])
        else:
            P = np.diag([
                500.0**2, 500.0**2, 500.0**2,   # position  (km)
                  2.0**2,   2.0**2,   2.0**2     # velocity  (km/s)
            ])

        self.filter.initialize_from_guess(initial_state, P)
        print(f"   Track {self.id} initialized: "
              f"alt = {alt:.0f} km | speed = {v_circular:.2f} km/s")

    # ------------------------------------------------------------------
    # PREDICT
    # ------------------------------------------------------------------
    def predict(self, current_time):
        dt = (current_time - self.last_update_time).total_seconds()
        self.last_dt = dt
        self.filter.propagate(dt)
        if dt > 0:
            self.total_frames += 1
        self.last_update_time = current_time

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------
    def update(self, measurement):
        site_pos  = measurement.radar_site_eci
        has_range = (hasattr(measurement, 'range_km')
                     and measurement.range_km > 0)

        if has_range:
            # 3-D measurement: RA, Dec, slant-range
            z = np.array([
                measurement.ra_rad,
                measurement.dec_rad,
                measurement.range_km
            ])

            def h(state):
                rho  = state[:3] - site_pos
                dist = np.linalg.norm(rho)
                ra   = np.arctan2(rho[1], rho[0])
                dec  = np.arcsin(np.clip(rho[2] / dist, -1.0, 1.0))
                return np.array([ra, dec, dist])

            R = np.diag([
                np.deg2rad(0.2) ** 2,   # RA  noise
                np.deg2rad(0.2) ** 2,   # Dec noise
                5.0 ** 2                # Range noise (km)
            ])

        else:
            # 2-D measurement: RA, Dec only
            z = np.array([measurement.ra_rad, measurement.dec_rad])

            def h(state):
                rho  = state[:3] - site_pos
                dist = np.linalg.norm(rho)
                ra   = np.arctan2(rho[1], rho[0])
                dec  = np.arcsin(np.clip(rho[2] / dist, -1.0, 1.0))
                return np.array([ra, dec])

            R = measurement.noise_matrix

        innovation, S = self.filter.update(z, h, R)
        self.missed_detections = 0
        self.matched_frames += 1
        
        # Accumulate NIS
        nis = float(innovation.T @ np.linalg.inv(S) @ innovation)
        self.nis_sum += nis

        # Filter anomaly detection (divergence)
        is_anomaly = self.anomaly_detector.check_for_anomaly(innovation, S)
        if is_anomaly:
            print(f"   FILTER ANOMALY on Track {self.id} (Divergence possible)")
            
            # Estimate Delta V sizing
            mean_state = self.state_estimate
            delta_v = self.maneuver_sizer.estimate_delta_v(
                innovation, S, mean_state, site_pos, self.last_dt
            )
            
            dv_mag = np.linalg.norm(delta_v)
            if dv_mag > 0:
                print(f"   MANEUVER DETECTED! Estimated Delta V: {dv_mag*1000:.2f} m/s")
                self.last_manuever_dv = dv_mag
                # Apply Delta V to all particles to shift the ensemble
                self.filter.particles[:, 3:] += delta_v
            
            # Inflate particles more aggressively to allow re-convergence
            self.filter.particles += np.random.normal(
                0, 0.5, size=self.filter.particles.shape
            )
            self.update_regime()

        # Periodically update regime if unknown
        if self.regime_info is None:
            self.update_regime()

    def update_regime(self):
        """Forces a regime classification update."""
        state = self.state_estimate
        if state is not None:
            self.regime_info = self.classifier.predict(state[:3], state[3:])

    def jpda_update(self, measurement_prob_pairs):
        """Processes multiple ambiguous measurements using JPDA."""
        meas0, _ = measurement_prob_pairs[0]
        site_pos = meas0.radar_site_eci
        has_range = (hasattr(meas0, 'range_km') and meas0.range_km > 0)

        if has_range:
            def h(state):
                rho = state[:3] - site_pos
                dist = np.linalg.norm(rho)
                ra = np.arctan2(rho[1], rho[0])
                dec = np.arcsin(np.clip(rho[2] / dist, -1.0, 1.0))
                return np.array([ra, dec, dist])
            R = np.diag([np.deg2rad(0.2) ** 2, np.deg2rad(0.2) ** 2, 5.0 ** 2])
        else:
            def h(state):
                rho = state[:3] - site_pos
                dist = np.linalg.norm(rho)
                ra = np.arctan2(rho[1], rho[0])
                dec = np.arcsin(np.clip(rho[2] / dist, -1.0, 1.0))
                return np.array([ra, dec])
            R = meas0.noise_matrix

        zs = []
        probs = []
        for m, p in measurement_prob_pairs:
            if has_range:
                zs.append(np.array([m.ra_rad, m.dec_rad, m.range_km]))
            else:
                zs.append(np.array([m.ra_rad, m.dec_rad]))
            probs.append(p)

        innovation, S = self.filter.jpda_update(zs, probs, h, R)
        self.missed_detections = 0
        self.matched_frames += 1

        nis = float(innovation.T @ np.linalg.inv(S) @ innovation)
        self.nis_sum += nis

        # Anomaly detection on combined innovation
        is_anomaly = self.anomaly_detector.check_for_anomaly(innovation, S)
        if is_anomaly:
            print(f"   FILTER ANOMALY on Track {self.id} (JPDA)!")
            
            mean_state = self.state_estimate
            delta_v = self.maneuver_sizer.estimate_delta_v(
                innovation, S, mean_state, site_pos, self.last_dt
            )
            
            dv_mag = np.linalg.norm(delta_v)
            if dv_mag > 0:
                print(f"   MANEUVER DETECTED (JPDA)! Estimated Delta V: {dv_mag*1000:.2f} m/s")
                self.last_manuever_dv = dv_mag
                self.filter.particles[:, 3:] += delta_v
            
            # covariance inflation for recovery
            self.filter.particles += np.random.normal(0, 0.5, size=self.filter.particles.shape)
            self.update_regime()
            
        # Periodically update regime if unknown
        if self.regime_info is None:
            self.update_regime()

            self.filter.particles += np.random.normal(0, 0.5, size=self.filter.particles.shape)

    # ------------------------------------------------------------------
    # PROPERTIES
    # ------------------------------------------------------------------
    @property
    def particles(self):
        return self.filter.particles

    @property
    def state_estimate(self):
        return self.filter.get_state_estimate()[0]

    @property
    def quality_metric(self) -> float:
        """
        Q = (matched_frames / total_frames) * NIS_consistency
        NIS_consistency = 1.0 / (1.0 + avg_nis / dof)
        """
        if self.total_frames == 0:
            return 0.0
            
        # Grace period for very young tracks to prevent early false degraded state
        if self.total_frames < 5:
            return 1.0
            
        match_ratio = self.matched_frames / self.total_frames
        
        if self.matched_frames > 0:
            avg_nis = self.nis_sum / self.matched_frames
            # Default to 3 degrees of freedom for NIS normalization
            nis_consistency = 1.0 / (1.0 + avg_nis / 3.0) 
        else:
            nis_consistency = 1.0
            
        return match_ratio * nis_consistency
