import numpy as np
from datetime import datetime
from src.tracking.track_hypothesis import Track, Measurement
from src.association.gnn_associator import GlobalNearestNeighbor

from datetime import datetime

def create_dummy_track(id, mean_pos):
    """Creates a track with a particle cloud around a mean position"""
    class DummyMeas:
        def __init__(self):
            self.time = datetime.now()
            self.ra = 0
            self.dec = 0
            self.ra_rad = 0
            self.dec_rad = 0
            self.site_ecef = [0,0,0]
            self.radar_site_eci = [0,0,0]
            self.range = 1000.0
            
    # Instantiate with fake measurement
    t = Track(track_id=id, initial_measurement=DummyMeas())
    
    # Overwrite the particles with our specific mean_pos
    particles = np.random.multivariate_normal(
        mean=np.concatenate([mean_pos, [0, 7.5, 0]]), # [x,y,z, vx,vy,vz]
        cov=np.eye(6) * 0.1, 
        size=t.filter.n
    )
    t.filter.particles = particles
    return t

def create_dummy_measurement(pos, radar_pos):
    """Creates a measurement from a position relative to a radar"""
    # Vector from radar to target
    rho = pos - radar_pos
    dist = np.linalg.norm(rho)
    ra = np.arctan2(rho[1], rho[0])
    dec = np.arcsin(rho[2] / dist)
    
    return Measurement(
        time=datetime.now(),
        radar_site_eci=radar_pos,
        range_m=dist*1000,
        ra_rad=ra,
        dec_rad=dec,
        noise_matrix=np.eye(2) # Placeholder
    )

def test_gnn_crossing():
    print("\n⚔️  TEST: SATELLITE CROSSING SCENARIO")
    
    # 1. Setup: Radar at [0,0,0] for simplicity
    radar_pos = np.array([0, 0, 0])
    
    # 2. Create Two Satellites (Tracks)
    # Sat 1 is at X=1000
    t1 = create_dummy_track(id=1, mean_pos=np.array([1000, 0, 0]))
    # Sat 2 is at X=2000
    t2 = create_dummy_track(id=2, mean_pos=np.array([2000, 0, 0]))
    
    tracks = [t1, t2]
    
    # 3. Create Two Measurements
    # Meas A corresponds to Sat 1
    m_A = create_dummy_measurement(np.array([1000, 0, 0]), radar_pos)
    # Meas B corresponds to Sat 2
    m_B = create_dummy_measurement(np.array([2000, 0, 0]), radar_pos)
    
    measurements = [m_A, m_B]
    
    # 4. Run GNN
    gnn = GlobalNearestNeighbor()
    assignments, unassigned_t, unassigned_m = gnn.associate(tracks, measurements)
    
    # 5. Verify Results
    print(f"   Assignments found: {assignments}")
    
    # We expect: (0, 0) -> Track 0 matched Meas 0
    #            (1, 1) -> Track 1 matched Meas 1
    
    # Sorting to ensure order doesn't fail the test
    assignments.sort()
    
    if assignments == [(0, 0), (1, 1)]:
        print("✅ SUCCESS: GNN correctly untangled the tracks.")
    else:
        print(f"❌ FAILURE: Unexpected assignments: {assignments}")

if __name__ == "__main__":
    test_gnn_crossing()
