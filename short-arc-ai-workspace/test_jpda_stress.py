"""
Stress test: When does JPDA beat GNN?
Tests 3 difficulty levels with active Radar Clutter (Ghosts).

    python test_jpda_stress.py --seed 7     # one reproducible run
    python test_jpda_stress.py --seeds 30   # seeds 0..29, summary stats
"""
from src.simulation.multi_object_scenarios import ScenarioGenerator
from src.tracking_system import MultiObjectTracker
from datetime import datetime, timezone
import datetime as dt
import numpy as np
import random
import argparse
import contextlib
import io
import logging
from scipy import stats

# Fixed epoch so the satellite geometry is the same every run
# (half a day after the Fengyun-1C TLE epoch, 2026-02-08).
BASE_TIME = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)

def run_difficulty_test(n_objects, label, ghosts_per_frame=0, seed=0):
    # One seed drives every random source: object pick and shuffle (random),
    # radar noise, ghosts and EnKF particles (np.random global state).
    random.seed(seed)
    np.random.seed(seed)

    print(f"\n{'='*70}")
    print(f"🔬 TESTING: {label} ({n_objects} objects + {ghosts_per_frame} Ghosts/Frame)")
    print(f"{'='*70}")

    gen = ScenarioGenerator()
    all_meas, _ = gen.generate_scenario(n_objects=n_objects, duration_sec=60, start_time=BASE_TIME)
    if not all_meas:
        # No object rose above 5 deg elevation at any radar: no frames, no ghosts,
        # and the rates below are 0/max(0,1) = 0.0, which means "no data", not 0%.
        print("   ⚠️  No object in view of any radar in this window; rates are not meaningful.")

    frames = {}
    for m in all_meas:
        frames.setdefault(m['time'], []).append(m)

    # ==========================================
    # 👻 THE CLUTTER INJECTION ENGINE
    # ==========================================
    if ghosts_per_frame > 0:
        for offset, meas_list in frames.items():
            if not meas_list:
                continue
            # Get the radar site coordinates to make the ghosts look like valid data packets
            site_eci = meas_list[0]['site_eci']

            for _ in range(ghosts_per_frame):
                ghost_meas = {
                    'time': offset,
                    'ra': np.random.uniform(-np.pi, np.pi),           # Random Angle
                    'dec': np.random.uniform(-np.pi/2, np.pi/2),      # Random Angle
                    'range': np.random.uniform(300.0, 3000.0),        # Random LEO altitude
                    'site_eci': site_eci,
                    'true_range_km': 0.0                              # Flagged as fake for debugging
                }
                frames[offset].append(ghost_meas)

            # Shuffle so the tracker can't just pick the first ones
            random.shuffle(frames[offset])
    # ==========================================

    base_time = BASE_TIME

    # Test GNN
    tracker_gnn = MultiObjectTracker(association_method='gnn')
    for offset in sorted(frames.keys()):
        tracker_gnn.process_frame(base_time + dt.timedelta(seconds=offset), frames[offset])

    # Test JPDA
    tracker_jpda = MultiObjectTracker(association_method='jpda')
    for offset in sorted(frames.keys()):
        tracker_jpda.process_frame(base_time + dt.timedelta(seconds=offset), frames[offset])

    # Results
    gnn_rate = tracker_gnn.total_matches / max(tracker_gnn.total_measurements, 1) * 100
    jpda_rate = tracker_jpda.total_matches / max(tracker_jpda.total_measurements, 1) * 100

    gnn_stable = sum(1 for t in tracker_gnn.tracks
                    if 150 < (np.linalg.norm(t.state_estimate[:3]) - 6378.137) < 2000
                    and 6.0 < np.linalg.norm(t.state_estimate[3:]) < 10.0)

    jpda_stable = sum(1 for t in tracker_jpda.tracks
                    if 150 < (np.linalg.norm(t.state_estimate[:3]) - 6378.137) < 2000
                    and 6.0 < np.linalg.norm(t.state_estimate[3:]) < 10.0)

    print(f"\n📊 RESULTS:")
    print(f"   GNN:  {gnn_rate:.1f}% assoc | {gnn_stable}/{len(tracker_gnn.tracks)} stable | {tracker_gnn.total_pruned} pruned")
    print(f"   JPDA: {jpda_rate:.1f}% assoc | {jpda_stable}/{len(tracker_jpda.tracks)} stable | {tracker_jpda.total_pruned} pruned")

    if jpda_rate > gnn_rate + 2:
        print(f"   ✅ JPDA WINS (+{jpda_rate - gnn_rate:.1f}%)")
    elif gnn_rate > jpda_rate + 2:
        print(f"   ✅ GNN WINS (+{gnn_rate - jpda_rate:.1f}%)")
    else:
        print(f"   ⚖️  TIE (difference: {abs(jpda_rate - gnn_rate):.1f}%)")

    return (gnn_rate, jpda_rate, len(all_meas),
            (gnn_stable, len(tracker_gnn.tracks)), (jpda_stable, len(tracker_jpda.tracks)))

