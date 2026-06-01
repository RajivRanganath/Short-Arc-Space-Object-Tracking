# AI-Based Data Association for Short-Arc Space Object Tracking

> **ORBIT GUARD AI** — A system that detects, tracks, and identifies multiple pieces of space debris in real time using radar measurements, AI-powered data association, and a live 3D visualization dashboard.

---

## 1. Title

**AI-Based Data Association for Short-Arc Space Object Tracking (ORBIT GUARD AI)**

This project builds an intelligent system that takes raw radar signals from ground stations, figures out which signal belongs to which piece of space debris (even when signals overlap), and tracks all of them simultaneously on a real-time 3D globe. It solves the critical "which blip belongs to which object?" problem using probabilistic AI algorithms.

---

## 2. About the Dataset

The dataset is **real Two-Line Element (TLE) orbital data** for the Fengyun-1C debris cloud, downloaded live from **CelesTrak** (a public NORAD satellite catalog). The Fengyun-1C was a Chinese weather satellite destroyed in a 2007 anti-satellite test, creating over **3,400+ trackable debris fragments** — one of the largest debris events in history. Each TLE record contains 2 lines of text encoding 6 orbital parameters (position, velocity, orbital shape). From these TLEs, the system simulates realistic radar measurements — producing hundreds of observations per scenario, each containing Right Ascension (RA), Declination (Dec), slant range, timestamp, and radar station ID. The data is time-series in nature and represents the kind of noisy, intermittent signals real radars produce.

---

## 3. About Features

The key input features used in the system are:

| Feature | Description |
|---|---|
| **Right Ascension (RA)** | The horizontal angle (in radians) where the radar detects the object in the sky — like the "longitude" of a star on the sky map. |
| **Declination (Dec)** | The vertical angle (in radians) — like the "latitude" of the object on the sky map. |
| **Slant Range** | The straight-line distance (in km) from the radar station to the detected object. |
| **Timestamp** | The exact time of each radar measurement, used to match observations across frames. |
| **Radar Site ECI Position** | The 3D coordinates (in km) of the ground radar station at the time of observation, needed to convert angles into actual space positions. |
| **Orbital State Vector** | A 6-element vector [x, y, z, vx, vy, vz] representing position (km) and velocity (km/s), computed internally by the filter from the raw measurements above. |

---

## 4. Preprocessing Algorithm

Several preprocessing steps are applied before the data reaches the tracking algorithms:

1. **Noise Injection** — Gaussian noise is added to simulated RA (±0.01°), Dec (±0.01°), and Range (±5 km) to mimic real-world radar imprecision. This makes the system robust to imperfect sensors.

2. **Coordinate Transformation** — Raw RA/Dec angles and range are converted from the radar's local frame into Earth-Centered Inertial (ECI) Cartesian coordinates [x, y, z]. This is needed because all physics calculations (gravity, drag) work in Cartesian space, not angles.

3. **Visibility Filtering** — Observations where the satellite is below 5° elevation (near the horizon) are discarded, since the atmosphere distorts signals too much at low angles.

4. **Temporal Sorting** — All measurements from all radars are sorted by timestamp. The tracker processes them chronologically, just like a real operations center.

5. **Measurement Grouping** — Observations from the same timestamp are grouped by radar station. This allows the system to handle multiple simultaneous detections from the global radar network independently.

---

## 5. Methodology

The project follows a clear pipeline from data to decision:

1. **Data Acquisition** — Real TLE orbital data is downloaded from CelesTrak for the Fengyun-1C debris cloud, providing ground truth orbital parameters for hundreds of objects.

2. **Radar Simulation** — Three globally distributed radar stations (India, Norway, Antarctica) generate synthetic measurements by computing where each debris piece would appear in each radar's field of view, then adding realistic noise.

3. **Measurement Processing** — Raw radar signals (angles + range) are converted into a standard format and grouped by time frame.

4. **Data Association (AI Core)** — The system uses either JPDA (Joint Probabilistic Data Association) or GNN (Global Nearest Neighbor with Hungarian Algorithm) to solve the assignment problem: "which measurement came from which tracked object?" This is the hardest part — multiple debris pieces can produce overlapping signals.

5. **Orbit Determination** — An Ensemble Kalman Filter (200 particles) maintains a statistical cloud of possible positions for each tracked object, updating it every time a new measurement arrives and propagating forward using real orbital physics (gravity, J2 oblateness, atmospheric drag, solar radiation pressure).

6. **Classification** — A Random Forest ML model classifies each tracked object into an orbital regime (LEO, MEO, GEO, HEO, GTO) based on computed orbital elements.

7. **Conjunction Assessment** — The system checks if any two tracked objects are getting dangerously close (collision risk), computing probability of collision.

8. **Visualization** — Results stream live via WebSocket to a React 3D dashboard showing orbits, confidence levels, event feeds, and alerts.

---

## 6. Flow Diagram Description

Below is the step-by-step flow of the system, suitable for drawing a flow diagram:

