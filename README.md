# 🛰️ Orbit Guard AI

> **AI-powered real-time space debris tracking, data association, and conjunction assessment system.**

Orbit Guard AI tackles one of the hardest problems in space situational awareness: associating noisy, short-arc radar observations with the correct orbital objects in real time. The system combines physics-informed orbital mechanics with modern AI-driven data association algorithms to maintain accurate track estimates even under high clutter and measurement noise.

---

## 🏗️ Architecture

The project is organized into two main components:

```
orbit-guard/
├── short-arc-ai-workspace/   # Python backend — tracking engine & API
│   ├── src/                   # Core library
│   │   ├── association/       # GNN & JPDA data association
│   │   ├── orbit_determination/ # Extended Kalman Filter (EnKF)
│   │   ├── orbital_mechanics/ # SGP4/J2 propagation, coordinate transforms
│   │   ├── simulation/        # Synthetic debris & sensor simulation
│   │   ├── tracking/          # Multi-object tracker & track management
│   │   ├── classification/    # Object type classification
│   │   ├── scheduling/        # Sensor scheduling & tasking
│   │   └── api/               # FastAPI WebSocket server
│   ├── tests/                 # Unit & integration tests
│   ├── data/                  # Reference orbital element datasets
│   └── papers/                # Literature notes
│
├── orbit-ui/                  # React + Three.js frontend
│   └── src/
│       ├── App.jsx            # Main 3D scene & WebSocket client
│       └── components/        # Earth, Satellite, TrackCard, etc.
│
└── DS(synopsis)/              # Project documentation & reports
```

## 🔬 Key Algorithms

| Module | Algorithm | Purpose |
|--------|-----------|---------|
| **Data Association** | Global Nearest Neighbor (GNN) | Fast, greedy measurement-to-track assignment |
| **Data Association** | Joint Probabilistic Data Association (JPDA) | Soft probabilistic assignment for dense clutter |
| **Orbit Determination** | Ensemble Kalman Filter (EnKF) | State estimation with non-linear dynamics |
| **Propagation** | J2-perturbed two-body dynamics | Physics-accurate short-term orbit prediction |
| **Conjunction Assessment** | Mahalanobis-distance screening | Collision probability estimation between tracks |

## 🚀 Quick Start

### Backend (Python)

```bash
cd short-arc-ai-workspace

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[dev,api]"

# Run the live tracking server (FastAPI + WebSocket on port 8000)
python run_live_3d_tracking.py
```

### Frontend (React + Three.js)

```bash
cd orbit-ui

# Install dependencies
npm install

# Start the dev server (Vite on port 5173)
npm run dev
```

Open `http://localhost:5173` to launch the 3D visualization. Ensure the Python backend is running so the WebSocket connection (`ws://localhost:8000/ws`) can attach.

## 🧪 Testing

```bash
cd short-arc-ai-workspace
pytest --cov=src tests/
```

## 📊 Demos & Benchmarks

| Script | Description |
|--------|-------------|
| `run_live_3d_tracking.py` | Full live simulation with WebSocket-fed 3D frontend |
| `run_tracking_demo.py` | Terminal-based single-scenario tracking demo |
| `run_gnn_vs_jpda_comparison.py` | Side-by-side GNN vs JPDA performance comparison |
| `run_multi_object_demo.py` | Multi-target tracking stress test |
| `run_benchmark.py` | Automated performance benchmarking |
| `run_scheduler_demo.py` | Sensor scheduling algorithm demo |

## 🛠️ Tech Stack

- **Backend**: Python 3.9+, NumPy, SciPy, Numba, Scikit-learn, Skyfield, FastAPI
- **Frontend**: React 18, Three.js (React Three Fiber), Vite, WebSockets
- **Testing**: pytest, pytest-cov



## 📝 License

This project was developed as an academic research project for AI-based space object tracking.

---

