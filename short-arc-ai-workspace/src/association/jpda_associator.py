"""
src/association/jpda_associator.py (FIXED VERSION)

Key improvements:
1. Tighter default gate (25.0 instead of 50.0)
2. Lower clutter density (space has almost no clutter)
3. Better probability normalization
4. Improved numerical stability
"""

import numpy as np
from scipy.stats import chi2


class JPDAAssociator:
    """
    Joint Probabilistic Data Association Filter (JPDAF).
    
    FIXED: Proper parameter tuning for space debris tracking.
    """
    
    def __init__(self, 
                 gate_threshold: float = 25.0,       # ← FIXED: Tighter gate
                 pd: float = 0.98,                   # ← FIXED: Higher P_D
                 clutter_density: float = 1e-8):     # ← FIXED: Much lower
        """
        Parameters
        ----------
        gate_threshold : float
            Chi-squared threshold (25.0 = tighter, less ambiguity)
        pd : float
            Detection probability (0.98 = radar rarely misses)
        clutter_density : float
            False alarms per unit volume (1e-8 = space is clean)
        """
        self.gate_threshold  = gate_threshold
        self.pd              = pd
        self.clutter_density = clutter_density
        
        # Statistics
        self.total_associations = 0
        self.ambiguous_cases    = 0
    
    def associate(self, tracks, measurements):
        """JPDA association with improved numerical stability."""
        n_tracks = len(tracks)
        n_meas   = len(measurements)
        
        if n_tracks == 0 or n_meas == 0:
            return [], list(range(n_tracks)), list(range(n_meas))
        
        # ── Step 1: Gating with improved distance calculation ────────
        validation_matrix = np.zeros((n_tracks, n_meas), dtype=bool)
        distance_matrix   = np.zeros((n_tracks, n_meas))
        
        for t_idx, track in enumerate(tracks):
            for m_idx, meas in enumerate(measurements):
                dist = self._compute_mahalanobis_distance(track, meas)
                distance_matrix[t_idx, m_idx]   = dist
                validation_matrix[t_idx, m_idx] = (dist < self.gate_threshold)
        
        # ── Step 2: Compute association probabilities (IMPROVED) ─────
        assignments = []
        used_measurements = set()
        
        for t_idx, track in enumerate(tracks):
            gated_indices = np.where(validation_matrix[t_idx])[0]
            
            if len(gated_indices) == 0:
                # No measurements in gate → track predicted only
                continue
            
            # Track ambiguity
            if len(gated_indices) > 1:
                self.ambiguous_cases += 1
            
            # Compute β with IMPROVED numerical stability
            beta = self._compute_association_probabilities(
                t_idx, gated_indices, distance_matrix, n_meas
            )
            
            # FIXED: Only use measurements with significant probability
            for m_idx, prob in zip(gated_indices, beta):
                if prob > 0.05:  # ← FIXED: Threshold at 5% instead of 1%
                    assignments.append((t_idx, m_idx, prob))
                    used_measurements.add(m_idx)
            
            self.total_associations += 1
        
        # ── Step 3: Identify unassigned ──────────────────────────────
        assigned_tracks = set(a[0] for a in assignments)
        
        unassigned_tracks = [i for i in range(n_tracks) 
                            if i not in assigned_tracks]
        unassigned_meas   = [i for i in range(n_meas) 
                            if i not in used_measurements]
        
        return assignments, unassigned_tracks, unassigned_meas
    
    def _compute_association_probabilities(self, 
                                          track_idx: int,
                                          gated_meas_indices,
                                          distance_matrix,
                                          n_total_meas: int):
        """
        Compute β_j with IMPROVED numerical stability.
        
        FIXED:
        1. Use log-space for exponentials (prevent underflow)
        2. Better clutter model
        3. Proper normalization
        """
        n_gated = len(gated_meas_indices)
        
        # ── Likelihoods in LOG space (numerical stability) ────────────
        distances   = distance_matrix[track_idx, gated_meas_indices]
        log_likelihoods = -0.5 * distances
        
        # Convert back from log space
        likelihoods = np.exp(log_likelihoods - np.max(log_likelihoods))
        
        # Normalize to prevent overflow
        likelihoods = likelihoods / (np.sum(likelihoods) + 1e-10)
        
        # ── Clutter model (IMPROVED) ──────────────────────────────────
        # Volume = 2π × threshold (2D angular gate)
        gate_volume = 2 * np.pi * self.gate_threshold
        lambda_c    = self.clutter_density * gate_volume
        
        # ── Compute probabilities (IMPROVED normalization) ────────────
        # β_j = (P_D × L_j) / (λ_c + Σ P_D × L_k)
        numerators  = self.pd * likelihoods
        denominator = lambda_c + np.sum(numerators)
        
        if denominator < 1e-12:
            # Uniform distribution as fallback
            return np.ones(n_gated) / n_gated
        
        beta = numerators / denominator
        
        # ── Final safety checks ───────────────────────────────────────
        beta = np.clip(beta, 0.0, 1.0)
        
        # Renormalize to ensure Σβ ≤ 1
        beta_sum = np.sum(beta)
        if beta_sum > 1.0:
            beta = beta / beta_sum
        
        return beta
    
    def _compute_mahalanobis_distance(self, track, measurement):
        """Compute Mahalanobis distance using Numba-compiled helper for extreme speed."""
        site_pos = measurement.radar_site_eci
        z_actual = np.array([measurement.ra_rad, measurement.dec_rad])
        R_noise = np.diag([np.deg2rad(0.05)**2, np.deg2rad(0.05)**2])
        
        return _compute_mahalanobis_distance_numba(
            track.particles, site_pos, z_actual, R_noise
        )
    
    def get_statistics(self):
        """Return performance statistics."""
        if self.total_associations == 0:
            return {
                'total_associations': 0,
                'ambiguous_cases': 0,
                'ambiguity_rate': 0.0
            }
        
        return {
            'total_associations': self.total_associations,
            'ambiguous_cases': self.ambiguous_cases,
            'ambiguity_rate': self.ambiguous_cases / self.total_associations
        }

