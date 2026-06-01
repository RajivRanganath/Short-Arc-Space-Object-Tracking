# ORBIT GUARD AI — Layered Explanation

---

## Level 1: The 5-Year-Old Version (1 paragraph)

Imagine thousands of broken pieces of a satellite zooming around Earth really fast — like tiny bullets in space. If one of these pieces hits a working satellite, it breaks it too, making MORE pieces. Our system is like a really smart air traffic controller for space: we have radar dishes on the ground that send beams up and listen for echoes. When we hear echoes, we know "something is up there!" But the echoes are fuzzy — like trying to hear someone whisper in a noisy room. So we use a clever trick: we make **200 guesses** about where each piece might be, then when the radar gives us a new clue, we keep the good guesses and throw away the bad ones. Over time, our guesses get really accurate! We show everything on a spinning 3D Earth so people can see the pieces flying around and get warned if two pieces might crash into each other. Pretty cool, right?

---

## Level 2: The Undergraduate Version (2 pages)

### What Problem Does It Solve?

The 2007 Chinese anti-satellite test destroyed the Fengyun-1C weather satellite at ~860 km altitude, creating **1,867+ tracked debris fragments** — the worst debris event in history. Each fragment orbits at ~7.5 km/s. A 10 cm piece at that speed carries the kinetic energy of a hand grenade. Our system tracks these fragments using simulated ground-based radar, determines their orbits, predicts future positions, warns of collisions, and visualizes everything in real-time 3D.

### System Architecture

The system has two halves:

**Python Backend** — The brain. Handles radar simulation, orbit determination, multi-object tracking, collision prediction, and radar scheduling. Runs a FastAPI WebSocket server that streams data at ~5 FPS.

**React Frontend** — The eyes. A Three.js-powered 3D globe showing tracked debris with orbit trails, uncertainty visualization (glow halos), conjunction warnings (red lines), and a mission control HUD with telemetry cards, event feeds, and statistics.

### Data Flow (10 Steps)

1. **TLE Download** — Fetch 1,867 Fengyun-1C debris TLEs from CelesTrak
2. **Scenario Generation** — Pick N random debris objects, simulate observations from 3 global radar stations (Bangalore, Svalbard, McMurdo) using Skyfield
3. **Radar Measurement** — Each station produces noisy RA/Dec/Range observations (0.01° angle noise, 5 km range noise) with elevation-based visibility filtering (>5°)
4. **Initial Orbit Determination** — First detection: estimate range from angular rate (v⊥/ω), compute position along line-of-sight, assume circular velocity
5. **EnKF Initialization** — Create 200 particles via admissible region sampling (reject particles with unphysical orbits: E≥0, perigee < 150 km)
6. **Prediction** — Propagate all particles forward using RK45 with two-body gravity + J2 + atmospheric drag + SRP. Add anisotropic RTN process noise (3× along-track)
7. **Data Association** — Match new measurements to existing tracks. GNN uses Hungarian algorithm on Mahalanobis distance matrix. JPDA computes probabilistic β weights
8. **EnKF Update** — Stochastic perturbed-observation update. Kalman gain K = P_xy · S⁻¹. Each particle updated with perturbed observation. Guardrails: 200 km position cap, 1 km/s velocity cap, LEO speed/altitude bounds
9. **Conjunction Assessment** — Screen all active track pairs. If distance < 1200 km: compute TCA analytically, propagate covariances via STM, project onto B-plane, compute Pc = π·R²·pdf₂D. MC pre-screening with EnKF particles for efficiency
10. **Visualization** — ECI→ECEF rotation (GMST from Skyfield), scale to Three.js coordinates, stream via WebSocket. Frontend renders with Bloom post-processing, orbit trails, uncertainty glows

### Key Algorithms

- **EnKF** — Ensemble Kalman Filter with 200 particles. Handles nonlinear orbital dynamics without linearization. Stochastic update with covariance inflation (1.02×)
- **GNN** — Global Nearest Neighbor. Builds Mahalanobis distance cost matrix, solves optimal assignment with Hungarian algorithm (O(n³)). Gate threshold χ² < 20
- **JPDA** — Joint Probabilistic Data Association. Computes association probabilities β_j using log-space likelihoods for numerical stability. Handles crossing trajectories and clutter
- **IOD** — Angular-rate Initial Orbit Determination. Estimates range from angular separation rate, then builds position/velocity assuming circular orbit

### Physics Model

