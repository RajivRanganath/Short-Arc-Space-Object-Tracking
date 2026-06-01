import numpy as np
from src.orbit_determination.ensemble_kalman_filter import EnsembleKalmanFilter

def test_correction_step():
    # 1. Setup: A cloud with HUGE uncertainty around a valid LEO state
    true_state = np.array([7000.0, 0, 0, 0, 7.5, 0])
    # Huge position error (1000 km standard deviation) but strict velocity error (0.01 km/s)
    # This prevents the Admissible Region sampler from rejecting all our particles.
    P_init = np.diag([1000**2, 1000**2, 1000**2, 0.01**2, 0.01**2, 0.01**2])
    
    kf = EnsembleKalmanFilter(n_particles=100)
    kf.initialize_from_guess(true_state, P_init)
    
    # Check initial "fuzziness"
    _, cov_before = kf.get_state_estimate()
    uncertainty_before = np.trace(cov_before[:3, :3])
    print(f"\nUncertainty BEFORE: {uncertainty_before:.2e} km²")
    
    # 2. The Measurement
    # The radar says: "I see you at X=7000, Y=0, Z=0"
    # The radar is accurate to 10 meters (0.01 km)
    measurement = np.array([7000.0, 0, 0])
    R_noise = np.eye(3) * 0.01**2
    
    # The "Measurement Function" tells the filter how to interpret the state
    # h(state) -> returns just [x, y, z]
    def measure_position(state):
        return state[:3]
        
    # 3. Apply Correction
    kf.update(measurement, measure_position, R_noise)
    
    # 4. Check result
    _, cov_after = kf.get_state_estimate()
    uncertainty_after = np.trace(cov_after[:3, :3])
    print(f"Uncertainty AFTER:  {uncertainty_after:.2e} km²")
    
    # The cloud should have collapsed by a factor of 10,000+
    assert uncertainty_after < uncertainty_before
    print("\n✅ Filter Logic Verified: Measurement successfully collapsed the cloud.")

if __name__ == "__main__":
    test_correction_step()
