import numpy as np
from scipy.integrate import solve_ivp
from numba import njit
from src.orbital_mechanics.perturbations import PerturbationEngine
from src.orbit_determination.adaptive_noise import AdaptiveNoiseCalculator

@njit(fastmath=True)
def _prograde_velocity_numba(r_vec: np.ndarray, mu: float) -> np.ndarray:
    """Return a prograde unit-velocity vector scaled to circular speed."""
    r_mag = np.linalg.norm(r_vec)
    if r_mag < 1e-3:
        return np.array([0.0, 7.5, 0.0])

    v_circ = np.sqrt(mu / r_mag)
    r_hat = r_vec / r_mag
    z_hat = np.array([0.0, 0.0, 1.0])
    
    # Cross product r_hat x z_hat
    h_dir = np.array([
        r_hat[1]*z_hat[2] - r_hat[2]*z_hat[1],
        r_hat[2]*z_hat[0] - r_hat[0]*z_hat[2],
        r_hat[0]*z_hat[1] - r_hat[1]*z_hat[0]
    ])

    if np.linalg.norm(h_dir) < 0.1:
        x_hat = np.array([1.0, 0.0, 0.0])
        h_dir = np.array([
            r_hat[1]*x_hat[2] - r_hat[2]*x_hat[1],
            r_hat[2]*x_hat[0] - r_hat[0]*x_hat[2],
            r_hat[0]*x_hat[1] - r_hat[1]*x_hat[0]
        ])

    h_mag = np.linalg.norm(h_dir)
    h_dir = h_dir / h_mag
    
    # Cross product h_dir x r_hat
    v_dir = np.array([
        h_dir[1]*r_hat[2] - h_dir[2]*r_hat[1],
        h_dir[2]*r_hat[0] - h_dir[0]*r_hat[2],
        h_dir[0]*r_hat[1] - h_dir[1]*r_hat[0]
    ])
    
    return v_dir * v_circ

@njit(fastmath=True)
def _clamp_particle_velocities_numba(particles: np.ndarray, v_min: float, v_max: float, mu: float) -> int:
    activations = 0
    n = particles.shape[0]
    for i in range(n):
        v_vec = particles[i, 3:]
        v_mag = np.linalg.norm(v_vec)
        if v_mag < v_min or v_mag > v_max:
            activations += 1
            r_vec = particles[i, :3]
            r_mag = np.linalg.norm(r_vec)
            if r_mag < 6378.0:
                r_mag = 6378.0 + 750.0
            
            v_circ = np.sqrt(mu / r_mag)
            if v_mag > 1e-6:
                particles[i, 3:] = (v_vec / v_mag) * v_circ
            else:
                particles[i, 3:] = _prograde_velocity_numba(r_vec, mu)
    return activations