```
[CelesTrak TLE Database]
        ↓
[Download Fengyun-1C Debris TLEs]
        ↓
[Select N Random Debris Objects]
        ↓
[Radar Simulation across 3 Global Stations]
  (ISTRAC India, SvalSat Norway, McMurdo Antarctica)
        ↓
[Generate Noisy RA/Dec/Range Measurements]
        ↓
[Sort & Group by Timestamp]
        ↓
[Data Association Engine]
  ┌────────────┴────────────┐
  │  JPDA (Probabilistic)   │  GNN (Hungarian Algorithm)  │
  └────────────┬────────────┘
        ↓
[Match Measurements → Existing Tracks]
  ┌──────┴──────┐
  │ Matched     │ Unmatched (New Track)
  ↓             ↓
[Update EnKF]  [Initialize New Track]
  (200 particles, J2+Drag+SRP physics)
        ↓
[Regime Classification via Random Forest]
  (LEO / MEO / GEO / HEO / GTO)
        ↓
[Conjunction Assessment]
  (Collision probability between pairs)
        ↓
[WebSocket Stream → React Frontend]
        ↓
[3D Globe Visualization]
  (Tracks, Orbits, Particles, Events, Alerts)
```

---

## 7. Algorithm Used

The project uses multiple AI/ML algorithms working together:

### Primary: Joint Probabilistic Data Association (JPDA)
JPDA is a probabilistic algorithm that solves the measurement-to-track assignment problem. When a radar detects multiple blips and we have multiple tracked objects, JPDA calculates the probability that each blip belongs to each object. It uses Mahalanobis distance (a statistical measure of "how expected is this measurement?") and Bayesian probability to assign soft weights instead of hard 1-or-0 assignments. This is crucial because in crowded debris fields, a single radar return might be ambiguous — JPDA handles this gracefully by splitting belief across candidates.

### Secondary: Global Nearest Neighbor (GNN) with Hungarian Algorithm
GNN is a simpler alternative that makes hard one-to-one assignments. It builds a cost matrix (distances between every track and every measurement), then uses the Hungarian Algorithm to find the global assignment that minimizes total cost. It's faster but less accurate in crowded scenarios.

### Orbit Determination: Ensemble Kalman Filter (EnKF)
The EnKF maintains 200 "particles" — each one a possible state of the object. At every step, all particles are propagated forward using real physics (gravity, Earth oblateness, drag, solar pressure), then corrected when a new measurement arrives. The spread of particles represents uncertainty — tight cloud means high confidence, wide cloud means uncertain.

### Classification: Random Forest
A Random Forest classifier (100 trees) categorizes each tracked object into its orbital regime (LEO, MEO, GEO, etc.) based on computed orbital elements like semi-major axis, eccentricity, and inclination. Physics-based rules override the ML model when necessary for safety.

---

## 8. Frontend Plan

The frontend is a **real-time 3D mission control dashboard** built using:

- **React.js** — For the UI components (mission control panel, event feed, telemetry cards, track details).
- **Three.js** (via React Three Fiber) — For rendering a photorealistic 3D Earth globe with orbiting debris.
- **WebSocket** — For live streaming data from the Python backend at ~1-2 frames per second.
- **Vite** — As the build tool for fast development.

**User Interaction Flow:**
1. The user opens the dashboard and sees a 3D spinning Earth with the ground station markers (green diamonds).
2. The user configures the mission — number of objects to track (1–20), simulation speed, and association method (JPDA or GNN) — using a control panel.
3. On clicking "Start Simulation," the backend begins processing and streams live tracking data.
4. The user sees satellites appear as glowing dots, with colored orbit trails, uncertainty clouds, and real-time telemetry (altitude, speed, confidence %).
5. If two objects approach each other dangerously, a red "Conjunction Alert" panel appears.
6. An event feed shows a live log of track acquisitions, losses, and maneuver detections.
7. The user can hover over any object to see its detailed stats, or click the "What am I watching?" button for a plain-English explanation.

---

## 9. Expected Output

The system produces the following outputs:

1. **Real-time 3D Visualization** — Each tracked debris object appears as a glowing dot on a 3D Earth globe, with colored orbit trails showing its path. Green = stable track, yellow = acquiring, red = signal lost.

2. **Telemetry Cards** — For every tracked object, the user sees: current altitude (km), orbital speed (km/s), confidence percentage (how sure the system is about the track), and orbital regime (LEO/MEO/GEO).

3. **Association Accuracy Score** — A percentage showing how well the AI matched radar blips to the correct objects (typically 70–96%), displayed in the top header bar.

4. **Conjunction Alerts** — If two objects are predicted to come within 200 km of each other, the system calculates collision probability and displays a risk level (RED / YELLOW / SAFE) with estimated closest approach distance and time.

5. **Event Feed** — A scrolling live log showing: "Track 5 acquired at 884 km", "Track 3 lost — signal faded", "Conjunction alert between TRK-02 and TRK-07", etc.

6. **Mission Report** — At the end of a simulation run, the system displays a final summary: total tracks processed, association accuracy rating (EXCELLENT / GOOD / NEEDS TUNING), and per-track health status.

The user walks away with a clear understanding of how many objects were tracked, how accurately the AI associated data, whether any collision risks were detected, and the orbital classification of each object.
