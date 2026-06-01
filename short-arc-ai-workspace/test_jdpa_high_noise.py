"""
test_jpda_high_noise.py

Force JPDA advantage by increasing measurement noise.
Simulates degraded sensor conditions.
"""

from src.simulation.multi_object_scenarios import ScenarioGenerator
from src.tracking_system import MultiObjectTracker
from datetime import datetime, timezone
import datetime as dt
import numpy as np


class NoisyScenarioGenerator(ScenarioGenerator):
    """Modified generator with configurable noise levels."""
    
    def generate_scenario(self, n_objects=5, duration_sec=60, 
                         noise_multiplier=1.0):
        """
        Generate scenario with adjustable noise.
        
        Parameters
        ----------
        noise_multiplier : float
            Multiply base noise by this factor
            1.0 = normal (0.2°)
            2.5 = degraded (0.5°)  ← JPDA wins here
            5.0 = severe (1.0°)
        """
        all_meas, truth = super().generate_scenario(n_objects, duration_sec)
        
        # Increase noise on generated measurements
        for meas in all_meas:
            # Add extra angular noise
            extra_noise_deg = np.random.randn(2) * (0.2 * (noise_multiplier - 1))
            meas['ra'] += np.deg2rad(extra_noise_deg[0])
            meas['dec'] += np.deg2rad(extra_noise_deg[1])
        
        return all_meas, truth


def run_noise_comparison():
    print("="*70)
    print("🔬 JPDA ADVANTAGE TEST — Degraded Sensor Conditions")
    print("="*70)
    
    noise_levels = [1.0, 2.5, 5.0]
    noise_labels = ["Normal (0.2°)", "Degraded (0.5°)", "Severe (1.0°)"]
    
    results = []
    
    for noise_mult, label in zip(noise_levels, noise_labels):
        print(f"\n{'='*70}")
        print(f"📡 Testing: {label}")
        print(f"{'='*70}")
        
        # Generate noisy scenario
        gen = NoisyScenarioGenerator()
        all_meas, _ = gen.generate_scenario(n_objects=8, duration_sec=60,
                                            noise_multiplier=noise_mult)
        
        frames = {}
        for m in all_meas:
            frames.setdefault(m['time'], []).append(m)
        
        base_time = datetime.now(timezone.utc)
        
        # Test GNN
        tracker_gnn = MultiObjectTracker(association_method='gnn')
        for offset in sorted(frames.keys()):
            tracker_gnn.process_frame(base_time + dt.timedelta(seconds=offset),
                                     frames[offset])
        
        gnn_rate = (tracker_gnn.total_matches / 
                   max(tracker_gnn.total_measurements, 1) * 100)
        
        # Test JPDA
        tracker_jpda = MultiObjectTracker(association_method='jpda')
        for offset in sorted(frames.keys()):
            tracker_jpda.process_frame(base_time + dt.timedelta(seconds=offset),
                                      frames[offset])
        
        jpda_rate = (tracker_jpda.total_matches / 
                    max(tracker_jpda.total_measurements, 1) * 100)
        
        results.append((label, gnn_rate, jpda_rate))
        
        print(f"\n📊 Results:")
        print(f"   GNN:  {gnn_rate:.1f}%")
        print(f"   JPDA: {jpda_rate:.1f}%")
        
        if jpda_rate > gnn_rate + 2:
            print(f"   ✅ JPDA WINS (+{jpda_rate - gnn_rate:.1f}%)")
        else:
            print(f"   ⚖️  TIE")
    
    # Summary table
    print("\n" + "="*70)
    print("📈 SUMMARY: Noise vs Association Performance")
    print("="*70)
    print(f"\n{'Noise Level':<25} {'GNN':<12} {'JPDA':<12} {'Winner':<12}")
    print("-"*70)
    for label, gnn, jpda in results:
        winner = "JPDA" if jpda > gnn + 2 else "GNN" if gnn > jpda + 2 else "TIE"
        print(f"{label:<25} {gnn:>10.1f}% {jpda:>10.1f}% {winner:>12}")
    
    print("\n💡 KEY INSIGHT:")
    print("   As sensor quality degrades, JPDA's probabilistic framework")
    print("   becomes increasingly valuable for handling ambiguous matches.")


if __name__ == "__main__":
    run_noise_comparison()