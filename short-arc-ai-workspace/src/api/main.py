from fastapi import FastAPI, HTTPException, WebSocket
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import asyncio
import json
from skyfield.api import load
from typing import List, Dict, Any, Optional
import numpy as np
import datetime
from src.tracking_system import MultiObjectTracker
from src.constants import get_logger

logger = get_logger("OrbitGuardAPI")

app = FastAPI(
    title="Orbit Guard API",
    description="Real-time satellite & debris tracking and conjunction assessment API",
    version="0.1.0"
)

# ── Constants ─────────────────────────────────────────────────────────
EARTH_RADIUS_KM = 6378.137
REACT_EARTH_RADIUS = 2.0
SCALE = REACT_EARTH_RADIUS / EARTH_RADIUS_KM

# Radar station metadata
RADAR_STATIONS = [
    {"name": "ISTRAC Bangalore", "lat": 12.9716, "lon": 77.5946, "country": "India"},
    {"name": "SvalSat Norway",   "lat": 78.2232, "lon": 15.6267, "country": "Norway"},
    {"name": "McMurdo Station",  "lat": -77.8463,"lon": 166.6682,"country": "Antarctica"},
]

def lat_lon_to_3d(lat_deg, lon_deg, radius=REACT_EARTH_RADIUS):
    """Convert lat/lon to 3D position on sphere surface."""
    lat = np.radians(lat_deg)
    lon = np.radians(lon_deg)
    x = radius * np.cos(lat) * np.cos(lon)
    y = radius * np.sin(lat)
    z = -radius * np.cos(lat) * np.sin(lon)
    return [float(x), float(y), float(z)]

def eci_to_ecef(x, y, z, gmst_rad):
    """Rotate ECI coordinates to ECEF using Greenwich Mean Sidereal Time."""
    cos_t = np.cos(gmst_rad)
    sin_t = np.sin(gmst_rad)
    
    x_ecef = x * cos_t + y * sin_t
    y_ecef = -x * sin_t + y * cos_t
    z_ecef = z
    return x_ecef, y_ecef, z_ecef

def build_station_data():
    """Pre-compute 3D positions for all radar stations."""
    stations = []
    for s in RADAR_STATIONS:
        pos = lat_lon_to_3d(s["lat"], s["lon"], REACT_EARTH_RADIUS * 1.01)
        stations.append({
            "name": s["name"],
            "country": s["country"],
            "lat": s["lat"],
            "lon": s["lon"],
            "position": pos,
        })
    return stations

# Global tracker instance
tracker = MultiObjectTracker(association_method='jpda')

class MeasurementModel(BaseModel):
    site_eci: List[float] = Field(..., description="Radar site ECI position (km) [x, y, z]")
    range: float = Field(0.0, description="Slant range (km)")
    ra: float = Field(..., description="Right Ascension (rad)")
    dec: float = Field(..., description="Declination (rad)")
    true_object_id: int = Field(-1, description="Simulation truth ID")

class FrameRequest(BaseModel):
    timestamp_iso: str = Field(..., description="ISO 8601 Timestamp of the observations")
    measurements: List[MeasurementModel]

class TrackState(BaseModel):
    id: int
    matched_frames: int
    quality_metric: float
    position: List[float]
    velocity: List[float]
    altitude: float
    speed: float
    status: str
    identification: Optional[str] = None

class ConjunctionAlert(BaseModel):
    t1: int
    t2: int
    distance_km: float
    miss_distance_km: float
    pc: float
    risk_level: str
    tca_seconds: float

class FrameResponse(BaseModel):
    timestamp: str
    active_tracks: int
    tracks: List[TrackState]
    active_conjunctions: List[ConjunctionAlert]

