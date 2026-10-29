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
    
    # First detection is held as tentative, not yet a track
    m1 = {
        'site_eci': [6378.0, 0, 0],
        'range': 1000.0,
        'ra': 0.1,
        'dec': 0.1,
    }

    system.process_frame(now, [m1])
    assert len(system.tracks) == 0
    assert len(system.tentative_tracks) == 1

    # A nearby second detection confirms it as a track
    m2 = {
        'site_eci': [6378.0, 0, 0],
        'range': 1000.0,
        'ra': 0.101,
        'dec': 0.101,
    }
    from datetime import timedelta
    next_time = now + timedelta(seconds=10)
    system.process_frame(next_time, [m2])
    assert len(system.tracks) == 1
    assert len(system.tentative_tracks) == 0

    # A third nearby detection updates that track instead of starting another
    m3 = {
        'site_eci': [6378.0, 0, 0],
        'range': 1000.0,
        'ra': 0.102,
        'dec': 0.102,
    }
    system.process_frame(next_time + timedelta(seconds=10), [m3])
    assert len(system.tracks) == 1
    
    # Clean up
    system.tracks.clear()
