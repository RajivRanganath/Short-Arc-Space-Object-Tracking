# ORBIT GUARD AI — Gotchas, Alternatives & Vocabulary

---

## Failure Modes & Fixes

| Problem | Symptom | Root Cause | Fix (in code) |
|---------|---------|------------|----------------|
| **Ghost Tracks** | Spurious tracks at random positions | Every unassociated measurement spawns a track | Two-tier pruning: young tracks (<5 updates) need alt -200 to 6000 km, mature need 150-3000 km ([tracking_system.py:228-251](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/tracking_system.py#L228-L251)) |
| **Velocity Explosions** | Speed spikes to 50 km/s | Process noise too large (was 0.5 km) → particles diverge → Kalman gain too large | Reduced to 0.05 km, Numba-compiled velocity clamping 5-10 km/s ([ensemble_kalman_filter.py:46-64](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/orbit_determination/ensemble_kalman_filter.py#L46-L64)) |
| **Slant Range Confusion** | Track at wrong altitude (12,000 km instead of 800 km) | Using radar slant range as altitude | Solve quadratic \|R_site + ρ·L̂\|² = (Re+h)² for ρ ([track_hypothesis.py:88-113](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/tracking/track_hypothesis.py#L88-L113)) |
| **Lost Track Cascades** | All tracks pruned after 30s | Adaptive covariance inflation grew unbounded → uncertainty exploded | Fixed inflation = 1.02 instead of adaptive ([ensemble_kalman_filter.py:330-331](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/orbit_determination/ensemble_kalman_filter.py#L330-L331)) |
| **RA Wrap Errors** | 358° innovation instead of 2° | RA wraps at ±180° — naive subtraction fails | `innov[0] = (innov[0] + π) % 2π − π` everywhere ([ensemble_kalman_filter.py:360](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/orbit_determination/ensemble_kalman_filter.py#L360)) |
| **Near-Polar Singularity** | Prograde velocity direction undefined | r̂ × ẑ ≈ 0 when orbit pole-aligned | Fallback: cross with x̂ when \|h_dir\| < 0.1 ([ensemble_kalman_filter.py:25-31](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/orbit_determination/ensemble_kalman_filter.py#L25-L31)) |
| **Update Magnitude Explosions** | Single update shifts position by 1000+ km | Large Kalman gain × large innovation in early updates | Cap: max 200 km position shift, 1 km/s velocity shift per update ([ensemble_kalman_filter.py:366-377](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/orbit_determination/ensemble_kalman_filter.py#L366-L377)) |
| **False Maneuver Detections** | "Maneuver detected!" on passive debris | Normal filter transients trigger low-threshold anomaly detection | Raised threshold to 8σ (from 3σ) for debris ([track_hypothesis.py:33](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/tracking/track_hypothesis.py#L33)) |

---

## Alternatives Analysis

### Filter Choice

| Option | Tried? | Performance | Why Chosen/Rejected |
|--------|--------|-------------|---------------------|
| **EKF** (Extended Kalman) | Yes | ~85% | Jacobian linearization fails for 1/r³ gravity + exponential drag |
| **UKF** (Unscented Kalman) | Considered | ~90% estimated | Similar performance to EnKF, more complex sigma-point math, harder to explain |
| **EnKF** (Ensemble Kalman) ✅ | Yes | 92% | Handles nonlinearity without Jacobians; 200 particles = tractable; easy to visualize |
| **Particle Filter** | Considered | ~93% (10K particles) | Weight degeneracy in 6D; needs 50× more particles; 50× slower |

### Data Association

| Option | Tried? | Normal | Clutter | Why Chosen/Rejected |
|--------|--------|--------|---------|---------------------|
| **Nearest Neighbor** (greedy) | Tested | 70% | 40% | Too simple — picks closest without global optimization |
| **GNN** (Hungarian) ✅ | Yes | 92% | 54% | Optimal 1-to-1 assignment. Fast. Fails in clutter |
| **JPDA** (Probabilistic) ✅ | Yes | 92% | 88% | Handles ambiguity. 5× slower but far better in clutter |
| **MHT** (Multiple Hypothesis) | Considered | ~95% | ~90% | Exponential complexity O(m^n). Overkill for this scale |

### Physics Model

| Option | Tried? | Accuracy (1 hr) | Speed | Why Chosen/Rejected |
|--------|--------|-----------------|-------|---------------------|
| **Two-body only** | Yes | Drifts after 5 min | Fastest | Unusable for tracking beyond minutes |
| **Two-body + J2** | Yes | ~95% | Fast | Good but misses drag effects |
| **Two-body + J2 + Drag** ✅ | Yes | ~98% | Fast enough | Sweet spot: captures main perturbations |
| **+ SRP** ✅ | Yes | ~98.1% | Negligible cost | Small effect but essentially free to compute |
| **Full geopotential (J2-J6) + third body** | Considered | ~99% | 10× slower | <1% improvement for 10× cost |

### Process Noise Strategy

| Option | Tried? | Accuracy | Notes |
|--------|--------|----------|-------|
| **Fixed (0.05 km)** ✅ | Yes | 92% | Consistent, predictable, no feedback loops |
| **NIS-Adaptive** | Yes | 86% | Feedback loops cause velocity explosions on passive debris |
| **Covariance-based** | Implemented | Not tested | Simpler but less responsive to filter surprises |

### Visualization

| Option | Why Chosen/Rejected |
|--------|---------------------|
| **2D Matplotlib plots** | Can't show orbital geometry. Non-interactive. Boring for demos |
| **Cesium.js** | Heavy dependency. Overkill for a tracking demo |
| **Three.js + React** ✅ | Lightweight, React integration, GPU bloom effects, auto-rotate globe |
| **Particle dots for uncertainty** | 200 dots = cluttered + GPU-heavy. Replaced with shader glow |

---

## Technical Vocabulary

### Orbital Mechanics

| Term | Definition | Where Used |
|------|-----------|------------|
| **TLE** | Two-Line Element — 2 lines of text encoding 6 orbital elements + drag term | [data_loader.py](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/data_loader.py), [radar_sim.py](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/simulation/radar_sim.py) |
| **ECI** | Earth-Centered Inertial frame — origin at Earth's center, axes fixed to stars | All dynamics, filter state |
| **ECEF** | Earth-Centered Earth-Fixed — rotates with Earth at ω = 7.29e-5 rad/s | Visualization only ([run_live_3d_tracking.py](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/run_live_3d_tracking.py)) |
| **J2** | Second zonal harmonic (1.08263×10⁻³) — Earth's equatorial bulge | [perturbations.py](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/orbital_mechanics/perturbations.py) |
| **SRP** | Solar Radiation Pressure — photon momentum transfer | [perturbations.py](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/orbital_mechanics/perturbations.py) |
| **Epoch** | Reference time for orbital elements in a TLE | TLE parsing |
| **Keplerian elements** | (a, e, i, Ω, ω, ν) — 6 numbers fully defining an orbit | [kepler_utils.py](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/orbital_mechanics/kepler_utils.py) |
| **Semi-major axis (a)** | Half the longest diameter of the orbital ellipse (km) | Filter state (derived) |
| **Eccentricity (e)** | Shape: 0 = circle, 0-1 = ellipse, ≥1 = escape | Admissible region check |
| **Inclination (i)** | Tilt of orbit plane relative to equator (degrees) | Regime classification |
| **RAAN (Ω)** | Right Ascension of Ascending Node — where orbit crosses equator going north | Catalog correlation |
| **GMST** | Greenwich Mean Sidereal Time — angle between vernal equinox and Greenwich | ECI→ECEF rotation |

### Filtering & Estimation

| Term | Definition | Where Used |
|------|-----------|------------|
| **State vector** | [x, y, z, vx, vy, vz] — 6D position + velocity in km, km/s | [ensemble_kalman_filter.py](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/orbit_determination/ensemble_kalman_filter.py) |
| **Covariance (P)** | 6×6 matrix of uncertainties — diagonals = variances, off-diagonals = correlations | Filter output |
| **Innovation (y)** | z_measured − z_predicted — "surprise" of new measurement | EnKF update |
| **Kalman gain (K)** | Weighting matrix — how much to trust measurement vs prediction | EnKF update |
| **Particle** | One hypothesis of the object's state (one row of the ensemble) | EnKF |
| **Ensemble** | The full collection of 200 particles | EnKF |
| **NIS** | Normalized Innovation Squared: yᵀ S⁻¹ y — filter consistency check | Anomaly detection |
| **Process noise (Q)** | Added randomness per timestep to model unmodeled dynamics | EnKF propagation |
| **Measurement noise (R)** | Sensor uncertainty: (0.2°)² for angles, (5 km)² for range | Update step |
| **Covariance inflation** | Multiply particle deviations by 1.02× to prevent filter collapse | EnKF update |
| **RTN frame** | Radial-Transverse-Normal — orbit-aligned coordinate system | Process noise |
| **Admissible region** | Set of physically valid orbits (bound, above atmosphere) | Initialization |

### Multi-Target Tracking

| Term | Definition | Where Used |
|------|-----------|------------|
| **Track** | Hypothesis that a sequence of measurements belongs to one object | [track_hypothesis.py](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/tracking/track_hypothesis.py) |
| **Association** | Matching measurements to tracks (the "who is who?" problem) | [gnn_associator.py](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/association/gnn_associator.py), [jpda_associator.py](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/association/jpda_associator.py) |
| **Gate** | Mahalanobis distance threshold for accepting a match | χ² = 20 (GNN), 25 (JPDA) |
| **Pruning** | Deleting tracks that are lost, unphysical, or low-quality | [tracking_system.py](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/tracking_system.py) |
| **Track initiation** | Creating a new track from an unassociated measurement | [tracking_system.py](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/tracking_system.py) |
| **Hungarian algorithm** | O(n³) optimal assignment solver for bipartite matching | [gnn_associator.py](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/association/gnn_associator.py) |
| **β (beta)** | JPDA association probability — P(measurement j → track t) | [jpda_associator.py](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/association/jpda_associator.py) |
| **Clutter density (λ)** | Expected false alarms per unit measurement-space volume | JPDA parameter |
| **Quality metric (Q)** | Track reliability: match_ratio × NIS_consistency | [track_hypothesis.py](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/tracking/track_hypothesis.py) |

### Conjunction & Safety

| Term | Definition | Where Used |
|------|-----------|------------|
| **Conjunction** | Two objects passing close to each other | [conjunction.py](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/test_conjunction.py) |
| **TCA** | Time of Closest Approach — when miss distance is minimum | Analytical: t = −(Δr·Δv)/\|Δv\|² |
| **Miss distance** | Minimum separation between two objects at TCA (km) | B-plane projection |
| **Pc** | Probability of Collision — integral of Gaussian over hard body | B-plane method |
| **HBR** | Hard Body Radius — combined physical size (default 15 m) | [conjunction.py](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/test_conjunction.py) |
| **B-plane** | 2D plane perpendicular to relative velocity at TCA | Pc computation |
| **STM** | State Transition Matrix — maps initial uncertainty to final | Covariance propagation |
| **RED/YELLOW/GREEN** | Risk levels: Pc > 1e-4 / 1e-5 / below | NASA CARA thresholds |
