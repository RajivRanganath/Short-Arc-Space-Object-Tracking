"""
src/orbit_determination/adaptive_noise.py

Adaptive Process Noise for EnKF
================================
Dynamically adjusts particle spread based on filter performance.

Theory
------
Fixed process noise is suboptimal:
  • High-performing tracks → noise wastes precision
  • Struggling tracks → noise is insufficient to explore

Adaptive approach:
  • Measure innovation magnitude (how wrong predictions are)
  • Scale noise proportionally: bad predictions → more noise

Result: Tracks self-tune to their own uncertainty level.
"""

import numpy as np


class AdaptiveNoiseCalculator:
    """
    Computes adaptive process noise based on filter performance.
    
    Key Idea
    --------
    If innovation (measurement - prediction) is large, the filter
    is uncertain → add MORE noise to help particles explore.
    
    If innovation is small, filter is confident → add LESS noise
    to preserve precision.
    """
    
    def __init__(self,
                 base_position_noise: float = 0.05,    # km
                 base_velocity_noise: float = 0.0005,  # km/s
                 min_scale: float = 0.8,
                 max_scale: float = 1.2,
                 adaptation_rate: float = 0.05):
        """
        Parameters
        ----------
        base_position_noise : float
            Baseline position noise (km)
        base_velocity_noise : float
            Baseline velocity noise (km/s)
        min_scale : float
            Minimum noise multiplier (don't go below this)
        max_scale : float
            Maximum noise multiplier (cap at this)
        adaptation_rate : float
            How quickly to adapt (0.1 = smooth, 0.5 = aggressive)
        """
        self.base_noise = np.array([
            base_position_noise,
            base_position_noise,
            base_position_noise,
            base_velocity_noise,
            base_velocity_noise,
            base_velocity_noise
        ])
        
        self.min_scale = min_scale
        self.max_scale = max_scale
        self.alpha     = adaptation_rate
        
        # Track history for smoothing
        self.noise_scales = {}  # {track_id: current_scale}
    
    def compute_noise(self, 
                      track_id: int,
                      innovation: np.ndarray,
                      innovation_covariance: np.ndarray) -> np.ndarray:
        """
        Compute adaptive process noise for one track.
        
        Parameters
        ----------
        track_id : int
            Track identifier
        innovation : np.ndarray
            Measurement residual (z_measured - z_predicted)
        innovation_covariance : np.ndarray
            Innovation covariance matrix S
        
        Returns
        -------
        noise : np.ndarray (6,)
            Adaptive process noise vector [σ_x, σ_y, σ_z, σ_vx, σ_vy, σ_vz]
        """
        # ── Compute Normalized Innovation Squared (NIS) ──────────────
        # NIS tells us how many standard deviations away the
        # measurement was from the prediction
        try:
            inv_S = np.linalg.inv(innovation_covariance)
            nis   = float(innovation.T @ inv_S @ innovation)
        except (np.linalg.LinAlgError, ValueError):
            # Singular matrix → use default
            nis = 1.0
        
        # ── Map NIS to noise scale ────────────────────────────────────
        # Expected NIS for 2 DOF (RA, Dec) = 2.0
        # If NIS >> 2 → filter is struggling → increase noise
        # If NIS << 2 → filter is confident → decrease noise
        
        expected_nis = len(innovation)
        nis_ratio    = nis / expected_nis
        
        # Scale proportional to sqrt(NIS ratio) for smooth response
        target_scale = 1.0 + 0.5 * (np.sqrt(nis_ratio) - 1.0)
        
        # Clamp to safe bounds
        target_scale = np.clip(target_scale, self.min_scale, self.max_scale)
        
        # ── Smooth adaptation (exponential moving average) ───────────
        if track_id not in self.noise_scales:
            # First time seeing this track → initialize
            self.noise_scales[track_id] = 1.0
        
        current_scale = self.noise_scales[track_id]
        
        # Exponential moving average: s_new = α·s_target + (1-α)·s_old
        new_scale = (self.alpha * target_scale + 
                     (1 - self.alpha) * current_scale)
        
        self.noise_scales[track_id] = new_scale
        
        # ── Return scaled noise ───────────────────────────────────────
        adaptive_noise = self.base_noise * new_scale
        
        return adaptive_noise
    
    def get_statistics(self) -> dict:
        """Return current noise scales for all tracks (debugging)."""
        if not self.noise_scales:
            return {}
        
        scales = list(self.noise_scales.values())
        return {
            'num_tracks': len(scales),
            'mean_scale': float(np.mean(scales)),
            'min_scale':  float(np.min(scales)),
            'max_scale':  float(np.max(scales)),
            'scales_by_track': dict(self.noise_scales)
        }
    
    def reset_track(self, track_id: int):
        """Reset adaptation for a track (e.g., after maneuver)."""
        if track_id in self.noise_scales:
            del self.noise_scales[track_id]


# ══════════════════════════════════════════════════════════════════════
# HELPER: Alternative Strategy (Covariance-Based)
# ══════════════════════════════════════════════════════════════════════

class CovarianceBasedNoise:
    """
    Alternative: Scale noise based on particle spread.
    
    If particles are tightly clustered → low noise
    If particles are widely spread → high noise
    
    This is simpler but less responsive to sudden changes.
    """
    
    def __init__(self, base_noise: np.ndarray):
        self.base_noise = base_noise
    
    def compute_noise(self, particles: np.ndarray) -> np.ndarray:
        """
        Scale noise based on current particle spread.
        
        Parameters
        ----------
        particles : np.ndarray (n_particles, 6)
            Current particle cloud
        
        Returns
        -------
        noise : np.ndarray (6,)
            Scaled noise
        """
        # Compute current spread (standard deviation per dimension)
        particle_std = np.std(particles, axis=0)
        
        # Scale noise proportional to current uncertainty
        # If particles are spread out → add more noise
        # If particles are tight → add less noise
        scale_factors = np.clip(particle_std / self.base_noise, 0.5, 2.0)
        
        return self.base_noise * scale_factors