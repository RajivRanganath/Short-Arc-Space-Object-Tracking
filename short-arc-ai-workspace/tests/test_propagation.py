import numpy as np
from datetime import datetime
from src.orbital_mechanics.propagator import OrbitPropagator

def test_prediction():
    print("🔮 ORBIT PREDICTION TEST (24 HOURS)")
    print("-----------------------------------")
    
    prop = OrbitPropagator()
    
    # Initial State: A standard LEO satellite (ISS-like orbit)
    # Position: [6700, 0, 0] km (approx 320km altitude)
    # Velocity: [0, 7.7, 0] km/s (circular speed)
    initial_state = np.array([6700.0, 0, 0, 0, 7.7, 0])
    start_time = datetime.now()
    
    print(f"📍 Start Position: {initial_state[:3]} km")
    
    # 1. Predict 24 hours into the future
    future_state, future_time = prop.propagate_state(initial_state, start_time, duration_hours=24)
    
    print(f"🏁 End Position:   {future_state[:3]} km")
    
    # Check Drift (J2 usually causes the plane to rotate)
    drift = np.linalg.norm(future_state[:3] - initial_state[:3])
    print(f"📉 Total Displacement after 24h: {drift:.2f} km")
    
    # Simple Validation: It should have moved!
    if drift > 1000:
        print("✅ SUCCESS: Physics engine is driving the orbit.")
    else:
        print("❌ FAILURE: Satellite didn't move?")

if __name__ == "__main__":
    test_prediction()
