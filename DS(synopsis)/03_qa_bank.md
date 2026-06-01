# ORBIT GUARD AI — Q&A Bank (50+ Questions)

---

## Category 1: Architecture & Design

**Q1: What problem does ORBIT GUARD solve?**
> **30s**: Tracks space debris from the 2007 Fengyun-1C breakup using simulated multi-radar observations, determines orbits, predicts collisions, and visualizes everything in real-time 3D.
> **Deep**: The system addresses the full Space Situational Awareness (SSA) pipeline: TLE ingestion → radar simulation → initial orbit determination → recursive Bayesian filtering → multi-target data association → conjunction screening → 3D visualization. It processes 1,867 cataloged debris objects from CelesTrak.

**Q2: Why Python + React instead of a unified stack?**
> Python: NumPy/SciPy/Skyfield ecosystem is the standard for astrodynamics computation. React Three Fiber: best-in-class WebGL rendering with React's component model. WebSocket bridges the two efficiently.

**Q3: Why WebSocket instead of REST?**
> Real-time streaming at ~5 FPS. REST requires client polling (latency + overhead). WebSocket maintains a persistent connection — server pushes frames whenever ready. Critical for live tracking UX.

**Q4: How many lines of code total?**
> ~3,000+ across 27 Python files and 14 React components. Core algorithms: ~2,000 lines Python. Frontend: ~1,000 lines JSX/CSS.

**Q5: What's the system's latency?**
> Frame delay is configurable: `max(0.1, 0.7/speed)` seconds. At speed=1.0, that's 0.7s per frame. Backend processing per frame: < 100ms (200-particle EnKF + association + conjunction screening).

**Q6: How does the backend stream data?**
> FastAPI WebSocket endpoint `/ws`. Each frame sends JSON: `{tracks, stations, events, stats, phase, conjunctions, simRunning}`. Tracks include 3D position (ECEF-scaled), particles, trail history, telemetry.

**Q7: Why three radar stations specifically?**
> Geometric coverage: Bangalore (equatorial, 13°N), Svalbard (polar, 78°N), McMurdo (antarctic, 78°S). This provides near-global visibility for LEO objects — at least one station can see most orbital passes.

**Q8: What makes this different from a toy demo?**
> Real TLE data (not synthetic orbits), full perturbation physics (J2+drag+SRP), industry-standard Pc computation (B-plane method), honest metrics (validated association rate via ground-truth tracking), and production-grade numerical safeguards.