Four force components: (1) Keplerian gravity −μ/r³·r, (2) J2 oblateness causing ~5°/day nodal precession, (3) Atmospheric drag using US Standard Atmosphere 1976 with 18 altitude bands and relative velocity (accounting for Earth rotation), (4) Solar radiation pressure with cylindrical Earth shadow model.

### Conjunction Assessment

Industry-aligned approach: analytical TCA → Monte Carlo pre-screening with EnKF particles → State Transition Matrix covariance propagation → B-plane projection → 2D Gaussian Pc integration. Risk thresholds: RED (Pc > 1e-4, maneuver recommended), YELLOW (Pc > 1e-5, enhanced monitoring).

---

## Level 3: The Expert Version

### 3.1 Ensemble Kalman Filter — Deep Dive

**Why EnKF over EKF?** Orbital dynamics are highly nonlinear (1/r³ gravity, trigonometric J2 terms, exponential drag). EKF linearizes around the mean via Jacobians — this introduces **linearization error** that accumulates over propagation intervals. EnKF avoids this entirely by propagating the full nonlinear dynamics through each particle independently.

**Why EnKF over Particle Filter?** Standard particle filters suffer from **weight degeneracy** in high dimensions (6D state space). After a few updates, one particle dominates all weights, requiring systematic resampling and 10,000+ particles for stable estimates. EnKF's linear update step (Kalman gain) implicitly performs optimal resampling, achieving comparable accuracy with only 200 particles.

