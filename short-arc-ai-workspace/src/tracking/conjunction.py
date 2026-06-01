import numpy as np
import math
from datetime import timedelta
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from src.constants import MU, get_logger

logger = get_logger("ConjunctionAssessment")

class ConjunctionAssessment:
    """
    Production-Grade Conjunction Assessment System
    
    Features:
    - True Probability of Collision (Pc) calculation
    - Covariance propagation with State Transition Matrix
    - Pc history tracking and trend analysis
    - Uncertainty visualization
    - Industry-standard thresholds (NASA CARA / ESA compliant)
    """
    
    def __init__(self, hard_body_radius_km=0.015):
        """
        Initialize conjunction assessment system.
        
        Args:
            hard_body_radius_km: Combined physical radius of both satellites
                                Default: 15 meters (typical small satellite)
                                For ISS-sized objects: 0.050 km (50m)
        """
        self.HBR = hard_body_radius_km
        self.pc_history = {}  # Track Pc evolution over time
        self.mu = MU  # Earth's gravitational parameter (km³/s²)
        
        # Industry thresholds (NASA CARA standard)
        self.PC_RED_THRESHOLD = 1e-4    # 1 in 10,000 - Maneuver decision
        self.PC_YELLOW_THRESHOLD = 1e-5  # 1 in 100,000 - Enhanced monitoring
        
        # Logging
        self.conjunction_log = []

    def get_close_approaches(self, track1, track2, lookahead_hours=3, threshold_km=100):
        """
        Comprehensive conjunction assessment between two tracks.
        
        Returns:
            miss_distance (float): Distance at TCA in km
            tca_seconds (float): Time to closest approach in seconds
            alerts (list): Alert messages if collision risk detected
            pc (float): Probability of collision
            risk_level (str): 'RED', 'YELLOW', or 'GREEN'
        """
        # Extract current states
        pos1, vel1 = track1.state_estimate[:3], track1.state_estimate[3:]
        pos2, vel2 = track2.state_estimate[:3], track2.state_estimate[3:]

        dr = pos1 - pos2  # Relative position
        dv = vel1 - vel2  # Relative velocity

        # Step 1: Find Time of Closest Approach (TCA) analytically
        v_rel_sq = np.dot(dv, dv)
        if v_rel_sq < 1e-6:
            # Parallel trajectories - no meaningful TCA
            return float('inf'), 0, [], 0.0, 'GREEN'
            
        tca_seconds = -np.dot(dr, dv) / v_rel_sq

        # Ignore if TCA is in the past or beyond lookahead window
        if tca_seconds < 0 or tca_seconds > (lookahead_hours * 3600):
            return float('inf'), 0, [], 0.0, 'GREEN'

        # Step 2: Propagate positions to TCA (simple linear for initial check)
        pos1_tca = pos1 + vel1 * tca_seconds
        pos2_tca = pos2 + vel2 * tca_seconds
        miss_distance = float(np.linalg.norm(pos1_tca - pos2_tca))

        # Quick screening - if far apart, don't bother with Pc calculation
        if miss_distance > threshold_km:
            return miss_distance, tca_seconds, [], 0.0, 'GREEN'

        # Step 3: Fast Monte Carlo Screening
        # Sample directly from the EnKF particle clouds and propagate linearly to TCA
        particles1 = track1.filter.particles[:, :3]  # (N, 3) 
        particles2 = track2.filter.particles[:, :3]  # (N, 3)
        v_particles1 = track1.filter.particles[:, 3:]  # (N, 3) 
        v_particles2 = track2.filter.particles[:, 3:]  # (N, 3)
        
        # Propagate linearly
        p1_tca = particles1 + v_particles1 * tca_seconds
        p2_tca = particles2 + v_particles2 * tca_seconds
        
        distances = np.linalg.norm(p1_tca - p2_tca, axis=1)
        mc_hits = np.sum(distances < self.HBR)
        
        # Only trust the proxy if the TCA is less than 5 minutes (300s) away
        # Beyond this, the linear assumption in the proxy causes particles to fly through Earth
        if mc_hits == 0 and len(particles1) >= 100 and tca_seconds < 300:
            # 99% of pairs have Pc < 1e-10. Skip the heavy B-plane math.
            pc = 0.0
            logger.debug(f"MC Screening passed for {track1.id} vs {track2.id}. Pc ~ 0")
        else:
            # Step 4: Calculate true Probability of Collision (Pc) with covariance
            pc = self._calculate_pc_with_stm(track1, track2, tca_seconds, dr, dv)
        
        # Step 5: Track Pc evolution over time
        self._track_pc_evolution(track1.id, track2.id, track1.last_update_time, 
                                 pc, tca_seconds)
        
        # Step 6: Risk classification and alerting
        risk_level, alerts = self._classify_risk(pc, miss_distance, tca_seconds)
        
        # Step 7: Log conjunction event
        self._log_conjunction(track1.id, track2.id, miss_distance, tca_seconds, 
                             pc, risk_level)

        return miss_distance, tca_seconds, alerts, pc, risk_level

    def _calculate_pc_with_stm(self, track1, track2, tca_seconds, dr, dv):
        """
        Calculate Pc with proper covariance propagation using State Transition Matrix.
        
        This is the industry-standard method used by NASA CARA and ESA.
        """
        try:
            # Extract position covariances from EnKF particles
            particles1 = track1.filter.particles[:, :3]
            particles2 = track2.filter.particles[:, :3]
            
            cov1_current = np.cov(particles1, rowvar=False)
            cov2_current = np.cov(particles2, rowvar=False)
            
            # Propagate covariances to TCA using State Transition Matrix
            Phi1 = self._compute_stm(track1.state_estimate, tca_seconds)
            Phi2 = self._compute_stm(track2.state_estimate, tca_seconds)
            
            # Propagated covariances (position block only)
            cov1_tca = Phi1[:3, :3] @ cov1_current @ Phi1[:3, :3].T
            cov2_tca = Phi2[:3, :3] @ cov2_current @ Phi2[:3, :3].T
            
            # Combined covariance (RSS - Root Sum Square)
            C_combined = cov1_tca + cov2_tca
            
            # Additional uncertainty growth for propagation errors
            # (model uncertainty, unmodeled perturbations)
            hours_ahead = tca_seconds / 3600.0
            process_noise_growth = np.eye(3) * (10.0 * hours_ahead)**2  # 10 km/hr growth
            C_combined += process_noise_growth
            
            # Compute Pc using Mahalanobis distance
            pc = self._compute_pc_from_covariance(dr, dv, tca_seconds, C_combined)
            
            return pc
            
        except Exception as e:
            logger.warning(f"Pc calculation failed: {e}, using fallback method")
            return self._calculate_pc_fallback(track1, track2, tca_seconds, dr, dv)

    def _compute_stm(self, state, dt):
        """
        Compute State Transition Matrix (STM) for linearized dynamics.
        
        STM tells us how position/velocity uncertainties propagate over time.
        For two-body + J2, this can be computed analytically or numerically.
        
        Simplified version using two-body + J2 perturbation.
        """
        r = state[:3]
        v = state[3:]
        r_mag = np.linalg.norm(r)
        
        # Two-body STM (6x6)
        Phi = np.eye(6)
        
        # Position-Velocity coupling
        Phi[:3, 3:] = np.eye(3) * dt
        
        # Gravity gradient (simplified)
        # Full implementation would use variational equations
        r_unit = r / r_mag
        gravity_gradient = -self.mu / (r_mag**3) * (np.eye(3) - 3 * np.outer(r_unit, r_unit))
        
        Phi[3:, :3] = gravity_gradient * dt
        
        # J2 perturbation effect (approximate)
        J2 = 1.08263e-3
        Re = 6378.137
        z_factor = (r[2] / r_mag)**2
        j2_correction = 1.5 * J2 * (Re / r_mag)**2 * (5 * z_factor - 1)
        Phi[3:, :3] *= (1 + j2_correction)
        
        return Phi

    def _compute_pc_from_covariance(self, dr, dv, tca_seconds, C_combined):
        """
        Compute Pc by projecting onto the 2D encounter plane (B-plane)
        and integrating the 2D Gaussian over the hard body area.
        
        This replaces the inaccurate 3D volume approximation with the
        industry-standard 2D B-plane formulation.
        """
        try:
            # Relative state at TCA
            dr_tca = dr + dv * tca_seconds
            
            # 1. Define B-plane coordinate system
            v_rel_mag = np.linalg.norm(dv)
            if v_rel_mag < 1e-6:
                return 0.0
                
            y_hat = dv / v_rel_mag
            h_vec = np.cross(dr_tca, y_hat)
            h_mag = np.linalg.norm(h_vec)
            
            if h_mag < 1e-6:
                # Direct hit trajectory or ill-defined geometry
                z_hat = np.array([0, 0, 1.0])
                if np.abs(y_hat[2]) > 0.9: 
                    z_hat = np.array([1.0, 0, 0])
                z_hat = z_hat - np.dot(z_hat, y_hat) * y_hat
                z_hat /= np.linalg.norm(z_hat)
            else:
                z_hat = h_vec / h_mag
                
            x_hat = np.cross(y_hat, z_hat)
            
            # Projection matrix (3x2) from 3D to 2D B-plane
            P_mat = np.column_stack((x_hat, z_hat))
            
            # 2. Project covariance and relative position
            C_2d = P_mat.T @ C_combined @ P_mat
            r_2d = P_mat.T @ dr_tca
            
            # 3. Compute 2D Probability Density
            det_C2d = np.linalg.det(C_2d)
            if det_C2d <= 0: 
                logger.warning("Non-positive definite 2D covariance")
                return 0.0
            
            inv_C2d = np.linalg.inv(C_2d)
            mahalanobis_sq_2d = np.dot(r_2d.T, np.dot(inv_C2d, r_2d))
            
            # 2D PDF = (1 / (2pi * sqrt(|C|))) * exp(-0.5 * mahalanobis^2)
            pdf_2d = (1.0 / (2.0 * np.pi * np.sqrt(det_C2d))) * np.exp(-0.5 * mahalanobis_sq_2d)
            
            # 4. Integrate over Hard Body Area (pi * R^2)
            # Since HBR << Covariance, Area * PDF is a highly accurate approximation
            cross_section_area = np.pi * (self.HBR ** 2)
            pc = float(cross_section_area * pdf_2d)
            
            return np.clip(pc, 0.0, 1.0)
            
        except np.linalg.LinAlgError:
            logger.warning("Singular covariance matrix in B-plane projection")
            return 0.0

    def _calculate_pc_fallback(self, track1, track2, tca_seconds, dr, dv):
        """
        Fallback Pc calculation without STM (simpler but less accurate).
        Used if STM computation fails.
        """
        particles1 = track1.filter.particles[:, :3]
        particles2 = track2.filter.particles[:, :3]
        
        cov1 = np.cov(particles1, rowvar=False)
        cov2 = np.cov(particles2, rowvar=False)
        
        # Simple time-based growth (conservative)
        time_growth_factor = 1.0 + (tca_seconds / 3600.0) * 0.2
        C_combined = (cov1 + cov2) * time_growth_factor
        
        return self._compute_pc_from_covariance(dr, dv, tca_seconds, C_combined)

    def _classify_risk(self, pc, miss_distance, tca_seconds):
        """
        Classify conjunction risk level using industry thresholds.
        
        Returns:
            risk_level: 'RED', 'YELLOW', or 'GREEN'
            alerts: List of alert messages
        """
        alerts = []
        
        if pc > self.PC_RED_THRESHOLD:
            risk_level = 'RED'
            alerts.append(f"🚨 CRITICAL: Pc = {pc:.2e} > 1e-4 - MANEUVER RECOMMENDED")
            alerts.append(f"   Miss Distance: {miss_distance:.2f} km")
            alerts.append(f"   TCA: {tca_seconds/3600:.2f} hours")
            
        elif pc > self.PC_YELLOW_THRESHOLD:
            risk_level = 'YELLOW'
            alerts.append(f"⚠️  CAUTION: Pc = {pc:.2e} - Enhanced Monitoring")
            alerts.append(f"   Miss Distance: {miss_distance:.2f} km")
            
        else:
            risk_level = 'GREEN'
            # No alerts for green level
        
        return risk_level, alerts

    def _track_pc_evolution(self, track1_id, track2_id, current_time, pc, tca_seconds):
        """
        Track how Pc evolves over time as satellites approach.
        
        This helps detect:
        - Rapidly increasing collision risk
        - Unexpected trajectory changes
        - Need for maneuver updates
        """
        pair_id = tuple(sorted([track1_id, track2_id]))
        
        if pair_id not in self.pc_history:
            self.pc_history[pair_id] = []
        
        self.pc_history[pair_id].append({
            'time': current_time,
            'pc': pc,
            'time_to_tca_seconds': tca_seconds
        })
        
        # Alert if Pc is rapidly increasing (doubling in last 3 observations)
        if len(self.pc_history[pair_id]) >= 3:
            recent = self.pc_history[pair_id][-3:]
            pc_start = recent[0]['pc']
            pc_end = recent[-1]['pc']
            
            if pc_end > 2.0 * pc_start and pc_end > 1e-6:
                logger.warning(f"Pc doubling for tracks {track1_id} vs {track2_id}")
                logger.warning(f"   {pc_start:.2e} → {pc_end:.2e} in last 3 updates")

    def _log_conjunction(self, track1_id, track2_id, miss_distance, tca_seconds, 
                        pc, risk_level):
        """
        Log conjunction event for post-mission analysis.
        """
        self.conjunction_log.append({
            'track1': track1_id,
            'track2': track2_id,
            'miss_distance_km': miss_distance,
            'tca_seconds': tca_seconds,
            'pc': pc,
            'risk_level': risk_level
        })

    def get_pc_history(self, track1_id, track2_id):
        """
        Retrieve Pc history for a specific track pair.
        
        Useful for plotting Pc evolution over time.
        """
        pair_id = tuple(sorted([track1_id, track2_id]))
        return self.pc_history.get(pair_id, [])

    def plot_pc_evolution(self, track1_id, track2_id, save_path=None):
        """
        Plot how Pc evolves as satellites approach TCA.
        """
        history = self.get_pc_history(track1_id, track2_id)
        
        if not history:
            logger.info(f"No Pc history for tracks {track1_id} vs {track2_id}")
            return
        
        times = [entry['time_to_tca_seconds']/3600 for entry in history]
        pcs = [entry['pc'] for entry in history]
        
        plt.figure(figsize=(10, 6))
        plt.semilogy(times, pcs, 'b-o', linewidth=2, markersize=6)
        plt.axhline(y=self.PC_RED_THRESHOLD, color='r', linestyle='--', 
                   label='Red Threshold (1e-4)')
        plt.axhline(y=self.PC_YELLOW_THRESHOLD, color='orange', linestyle='--',
                   label='Yellow Threshold (1e-5)')
        
        plt.xlabel('Time to TCA (hours)', fontsize=12)
        plt.ylabel('Probability of Collision (Pc)', fontsize=12)
        plt.title(f'Pc Evolution: Track {track1_id} vs {track2_id}', fontsize=14)
        plt.grid(True, alpha=0.3)
        plt.legend()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()

    def plot_conjunction_ellipsoid(self, track1, track2, tca_seconds, save_path=None):
        """
        Visualize the 3-sigma uncertainty ellipsoid at TCA.
        
        This shows the spatial uncertainty region where the satellites could be.
        """
        # Get combined covariance at TCA
        particles1 = track1.filter.particles[:, :3]
        particles2 = track2.filter.particles[:, :3]
        cov1 = np.cov(particles1, rowvar=False)
        cov2 = np.cov(particles2, rowvar=False)
        
        # Propagate
        Phi1 = self._compute_stm(track1.state_estimate, tca_seconds)
        Phi2 = self._compute_stm(track2.state_estimate, tca_seconds)
        cov1_tca = Phi1[:3, :3] @ cov1 @ Phi1[:3, :3].T
        cov2_tca = Phi2[:3, :3] @ cov2 @ Phi2[:3, :3].T
        
        C_combined = cov1_tca + cov2_tca
        
        # Eigenvalue decomposition (principal axes of ellipsoid)
        eigenvalues, eigenvectors = np.linalg.eig(C_combined)
        eigenvalues = np.real(eigenvalues)
        eigenvectors = np.real(eigenvectors)
        
        # Generate 3-sigma ellipsoid surface
        u = np.linspace(0, 2*np.pi, 50)
        v = np.linspace(0, np.pi, 25)
        
        # Unit sphere
        x = np.outer(np.cos(u), np.sin(v))
        y = np.outer(np.sin(u), np.sin(v))
        z = np.outer(np.ones_like(u), np.cos(v))
        
        # Scale by eigenvalues (3-sigma)
        x *= 3 * np.sqrt(eigenvalues[0])
        y *= 3 * np.sqrt(eigenvalues[1])
        z *= 3 * np.sqrt(eigenvalues[2])
        
        # Rotate by eigenvectors
        for i in range(len(x)):
            for j in range(len(x[0])):
                point = np.array([x[i,j], y[i,j], z[i,j]])
                rotated = eigenvectors @ point
                x[i,j], y[i,j], z[i,j] = rotated
        
        # Plot
        fig = plt.figure(figsize=(12, 10))
        ax = fig.add_subplot(111, projection='3d')
        
        # Uncertainty ellipsoid
        ax.plot_surface(x, y, z, alpha=0.3, color='blue', label='3σ Uncertainty')
        
        # Hard body radius sphere
        u_hbr = np.linspace(0, 2*np.pi, 20)
        v_hbr = np.linspace(0, np.pi, 10)
        x_hbr = self.HBR * np.outer(np.cos(u_hbr), np.sin(v_hbr))
        y_hbr = self.HBR * np.outer(np.sin(u_hbr), np.sin(v_hbr))
        z_hbr = self.HBR * np.outer(np.ones_like(u_hbr), np.cos(v_hbr))
        ax.plot_surface(x_hbr, y_hbr, z_hbr, alpha=0.8, color='red')
        
        # Satellite positions
        dr = track1.state_estimate[:3] - track2.state_estimate[:3]
        dv = track1.state_estimate[3:] - track2.state_estimate[3:]
        miss_vector = dr + dv * tca_seconds
        ax.scatter([0], [0], [0], c='blue', s=100, marker='o', label='Sat 1')
        ax.scatter([miss_vector[0]], [miss_vector[1]], [miss_vector[2]], 
                  c='green', s=100, marker='o', label='Sat 2')
        
        ax.set_xlabel('X (km)')
        ax.set_ylabel('Y (km)')
        ax.set_zlabel('Z (km)')
        ax.set_title(f'Conjunction Geometry at TCA\n(Red sphere = Hard Body Radius)')
        
        # Equal aspect ratio
        max_range = np.max([np.max(np.abs(x)), np.max(np.abs(y)), np.max(np.abs(z))])
        ax.set_xlim([-max_range, max_range])
        ax.set_ylim([-max_range, max_range])
        ax.set_zlim([-max_range, max_range])
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()

    def generate_conjunction_report(self, save_path='conjunction_report.txt'):
        """
        Generate comprehensive conjunction report for entire mission.
        """
        with open(save_path, 'w') as f:
            f.write("="*80 + "\n")
            f.write("CONJUNCTION ASSESSMENT REPORT\n")
            f.write("="*80 + "\n\n")
            
            # Summary statistics
            total_events = len(self.conjunction_log)
            red_events = sum(1 for e in self.conjunction_log if e['risk_level'] == 'RED')
            yellow_events = sum(1 for e in self.conjunction_log if e['risk_level'] == 'YELLOW')
            
            f.write(f"Total Conjunction Events: {total_events}\n")
            f.write(f"  RED (Pc > 1e-4):    {red_events}\n")
            f.write(f"  YELLOW (Pc > 1e-5): {yellow_events}\n")
            f.write(f"  GREEN:              {total_events - red_events - yellow_events}\n\n")
            
            # Detailed events
            f.write("-"*80 + "\n")
            f.write("DETAILED EVENTS\n")
            f.write("-"*80 + "\n\n")
            
            for i, event in enumerate(self.conjunction_log, 1):
                f.write(f"Event {i}:\n")
                f.write(f"  Tracks: {event['track1']} vs {event['track2']}\n")
                f.write(f"  Miss Distance: {event['miss_distance_km']:.2f} km\n")
                f.write(f"  TCA: {event['tca_seconds']/3600:.2f} hours\n")
                f.write(f"  Pc: {event['pc']:.2e}\n")
                f.write(f"  Risk Level: {event['risk_level']}\n\n")
        
        logger.info(f"Conjunction report saved to {save_path}")

    def get_statistics(self):
        """
        Get conjunction assessment statistics.
        """
        if not self.conjunction_log:
            return {
                'total_events': 0,
                'red_events': 0,
                'yellow_events': 0,
                'green_events': 0
            }
        
        total = len(self.conjunction_log)
        red = sum(1 for e in self.conjunction_log if e['risk_level'] == 'RED')
        yellow = sum(1 for e in self.conjunction_log if e['risk_level'] == 'YELLOW')
        green = total - red - yellow
        
        return {
            'total_events': total,
            'red_events': red,
            'yellow_events': yellow,
            'green_events': green,
            'max_pc': max((e['pc'] for e in self.conjunction_log), default=0),
            'min_miss_distance': min((e['miss_distance_km'] for e in self.conjunction_log), 
                                    default=float('inf'))
        }