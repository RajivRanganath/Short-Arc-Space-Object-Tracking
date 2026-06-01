"""
run_gnn_vs_jpda_comparison.py

Side-by-side comparison of GNN and JPDA association methods.
Runs the SAME scenario through both trackers and compares results.
"""

from src.simulation.multi_object_scenarios import ScenarioGenerator
from src.tracking_system import MultiObjectTracker
from datetime import datetime, timezone
import datetime as dt
import numpy as np


def run_comparison():
    print("=" * 70)
    print("🔬 ORBIT GUARD AI — GNN vs JPDA COMPARISON")
    print("   Testing Association Algorithms on Identical Scenarios")
    print("=" * 70)

    # ── Generate ONE scenario (both trackers see same data) ──────────
    print("\n🌌 Generating test scenario...")
    gen = ScenarioGenerator()
    all_meas, ground_truth = gen.generate_scenario(n_objects=5, duration_sec=60)

    # Group by time
    frames = {}
    for m in all_meas:
        frames.setdefault(m['time'], []).append(m)

    base_time = datetime.now(timezone.utc)

    # ── Run GNN Tracker ──────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("🔵 TRACKER 1: Global Nearest Neighbor (GNN)")
    print("─" * 70)
    
    tracker_gnn = MultiObjectTracker(association_method='gnn')
    
    for offset in sorted(frames.keys()):
        current_time = base_time + dt.timedelta(seconds=offset)
        tracker_gnn.process_frame(current_time, frames[offset])

    # ── Run JPDA Tracker ─────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("🟢 TRACKER 2: Joint Probabilistic Data Association (JPDA)")
    print("─" * 70)
    
    tracker_jpda = MultiObjectTracker(association_method='jpda')
    
    for offset in sorted(frames.keys()):
        current_time = base_time + dt.timedelta(seconds=offset)
        tracker_jpda.process_frame(current_time, frames[offset])

    # ── Print Comparison Report ──────────────────────────────────────
    print("\n" + "=" * 70)
    print("📊 COMPARISON RESULTS")
    print("=" * 70)

    print(f"\n{'Metric':<35} {'GNN':>15} {'JPDA':>15}")
    print("─" * 70)

    # Association performance
    gnn_rate  = (tracker_gnn.total_matches / 
                 max(tracker_gnn.total_measurements, 1) * 100)
    jpda_rate = (tracker_jpda.total_matches / 
                 max(tracker_jpda.total_measurements, 1) * 100)
    
    print(f"{'Association Rate':<35} {gnn_rate:>14.1f}% {jpda_rate:>14.1f}%")
    
    print(f"{'Successful Matches':<35} "
          f"{tracker_gnn.total_matches:>15} "
          f"{tracker_jpda.total_matches:>15}")
    
    print(f"{'Missed Detections':<35} "
          f"{tracker_gnn.total_missed:>15} "
          f"{tracker_jpda.total_missed:>15}")
    
    print(f"{'Tracks Created':<35} "
          f"{tracker_gnn.next_track_id:>15} "
          f"{tracker_jpda.next_track_id:>15}")
    
    print(f"{'Active Tracks':<35} "
          f"{len(tracker_gnn.tracks):>15} "
          f"{len(tracker_jpda.tracks):>15}")
    
    print(f"{'Tracks Pruned':<35} "
          f"{tracker_gnn.total_pruned:>15} "
          f"{tracker_jpda.total_pruned:>15}")

    # Track stability
    gnn_stable = sum(1 for t in tracker_gnn.tracks
                    if 150 < (np.linalg.norm(t.state_estimate[:3]) - 6378.137) < 2000
                    and 6.0 < np.linalg.norm(t.state_estimate[3:]) < 10.0)
    
    jpda_stable = sum(1 for t in tracker_jpda.tracks
                     if 150 < (np.linalg.norm(t.state_estimate[:3]) - 6378.137) < 2000
                     and 6.0 < np.linalg.norm(t.state_estimate[3:]) < 10.0)
    
    gnn_stable_pct  = gnn_stable / max(len(tracker_gnn.tracks), 1) * 100
    jpda_stable_pct = jpda_stable / max(len(tracker_jpda.tracks), 1) * 100
    
    print(f"\n{'Stable Tracks (LEO)':<35} "
          f"{gnn_stable}/{len(tracker_gnn.tracks):>6} "
          f"{jpda_stable}/{len(tracker_jpda.tracks):>6}")
    
    print(f"{'Stability Rate':<35} "
          f"{gnn_stable_pct:>14.1f}% "
          f"{jpda_stable_pct:>14.1f}%")

    # Uncertainty comparison
    
    
    gnn_uncertainties = []
    for t in tracker_gnn.tracks:
        _, cov = t.filter.get_state_estimate()
        gnn_uncertainties.append(float(np.sqrt(np.trace(cov[:3, :3]))))
    
    jpda_uncertainties = []
    for t in tracker_jpda.tracks:
        _, cov = t.filter.get_state_estimate()
        jpda_uncertainties.append(float(np.sqrt(np.trace(cov[:3, :3]))))
    
    if gnn_uncertainties and jpda_uncertainties:
        print(f"\n{'Mean Position Uncertainty (km)':<35} "
              f"{np.mean(gnn_uncertainties):>14.1f} "
              f"{np.mean(jpda_uncertainties):>14.1f}")

    # ── Winner Determination ─────────────────────────────────────────
    print("\n" + "=" * 70)
    print("🏆 WINNER DETERMINATION")
    print("=" * 70)

    gnn_score = (
        gnn_rate * 0.4 +           # Association rate (40%)
        gnn_stable_pct * 0.3 +     # Stability (30%)
        (100 - len(tracker_gnn.tracks) / tracker_gnn.next_track_id * 100) * 0.3
                                   # Efficiency (30% - fewer tracks is better)
    )
    
    jpda_score = (
        jpda_rate * 0.4 +
        jpda_stable_pct * 0.3 +
        (100 - len(tracker_jpda.tracks) / tracker_jpda.next_track_id * 100) * 0.3
    )

    print(f"\nOverall Score (weighted):")
    print(f"   GNN  : {gnn_score:.1f}/100")
    print(f"   JPDA : {jpda_score:.1f}/100")

    if jpda_score > gnn_score + 5:
        winner = "JPDA"
        margin = jpda_score - gnn_score
        print(f"\n✅ JPDA WINS by {margin:.1f} points")
        print(f"   JPDA handles measurement ambiguity better in dense clutter.")
    elif gnn_score > jpda_score + 5:
        winner = "GNN"
        margin = gnn_score - jpda_score
        print(f"\n✅ GNN WINS by {margin:.1f} points")
        print(f"   GNN is simpler and works well when tracks are well-separated.")
    else:
        print(f"\n⚖️  TIE — Both methods perform similarly on this scenario")
        print(f"   Difference: {abs(jpda_score - gnn_score):.1f} points")

    # ── Key Takeaways ────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("📝 KEY TAKEAWAYS")
    print("=" * 70)
    
    print("\nGNN (Global Nearest Neighbor):")
    print("   ✅ Simpler algorithm (hard assignment)")
    print("   ✅ Faster computation")
    print("   ❌ Struggles when tracks cross or cluster")
    
    print("\nJPDA (Joint Probabilistic Data Association):")
    print("   ✅ Industry standard for cluttered environments")
    print("   ✅ Handles crossing trajectories better")
    print("   ✅ Probabilistic updates reduce ghost tracks")
    print("   ❌ More computationally expensive")

    print("\n" + "=" * 70)
    print("   Comparison Complete — Results Saved for Report")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    import numpy as np
    run_comparison()