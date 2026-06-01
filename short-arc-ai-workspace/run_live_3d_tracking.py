import asyncio
import json
import numpy as np
from fastapi import FastAPI, WebSocket
import uvicorn
from src.simulation.multi_object_scenarios import ScenarioGenerator
from src.tracking_system import MultiObjectTracker
from datetime import datetime, timezone
import datetime as dt
from skyfield.api import load

app = FastAPI()

# ── Constants ─────────────────────────────────────────────────────────
EARTH_RADIUS_KM = 6378.137
REACT_EARTH_RADIUS = 2.0
SCALE = REACT_EARTH_RADIUS / EARTH_RADIUS_KM

# Radar station metadata (matches ScenarioGenerator)
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


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🟢 React Frontend Connected!")

    station_data = build_station_data()

    # Default config
    config = {
        "nObjects": 5,
        "duration": 300,
        "speed": 0.5,
        "method": "jpda",
    }
    sim_running = False
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
        while True:
            # Listen for config messages from React
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            print(f"📩 Received: {msg}")

            action = msg.get("action", "")

            if action == "start":
                # Update config from frontend
                config["nObjects"] = msg.get("nObjects", 5)
                config["duration"] = msg.get("duration", 300)
                config["speed"]    = msg.get("speed", 0.5)
                config["method"]   = msg.get("method", "jpda")
                stop_flag["stop"]  = False

                print(f"🚀 Starting simulation: {config}")

                # Cancel any previous sim
                if sim_task and not sim_task.done():
                    stop_flag["stop"] = True
                    await asyncio.sleep(0.2)
                    stop_flag["stop"] = False

                sim_task = asyncio.create_task(
                    run_simulation(websocket, station_data, config, stop_flag)
                )

            elif action == "stop":
                stop_flag["stop"] = True
                print("🛑 Stopping simulation...")
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
        print(f"🔴 Connection closed: {e}")


