import numpy as np
from src.orbit_determination.ensemble_kalman_filter import EnsembleKalmanFilter

def test_particle_cloud():
    # 1. Start with a "Truth" (LEO orbit, ~600km altitude)
    true_state = np.array([7000.0, 0, 0, 0, 7.55, 0])
    
    # 2. Define our uncertainty
    # We are fairly sure about position (10km error), 
    # but UNSURE about velocity (0.01 km/s error)
    P = np.diag([10**2, 10**2, 10**2, 0.01**2, 0.01**2, 0.01**2])
    
    # 3. Initialize Filter
    kf = EnsembleKalmanFilter(n_particles=50)
    kf.initialize_from_guess(true_state, P)
    
    # 4. Check initial spread
    mean, cov = kf.get_state_estimate()
    initial_pos_spread = np.trace(cov[:3, :3])
    print(f"\nInitial Position Variance: {initial_pos_spread:.2e}")
    
    # 5. Propagate for 10 mins (600s)
    # The particles should drift apart!
    kf.propagate(600.0)
    
    # 6. Check final spread
    mean_new, cov_new = kf.get_state_estimate()
    final_pos_spread = np.trace(cov_new[:3, :3])
    print(f"Final Position Variance:   {final_pos_spread:.2e}")
    
    # 7. Verification
    # The cloud MUST have expanded (Entropy increases without data)
    assert final_pos_spread > initial_pos_spread
    print("\n✅ Physics Validated: The cloud is expanding as expected.")

if __name__ == "__main__":
    test_particle_cloud()
