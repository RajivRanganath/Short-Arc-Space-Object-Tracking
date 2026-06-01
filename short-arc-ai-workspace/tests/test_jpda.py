import numpy as np
import pytest
from src.association.jpda_associator import JPDAAssociator
from src.tracking.track_hypothesis import Track, Measurement
import datetime

def test_jpda_associator_empty():
    jpda = JPDAAssociator()
    assignments, unassigned_t, unassigned_m = jpda.associate([], [])
    assert len(assignments) == 0
    assert len(unassigned_t) == 0
    assert len(unassigned_m) == 0

def test_jpda_associator_logic():
    jpda = JPDAAssociator(gate_threshold=100.0)
    
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    
    dummy_meas = Measurement(
        time=now_dt,
        ra_rad=0.0,
        dec_rad=0.0,
        radar_site_eci=np.array([6378.0, 0, 0]),
        range_km=0.0,
        range_m=0.0,
        noise_matrix=np.eye(2)
    )
    
    # Create dummy track
    track = Track(track_id=1, initial_measurement=dummy_meas)
    track.filter.particles = np.random.multivariate_normal(
        mean=np.array([7000.0, 0, 0, 0, 7.5, 0]), cov=np.eye(6)*0.01, size=200
    )
    track.predict(now_dt + datetime.timedelta(seconds=10))
    
    # Create perfectly matching measurement
    # The track particles will predict some RA/DEC.
    # We need to find the expected RA/DEC.
    site_eci = np.array([6378.0, 0, 0])
    rho = track.state_estimate[:3] - site_eci
    dist = np.linalg.norm(rho)
    ra = np.arctan2(rho[1], rho[0])
    dec = np.arcsin(rho[2] / dist)
    
    meas = Measurement(
        time=now_dt + datetime.timedelta(seconds=10),
        ra_rad=ra,
        dec_rad=dec,
        radar_site_eci=site_eci,
        range_km=dist,
        range_m=dist*1000.0,
        noise_matrix=np.eye(2)
    )
    
    assignments, unassigned_t, unassigned_m = jpda.associate([track], [meas])
    
    assert len(assignments) == 1
    assert assignments[0][0] == 0 # Track idx 0
    assert assignments[0][1] == 0 # Meas idx 0
    assert assignments[0][2] > 0.0 # Prob > 0
    
    stats = jpda.get_statistics()
    assert stats['total_associations'] == 1
    
    # Test far away measurement
    meas_far = Measurement(
        time=now_dt + datetime.timedelta(seconds=10),
        ra_rad=ra + 0.5, # Huge error
        dec_rad=dec + 0.5,
        radar_site_eci=site_eci,
        range_km=dist,
        range_m=dist*1000.0,
        noise_matrix=np.eye(2)
    )
    
    assignments_far, unassigned_t_far, unassigned_m_far = jpda.associate([track], [meas_far])
    assert len(assignments_far) == 0
    assert len(unassigned_t_far) == 1
    assert len(unassigned_m_far) == 1

def test_jpda_statistics_empty():
    jpda = JPDAAssociator()
    stats = jpda.get_statistics()
    assert stats['total_associations'] == 0
