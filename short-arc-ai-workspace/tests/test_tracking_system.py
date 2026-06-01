import pytest
import numpy as np
from datetime import datetime, timezone
from src.tracking_system import MultiObjectTracker

def test_tracking_system_pipeline():
    system = MultiObjectTracker()
    
    now = datetime.now(timezone.utc)
    
    # Send a frame with no measurements
    system.process_frame(now, [])
    assert len(system.tracks) == 0
    
    # Send a frame with one measurement (initializes track)
    m1 = {
        'site_eci': [6378.0, 0, 0],
        'range': 1000.0,
        'ra': 0.1,
        'dec': 0.1,
    }
    
    system.process_frame(now, [m1])
    assert len(system.tracks) == 1
    
    # Send another frame with a nearby measurement (updates track)
    m2 = {
        'site_eci': [6378.0, 0, 0],
        'range': 1000.0,
        'ra': 0.101,
        'dec': 0.101,
    }
    from datetime import timedelta
    next_time = now + timedelta(seconds=10)
    system.process_frame(next_time, [m2])
    assert len(system.tracks) == 1 # Still 1 track, should be updated
    
    # Clean up
    system.tracks.clear()