async def run_simulation(websocket, station_data, config, stop_flag):
    """Run one full simulation cycle and stream data to React."""

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
    frame_delay = max(0.1, 0.7 / max(config["speed"], 0.1))

    # ── Phase 1: Scanning ─────────────────────────────────────────
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

    if stop_flag["stop"]:
        return

    # Generate scenario — pick nearby TLEs to force close approaches
    gen = ScenarioGenerator()
    add_event("info", f"📡 Scanning for {n_objects} debris objects...")
    # Use longer duration to get more orbital overlap (forces conjunctions)
    effective_duration = max(duration, 300)
    all_meas, ground_truth = gen.generate_scenario(
        n_objects=n_objects, duration_sec=effective_duration
    )

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

    if stop_flag["stop"]:
        return

    # Group measurements by time frame
    frames = {}
    for m in all_meas:
        frames.setdefault(m['time'], []).append(m)

    base_time = datetime.now(timezone.utc)
    tracker = MultiObjectTracker(association_method=method)

    # Store orbit trails (last N positions per track)
    trail_history = {}
    MAX_TRAIL = 300
    
    # Skyfield timescale for GMST calculation
    ts = load.timescale()

    frame_num = 0
    sorted_offsets = sorted(frames.keys())

    for offset in sorted_offsets:
        if stop_flag["stop"]:
            return

        frame_num += 1
        current_time = base_time + dt.timedelta(seconds=offset)
        
        # Calculate GMST (in radians) for ECI -> ECEF conversion
        t_skyfield = ts.from_datetime(current_time)
        gmst_hours = t_skyfield.gast  # Greenwich Apparent Sidereal Time (hours)
        gmst_rad = gmst_hours * (np.pi / 12.0)

        prev_track_ids = {t.id for t in tracker.tracks}

        # ── Process frame with the full model ─────────────────────
        tracker.process_frame(current_time, frames[offset])

        # ── Detect events ─────────────────────────────────────────
        curr_track_ids = {t.id for t in tracker.tracks}
        new_ids = curr_track_ids - prev_track_ids
        pruned_ids = prev_track_ids - curr_track_ids

        for tid in new_ids:
            track = next((t for t in tracker.tracks if t.id == tid), None)
            if track:
                alt = float(np.linalg.norm(track.state_estimate[:3])) - EARTH_RADIUS_KM
                add_event("new_track", f"🆕 Track {tid} acquired — Alt: {alt:.0f} km", tid)

        for tid in pruned_ids:
            add_event("pruned", f"💀 Track {tid} lost — signal faded", tid)

        # ── Build track payload ───────────────────────────────────
        track_payload = []
        for track in tracker.tracks:
            state = track.state_estimate
            x, y, z = state[:3]
            
            # Convert ECI to ECEF for 3D globe visualization
            x_ecef, y_ecef, z_ecef = eci_to_ecef(x, y, z, gmst_rad)

            alt = float(np.linalg.norm(state[:3])) - EARTH_RADIUS_KM
            speed = float(np.linalg.norm(state[3:]))
            updates = getattr(track.filter, 'update_count', 0)
            guardrail_activations = getattr(track.filter, 'guardrail_activations', 0)

            is_leo = (150 < alt < 2000) and (5.0 < speed < 10.0)
            if updates < 3:
                status = "acquiring"
            elif is_leo:
                status = "stable"
            else:
                status = "unstable"

            # Re-calculate correct ECEF particle spread
            raw_particles = track.filter.particles[:, :3]
            
            # Replace cosmetic confidence with statistically meaningful covariance trace
            cov = np.cov(raw_particles.T)
            pos_trace = np.trace(cov)  # km^2 (sum of variances in x, y, z)
            
            # Tuned for LEO particle filters where angles-only traces can be ~50,000 km²
            # e^(-trace / 50000) allows realistic along-track uncertainty to still map to decent confidence
            raw_confidence = max(0, min(100, int(100 * np.exp(-pos_trace / 50000))))
            
            # Decay guardrail activations faster (0.85 per update)
            effective_guardrails = guardrail_activations * (0.85 ** max(0, updates - 1))
            
            # Calculate base confidence with guardrail penalty
            confidence = int(raw_confidence * max(0.3, 1.0 - effective_guardrails / 30.0))
            
            # Boost based on number of successful updates (proven persistence)
            confidence = min(100, confidence + min(40, updates * 5))
            
            # Ensure STABLE tracks reflect actual stability in the UI
            if status == "stable":
                confidence = max(60, confidence)
            
            print(f"TRK-{track.id} | trace={pos_trace:.1f} raw_conf={raw_confidence} eff_gr={effective_guardrails:.1f} conf={confidence}")
            
            uncertainty_pct = 100 - confidence

            pos_3d = [float(x_ecef * SCALE), float(y_ecef * SCALE), float(z_ecef * SCALE)]

            if track.id not in trail_history:
                trail_history[track.id] = []
            trail_history[track.id].append(pos_3d)
            if len(trail_history[track.id]) > MAX_TRAIL:
                trail_history[track.id] = trail_history[track.id][-MAX_TRAIL:]

            sampled = raw_particles[:200]
            
            # Transform particles to ECEF
            clean = []
            for p in sampled:
                if not any(np.isnan(v) for v in p):
                    px, py, pz = eci_to_ecef(p[0], p[1], p[2], gmst_rad)
                    clean.append([float(px * SCALE), float(py * SCALE), float(pz * SCALE)])

            # Get regime if available
            regime = track.regime_info['regime'] if track.regime_info else "Unknown"

            # Detect maneuvers for event log
            if hasattr(track, 'last_manuever_dv') and track.last_manuever_dv > 0:
                dv_ms = track.last_manuever_dv * 1000
                add_event("maneuver", f"🚀 Track {track.id} performed {dv_ms:.1f} m/s maneuver!", track.id)
                track.last_manuever_dv = 0.0 # Reset once consumed by sim

            track_payload.append({
                "id": int(track.id),
                "position": pos_3d,
                "particles": clean,
                "trail": list(trail_history[track.id]),
                "altitude": round(alt, 1),
                "speed": round(speed, 2),
                "status": status,
                "regime": regime,
                "updates": updates,
                "uncertainty": uncertainty_pct,
                "confidence": confidence,
                "missedDetections": track.missed_detections,
            })

        # ── Stats ─────────────────────────────────────────────────
        raw_assoc_rate = (tracker.total_matches / max(tracker.total_measurements, 1)) * 100
        validated_assoc_rate = (getattr(tracker, 'validated_matches', 0) / max(tracker.total_measurements, 1)) * 100
        assoc_rate = validated_assoc_rate if hasattr(tracker, 'validated_matches') else raw_assoc_rate
        
        n_active = len(tracker.tracks)

        if n_active == 0:
            phase = "Scanning for debris..."
        elif frame_num < 3:
            phase = f"Acquiring {n_active} target{'s' if n_active > 1 else ''}..."
        else:
            phase = f"Tracking {n_active} Object{'s' if n_active > 1 else ''} — {assoc_rate:.0f}% Association"

        if hasattr(tracker, 'conjunction_warnings') and tracker.conjunction_warnings > 0:
            phase = f"⚠️ CONJUNCTION ALERT — Tracking {n_active} Objects"

        # Determine active station based on current frame measurements
        station_counts = {}
        for m in frames[offset]:
            sid = m.get('station_id', 0)
            station_counts[sid] = station_counts.get(sid, 0) + 1
        active_station_idx = max(station_counts, key=station_counts.get) if station_counts else 0
        active_station_name = RADAR_STATIONS[active_station_idx % len(RADAR_STATIONS)]["name"].split()[0]

        payload = {
            "tracks": track_payload,
            "stations": station_data,
            "events": events[-5:],
            "stats": {
                "frame": frame_num,
                "totalFrames": len(sorted_offsets),
                "activeTracks": n_active,
                "totalTracks": tracker.next_track_id,
                "method": method.upper(),
                "associationRate": round(assoc_rate, 1),
                "rawAssociationRate": round(raw_assoc_rate, 1),
                "matches": tracker.total_matches,
                "missed": tracker.total_missed,
                "pruned": tracker.total_pruned,
                "activeStation": active_station_name,
            },
            "phase": phase,
            "conjunctions": getattr(tracker, 'active_conjunctions', []),
            "simRunning": True,
        }

        await websocket.send_json(payload)

        # Use current speed config for frame delay
        current_delay = max(0.1, 0.7 / max(config["speed"], 0.1))
        await asyncio.sleep(current_delay)

    # ── Final report ──────────────────────────────────────────────
    add_event("complete", f"✅ Mission Complete — {tracker.next_track_id} tracks processed")
    
    raw_assoc_rate = (tracker.total_matches / max(tracker.total_measurements, 1)) * 100
    validated_assoc_rate = (getattr(tracker, 'validated_matches', 0) / max(tracker.total_measurements, 1)) * 100
    assoc_rate = validated_assoc_rate if hasattr(tracker, 'validated_matches') else raw_assoc_rate
    
    if assoc_rate >= 85:
        rating = "EXCELLENT"
    elif assoc_rate >= 70:
        rating = "GOOD"
    else:
        rating = "NEEDS TUNING"

    add_event("info", f"📊 Validated Association: {assoc_rate:.1f}% — {rating}")
    add_event("info", f"   (Raw gateway match rate: {raw_assoc_rate:.1f}%)")

    final_payload = {
        "tracks": track_payload if track_payload else [],
        "stations": station_data,
        "events": events[-8:],
        "stats": {
            "frame": frame_num,
            "totalFrames": len(sorted_offsets),
            "totalTracks": tracker.next_track_id,
            "activeTracks": len(tracker.tracks),
            "associationRate": round(assoc_rate, 1),
            "rawAssociationRate": round(raw_assoc_rate, 1),
            "method": method.upper(),
            "totalMeasurements": tracker.total_measurements,
            "matches": tracker.total_matches,
            "missed": tracker.total_missed,
            "pruned": tracker.total_pruned,
        },
        "phase": f"Mission Complete — {rating}",
        "simRunning": False,
    }
    await websocket.send_json(final_payload)
    print("✅ Simulation complete.")


if __name__ == "__main__":
    print("🚀 Starting Live Tracking Server on ws://localhost:8000/ws")
    uvicorn.run(app, host="0.0.0.0", port=8000)