import numpy as np
from src.orbit_determination.gauss_iod import RobustIOD

def test_robust_iod_structure():
    solver = RobustIOD()
    
    # Simulate a tracking pass
    obs1 = {
        'time': 0, 'ra': 0.5, 'dec': 0.2, 
        'site_ecef': [6378.137, 0, 0]
    }
    obs2 = {
        'time': 60, 'ra': 0.51, 'dec': 0.21, 
        'site_ecef': [6378.137, 0, 0]
    }
    obs3 = {
        'time': 120, 'ra': 0.52, 'dec': 0.22, 
        'site_ecef': [6378.137, 0, 0]
    }
    
    state = solver.solve(obs1, obs2, obs3)
    assert len(state) == 6
    print("\n✅ Robust IOD Module is correctly linked!")

if __name__ == "__main__":
    test_robust_iod_structure()
