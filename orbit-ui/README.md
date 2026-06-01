# Orbit Guard AI - Frontend Visualization

React + Three.js (React Three Fiber) frontend for real-time visualization of the Orbit Guard AI space debris tracking system.

## Overview
This visualization runs in the browser, providing a 3D interface to interact with the Python backend's EnKF and JPDA association engines. It displays live orbital telemetry, particle clouds, tracking confidence, and conjunction alerts.

## Features
- **Live 3D Rendering**: View the Earth (with atmospheric scattering) and orbital debris paths in real-time.
- **Algorithm Switcher**: Toggle instantaneously between GNN (Global Nearest Neighbor) and JPDA (Joint Probabilistic Data Association) tracking mechanisms.
- **Particle Clouds**: Visualize the EnKF uncertainty covariance matrices as glowing particle clouds around target objects.
- **Live Telemetry & Logs**: Track state estimates, speed, altitude, and confidence metrics streamed continually via WebSockets.
- **Stress Testing**: Manually adjust debris density and simulation speed to evaluate backend tracking performance.

## Installation & Deployment

### Prerequisites
- Node.js (v18+)
- Local instance of Orbit Guard AI Python backend running (`uvicorn` or `python run_live_3d_tracking.py`)

### Development Setup
1. Open this directory (`orbit-ui`):
   ```bash
   cd orbit-ui
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run the development server (Vite):
   ```bash
   npm run dev
   ```
4. Access the visualization at `http://localhost:5173`. Make sure your Python backend is running locally so the WebSocket connection (`ws://localhost:8000/ws`) can attach.

### Building for Production
To create a static production build:
```bash
npm run build
```
This generates static files inside the `dist/` folder which can be served using any web server like NGINX or injected directly into a FastAPI static route if needed.

## Architecture
- **Vite & React 18**: Fast frontend toolchain and component framework.
- **Three.js & React Three Fiber**: WebGL engine and declarative 3D scene graph.
- **WebSocket Protocol**: Consumes high-throughput state vectors from the Python sensor simulation.
