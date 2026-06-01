"""
Stress test: When does JPDA beat GNN?
Tests 3 difficulty levels with active Radar Clutter (Ghosts).
"""
from src.simulation.multi_object_scenarios import ScenarioGenerator
from src.tracking_system import MultiObjectTracker
from datetime import datetime, timezone
import datetime as dt
import numpy as np
import random

def run_difficulty_test(n_objects, label, ghosts_per_frame=0):
    print(f"\n{'='*70}")
    print(f"🔬 TESTING: {label} ({n_objects} objects + {ghosts_per_frame} Ghosts/Frame)")
    print(f"{'='*70}")
    
    gen = ScenarioGenerator()
    all_meas, _ = gen.generate_scenario(n_objects=n_objects, duration_sec=60)
    
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
    
    base_time = datetime.now(timezone.utc)
    
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
    
    return gnn_rate, jpda_rate

# Run 3 difficulty levels with increasing clutter
print("="*70)
print("🧪 JPDA STRESS TEST — When Does Probabilistic Association Win?")
print("="*70)

easy_gnn, easy_jpda = run_difficulty_test(3, "EASY — 3 objects", ghosts_per_frame=0)
med_gnn, med_jpda = run_difficulty_test(5, "MEDIUM — 5 objects", ghosts_per_frame=5)
hard_gnn, hard_jpda = run_difficulty_test(8, "HARD — dense cloud", ghosts_per_frame=15)

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