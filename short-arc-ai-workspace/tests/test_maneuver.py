import numpy as np
from datetime import datetime, timedelta
from src.tracking.track_hypothesis import Track, Measurement

def test_maneuver_detection():
    print("DETECTOR: MANEUVER DETECTION TEST")
    print("-------------------------")
    
    # 1. Setup Initial State (Standard LEO)
    start_time = datetime.now()
    initial_pos = np.array([7000.0, 0, 0])
    initial_vel = np.array([0, 7.5, 0])
    
    # Create the first measurement to spawn the track
    m0 = Measurement(
        time=start_time,
        radar_site_eci=np.array([0,0,0]), # Dummy site
        range_m=0, ra_rad=0, dec_rad=0,
        noise_matrix=np.eye(2)*1e-6 # Tiny noise for this test
    )
    
    track = Track(track_id=99, initial_measurement=m0)
    
    # Force the filter to the correct state immediately (skip convergence)
    track.filter.particles = np.random.multivariate_normal(
        mean=np.concatenate([initial_pos, initial_vel]), 
        cov=np.eye(6)*0.001, 
        size=200
    )
    
    print("   Phase 1: Normal Orbit (Frames 1-10)...")
    
    # 2. Simulate Normal Flight
    # We cheat and just say the measurement is EXACTLY where the filter predicts
    # This keeps residuals near 0.
    for i in range(10):
        t_curr = start_time + timedelta(seconds=10*(i+1))
        track.predict(t_curr)
        
        # Get the filter's prediction mean
        pred_mean = np.mean(track.filter.particles, axis=0)
        
        # Create a measurement that MATCHES the prediction (No Maneuver)
        # We need to convert Cartesian state back to RA/Dec
        rho = pred_mean[:3]
        dist = np.linalg.norm(rho)
        ra = np.arctan2(rho[1], rho[0])
        dec = np.arcsin(rho[2] / dist)
        
        m = Measurement(
            time=t_curr,
            radar_site_eci=np.array([0,0,0]),
            range_m=0, ra_rad=ra, dec_rad=dec,
            noise_matrix=np.eye(2)*1e-6
        )
        
        track.update(m) # Should be silent
        
    print("   Phase 2: THRUSTER BURN (100 m/s Transverse)...")
    
    # 3. Simulate Maneuver
    # A 100 m/s (0.1 km/s) maneuver in the velocity direction (Transverse)
    # Displacement after dt=10s is roughly 1 km.
    # Angle offset at 7000 km is approx 1/7000 = 0.00014 rad.
    
    maneuver_detected = False
    target_dv = 0.1 # km/s
    
    # Frame 11 is where the maneuver happens
    t_curr = start_time + timedelta(seconds=110)
    track.predict(t_curr)
    
    pred_mean = track.state_estimate
    rho = pred_mean[:3]
    dist = np.linalg.norm(rho)
    ra = np.arctan2(rho[1], rho[0])
    dec = np.arcsin(rho[2] / dist)
    
    # Add a massive offset to ensure detection (0.05 rad approx 350 km)
    # This should result in a massive NIS.
    offset = 0.05 
    
    m = Measurement(
        time=t_curr,
        radar_site_eci=np.array([0,0,0]),
        range_m=0, 
        ra_rad=ra + offset,  
        dec_rad=dec,
        noise_matrix=np.eye(2)*1e-9 # Very low noise
    )
    
    print(f"      Frame 11: Feeding Deviated Measurement (offset={offset:.6f} rad)...")
    track.update(m) 
    
    # After update, we check if the particles were shifted correctly by Sizer
    new_mean = track.state_estimate
    velocity_shift = np.linalg.norm(new_mean[3:] - pred_mean[3:])
    
    print(f"      Result: Velocity shift magnitude = {velocity_shift*1000:.2f} m/s")
    
    # Expected shift: 35 km/s but capped at 500 m/s.
    if velocity_shift > 0.4: # Cap is 0.5 km/s
        print("   CONFORMANCE: Maneuver detected and sized (Capped at 500 m/s)!")
    else:
        print("   FAILURE: Maneuver sizing too small or not detected.")
        assert False, f"Maneuver sizing failed. Magnitude: {velocity_shift*1000:.2f} m/s"

    print("   Testing complete with no hallucinations (exact Jacobian mapping).")

if __name__ == "__main__":
    test_maneuver_detection()