**Q9: What are the main modules and their responsibilities?**
> See the Architecture table in the Cheat Sheet. Key pipeline: `data_loader` → `radar_sim` → `multi_object_scenarios` → `tracking_system` (orchestrator) → `track_hypothesis` → `ensemble_kalman_filter` + `gnn/jpda_associator` → [conjunction](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/tracking/conjunction.py#330-343) → `run_live_3d_tracking` (API) → React frontend.

**Q10: How is ground-truth tracking implemented?**
> Each simulated measurement carries a hidden `true_object_id`. The tracker never sees this. After association, `ground_truth_map` records which true objects each track matched. `validated_matches` counts correct associations by checking the dominant object per track.

---

## Category 2: Algorithms & Math

**Q11: Why EnKF instead of EKF?**
> EKF linearizes dynamics via Jacobians — introduces **linearization error** in nonlinear orbital dynamics (1/r³ gravity, exponential drag). EnKF propagates full nonlinear dynamics through each particle independently. No Jacobians needed.

**Q12: Why EnKF instead of Particle Filter?**
> Particle filters suffer from **weight degeneracy** in 6D state space — after a few updates, one particle dominates. Requires 10,000+ particles with systematic resampling. EnKF's Kalman gain acts as implicit optimal resampling with only 200 particles.

**Q13: Why exactly 200 particles?**
> Empirical sweet spot. 100 particles: position uncertainty ~350 km (too noisy). 500 particles: <50ms improvement but 2.5× slower. 200 particles: ~203 km uncertainty, <100ms processing time.

**Q14: What is the Kalman gain intuitively?**
> A "trust knob" between prediction and measurement. K = P_xy · (P_yy + R)⁻¹. If measurement noise R is large → K is small → trust prediction more. If prediction uncertainty P is large → K is large → trust measurement more.

**Q15: What is Mahalanobis distance?**
> "How many standard deviations away is this measurement from the prediction?" d² = (z−ẑ)ᵀ S⁻¹ (z−ẑ). Unlike Euclidean distance, it accounts for the shape and orientation of the uncertainty ellipse. If d² < χ²₃,₀.₉₉₉ = 16.27, we accept the match.

**Q16: What is the Hungarian algorithm?**
> Solves the optimal assignment problem in O(n³). Given a cost matrix C[tracks × measurements], finds the 1-to-1 matching that minimizes total cost. Used in GNN to find the globally optimal set of track-measurement pairs.

**Q17: How does JPDA handle ambiguity?**
> Instead of hard 1-to-1 assignment, JPDA computes probability β_j that measurement j belongs to a track: β_j = P_D·L_j / (λ_c + Σ P_D·L_k). The track is updated with a weighted combination of all gated measurements. This handles crossing trajectories where GNN would pick the wrong match.

**Q18: What is covariance inflation and why 1.02?**
> Particles are scaled: x_i ← x̄ + 1.02·(x_i − x̄). This prevents the particle cloud from collapsing to a point (filter divergence). 1.02 was chosen after adaptive inflation (which varied based on NIS) caused velocity explosions through positive feedback loops.

**Q19: What is admissible region sampling?**
> When initializing the EnKF, naive Gaussian sampling creates unphysical particles (hyperbolic orbits, Earth-intersecting). Admissible region sampling rejects particles with: orbital energy E ≥ 0 (unbound), altitude < 100 km, or perigee < 150 km. Only physically plausible LEO orbits are kept.

**Q20: What is NIS and how is it used?**
> Normalized Innovation Squared: NIS = yᵀ S⁻¹ y. Measures filter consistency. Expected value = degrees of freedom (2 for RA/Dec, 3 for RA/Dec/Range). If NIS >> expected: filter is struggling → increase process noise or flag anomaly.

---

## Category 3: Physics & Orbital Mechanics

**Q21: What perturbations are modeled and why?**
> **J2**: Earth's equatorial bulge causes ~5°/day RAAN precession at 800 km. Ignoring it: predictions drift within 10 minutes. **Drag**: Exponential atmosphere causes ~0.44 m/day altitude decay at 800 km. Ignoring it: predictions biased downward. **SRP**: Solar radiation pressure ~10⁻⁸ km/s² — smallest effect but included for completeness.

**Q22: Why not full geopotential (J3, J4, ...)?**
> Diminishing returns. J2 captures >98% of Earth's gravity perturbation. J3-J6 contribute <0.1% improvement for LEO. The computational cost of computing higher-order harmonics doesn't justify the marginal accuracy gain for short tracking arcs.

**Q23: How does the atmosphere model work?**
> US Standard Atmosphere 1976 approximation with 18 altitude bands (0-1000 km). Each band: ρ(h) = ρ₀·exp(−(h−h₀)/H). Scale height H increases with altitude (7.2 km at surface → 139 km at 1000 km). Above 1500 km: drag = 0.

**Q24: Why account for Earth rotation in drag?**
> Drag depends on velocity **relative to the atmosphere**, not inertial velocity. The atmosphere co-rotates with Earth at ω = 7.292×10⁻⁵ rad/s. v_rel = v_inertial − (ω × r). Ignoring this: drag direction is wrong (biased toward retrograde for prograde orbits).

**Q25: What reference frames are used?**
> **ECI** (Earth-Centered Inertial): Fixed to stars. Used for all dynamics/filtering — no pseudoforces needed. **ECEF** (Earth-Centered Earth-Fixed): Rotates with Earth. Used only for 3D visualization (matching globe texture). Conversion: GMST rotation matrix from Skyfield.

**Q26: How is the SRP shadow model implemented?**
> Cylindrical approximation. If satellite is behind Earth (dot(r, r̂_sun) < 0) AND perpendicular distance to Sun-Earth line < R_earth: in shadow → SRP = 0. Simple but effective for LEO where eclipse fraction is ~35%.

**Q27: What integrator is used and why?**
> **RK45** (Runge-Kutta-Fehlberg 4th/5th order) for EnKF propagation — fast, adaptive step size, suitable for short arcs (5s). **DOP853** (Dormand-Prince 8th order) for long-term prediction in [OrbitPropagator](file:///Users/rajiv/Desktop/ORBIT-GUARD-COMPLETE-BOTH-2026-03-11/short-arc-ai-workspace/src/orbital_mechanics/propagator.py#6-45) — higher accuracy for hours-long predictions.

**Q28: What is RTN frame and why add noise there?**
> Radial-Transverse-Normal: a coordinate system aligned with the orbit. R points along position, T along velocity, N along angular momentum. Orbital uncertainty is **anisotropic**: 3× larger along-track (timing error) than radial or cross-track. Adding noise in RTN correctly captures this physics.

---

## Category 4: Data Association

**Q29: When should you use GNN vs JPDA?**
> **GNN**: Objects well-separated (>200 km), low noise (<0.3°), need speed. **JPDA**: Dense environments, crossing trajectories, high clutter, safety-critical applications. GNN: 92% normal / 54% clutter. JPDA: 92% normal / 88% clutter.

**Q30: What does the gating threshold mean?**
> GNN gate = 20.0 (χ²₃ at 99.9%). JPDA gate = 25.0. This means: if a measurement's Mahalanobis distance from a track prediction exceeds this threshold, it's rejected as impossible. Higher gate = more permissive (catches more but risks false matches).

**Q31: Why does JPDA use log-space likelihoods?**
> Mahalanobis distances can be large (e.g., d² = 15), causing exp(−d²/2) = exp(−7.5) ≈ 5.5×10⁻⁴. With multiple measurements, products underflow to zero. Computing in log-space: log L_j = −d²_j/2, then subtracting max before exponentiating, prevents this.

**Q32: What is clutter density and why 1e-8?**
> Clutter = false alarms (radar echoes from nothing). In space tracking, false alarm rate is extremely low — space is "clean" compared to ground-based radar. λ_c = density × volume = 1e-8 × (2π×25) ≈ 1.6×10⁻⁶. This makes the clutter term negligible, so real measurements dominate.

**Q33: How are tracks initiated?**
> Any unassigned measurement spawns a new track. The measurement's RA/Dec determine line-of-sight; range is estimated via quadratic geometry (solving for 750 km altitude intersection). EnKF is initialized with 200 particles.

**Q34: How are ghost tracks pruned?**
> Multi-criteria: (1) > 1200 missed detections (~100 minutes unseen), (2) covariance trace > 10⁶ km² after 5 misses, (3) altitude outside 200-3000 km (or ±200 km for young tracks), (4) speed outside 5-10 km/s. Young tracks (< 5 updates) get wider bounds as they stabilize.

**Q35: What is track quality metric Q?**
> Q = (matched_frames / total_frames) × NIS_consistency, where NIS_consistency = 1/(1 + avg_NIS/3). Young tracks (< 5 frames) get Q = 1.0 (grace period). Q < 0.3 → "DEGRADED" status.

**Q36: How does multi-radar fusion work?**
> Measurements are grouped by radar site (via rounded ECI position). Each site's batch is associated sequentially — this preserves JPDA's statistical assumptions (independent measurements within each batch). Track update tracking spans all sites per frame.

---

## Category 5: Frontend & Visualization

**Q37: Why Three.js for a space tracking app?**
> Space is 3D — orbital mechanics (inclination, RAAN, conjunction geometry) are impossible to visualize correctly in 2D. Three.js with React Three Fiber provides GPU-accelerated rendering with React's component model.

**Q38: How is uncertainty visualized?**
> Glow halos proportional to covariance trace. Color mapping: green (stable) → yellow (acquiring) → red (unstable). The glow radius scales with `uncertainty` percentage (100 - confidence). Implemented via `<Satellite>` component with shader-based bloom.

**Q39: What are all the HUD components?**
> Header (status, tracks, method, accuracy), StatusBanner (natural language events), Legend (color key), MissionControl (config panel), EventFeed (scrolling log), TrackCard (per-track telemetry), ConjunctionPanel (risk alerts), ExplainModal ("What am I watching?"), ProgressBar.

**Q40: How is ECI→3D conversion done?**
> ECI → ECEF via GMST rotation matrix, then ECEF → Three.js coordinates: x_3d = x_ecef × SCALE, y_3d = y_ecef × SCALE, z_3d = z_ecef × SCALE, where SCALE = 2.0 / 6378.137. The y-axis swap matches Three.js convention (Y-up).

**Q41: What post-processing effects are used?**
> Bloom (`@react-three/postprocessing`): luminance threshold 0.8, mipmap blur, intensity 1.2. Makes satellite markers and uncertainty glows "glow" realistically against the dark space background.

**Q42: How do orbit trails work?**
> Backend maintains `trail_history[track_id]` — last 300 ECEF positions. Sent with each frame. Frontend `<OrbitTrail>` renders as a `<Line>` from `@react-three/drei`, colored by track status.

**Q43: How does the conjunction danger line work?**
> `<DangerLine>` draws a red line between two tracks flagged in a conjunction. Opacity pulsates. Risk level determines color intensity. Only rendered when `visibility.conjunctions` is toggled on.

---

## Category 6: Gotchas & Edge Cases

**Q44: What causes ghost tracks?**
> Every unassociated measurement creates a new track. If noise produces false detections, ghost tracks appear at random positions. Fix: two-tier pruning — young tracks (< 5 updates) need narrower physical bounds (alt -200 to 6000 km), while mature tracks need tighter bounds (150-3000 km).

**Q45: What causes velocity explosions?**
> Process noise too large → particles diverge → cross-covariance inflated → Kalman gain too large → velocity jumps. Original issue: process noise of 0.5 km caused particles at 50 km/s. Fix: reduced to 0.05 km, added velocity clamping (5-10 km/s), soft reset to circular velocity.

**Q46: What is the slant range confusion problem?**
> Radar measures slant range (distance along line-of-sight, e.g., 12,000 km), not altitude (e.g., 800 km). Early bug: used range as altitude → tracks initialized at wrong position. Fix: solve |R_site + ρ·L̂|² = (R_earth + h_target)² for ρ.

**Q47: Why does the filter use fixed inflation instead of adaptive?**
> Adaptive inflation: scale = f(NIS). If NIS high → inflate more → particles spread → next NIS higher → inflate MORE → runaway feedback → velocity explosion. Fixed 1.02 breaks this loop.

**Q48: What happens when all tracks are lost?**
> Cascading loss: covariance grows during coasting (no measurements) → eventually exceeds pruning threshold (10⁶ km²) → all tracks pruned. Root cause in early versions: unbounded adaptive inflation. Fix: fixed inflation + generous pruning threshold.

**Q49: How are angle wrapping issues handled?**
> RA (Right Ascension) wraps at ±π. Innovation computation: `innov[0] = (innov[0] + π) % 2π − π`. Without this: a track at RA = 179° and measurement at RA = -179° would show innovation = 358° instead of 2°.

**Q50: What if a particle falls below Earth's surface?**
> Propagation dynamics check: if `r_norm < 6378 km`, acceleration is zeroed (particle frozen). Initialization rejects particles with altitude < 100 km. Post-propagation velocity clamping resets unphysical particles to circular velocity at 750 km altitude.

**Q51: Why does the maneuver detector have high threshold (8σ)?**
> Fengyun-1C debris is passive — it doesn't maneuver. A low threshold (3σ) would trigger false maneuver detections from normal filter transients. 8σ ensures only genuine filter divergence (actual anomalies) triggers the detector.

**Q52: What happens with near-polar orbits?**
> The prograde velocity computation uses r̂ × ẑ for the angular momentum direction. If the orbit is nearly polar (r̂ ≈ ẑ), this cross product is near-zero. Fix: fall back to r̂ × x̂ instead. Checked with `norm(h_dir) < 0.1`.
