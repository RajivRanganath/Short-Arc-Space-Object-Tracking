import numpy as np
import pytest
from src.tracking.catalog import TLECatalog

def test_catalog_correlation():
    catalog = TLECatalog()
    
    # Test unbound orbit (energy >= 0)
    r_unbound = np.array([10000.0, 0, 0])
    v_unbound = np.array([0, 15.0, 0]) # Escape velocity
    match = catalog.correlate_track(r_unbound, v_unbound)
    assert match is None
    
    # Test ISS match
    # a = 6790.0
    # For circular, v = sqrt(mu/a)
    mu = 398600.4418
    v_iss = np.sqrt(mu / 6790.0)
    
    r_iss = np.array([6790.0, 0.0, 0.0])
    v_iss_vec = np.array([0.0, v_iss * np.cos(np.deg2rad(51.6)), v_iss * np.sin(np.deg2rad(51.6))])
    
    # Adjust velocity to roughly match inclination
    # h = r x v
    
    # Simplest way: just mock the correlation inputs or use an exact state
    # We will compute state for exactly 6790, e=0, i=51.6
    from src.orbital_mechanics.kepler_utils import keplerian_to_cartesian
    r_exact, v_exact = keplerian_to_cartesian(6790.0, 0.0, np.deg2rad(51.6), 0.0, np.deg2rad(150.0), 0.0)
    
    match = catalog.correlate_track(r_exact, v_exact)
    assert match is not None
    assert match[0] == 25544
    assert match[1] == "ISS"
    assert match[2] > 0.8 # High confidence
    
    # Test mismatch
    r_mismatch, v_mismatch = keplerian_to_cartesian(8000.0, 0.1, np.deg2rad(90.0), 0.0, 0.0, 0.0)
    match_miss = catalog.correlate_track(r_mismatch, v_mismatch)
    assert match_miss is None
    
    # Test exception handling (pass invalid arrays)
    match_err = catalog.correlate_track(None, None)
    assert match_err is None