LEVELS = [(3, "EASY — 3 objects", 0), (5, "MEDIUM — 5 objects", 5), (8, "HARD — dense cloud", 15)]

def run_seed_sweep(n_seeds):
    logging.disable(logging.INFO)  # tracker logs every frame; keep only the summary
    for n_objects, label, ghosts in LEVELS:
        rows = []
        for seed in range(n_seeds):
            with contextlib.redirect_stdout(io.StringIO()):
                rows.append(run_difficulty_test(n_objects, label, ghosts, seed))
        used = [r for r in rows if r[2] > 0]  # empty scenarios have no rate to compare
        g = np.array([r[0] for r in used])
        j = np.array([r[1] for r in used])
        d = j - g
        half = stats.t.ppf(0.975, len(used) - 1) * d.std(ddof=1) / np.sqrt(len(used))
        g_st, g_tot = (sum(r[3][k] for r in rows) for k in (0, 1))
        j_st, j_tot = (sum(r[4][k] for r in rows) for k in (0, 1))
        print(f"\n{label} ({ghosts} ghosts/frame), {n_seeds} seeds")
        print("   seed  real_meas    GNN%   JPDA%   GNN stable   JPDA stable")
        for seed, r in enumerate(rows):
            print(f"   {seed:>4}  {r[2]:>9}  {r[0]:>6.1f}  {r[1]:>6.1f}   {r[3][0]:>4}/{r[3][1]:<6}  {r[4][0]:>4}/{r[4][1]}")
        print(f"   Stats below use the {len(used)} seeds with at least one real measurement")
        print(f"   GNN  mean {g.mean():.1f}  sd {g.std(ddof=1):.1f}")
        print(f"   JPDA mean {j.mean():.1f}  sd {j.std(ddof=1):.1f}")
        print(f"   JPDA minus GNN: {d.mean():+.1f} points, 95% CI [{d.mean() - half:+.1f}, {d.mean() + half:+.1f}]")
        print(f"   JPDA wins {int((d > 0).sum())}, ties {int((d == 0).sum())}, GNN wins {int((d < 0).sum())}")
        print(f"   Stable tracks: GNN {g_st}/{g_tot}, JPDA {j_st}/{j_tot}")
        print(f"   Seeds with no real measurements (excluded): {len(rows) - len(used)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--seeds", type=int, help="run seeds 0..N-1 and print summary stats")
    args = parser.parse_args()
    if args.seeds:
        run_seed_sweep(args.seeds)
        raise SystemExit

    # Run 3 difficulty levels with increasing clutter
    print("="*70)
    print("🧪 JPDA STRESS TEST — When Does Probabilistic Association Win?")
    print("="*70)

    easy_gnn, easy_jpda = run_difficulty_test(3, "EASY — 3 objects", 0, args.seed)[:2]
    med_gnn, med_jpda = run_difficulty_test(5, "MEDIUM — 5 objects", 5, args.seed)[:2]
    hard_gnn, hard_jpda = run_difficulty_test(8, "HARD — dense cloud", 15, args.seed)[:2]

    # Summary
    print("\n" + "="*70)
    print("📈 SUMMARY ACROSS DIFFICULTY LEVELS")
    print("="*70)
    print(f"\nScenario          GNN Accuracy    JPDA Accuracy    Winner")
    print("-" * 60)
    print(f"Easy (3 obj)      {easy_gnn:>11.1f}%    {easy_jpda:>12.1f}%    {'JPDA' if easy_jpda > easy_gnn else 'GNN' if easy_gnn > easy_jpda else 'TIE'}")
    print(f"Medium (5 obj)    {med_gnn:>11.1f}%    {med_jpda:>12.1f}%    {'JPDA' if med_jpda > med_gnn else 'GNN' if med_gnn > med_jpda else 'TIE'}")
    print(f"Hard (8 obj)      {hard_gnn:>11.1f}%    {hard_jpda:>12.1f}%    {'JPDA' if hard_jpda > hard_gnn else 'GNN' if hard_gnn > hard_jpda else 'TIE'}")

    print("\n💡 KEY INSIGHT:")
    if hard_jpda > hard_gnn + 2:
        print("   JPDA drastically outperforms GNN when radar clutter increases.")
        print("   Probabilistic association successfully filters out ghost tracks.")
    else:
        print("   GNN and JPDA tied. The noise rejection gate might be too tight.")
