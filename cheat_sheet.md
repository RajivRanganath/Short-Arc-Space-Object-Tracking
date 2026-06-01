# 🛰️ Orbit Guard AI — Cheat Sheet

---

## 🚀 Quick Start Commands

```bash
# ── Backend (Python) ──────────────────────────────────
cd short-arc-ai-workspace
source venv/bin/activate

# Start live 3D tracking server (WebSocket on ws://localhost:8000/ws)
python run_live_3d_tracking.py

# Run GNN vs JPDA comparison benchmark
python run_gnn_vs_jpda_comparison.py

# Quick multi-object tracking demo (console)
python run_multi_object_demo.py

# Single-object tracking demo
python run_tracking_demo.py

# Scheduler demo
python run_scheduler_demo.py

# Run all tests
pytest

# ── Frontend (React + Three.js) ──────────────────────
cd orbit-ui
npm install
npm run dev          # Dev server on http://localhost:5173
```

### ⚠️ Common Issues

| Problem | Fix |
|---------|-----|
| `address already in use :8000` | `lsof -ti:8000 \| xargs kill -9` |
| `ModuleNotFoundError: numba` | `source venv/bin/activate` first |
| Frontend can't connect | Ensure backend is running on port 8000 |
| Track explosion (too many tracks) | Tentative track logic handles this — see `_try_tentative_or_initiate()` |

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    React Frontend (orbit-ui)                │
│   Three.js 3D Globe · WebSocket Client · Mission Control    │
│                    http://localhost:5173                     │
└──────────────────────────┬──────────────────────────────────┘
                           │ WebSocket (ws://localhost:8000/ws)
┌──────────────────────────▼──────────────────────────────────┐
│              FastAPI Backend (Python)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐    │
│  │  Scenario     │  │  Multi-Object│  │  WebSocket     │    │
│  │  Generator    │──▶│  Tracker     │──▶│  Streamer      │    │
│  │  (TLE-based)  │  │  (GNN/JPDA)  │  │  (JSON frames) │    │
│  └──────────────┘  └──────┬───────┘  └────────────────┘    │
│                           │                                  │
│  ┌──────────────┐  ┌──────▼───────┐  ┌────────────────┐    │
│  │  Radar Sim   │  │  EnKF Filter │  │  Conjunction   │    │
│  │  (angles+    │  │  (Particle   │  │  Assessment    │    │
│  │   range)     │  │   Filter)    │  │  (Pc, TCA)     │    │
│  └──────────────┘  └──────────────┘  └────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 📂 File Map

### Backend — `short-arc-ai-workspace/`

| File | Purpose |
|------|---------|
| `run_live_3d_tracking.py` | **Main entry** — FastAPI + WebSocket server, streams frames to React |
| `run_gnn_vs_jpda_comparison.py` | Side-by-side algorithm benchmark |
| `run_tracking_demo.py` | Console tracking demo |
| `pyproject.toml` | Python project config |

#### `src/` — Core Modules

| Module | Key Files | What it does |
|--------|-----------|-------------|
| `tracking_system.py` | — | **Orchestrator** — processes frames, manages tracks, runs pruning |
| `association/` | `gnn_associator.py`, `jpda_associator.py` | Data association algorithms |
| `orbit_determination/` | `ensemble_kalman_filter.py`, `gauss_iod.py`, `adaptive_noise.py` | State estimation & IOD |
| `tracking/` | `track_hypothesis.py`, `conjunction.py`, `catalog.py`, `maneuver.py` | Track lifecycle, conjunction assessment, catalog correlation |
| `simulation/` | `multi_object_scenarios.py`, `radar_sim.py` | TLE-based scenario generation & radar measurement simulation |
| `classification/` | — | Orbit regime classification |
| `orbital_mechanics/` | — | Physics propagation (J2, drag) |
| `scheduling/` | — | Sensor tasking |

### Frontend — `orbit-ui/src/`

| File | Purpose |
|------|---------|
| `App.jsx` | Main app — WebSocket connection, state management |
| `index.css` | Global styles (dark theme, glassmorphism) |
| **Components:** | |
| `Earth.jsx` | 3D Earth with atmosphere shader |
| `Satellite.jsx` | Debris marker + particle cloud visualization |
| `OrbitTrail.jsx` | Orbit path trail rendering |
| `RadarStation.jsx` | Radar station markers on globe |
| `MissionControl.jsx` | Config panel (objects, speed, algorithm) |
| `StatusBanner.jsx` | Phase/status header bar |
| `TrackCard.jsx` | Per-track telemetry card |
| `EventFeed.jsx` | Live event log |
| `ConjunctionPanel.jsx` | Conjunction warning display |
| `DangerLine.jsx` | Visual line between conjuncting objects |
| `ExplainModal.jsx` | Algorithm explainer popup |
| `Legend.jsx` | Color/status legend |

---

## 🧠 Algorithms at a Glance

### Data Association

| Algorithm | Full Name | How it works | When to use |
|-----------|-----------|-------------|-------------|
| **GNN** | Global Nearest Neighbor | Optimal 1-to-1 matching via Hungarian algorithm; uses Mahalanobis distance gating (χ² ≤ 16.27) | Low-density scenes, fast |
| **JPDA** | Joint Probabilistic Data Association | Computes probability weights for **all** measurement-to-track pairs; handles ambiguity gracefully | High-density / cluttered scenes |

### State Estimation

| Component | What it does |
|-----------|-------------|
| **EnKF** (Ensemble Kalman Filter) | Particle-based filter; 200 particles; handles nonlinear orbital dynamics; includes guardrail resampling |
| **Gauss IOD** | Initial Orbit Determination from 3 angle observations — bootstraps new tracks |
| **Adaptive Noise** | Dynamically adjusts process noise based on residuals |

### Track Lifecycle

```
Unassigned Measurement
        │
        ▼
  ┌─────────────┐     No 2nd hit     ┌──────────┐
  │  TENTATIVE   │ ──── (5 frames) ──▶│  EXPIRED  │
  │  Detection   │                    └──────────┘
  └──────┬──────┘
         │ 2nd correlated measurement (within 150 km gate)
         ▼
  ┌─────────────┐     Missed > 120     ┌──────────┐
  │  CONFIRMED   │ ── or bad physics ──▶│  PRUNED   │
  │  Track       │                      └──────────┘
  └──────┬──────┘
         │ > 10 updates
         ▼
  ┌─────────────┐
  │  CORRELATED  │  (matched to TLE catalog)
  └─────────────┘
```

### Pruning Rules

| Condition | Threshold |
|-----------|-----------|
| Young + missed | < 3 updates AND > 3 missed → prune |
| Long coast | > 120 missed detections → prune |
| Uncertainty explosion | Covariance trace > 10⁶ km² → prune |
| Altitude (young) | < -200 km or > 6000 km → prune |
| Altitude (mature) | < 150 km or > 3000 km → prune |
| Speed (young) | < 1 km/s or > 20 km/s → prune |
| Speed (mature) | < 5 km/s or > 10 km/s → prune |

---

## 📡 Key Constants

| Constant | Value | Where |
|----------|-------|-------|
| Earth radius | 6378.137 km | `run_live_3d_tracking.py` |
| 3D globe scale | `2.0 / 6378.137` | React visualization |
| Validation gate (χ²) | 16.27 (3 DOF, 99%) | GNN & JPDA associators |
| Tentative gate | 150 km | `tracking_system.py` |
| EnKF particles | 200 | `ensemble_kalman_filter.py` |
| Max trail length | 300 points | `run_live_3d_tracking.py` |
| Conjunction threshold | 200 km, 3h lookahead | `tracking_system.py` |

---

## 🔌 WebSocket Protocol

**Endpoint:** `ws://localhost:8000/ws`

### Client → Server Messages

```json
{"action": "start", "nObjects": 5, "duration": 300, "speed": 0.5, "method": "jpda"}
{"action": "stop"}
{"action": "update_speed", "speed": 1.0}
```

### Server → Client Payload (per frame)

```json
{
  "tracks": [{
    "id": 1,
    "position": [x, y, z],
    "particles": [[x,y,z], ...],
    "trail": [[x,y,z], ...],
    "altitude": 412.5,
    "speed": 7.66,
    "status": "stable|acquiring|unstable",
    "regime": "LEO|MEO|GEO|Unknown",
    "confidence": 85,
    "uncertainty": 15,
    "updates": 12,
    "missedDetections": 0
  }],
  "stations": [{...}],
  "events": [{"type": "new_track|pruned|maneuver|info", "message": "..."}],
  "stats": {
    "frame": 10,
    "totalFrames": 60,
    "activeTracks": 5,
    "totalTracks": 8,
    "method": "JPDA",
    "associationRate": 82.5,
    "activeStation": "ISTRAC"
  },
  "phase": "Tracking 5 Objects — 82% Association",
  "conjunctions": [{...}],
  "simRunning": true
}
```

---

## 📊 Key Metrics

| Metric | Formula | Good Target |
|--------|---------|-------------|
| **Association Rate** | `matches / total_measurements × 100` | ≥ 85% = Excellent |
| **Validated Rate** | Based on dominant true object per track | ≥ 85% = Excellent |
| **Track Purity** | Fraction of associations to correct object | Higher = better |
| **Confidence** | `exp(-cov_trace / 50000)` + update bonus − guardrail penalty | 60-100 for stable |

---

## 📻 Radar Stations

| Station | Location | Lat / Lon |
|---------|----------|-----------|
| ISTRAC Bangalore | India 🇮🇳 | 12.97° N, 77.59° E |
| SvalSat | Norway 🇳🇴 | 78.22° N, 15.63° E |
| McMurdo Station | Antarctica 🇦🇶 | 77.85° S, 166.67° E |

---

## 🧪 Test Suite

```bash
# All tests
pytest

# Specific test files
pytest test_conjunction.py         # Conjunction assessment
pytest test_jpda_stress.py         # JPDA under high density
pytest test_jdpa_high_noise.py     # JPDA with noisy measurements
pytest test_adaptive_noise.py      # Adaptive noise tuning
pytest test_edge_cases.py          # Edge case handling
pytest test_physics_accuracy.py    # Orbital mechanics validation
```

---

## 🔑 Glossary

| Term | Meaning |
|------|---------|
| **Short-arc** | Tracking with limited observation time (< 1 orbit) |
| **IOD** | Initial Orbit Determination — first orbit estimate from few observations |
| **EnKF** | Ensemble Kalman Filter — particle-based state estimator |
| **JPDA** | Joint Probabilistic Data Association — handles measurement ambiguity |
| **GNN** | Global Nearest Neighbor — 1:1 optimal assignment |
| **TLE** | Two-Line Element — standard orbit description format |
| **UCT** | Uncorrelated Track — not yet matched to known catalog object |
| **Conjunction** | Close approach between two tracked objects |
| **Pc** | Probability of Collision |
| **TCA** | Time of Closest Approach |
| **GMST** | Greenwich Mean Sidereal Time — Earth rotation angle |
| **ECI** | Earth-Centered Inertial — non-rotating reference frame |
| **ECEF** | Earth-Centered Earth-Fixed — rotates with Earth |
| **LEO** | Low Earth Orbit (150–2000 km altitude) |
| **Mahalanobis distance** | Statistical distance accounting for covariance shape |
| **Guardrail** | Particle filter resampling when estimate diverges |
| **Association density** | Avg candidate measurements per track per scan — higher = harder |