from numba import njit
import numpy as np

@njit(fastmath=True)
def _compute_mahalanobis_distance_numba(particles: np.ndarray, site_pos: np.ndarray, z_actual: np.ndarray, R_noise: np.ndarray) -> float:
    # 1. Project particles to measurement space
    n_particles = particles.shape[0]
    predicted_measurements = np.zeros((n_particles, 2))
    n_valid = 0
    
    for i in range(n_particles):
        rho_x = particles[i, 0] - site_pos[0]
        rho_y = particles[i, 1] - site_pos[1]
        rho_z = particles[i, 2] - site_pos[2]
        
        dist = np.sqrt(rho_x**2 + rho_y**2 + rho_z**2)
        if dist < 1e-3: continue
            
        ra = np.arctan2(rho_y, rho_x)
        dec_ratio = rho_z / dist
        if dec_ratio > 1.0: dec_ratio = 1.0
        if dec_ratio < -1.0: dec_ratio = -1.0
        dec = np.arcsin(dec_ratio)
        
        predicted_measurements[n_valid, 0] = ra
        predicted_measurements[n_valid, 1] = dec
        n_valid += 1
        
    if n_valid == 0: return 1e9
    z_predicted = predicted_measurements[:n_valid]
    
    # 2. Compute Mean & Covariance
    z_mean = np.zeros(2)
    for i in range(n_valid):
        z_mean[0] += z_predicted[i, 0]
        z_mean[1] += z_predicted[i, 1]
    z_mean /= n_valid
    
    P_zz = np.zeros((2, 2))
    for i in range(n_valid):
        dev0 = z_predicted[i, 0] - z_mean[0]
        dev1 = z_predicted[i, 1] - z_mean[1]
        P_zz[0, 0] += dev0 * dev0
        P_zz[0, 1] += dev0 * dev1
        P_zz[1, 0] += dev1 * dev0
        P_zz[1, 1] += dev1 * dev1
    P_zz /= (n_valid - 1)
    
    # 3. Add noise and invert
    S = P_zz + R_noise
    
    det = S[0, 0] * S[1, 1] - S[0, 1] * S[1, 0]
    if abs(det) < 1e-12: return 1e9
    
    S_inv = np.zeros((2, 2))
    S_inv[0, 0] = S[1, 1] / det
    S_inv[1, 1] = S[0, 0] / det
    S_inv[0, 1] = -S[0, 1] / det
    S_inv[1, 0] = -S[1, 0] / det
    
    # 4. Mahalanobis distance
    innov0 = z_actual[0] - z_mean[0]
    innov1 = z_actual[1] - z_mean[1]
    
    # Angle wrap [-pi, pi]
    pi2 = 2 * np.pi
    innov0 = (innov0 + np.pi) % pi2 - np.pi
    
    dist = (innov0 * S_inv[0, 0] + innov1 * S_inv[1, 0]) * innov0 + \
           (innov0 * S_inv[0, 1] + innov1 * S_inv[1, 1]) * innov1
           
    return float(dist)