@app.post("/process_frame", response_model=FrameResponse)
async def process_frame(request: FrameRequest):
    try:
        current_time = datetime.datetime.fromisoformat(request.timestamp_iso.replace('Z', '+00:00'))
        
        # Convert objects to dictionary format expected by tracker
        raw_measurements = [m.model_dump() for m in request.measurements]
        
        # Process frame
        tracker.process_frame(current_time, raw_measurements)
        
        # Format response
        track_states = []
        for t in tracker.tracks:
            state = t.state_estimate
            alt = float(np.linalg.norm(state[:3])) - 6378.137
            speed = float(np.linalg.norm(state[3:]))
            q = t.quality_metric
            
            is_leo = (150 < alt < 2000) and (6.0 < speed < 10.0)
            if q < 0.3:
                status = "DEGRADED"
            elif is_leo:
                status = "LEO"
            else:
                status = "UNSTABLE"
                
            ident = tracker.identifications.get(t.id, None)
            ident_str = ident[1] if ident else None

            track_states.append(TrackState(
                id=t.id,
                matched_frames=t.matched_frames,
                quality_metric=q,
                position=state[:3].tolist(),
                velocity=state[3:].tolist(),
                altitude=alt,
                speed=speed,
                status=status,
                identification=ident_str
            ))
            
        return FrameResponse(
            timestamp=current_time.isoformat(),
            active_tracks=len(tracker.tracks),
            tracks=track_states,
            active_conjunctions=tracker.active_conjunctions
        )
        
    except Exception as e:
        logger.error(f"Error processing frame: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "tracks": len(tracker.tracks)}

# ── WebSocket Simulation ──────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("🟢 React Frontend Connected via WebSocket!")

    station_data = build_station_data()

    # Default config
    config = {
        "nObjects": 5,
        "duration": 300,
        "speed": 0.5,
        "method": "jpda",
    }
    sim_task = None
    stop_flag = {"stop": False}

    # Send initial idle state
    await websocket.send_json({
        "tracks": [],
        "stations": station_data,
        "events": [{"type": "info", "message": "🟢 Connected — Configure and press Start"}],
        "stats": {"frame": 0, "totalTracks": 0, "activeTracks": 0,
                  "associationRate": 0, "method": config["method"].upper()},
        "phase": "Ready — Configure Mission",
        "simRunning": False,
    })

    try:
        from src.simulation.multi_object_scenarios import ScenarioGenerator
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            logger.debug(f"📩 Received: {msg}")

            action = msg.get("action", "")

            if action == "start":
                config["nObjects"] = msg.get("nObjects", 5)
                config["duration"] = msg.get("duration", 300)
                config["speed"]    = msg.get("speed", 0.5)
                config["method"]   = msg.get("method", "jpda")
                stop_flag["stop"]  = False

                logger.info(f"🚀 Starting simulation: {config}")

                if sim_task and not sim_task.done():
                    stop_flag["stop"] = True
                    await asyncio.sleep(0.2)
                    stop_flag["stop"] = False

                sim_task = asyncio.create_task(
                    run_simulation(websocket, station_data, config, stop_flag, ScenarioGenerator)
                )

            elif action == "stop":
                stop_flag["stop"] = True
                logger.info("🛑 Stopping simulation...")
                await websocket.send_json({
                    "tracks": [],
                    "stations": station_data,
                    "events": [{"type": "info", "message": "🛑 Simulation stopped by operator"}],
                    "stats": {"frame": 0, "totalTracks": 0, "activeTracks": 0,
                              "associationRate": 0, "method": config["method"].upper()},
                    "phase": "Stopped — Ready to Reconfigure",
                    "simRunning": False,
                })

            elif action == "update_speed":
                config["speed"] = msg.get("speed", 0.5)

    except Exception as e:
        logger.warning(f"🔴 Connection closed: {e}")

async def run_simulation(websocket, station_data, config, stop_flag, ScenarioGeneratorClass):
    """Run one full simulation cycle and stream data to React using the MultiObjectTracker."""
    events = []

    def add_event(event_type, message, track_id=None):
        events.append({
            "type": event_type,
            "message": message,
            "trackId": track_id,
        })

    n_objects = config["nObjects"]
    duration = config["duration"]
    method = config["method"]
    
    add_event("info", f"🌌 Initializing {method.upper()} tracker...")
    await websocket.send_json({
        "tracks": [],
        "stations": station_data,
        "events": events[-5:],
        "stats": {"frame": 0, "totalTracks": 0, "activeTracks": 0,
                  "associationRate": 0, "method": method.upper()},
        "phase": "Initializing Radar Network...",
        "simRunning": True,
    })
    await asyncio.sleep(1.0)

    if stop_flag["stop"]: return

    gen = ScenarioGeneratorClass()
    add_event("info", f"📡 Scanning for {n_objects} debris objects...")
    effective_duration = max(duration, 300)
    all_meas, ground_truth = gen.generate_scenario(n_objects=n_objects, duration_sec=effective_duration)

    if not all_meas:
        add_event("warning", "⚠️ No debris visible — retrying with longer arc...")
        all_meas, ground_truth = gen.generate_scenario(n_objects=n_objects, duration_sec=600)

    add_event("success", f"✅ Detected {len(all_meas)} radar measurements")

    await websocket.send_json({
        "tracks": [],
        "stations": station_data,
        "events": events[-5:],
        "stats": {"frame": 0, "totalTracks": 0, "activeTracks": 0,
                  "associationRate": 0, "method": method.upper(),
                  "totalMeasurements": len(all_meas)},
        "phase": f"Detected {len(all_meas)} Measurements — Starting Tracker",
        "simRunning": True,
    })
    await asyncio.sleep(1.0)

    if stop_flag["stop"]: return

    frames = {}
    for m in all_meas:
        frames.setdefault(m['time'], []).append(m)

    base_time = datetime.datetime.now(datetime.timezone.utc)
    sim_tracker = MultiObjectTracker(association_method=method)
    trail_history = {}
    MAX_TRAIL = 300
    ts = load.timescale()
    frame_num = 0
    sorted_offsets = sorted(frames.keys())

    for offset in sorted_offsets:
        if stop_flag["stop"]: return
        frame_num += 1
        current_time = base_time + datetime.timedelta(seconds=offset)
        
        t_skyfield = ts.from_datetime(current_time)
        gmst_rad = t_skyfield.gast * (np.pi / 12.0)

        prev_track_ids = {t.id for t in sim_tracker.tracks}
        sim_tracker.process_frame(current_time, frames[offset])

        curr_track_ids = {t.id for t in sim_tracker.tracks}
        for tid in (curr_track_ids - prev_track_ids):
            track = next((t for t in sim_tracker.tracks if t.id == tid), None)
            if track:
                alt = float(np.linalg.norm(track.state_estimate[:3])) - EARTH_RADIUS_KM
                add_event("new_track", f"🆕 Track {tid} acquired — Alt: {alt:.0f} km", tid)

        for tid in (prev_track_ids - curr_track_ids):
            add_event("pruned", f"💀 Track {tid} lost — signal faded", tid)

        track_payload = []
        for track in sim_tracker.tracks:
            state = track.state_estimate
            x, y, z = state[:3]
            x_ecef, y_ecef, z_ecef = eci_to_ecef(x, y, z, gmst_rad)

            alt = float(np.linalg.norm(state[:3])) - EARTH_RADIUS_KM
            speed = float(np.linalg.norm(state[3:]))
            updates = getattr(track.filter, 'update_count', 0)
            guardrail_activations = getattr(track.filter, 'guardrail_activations', 0)

            # Updated status based on quality metric if available
            q = track.quality_metric
            is_leo = (150 < alt < 2000) and (5.0 < speed < 10.0)
            if q < 0.3:
                status = "unstable"
            elif updates < 3:
                status = "acquiring"
            elif is_leo:
                status = "stable"
            else:
                status = "unstable"

            cov = np.cov(track.filter.particles[:, :3].T)
            pos_trace = np.trace(cov)
            raw_confidence = max(0, min(100, int(100 * np.exp(-pos_trace / 2000))))
            confidence = int(raw_confidence * max(0.3, 1.0 - guardrail_activations / 20.0))
            uncertainty_pct = 100 - confidence

            pos_3d = [float(x_ecef * SCALE), float(y_ecef * SCALE), float(z_ecef * SCALE)]

            if track.id not in trail_history: trail_history[track.id] = []
            trail_history[track.id].append(pos_3d)
            if len(trail_history[track.id]) > MAX_TRAIL:
                trail_history[track.id] = trail_history[track.id][-MAX_TRAIL:]

            regime_info = getattr(track, 'regime_info', None)
            regime_str = regime_info['regime'] if regime_info else (is_leo and "LEO" or "UCT")

            track_payload.append({
                "id": int(track.id),
                "position": pos_3d,
                "trail": list(trail_history[track.id]),
                "altitude": round(alt, 1),
                "speed": round(speed, 2),
                "status": status,
                "regime": regime_str,
                "updates": updates,
                "uncertainty": uncertainty_pct,
                "confidence": confidence,
                "missedDetections": track.missed_detections,
            })

        raw_assoc_rate = (sim_tracker.total_matches / max(sim_tracker.total_measurements, 1)) * 100
        validated_assoc_rate = (getattr(sim_tracker, 'validated_matches', 0) / max(sim_tracker.total_measurements, 1)) * 100
        assoc_rate = validated_assoc_rate if hasattr(sim_tracker, 'validated_matches') else raw_assoc_rate
        
        n_active = len(sim_tracker.tracks)
        if n_active == 0: phase = "Scanning for debris..."
        elif frame_num < 3: phase = f"Acquiring {n_active} target{'s' if n_active > 1 else ''}..."
        else: phase = f"Tracking {n_active} Object{'s' if n_active > 1 else ''} — {assoc_rate:.0f}% Association"

        if len(sim_tracker.active_conjunctions) > 0:
            phase = f"⚠️ CONJUNCTION ALERT — Tracking {n_active} Objects"

        station_counts = {}
        for m in frames[offset]:
            sid = m.get('station_id', 0)
            station_counts[sid] = station_counts.get(sid, 0) + 1
        active_station_idx = max(station_counts, key=station_counts.get) if station_counts else 0
        active_station_name = RADAR_STATIONS[active_station_idx % len(RADAR_STATIONS)]["name"].split()[0]

        conjunctions = [
            {"t1": c[0], "t2": c[1], "missDistance": c[2], "pc": c[3], "riskLevel": c[4]} 
            for c in sim_tracker.active_conjunctions
        ] if hasattr(sim_tracker, 'active_conjunctions') else []

        payload = {
            "tracks": track_payload,
            "stations": station_data,
            "events": events[-5:],
            "stats": {
                "frame": frame_num,
                "totalFrames": len(sorted_offsets),
                "activeTracks": n_active,
                "totalTracks": sim_tracker.next_track_id,
                "method": method.upper(),
                "associationRate": round(assoc_rate, 1),
                "rawAssociationRate": round(raw_assoc_rate, 1),
                "matches": sim_tracker.total_matches,
                "missed": sim_tracker.total_missed,
                "pruned": sim_tracker.total_pruned,
                "activeStation": active_station_name,
            },
            "phase": phase,
            "conjunctions": conjunctions,
            "simRunning": True,
        }

        await websocket.send_json(payload)
        current_delay = max(0.1, 0.7 / max(config["speed"], 0.1))
        await asyncio.sleep(current_delay)

    add_event("complete", f"✅ Mission Complete — {sim_tracker.next_track_id} tracks processed")
    
    if assoc_rate >= 85: rating = "EXCELLENT"
    elif assoc_rate >= 70: rating = "GOOD"
    else: rating = "NEEDS TUNING"

    add_event("info", f"📊 Validated Association: {assoc_rate:.1f}% — {rating}")

    await websocket.send_json({
        "tracks": track_payload if track_payload else [],
        "stations": station_data,
        "events": events[-8:],
        "stats": {
            "frame": frame_num,
            "totalFrames": len(sorted_offsets),
            "totalTracks": sim_tracker.next_track_id,
            "activeTracks": len(sim_tracker.tracks),
            "associationRate": round(assoc_rate, 1),
            "rawAssociationRate": round(raw_assoc_rate, 1),
            "method": method.upper(),
            "totalMeasurements": sim_tracker.total_measurements,
            "matches": sim_tracker.total_matches,
            "missed": sim_tracker.total_missed,
            "pruned": sim_tracker.total_pruned,
        },
        "phase": f"Mission Complete — {rating}",
        "simRunning": False,
    })
    logger.info("✅ Simulation complete.")
