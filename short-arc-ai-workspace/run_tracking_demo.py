from src.data_loader import download_fengyun_data
from src.simulation.radar_sim import RadarSimulator
from src.tracking_system import MultiObjectTracker
from datetime import datetime, timezone, timedelta
import numpy as np

def run_mission():
    print("==================================================")
    print("🛰️  ORBIT GUARD AI - MISSION CONTROL (MONTH 1)")
    print("==================================================")

    # 1. Get Data
    # (Only downloads if file is missing)
    try:
        with open('data/fengyun_1c.txt', 'r') as f:
            lines = f.readlines()
            # Pick a random object from the file to track
            idx = 30  # Let's track Object #10
            l1 = lines[idx*3 + 1].strip()
            l2 = lines[idx*3 + 2].strip()
            print(f"🎯 Target Selected: Object #{idx}")
    except:
        print("❌ Data missing. Please run src/data_loader.py first.")
        return

    # 2. Simulate Radar Pass
    print("\n📡 INITIALIZING RADAR SIMULATION...")
    sim = RadarSimulator()
    now = datetime.now(timezone.utc)
    
    # Generate 10 measurements over 60 seconds (One every 6 seconds)
    observations = sim.generate_arc(l1, l2, now, duration_sec=180, step_sec=6)

    # 3. Handover to Tracking System
    print("\n⚙️  HANDING OVER TO TRACKING AI...")
    tracker = MultiObjectTracker(association_method='jpda')
    
    for obs in observations:
        # Create a datetime object using the start time and the observation's 'time' offset in seconds
        current_time = now + timedelta(seconds=obs['time'])
        tracker.process_frame(current_time, [obs])
        
    estimated_state = tracker.tracks[0].state_estimate if tracker.tracks else np.zeros(6)


    
    # 4. Comprehensive Validation
    print("\n🔍 DETAILED DIAGNOSTICS")
    print("=" * 50)
    
    # Position Analysis
    r_vec = estimated_state[:3]
    r_mag_km = np.linalg.norm(r_vec)
    altitude_km = r_mag_km - 6378.137
    
    print(f"Position Vector (km):     {r_vec}")
    print(f"Position Magnitude:       {r_mag_km:.2f} km")
    print(f"Altitude:                 {altitude_km:.2f} km")
    
    # Velocity Analysis (Auto-Detect Units)
    v_vec = estimated_state[3:]
    v_mag_raw = np.linalg.norm(v_vec)
    
    if v_mag_raw > 100:  # Likely m/s
        v_mag_km_s = v_mag_raw / 1000
        print(f"Velocity Magnitude (raw): {v_mag_raw:.2f} m/s")
        print(f"Speed (converted):        {v_mag_km_s:.2f} km/s")
    else:  # Already km/s
        v_mag_km_s = v_mag_raw
        print(f"Speed:                    {v_mag_km_s:.2f} km/s")
        
    # Orbital Parameters (Physics Check)
    # Period T = 2*pi * sqrt(a^3 / mu)
    orbital_period_min = 2 * np.pi * np.sqrt(r_mag_km**3 / 398600.4418) / 60
    
    # Expected Circular Speed
    expected_circular_speed = np.sqrt(398600.4418 / r_mag_km)
    speed_error_pct = abs(v_mag_km_s - expected_circular_speed) / expected_circular_speed * 100

    print("\n✅ VALIDATION CHECKS")
    print("=" * 50)
    checks_passed = 0
    checks_total = 4

    # Check 1: Altitude (LEO is 300-2000 km)
    if 300 < altitude_km < 2000:
        print(f"✅ Altitude ({altitude_km:.0f} km) is in LEO range")
        checks_passed += 1
    else:
        print(f"❌ Altitude ({altitude_km:.0f} km) is OUTSIDE LEO (300-2000 km)")

    # Check 2: Speed (LEO is 7-8 km/s)
    if 7.0 < v_mag_km_s < 8.0:
        print(f"✅ Speed ({v_mag_km_s:.2f} km/s) is realistic for LEO")
        checks_passed += 1
    else:
        print(f"⚠️ Speed ({v_mag_km_s:.2f} km/s) is atypical (Expected 7-8 km/s)")

    # Check 3: Orbital Period (LEO is 85-110 min)
    if 85 < orbital_period_min < 110:
        print(f"✅ Orbital Period ({orbital_period_min:.1f} min) matches LEO physics")
        checks_passed += 1
    else:
        print(f"❌ Orbital Period ({orbital_period_min:.1f} min) is unusual")

    # Check 4: Circularity (Is the physics consistent?)
    if speed_error_pct < 10:
        print(f"✅ Speed matches circular orbit assumption ({speed_error_pct:.1f}% deviation)")
        checks_passed += 1
    else:
        print(f"⚠️ Speed deviates from circular orbit logic by {speed_error_pct:.1f}%")

    print(f"\n🎯 SCORE: {checks_passed}/{checks_total} checks passed")
    
    if checks_passed == checks_total:
        print("🏆 PERFECT TRACK - All physics validated!")
    elif checks_passed >= checks_total - 1:
        print("✅ GOOD TRACK - Minor deviations acceptable")
    else:
        print("⚠️ REVIEW NEEDED - Significant anomalies detected")

if __name__ == "__main__":
    run_mission()
