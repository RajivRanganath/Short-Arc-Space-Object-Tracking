import numpy as np
from src.orbital_mechanics.kepler_utils import keplerian_to_cartesian

def test_geostationary_orbit():
    # GEO parameters: Circular (e=0), Equatorial (i=0)
    a, e, i, omega, Omega, nu = 42164.0, 0.0, 0.0, 0.0, 0.0, 0.0
    
    r, v = keplerian_to_cartesian(a, e, i, omega, Omega, nu)
    
    # Assert Position is correct (approx [42164, 0, 0])
    assert np.allclose(r, [42164.0, 0, 0], atol=1e-1)
    print("\n✅ Keplerian to Cartesian conversion works!")
    print(f"Position Vector: {r}")

if __name__ == "__main__":
    test_geostationary_orbit()
