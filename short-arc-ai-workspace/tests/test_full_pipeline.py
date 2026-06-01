from src.simulation.radar_sim import RadarSimulator
from src.orbit_determination.gauss_iod import RobustIOD
from datetime import datetime, timezone

def test_pipeline():
    # 1. Load the first piece of debris from our file
    with open('data/fengyun_1c.txt', 'r') as f:
        lines = f.readlines()
        # TLEs are 3 lines each (Name, Line1, Line2)
        name = lines[0].strip()
        l1 = lines[1].strip()
        l2 = lines[2].strip()

    print(f"🎯 Target Acquired: {name}")

    # 2. Simulate a pass happening RIGHT NOW
    sim = RadarSimulator()
    now = datetime.now(timezone.utc)
    
    # Generate an arc long enough to guarantee a pass (24 hours)
    observations = sim.generate_arc(l1, l2, now, duration_sec=86400, step_sec=60)
    
    # We only need the first 3 valid observations for IOD
    observations = observations[:3]
    
    print(f"\n📡 Measurements Generated:")
    for obs in observations:
        print(f"   T+{obs['time']}s: RA={obs['ra']:.4f}, Dec={obs['dec']:.4f}")

    # 3. Solve for Orbit
    print("\n🧮 Running Robust Initial Orbit Determination...")
    iod = RobustIOD()
    
    # We use the first, middle, and last observation
    state_vector = iod.solve(observations[0], observations[1], observations[2])
    
    print(f"\n✅ Orbit Determined!")
    print(f"   Position (r): {state_vector[:3]} km")
    print(f"   Velocity (v): {state_vector[3:]} km/s")

if __name__ == "__main__":
    test_pipeline()