**Initialization — Admissible Region Sampling** ([ensemble_kalman_filter.py:114-173](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/orbit_determination/ensemble_kalman_filter.py#L114-L173)):

Naive Gaussian sampling produces many unphysical particles (hyperbolic orbits, Earth-intersecting). The admissible region approach:
1. Sample from N(x₀, P₀) in batches of 100
2. **Reject** if: altitude < 100 km, orbital energy E ≥ 0 (unbound), perigee < 150 km
3. Repeat until 200 valid particles collected (up to 20,000 attempts)

This ensures every initial particle represents a plausible bound LEO orbit.

**Propagation — Vectorized Two-Body + Perturbations** ([ensemble_kalman_filter.py:178-242](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/orbit_determination/ensemble_kalman_filter.py#L178-L242)):

All 200 particles propagated simultaneously via vectorized `solve_ivp` (RK45). Dynamics: ẍ = −μ/r³·x + a_J2(x) + a_drag(x,v) + a_SRP(x). Process noise added in RTN frame:
- **Radial (R)**: 1× base noise (0.05 km) — radial uncertainty is small
- **Transverse (T)**: 3× base noise (0.15 km) — along-track uncertainty dominates
- **Normal (N)**: 0.5× base noise (0.025 km) — cross-track is most constrained

This anisotropy matches the physical reality: timing uncertainty maps to along-track position error.

**Update — Perturbed-Observation EnKF** ([ensemble_kalman_filter.py:294-401](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/orbit_determination/ensemble_kalman_filter.py#L294-L401)):

1. Project each particle through measurement function h(x) → predicted [RA, Dec, Range]
2. Compute ensemble cross-covariance P_xy and measurement covariance P_yy
3. Innovation covariance S = P_yy + R (measurement noise)
4. Kalman gain K = P_xy · S⁻¹
5. For each particle: perturb observation z̃ᵢ = z + ε (ε ~ N(0,R)), compute innovation, apply K·innovation with magnitude limiting
6. Post-update sanity check: if mean velocity or altitude outside LEO bounds → soft reset

The **covariance inflation** (1.02×) prevents filter collapse by slightly expanding the particle cloud before each update. The fixed value was chosen after adaptive inflation caused velocity explosions due to feedback loops.

### 3.2 Data Association — GNN vs JPDA

**GNN** ([gnn_associator.py](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/association/gnn_associator.py)):

1. Build cost matrix C[i,j] = Mahalanobis distance between track i prediction and measurement j
2. Gating: C[i,j] > χ²₃,₀.₉₉₉ = 20.0 → set to ∞
3. Solve assignment via `scipy.optimize.linear_sum_assignment` (Hungarian, O(n³))
4. Filter: only accept assignments within gate

**Strength**: Optimal 1-to-1 assignment. **Weakness**: Hard assignment — wrong in clutter/crossings.

**JPDA** ([jpda_associator.py](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/association/jpda_associator.py)):

1. Gate with χ² < 25.0
2. For each track, compute likelihoods L_j = exp(−d²_j/2) in log-space (subtract max for stability)
3. β_j = P_D·L_j / (λ_c + Σ P_D·L_k) where λ_c = clutter_density × gate_volume
4. Threshold at β > 0.05 to reject noise
5. Weighted update: combined innovation = Σ β_j · (z_j − ẑ)

**Key parameters**: P_D = 0.98 (radar rarely misses), clutter density = 1e-8 (space is clean).

### 3.3 Orbital Mechanics

**J2 Acceleration** ([perturbations.py:49-62](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/orbital_mechanics/perturbations.py#L49-L62)):

a_J2 = (3μJ₂R²_e)/(2r⁵) · [(5z²/r² − 1)x, (5z²/r² − 1)y, (5z²/r² − 3)z]

Physical effect: ~5°/day RAAN precession for sun-synchronous orbits at 800 km.

**Atmospheric Drag** ([perturbations.py:89-132](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/orbital_mechanics/perturbations.py#L89-L132)):

a_drag = −½ρ(h)·(C_D·A/m)·|v_rel|·v_rel, where v_rel = v_inertial − ω_⊕ × r

Density ρ(h) from US Std 1976 segmented model (18 bands from 0-1000 km). Above 1500 km: drag = 0. Cd = 2.2, A = 1 m², m = 100 kg. Effect at 800 km: ~0.44 m/day altitude decay.

**SRP** ([perturbations.py:64-87](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/orbital_mechanics/perturbations.py#L64-L87)):

Cannonball model: a_SRP = −P_sr·(1+C_r)·A/m · r̂_sun. Cylindrical shadow model zeroes SRP when satellite is behind Earth. Effect: ~10⁻⁸ km/s² (smallest perturbation).

### 3.4 Conjunction Assessment

**TCA Computation**: t_TCA = −(Δr · Δv) / |Δv|² (analytical from linear relative motion)

**B-Plane Projection** ([conjunction.py:193-254](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/tracking/conjunction.py#L193-L254)): Define encounter frame: ŷ = Δv/|Δv|, ẑ = (Δr×ŷ)/|...|, x̂ = ŷ×ẑ. Project combined covariance C₂D = Pᵀ·C₃D·P. Project miss distance r₂D = Pᵀ·Δr_TCA.

**Pc**: Approximate integral of 2D Gaussian over hard body circle: Pc = π·R²_HBR · (1/(2π√|C₂D|)) · exp(−½·r₂Dᵀ·C₂D⁻¹·r₂D). Valid when HBR << √(eigenvalues of C₂D).

**MC Pre-screening**: Propagate all 200 particle pairs linearly to TCA. If zero pairs closer than HBR (and TCA < 5 min): skip expensive B-plane math, Pc ≈ 0.

### 3.5 Information-Theoretic Scheduling

Information gain: IG = log|S| − log|R| = log(|P_zz + R|/|R|)

Boosted by missed detections: IG_final = IG + 0.5 × missed_count. Visibility check: cos(θ) > R_⊕/r_target (horizon constraint). Selects (radar, track) pair with highest IG. Effect: +14.8% tracking performance vs round-robin.

### 3.6 Design Decision Summary

| Decision | Chosen | Rejected | Rationale |
|---|---|---|---|
| Filter | EnKF (200 particles) | EKF, UKF, Particle Filter | Handles nonlinearity without Jacobians; 200 particles sufficient (PF needs 10K+) |
| Noise | Fixed 0.05/0.0005 | Adaptive NIS-based | Adaptive noise tested worse (86% vs 92%); passive debris has deterministic dynamics |
| Inflation | Fixed 1.02× | Adaptive scaling | Adaptive caused velocity explosions via feedback loops |
| Association | GNN + JPDA (both) | Nearest Neighbor, MHT | NN too simple (70%); MHT exponential complexity; GNN/JPDA demonstrate trade-offs |
| Physics | J2+Drag+SRP | Two-body only; Full geopotential | Two-body drifts after 5 min; full model <1% improvement, much slower |
| Pc method | B-plane 2D Gaussian | 3D volume, Monte Carlo only | B-plane is industry standard (NASA CARA); MC alone needs millions of samples |
| Frontend | WebSocket + Three.js | REST API + 2D plots | Real-time push vs request-response latency; 3D shows orbital geometry intuitively |
| Uncertainty viz | Glow halo | Particle dots | 200 dots cluttered/GPU-heavy; glow cleaner, shader-efficient |
