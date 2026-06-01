import numpy as np

def keplerian_to_cartesian(a, e, i, omega, Omega, nu, mu=398600.4418):
    """
    Convert Keplerian elements to Cartesian state vector (ECI frame).
    """
    # 1. Compute distance (r) and speed (v) in the perifocal frame (PQW)
    p = a * (1 - e**2)
    r_val = p / (1 + e * np.cos(nu))
    
    r_pqw = np.array([r_val * np.cos(nu), r_val * np.sin(nu), 0.0])
    
    v_fac = np.sqrt(mu / p)
    v_pqw = np.array([-v_fac * np.sin(nu), v_fac * (e + np.cos(nu)), 0.0])
    
    # 2. Rotation Matrix (PQW -> ECI)
    c_O, s_O = np.cos(Omega), np.sin(Omega)
    c_w, s_w = np.cos(omega), np.sin(omega)
    c_i, s_i = np.cos(i), np.sin(i)
    
    R = np.array([
        [c_O*c_w - s_O*s_w*c_i, -c_O*s_w - s_O*c_w*c_i,  s_O*s_i],
        [s_O*c_w + c_O*s_w*c_i, -s_O*s_w + c_O*c_w*c_i, -c_O*s_i],
        [s_w*s_i,                c_w*s_i,                c_i]
    ])
    
    return R @ r_pqw, R @ v_pqw

def cartesian_to_keplerian(r_vec, v_vec, mu=398600.4418):
    """
    Convert Cartesian state vector (ECI) to Keplerian elements.
    Returns: (a, e, i, omega, Omega, nu)
    """
    r = np.linalg.norm(r_vec)
    v = np.linalg.norm(v_vec)
    
    # 1. Specific Angular Momentum
    h_vec = np.cross(r_vec, v_vec)
    h = np.linalg.norm(h_vec)
    
    # 2. Inclination
    cos_i = np.clip(h_vec[2] / h, -1.0, 1.0)
    i = np.arccos(cos_i)
    
    # 3. Node vector
    n_vec = np.cross([0, 0, 1], h_vec)
    n = np.linalg.norm(n_vec)
    
    # 4. Right Ascension of Ascending Node (RAAN)
    if n != 0:
        Omega = np.arccos(n_vec[0] / n)
        if n_vec[1] < 0:
            Omega = 2 * np.pi - Omega
    else:
        Omega = 0 # Equatorial orbit
        
    # 5. Eccentricity vector
    e_vec = ((v**2 - mu/r) * r_vec - np.dot(r_vec, v_vec) * v_vec) / mu
    e = np.linalg.norm(e_vec)
    
    # 6. Argument of perigee
    if n > 1e-10:
        if e > 1e-10:
            cos_w = np.clip(np.dot(n_vec, e_vec) / (n * e), -1.0, 1.0)
            omega = np.arccos(cos_w)
            if e_vec[2] < 0:
                omega = 2 * np.pi - omega
        else:
            omega = 0
    else:
        omega = 0 # Equatorial
        
    # 7. True Anomaly
    if e > 1e-10:
        nu_cos = np.dot(e_vec, r_vec) / (e * r)
        nu = np.arccos(np.clip(nu_cos, -1.0, 1.0))
        if np.dot(r_vec, v_vec) < 0:
            nu = 2 * np.pi - nu
    else:
        # Circular orbit: use angle from node or X-axis
        if n != 0:
            nu_cos = np.dot(n_vec, r_vec) / (n * r)
            nu = np.arccos(np.clip(nu_cos, -1.0, 1.0))
            if r_vec[2] < 0:
                nu = 2 * np.pi - nu
        else:
            nu = np.arctan2(r_vec[1], r_vec[0])
            if nu < 0: nu += 2*np.pi
            
    # 8. Semi-major axis
    energy = 0.5 * v**2 - mu / r
    if np.abs(energy) > 1e-10:
        a = -mu / (2 * energy)
    else:
        a = np.inf # Parabolic
        
    return a, e, i, omega, Omega, nu
