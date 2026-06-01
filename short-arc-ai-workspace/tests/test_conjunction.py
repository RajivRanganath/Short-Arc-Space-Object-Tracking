import numpy as np
from datetime import datetime
from src.tracking.track_hypothesis import Track, Measurement
from src.tracking.conjunction import ConjunctionAssessment

# Mock Measurement to create a Track
def create_dummy_track(id, pos, vel):
    # Create a dummy measurement just to initialize the track
    m = Measurement(datetime.now(), np.array([0,0,0]), 0, 0, 0, np.eye(2))
    t = Track(id, m)
    # Force the state to our desired test state
    t.filter.particles = np.random.multivariate_normal(
        mean=np.concatenate([pos, vel]), cov=np.eye(6)*0.01, size=200
    )
    return t

def test_collision_warning():
    print("🚨 CONJUNCTION ASSESSMENT TEST")
    print("----------------------------")

    # Scenario: 90-degree crossing at [7000, 0, 0]
    # Sat A: Moving +Y towards the crossing
    pos_A = np.array([7000.0, -1000.0, 0.0]) 
    vel_A = np.array([0.0, 7.5, 0.0])       # Speed 7.5 km/s
    
    # Sat B: Moving +Z towards the crossing
    pos_B = np.array([7000.0, 0.0, -1000.0])
    vel_B = np.array([0.0, 0.0, 7.5])       # Speed 7.5 km/s
    
    # Create Tracks
    t1 = create_dummy_track(1, pos_A, vel_A)
    t2 = create_dummy_track(2, pos_B, vel_B)
    
    # Run Assessment
    ca = ConjunctionAssessment()
    
    # Look ahead 1 hour
    min_dist, tca, alerts, pc, risk = ca.get_close_approaches(t1, t2, lookahead_hours=1, threshold_km=500)
    
    print(f"💥 Minimum Distance: {min_dist:.2f} km")
    print(f"⏰ Time of Closest Approach: {tca}")
    print(f"🎲 Probability of Collision: {pc:.2e}")
    
    if min_dist < 200:
        print("✅ SUCCESS: Collision course detected!")
    else:
        print(f"❌ FAILURE: Missed the collision (Dist: {min_dist}km)")

if __name__ == "__main__":
    test_collision_warning()
