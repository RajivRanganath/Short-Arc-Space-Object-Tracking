import numpy as np
from datetime import datetime, timedelta
import os
import pytest
from src.tracking.track_hypothesis import Track, Measurement
from src.tracking.conjunction import ConjunctionAssessment

def test_conjunction_assessment_full():
    ca = ConjunctionAssessment()
    
    # Needs Track instances
    now = datetime.now()
    m1 = Measurement(now, np.array([0,0,0]), 0, 0, 0, np.eye(2), 0)
    t1 = Track(1, m1)
    # Set random positive trajectory
    t1.filter.particles = np.random.multivariate_normal(
        mean=np.array([7000.0, 0, 0, 0, 7.5, 0]), cov=np.eye(6)*0.01, size=200
    )
    
    m2 = Measurement(now, np.array([0,0,0]), 0, 0, 0, np.eye(2), 0)
    t2 = Track(2, m2)
    # Give it a trajectory that intersects right now
    t2.filter.particles = np.random.multivariate_normal(
        mean=np.array([7000.1, 0, 0, 0, 0, 7.5]), cov=np.eye(6)*0.01, size=200
    )
    
    # Test collision warning directly and log the event
    miss_distance, tca_seconds, alerts, pc, risk_level = ca.get_close_approaches(t1, t2)
    assert pc >= 0.0
    assert risk_level in ['RED', 'YELLOW', 'GREEN']
    
    # Track PC evolution with fake history
    ca._track_pc_evolution(1, 2, now, pc, tca_seconds)
    ca._track_pc_evolution(1, 2, now + timedelta(seconds=1), pc*2 + 0.0001, tca_seconds - 1)
    ca._track_pc_evolution(1, 2, now + timedelta(seconds=2), pc*4 + 0.0002, tca_seconds - 2)
    
    # Test properties and plots
    history = ca.get_pc_history(1, 2)
    assert len(history) >= 3 # At least the 3 manual ones
    
    ca._log_conjunction(1, 2, 0.0, 0.0, 0.1, 'RED')
    stats = ca.get_statistics()
    assert stats['total_events'] >= 1
    
    # Test plotting without display (file save)
    ca.plot_pc_evolution(1, 2, save_path="temp_pc.png")
    assert os.path.exists("temp_pc.png")
    os.remove("temp_pc.png")
    
    ca.plot_conjunction_ellipsoid(t1, t2, tca_seconds, save_path="temp_ellipsoid.png")
    assert os.path.exists("temp_ellipsoid.png")
    os.remove("temp_ellipsoid.png")
    
    # Test report generation
    ca.generate_conjunction_report(save_path="temp_report.txt")
    assert os.path.exists("temp_report.txt")
    os.remove("temp_report.txt")
