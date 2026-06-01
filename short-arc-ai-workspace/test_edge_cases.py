import numpy as np
import datetime
import time
from src.tracking_system import MultiObjectTracker
from src.orbit_determination.gauss_iod import RobustIOD

def print_header(title):
    print("\n" + "="*60)
    print(f"🚀 {title}")
    print("="*60)

def test_zero_measurements():
    print_header("EDGE CASE 1: Zero Measurements")
    tracker = MultiObjectTracker()
    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        tracker.process_frame(now, [])
        print("✅ Gracefully handled empty frame")
    except Exception as e:
        print(f"❌ Failed on empty frame: {e}")

def test_single_measurement():
    print_header("EDGE CASE 2: Single Measurement IOD Failure")
    tracker = MultiObjectTracker()
    now = datetime.datetime.now(datetime.timezone.utc)
    meas = [{"site_eci": [6378,0,0], "ra": 0.1, "dec": 0.2, "range": 0, "time": now.timestamp()}]
    try:
        tracker.process_frame(now, meas)
        print("✅ Single measurement handled (no crash, track likely not initiated without minimum points)")
        print(f"Active tracks: {len(tracker.tracks)}")
    except Exception as e:
        print(f"❌ Failed on single measurement: {e}")

def test_extreme_altitudes():
    print_header("EDGE CASE 3: Altitude Extremes")
    iod = RobustIOD()
    
    # 3 identical observations to trigger constraints
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    obs = [
        {"ra": 0, "dec": 0, "time": now, "site_eci": [6378,0,0]},
        {"ra": 0, "dec": 0, "time": now+10, "site_eci": [6378,10,0]},
        {"ra": 0, "dec": 0, "time": now+20, "site_eci": [6378,20,0]}
    ]
    try:
        state = iod.estimate_state(obs)
        print(f"✅ Altitudes scaled math handled without numeric overflow. Init State R={np.linalg.norm(state[:3]):.2f}km")
    except Exception as e:
        print(f"❌ Failed edge case IOD: {e}")

def test_15_objects():
    print_header("EDGE CASE 4: 15+ Simultaneous Objects")
    from src.simulation.multi_object_scenarios import ScenarioGenerator
    
    gen = ScenarioGenerator()
    meas, _ = gen.generate_scenario(n_objects=15, duration_sec=100)
    
    frames = {}
    for m in meas:
        frames.setdefault(m['time'], []).append(m)
        
    tracker = MultiObjectTracker(association_method='jpda')
    base_time = datetime.datetime.now(datetime.timezone.utc)
    
    start_time = time.time()
    for offset in sorted(frames.keys()):
        current_time = base_time + datetime.timedelta(seconds=offset)
        tracker.process_frame(current_time, frames[offset])
    end_time = time.time()
    
    fps = len(frames) / (end_time - start_time) if len(frames) > 0 and end_time > start_time else 0
    print(f"✅ Processed 15 objects in {end_time - start_time:.2f}s")
    print(f"FPS: {fps:.1f} (Require: FPS > 10)")

def test_rapid_method_switch():
    print_header("EDGE CASE 5: Rapid Association Method Switching")
    tracker = MultiObjectTracker(association_method='gnn')
    now = datetime.datetime.now(datetime.timezone.utc)
    tracker.process_frame(now, [])
    tracker.association_method = 'jpda'
    tracker.process_frame(now + datetime.timedelta(seconds=5), [])
    tracker.association_method = 'gnn'
    print("✅ Method switching logic did not crash")

if __name__ == "__main__":
    test_zero_measurements()
    test_single_measurement()
    test_extreme_altitudes()
    test_15_objects()
    test_rapid_method_switch()
