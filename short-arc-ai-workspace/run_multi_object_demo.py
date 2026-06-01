from src.simulation.multi_object_scenarios import ScenarioGenerator
from src.tracking_system import MultiObjectTracker
from datetime import datetime, timezone

def run_mission():
    print("=" * 50)
    print("🌌 ORBIT GUARD AI - MULTI-OBJECT TRACKING (MONTH 1 FINAL)")
    print("=" * 50)

    # ── 1. Generate Scenario ──────────────────────────────────────────
    gen      = ScenarioGenerator()
    all_meas, ground_truth = gen.generate_scenario(n_objects=5, duration_sec=60)

    # ── 2. Group measurements by time frame ──────────────────────────
    frames = {}
    for m in all_meas:
        t = m['time']
        if t not in frames:
            frames[t] = []
        frames[t].append(m)

    # ── 3. Run Tracker ────────────────────────────────────────────────
    tracker   = MultiObjectTracker()
    base_time = datetime.now(timezone.utc)

    import datetime as dt
    for frame_offset in sorted(frames.keys()):
        current_time = base_time + dt.timedelta(seconds=frame_offset)
        tracker.process_frame(current_time, frames[frame_offset])

    # ── 4. Print full mission report ──────────────────────────────────
    tracker.print_mission_report()


if __name__ == "__main__":
    run_mission()