class EnsembleKalmanFilter:
    """
    Ensemble Kalman Filter for short-arc space object tracking.

    Units throughout:
        position  → km
        velocity  → km/s
        time      → seconds
    """

    # ── Physical sanity bounds ────────────────────────────────────────
    _V_MIN   =  5.0    # km/s  (LEO floor  — GEO is ~3.07, but we track LEO)
    _V_MAX   = 10.0    # km/s  (LEO ceiling with margin for eccentricity)
    _ALT_MIN =  200.0  # km
    _ALT_MAX = 3000.0  # km

    def __init__(self, n_particles: int = 200, mu: float = 398600.4418,
                 use_adaptive_noise: bool = True):
        self.n          = n_particles
        self.mu         = mu
        self.particles  = None          # shape (n, 6)
        self.update_count = 0
        self.physics    = PerturbationEngine()
        
        # ── Guardrail transparency ────────────────────────────────────
        self.guardrail_activations = 0   # Track when safety clamps fire
        
        # ── Adaptive noise calculator ─────────────────────────────────
        self.use_adaptive_noise = use_adaptive_noise
        if use_adaptive_noise:
            self.noise_calculator = AdaptiveNoiseCalculator(
                base_position_noise=0.05,     # km
                base_velocity_noise=0.0005,   # km/s
                min_scale=0.5,                # Don't go below 0.5x
                max_scale=2.0,                # Don't go above 2.0x
                adaptation_rate=0.15          # Smooth adaptation
            )
        else:
            self.noise_calculator = None
        
        # For adaptive noise tracking
        self.track_id = 0
        self.last_innovation = None
        self.last_S = None

    # ══════════════════════════════════════════════════════════════════
    # INITIALISATION
    # ══════════════════════════════════════════════════════════════════
    def initialize_from_guess(self, initial_state: np.ndarray,
                              initial_covariance: np.ndarray) -> None:
        """
        Seed the particle cloud from a Gaussian using Admissible Region Sampling.
        Only keeps particles that represent valid bound orbits (E < 0) that 
        do not intersect the Earth (q > R_earth + some margin).
        """
        valid_particles = []
        max_attempts = self.n * 100
        attempts = 0
        
        while len(valid_particles) < self.n and attempts < max_attempts:
            # Sample a batch to speed things up
            batch = np.random.multivariate_normal(initial_state, initial_covariance, size=100)
            attempts += 100
            
            for p in batch:
                r_vec = p[:3]
                v_vec = p[3:]
                r_mag = np.linalg.norm(r_vec)
                v_mag = np.linalg.norm(v_vec)
                
                # Minimum altitude check
                if r_mag < 6378.137 + 100:
                    continue
                    
                # Specific Energy
                energy = 0.5 * v_mag**2 - self.mu / r_mag
                
                # Must be a bound orbit (ellipse/circle)
                if energy >= 0:
                    continue
                    
                # Pericenter check (q = a(1-e))
                a = -self.mu / (2 * energy)
                h_vec = np.cross(r_vec, v_vec)
                h_mag_sq = np.dot(h_vec, h_vec)
                e_sq = 1.0 - h_mag_sq / (self.mu * a)
                
                if e_sq < 0:
                    e = 0
                else:
                    e = np.sqrt(e_sq)
                    
                q = a * (1 - e)
                
                # Pericenter must be above Earth's atmosphere limit (e.g. 150 km)
                if q > 6378.137 + 150:
                    valid_particles.append(p)
                    if len(valid_particles) == self.n:
                        break
                        
        if len(valid_particles) < self.n:
            print(f"⚠️ Could only find {len(valid_particles)} admissible particles. Filling rest with mean.")
            while len(valid_particles) < self.n:
                valid_particles.append(initial_state)
                
        self.particles = np.array(valid_particles)
        self.update_count = 0
        self._clamp_particle_velocities()

    # ══════════════════════════════════════════════════════════════════
    # PROPAGATION
    # ══════════════════════════════════════════════════════════════════
    def propagate(self, dt: float) -> None:
        """
        Propagate every particle forward by dt seconds using
        vectorized two-body + J2 + drag dynamics.

        Process noise:
            ADAPTIVE: Adjusts based on filter performance.
            Good tracks get less noise (preserve precision).
            Bad tracks get more noise (explore more).
        """
        def dynamics_batch(t, y_flat):
            y = y_flat.reshape((self.n, 6))
            r_vec = y[:, :3]
            v_vec = y[:, 3:]
            
            r_norm = np.linalg.norm(r_vec, axis=1, keepdims=True)
            valid_mask = (r_norm > 6378.0).flatten()
            
            acc = np.zeros_like(r_vec)
            if np.any(valid_mask):
                r_valid = r_vec[valid_mask]
                v_valid = v_vec[valid_mask]
                r_norm_valid = r_norm[valid_mask]
                
                a_grav = -self.mu / (r_norm_valid**3) * r_valid
                a_j2 = self.physics.compute_j2_acceleration_batch(r_valid)
                a_drag = self.physics.compute_drag_acceleration_batch(r_valid, v_valid)
                a_srp = self.physics.compute_srp_acceleration_batch(r_valid)
                
                acc[valid_mask] = a_grav + a_j2 + a_drag + a_srp
                
            dydt = np.concatenate((v_vec, acc), axis=1)
            dydt[~valid_mask] = 0.0
            return dydt.flatten()

        sol = solve_ivp(dynamics_batch, [0, dt], self.particles.flatten(),
                        method='RK45', rtol=1e-6, atol=1e-8,
                        max_step=dt)
        self.particles = sol.y[:, -1].reshape((self.n, 6))

        # ── Adaptive process noise ────────────────────────────────────
        if (self.use_adaptive_noise and 
            self.last_innovation is not None and 
            self.last_S is not None):
            # Use adaptive noise based on last update performance
            try:
                adaptive_noise = self.noise_calculator.compute_noise(
                    track_id=self.track_id,
                    innovation=self.last_innovation,
                    innovation_covariance=self.last_S
                )
            except Exception:
                # Fallback to base noise if calculation fails
                adaptive_noise = np.array([0.05, 0.05, 0.05,
                                          0.0005, 0.0005, 0.0005])
        else:
            # Fixed noise (fallback or first propagation)
            adaptive_noise = np.array([0.05, 0.05, 0.05,
                                      0.0005, 0.0005, 0.0005])
        
        # Add noise using Anisotropic RTN frame
        self._add_rtn_process_noise(adaptive_noise)

        # Safety clamp after propagation
        self._clamp_particle_velocities()

    def _add_rtn_process_noise(self, adaptive_noise: np.ndarray) -> None:
        """
        Calculates the mean state's RTN frame and adds anisotropic 
        process noise to the particle cloud. Orbital uncertainty grows 
        predominantly in the along-track (Transverse) direction.
        """
        mean_state = np.mean(self.particles, axis=0)
        r_vec = mean_state[:3]
        v_vec = mean_state[3:]
        
        r_mag = np.linalg.norm(r_vec)
        if r_mag < 1e-3:
            # Fallback for degenerate states
            self.particles += np.random.randn(self.n, 6) * adaptive_noise
            return
            
        R_hat = r_vec / r_mag
        h_vec = np.cross(r_vec, v_vec)
        h_mag = np.linalg.norm(h_vec)
        
        if h_mag < 1e-3:
            N_hat = np.array([0.0, 0.0, 1.0])
        else:
            N_hat = h_vec / h_mag
            
        T_hat = np.cross(N_hat, R_hat)
        
        rot_rtn_to_eci = np.column_stack([R_hat, T_hat, N_hat])
        
        base_pos_noise = np.mean(adaptive_noise[:3])
        base_vel_noise = np.mean(adaptive_noise[3:])
        
        # Scale noise: Transverse (x3), Radial (x1), Normal (x0.5)
        rtn_pos_noise = np.array([base_pos_noise * 1.0, base_pos_noise * 3.0, base_pos_noise * 0.5])
        rtn_vel_noise = np.array([base_vel_noise * 1.0, base_vel_noise * 3.0, base_vel_noise * 0.5])
        
        pos_noise_rtn = np.random.randn(self.n, 3) * rtn_pos_noise
        vel_noise_rtn = np.random.randn(self.n, 3) * rtn_vel_noise
        
        pos_noise_eci = pos_noise_rtn @ rot_rtn_to_eci.T
        vel_noise_eci = vel_noise_rtn @ rot_rtn_to_eci.T
        
        eci_noise = np.concatenate([pos_noise_eci, vel_noise_eci], axis=1)
        
        self.particles += eci_noise


    # ══════════════════════════════════════════════════════════════════
    # UPDATE
    # ══════════════════════════════════════════════════════════════════
    def update(self, measurement: np.ndarray,
               measurement_fn,
               R_cov: np.ndarray):
        """
        EnKF measurement update.

        Returns
        -------
        innovation_final : np.ndarray   (for maneuver detection)
        S                : np.ndarray   innovation covariance
        """
        self.update_count += 1

        # ── Predict measurements for every particle ───────────────────
        predictions = []
        for p in self.particles:
            try:
                pred = measurement_fn(p)
                if np.any(np.isnan(pred)) or np.any(np.isinf(pred)):
                    raise ValueError("Bad prediction")
                predictions.append(pred)
            except Exception:
                # Fallback: use mean of what we have so far
                predictions.append(
                    predictions[-1] if predictions else np.zeros_like(measurement)
                )

        predictions  = np.array(predictions)           # (n, m)
        mean_pred    = np.mean(predictions, axis=0)    # (m,)
        mean_state   = np.mean(self.particles, axis=0) # (6,)

        # ── Conservative covariance inflation ────────────────────────
        # Inflation prevents filter divergence by keeping the particle
        # cloud from collapsing prematurely.
        # We use a FIXED small value (1.02) instead of adaptive — the
        # adaptive scheme was growing K too fast and exploding velocity.
        inflation = 1.02
        self.particles = mean_state + inflation * (self.particles - mean_state)

        # Recompute deviations after inflation
        state_dev = self.particles - np.mean(self.particles, axis=0)  # (n, 6)
        meas_dev  = predictions    - np.mean(predictions,   axis=0)   # (n, m)

        # ── Cross-covariance & innovation covariance ──────────────────
        P_xy = (state_dev.T @ meas_dev) / (self.n - 1)   # (6, m)
        P_yy = (meas_dev.T  @ meas_dev) / (self.n - 1)   # (m, m)

        S     = P_yy + R_cov
        S_reg = S + np.eye(S.shape[0]) * 1e-8            # regularisation

        # ── Kalman gain ───────────────────────────────────────────────
        try:
            K = P_xy @ np.linalg.inv(S_reg)              # (6, m)
        except np.linalg.LinAlgError:
            print("⚠️  Singular S matrix — skipping update")
            return np.zeros(len(measurement)), S

        # ── Stochastic update (perturbed-observation EnKF) ────────────
        obs_perturbed = measurement + np.random.multivariate_normal(
            np.zeros(len(measurement)), R_cov, size=self.n
        )

        for i in range(self.n):
            innov = obs_perturbed[i] - predictions[i]

            # Wrap RA (first angle component) to [-π, π]
            innov[0] = (innov[0] + np.pi) % (2 * np.pi) - np.pi

            delta = K @ innov
            
            # Limit the magnitude of the update to prevent filter explosions
            # Allow max 200 km position shift and 1.0 km/s velocity shift per update
            delta_pos_mag = np.linalg.norm(delta[:3])
            delta_vel_mag = np.linalg.norm(delta[3:])
            
            scale = 1.0
            if delta_pos_mag > 200.0:
                scale = min(scale, 200.0 / delta_pos_mag)
                self.guardrail_activations += 1
            if delta_vel_mag > 1.0:
                scale = min(scale, 1.0 / delta_vel_mag)
                self.guardrail_activations += 1
            
            self.particles[i] += delta * scale

        # ── Post-update sanity check & soft reset ────────────────────
        mean_after = np.mean(self.particles, axis=0)
        v_after    = float(np.linalg.norm(mean_after[3:]))
        r_after    = float(np.linalg.norm(mean_after[:3]))
        alt_after  = r_after - 6378.137

        velocity_ok  = self._V_MIN   < v_after  < self._V_MAX
        altitude_ok  = self._ALT_MIN < alt_after < self._ALT_MAX

        if not velocity_ok or not altitude_ok:
            # Soft reset: keep position, recalculate circular velocity
            self.guardrail_activations += 10  # Heavy penalty for full reset
            self._soft_reset_velocity(mean_after[:3])

        # ── Final innovation for maneuver detector ────────────────────
        innov_final    = measurement - mean_pred
        innov_final[0] = (innov_final[0] + np.pi) % (2 * np.pi) - np.pi

        # ── Store for adaptive noise ──────────────────────────────────
        self.last_innovation = innov_final
        self.last_S          = S

        return innov_final, S

    # ══════════════════════════════════════════════════════════════════
    # JPDA UPDATE
    # ══════════════════════════════════════════════════════════════════
    def jpda_update(self, zs, probs, measurement_fn, R_cov):
        """
        EnKF measurement update combining multiple measurements probabilistically.
        """
        self.update_count += 1

        # Predict measurements for every particle
        predictions = []
        for p in self.particles:
            try:
                pred = measurement_fn(p)
                if np.any(np.isnan(pred)) or np.any(np.isinf(pred)):
                    raise ValueError("Bad prediction")
                predictions.append(pred)
            except Exception:
                predictions.append(predictions[-1] if predictions else np.zeros_like(zs[0]))

        predictions  = np.array(predictions)
        mean_pred    = np.mean(predictions, axis=0)
        mean_state   = np.mean(self.particles, axis=0)

        # Inflation
        inflation = 1.02
        self.particles = mean_state + inflation * (self.particles - mean_state)

        state_dev = self.particles - np.mean(self.particles, axis=0)
        meas_dev  = predictions    - np.mean(predictions,   axis=0)

        P_xy = (state_dev.T @ meas_dev) / (self.n - 1)
        P_yy = (meas_dev.T  @ meas_dev) / (self.n - 1)

        S     = P_yy + R_cov
        S_reg = S + np.eye(S.shape[0]) * 1e-8

        try:
            K = P_xy @ np.linalg.inv(S_reg)
        except np.linalg.LinAlgError:
            print("⚠️ Singulary S matrix in JPDA — skipping")
            return np.zeros_like(zs[0]), S

        # Compute final overall innovation for the track (for adaptive noise/maneuvers)
        innov_final = np.zeros_like(zs[0])
        for z, prob in zip(zs, probs):
            innov = z - mean_pred
            innov[0] = (innov[0] + np.pi) % (2 * np.pi) - np.pi
            innov_final += prob * innov

        # Update particles with combined weighted innovation
        for i in range(self.n):
            comb_innov = np.zeros_like(zs[0])
            for z, prob in zip(zs, probs):
                # Perturb each observation
                z_pert = z + np.random.multivariate_normal(np.zeros_like(z), R_cov)
                innov = z_pert - predictions[i]
                innov[0] = (innov[0] + np.pi) % (2 * np.pi) - np.pi
                comb_innov += prob * innov
            
            delta = K @ comb_innov
            
            # Magnitude Limiting
            delta_pos_mag = np.linalg.norm(delta[:3])
            delta_vel_mag = np.linalg.norm(delta[3:])
            scale = 1.0
            if delta_pos_mag > 200.0:
                scale = min(scale, 200.0 / delta_pos_mag)
                self.guardrail_activations += 1
            if delta_vel_mag > 1.0:
                scale = min(scale, 1.0 / delta_vel_mag)
                self.guardrail_activations += 1
                
            self.particles[i] += delta * scale

        # Sanity check
        mean_after = np.mean(self.particles, axis=0)
        v_after    = float(np.linalg.norm(mean_after[3:]))
        r_after    = float(np.linalg.norm(mean_after[:3]))
        alt_after  = r_after - 6378.137

        if not (self._V_MIN < v_after < self._V_MAX) or not (self._ALT_MIN < alt_after < self._ALT_MAX):
            self.guardrail_activations += 10
            self._soft_reset_velocity(mean_after[:3])

        self.last_innovation = innov_final
        self.last_S          = S

        return innov_final, S

    # ══════════════════════════════════════════════════════════════════
    # INTERNAL HELPERS
    # ══════════════════════════════════════════════════════════════════
    def _propagate_particle(self, state: np.ndarray, dt: float) -> np.ndarray:
        """Two-body + J2 + drag propagation for a single particle."""

        def dynamics(t, y):
            r_vec  = y[:3]
            v_vec  = y[3:]
            r_norm = np.linalg.norm(r_vec)

            if r_norm < 6378.0:          # below Earth's surface — abort
                return np.zeros(6)

            acc  = -self.mu / r_norm ** 3 * r_vec
            acc += self.physics.compute_j2_acceleration(r_vec)
            acc += self.physics.compute_drag_acceleration(r_vec, v_vec)
            acc += self.physics.compute_srp_acceleration(r_vec)

            return np.concatenate((v_vec, acc))

        sol = solve_ivp(dynamics, [0, dt], state,
                        method='RK45', rtol=1e-7, atol=1e-9,
                        max_step=dt)          # don't overshoot
        return sol.y[:, -1]

    def _clamp_particle_velocities(self) -> None:
        """
        Hard-clamp particle velocities to physically possible LEO range.
        Uses Numba JIT helper for vectorised speedup.
        """
        activations = _clamp_particle_velocities_numba(
            self.particles, self._V_MIN, self._V_MAX, self.mu
        )
        self.guardrail_activations += activations

    def _soft_reset_velocity(self, r_vec: np.ndarray) -> None:
        """
        Keep the current position of every particle but reset velocity
        to circular speed + small Gaussian noise.

        Called only when the mean state becomes physically impossible.
        """
        r_mag  = float(np.linalg.norm(r_vec))
        if r_mag < 6378.0:
            r_mag = 6378.0 + 750.0
        v_circ = float(np.sqrt(self.mu / r_mag))

        v_base = self._prograde_velocity(r_vec)

        # Keep particle positions, reset velocities
        pos_mean = np.mean(self.particles[:, :3], axis=0)
        P_pos    = np.cov(self.particles[:, :3].T)

        new_pos = np.random.multivariate_normal(pos_mean, P_pos, size=self.n)
        new_vel = v_base + np.random.randn(self.n, 3) * 0.1   # ±0.1 km/s spread

        self.particles = np.hstack([new_pos, new_vel])
        self.update_count = 0

    def _prograde_velocity(self, r_vec: np.ndarray) -> np.ndarray:
        """Return a prograde unit-velocity vector scaled to circular speed."""
        r_mag  = float(np.linalg.norm(r_vec))
        if r_mag < 1e-3:
            return np.array([0.0, 7.5, 0.0])

        v_circ = float(np.sqrt(self.mu / r_mag))
        r_hat  = r_vec / r_mag
        z_hat  = np.array([0.0, 0.0, 1.0])
        h_dir  = np.cross(r_hat, z_hat)

        if np.linalg.norm(h_dir) < 0.1:
            h_dir = np.cross(r_hat, np.array([1.0, 0.0, 0.0]))

        h_dir = h_dir / np.linalg.norm(h_dir)
        v_dir = np.cross(h_dir, r_hat)
        return v_dir * v_circ

    # ══════════════════════════════════════════════════════════════════
    # ADAPTIVE NOISE INTERFACE
    # ══════════════════════════════════════════════════════════════════
    def set_track_id(self, track_id: int):
        """Set track ID for adaptive noise tracking."""
        self.track_id = track_id
    
    def get_noise_statistics(self):
        """Get current adaptive noise statistics."""
        if self.use_adaptive_noise and self.noise_calculator:
            return self.noise_calculator.get_statistics()
        return {}

    # ══════════════════════════════════════════════════════════════════
    # OUTPUTS
    # ══════════════════════════════════════════════════════════════════
    def get_state_estimate(self):
        """Return (mean_state [6], covariance [6×6])."""
        mean = np.mean(self.particles, axis=0)
        cov  = np.cov(self.particles.T)
        return mean, cov