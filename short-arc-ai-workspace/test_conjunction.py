
import numpy as np
from src.tracking.conjunction import ConjunctionAssessment
from datetime import datetime, timezone

# Example 1: Basic Conjunction Check
def example_basic_check():
    """Simple conjunction assessment between two tracks"""
    
    # Initialize system
    ca = ConjunctionAssessment(hard_body_radius_km=0.015)  # 15 meters
    
    # Simulate two tracks (in reality, these come from your tracker)
    class MockTrack:
        def __init__(self, track_id, position, velocity):
            self.id = track_id
            self.state_estimate = np.concatenate([position, velocity])
            self.last_update_time = datetime.now(timezone.utc)
            
            # Mock filter with particles
            class MockFilter:
                def __init__(self, state):
                    # Generate 200 particles around state with uncertainty
                    self.particles = np.random.multivariate_normal(
                        mean=state,
                        cov=np.diag([50**2, 50**2, 50**2, 1**2, 1**2, 1**2]),
                        size=200
                    )
            self.filter = MockFilter(self.state_estimate)
    
    # Track 1: Altitude 800 km, circular orbit
    track1 = MockTrack(
        track_id=0,
        position=np.array([7178.0, 0.0, 0.0]),     # km
        velocity=np.array([0.0, 7.5, 0.0])         # km/s
    )
    
    # Track 2: Similar orbit, potential conjunction
    track2 = MockTrack(
        track_id=1,
        position=np.array([7180.0, 5.0, 0.0]),     # 5 km away
        velocity=np.array([0.0, 7.5, 0.05])        # Slightly different velocity
    )
    
    # Run conjunction assessment
    miss_dist, tca, alerts, pc, risk = ca.get_close_approaches(
        track1, track2,
        lookahead_hours=3,
        threshold_km=100
    )
    
    # Print results
    print("\n" + "="*60)
    print("CONJUNCTION ASSESSMENT RESULTS")
    print("="*60)
    print(f"Miss Distance:    {miss_dist:.2f} km")
    print(f"TCA:              {tca/3600:.2f} hours from now")
    print(f"Pc:               {pc:.2e}")
    print(f"Risk Level:       {risk}")
    print("\nAlerts:")
    for alert in alerts:
        print(f"  {alert}")
    print("="*60 + "\n")

# Example 2: Monitor Multiple Track Pairs Over Time
def example_continuous_monitoring():
    """Monitor multiple conjunctions over time"""
    
    ca = ConjunctionAssessment(hard_body_radius_km=0.020)  # 20 meters
    
    # Simulate 5 tracks
    tracks = []
    for i in range(5):
        altitude = 700 + i * 50  # 700, 750, 800, 850, 900 km
        r_mag = 6378.137 + altitude
        v_circ = np.sqrt(398600.4418 / r_mag)
        
        # Random positions in circular orbits
        angle = i * np.pi / 5
        pos = r_mag * np.array([np.cos(angle), np.sin(angle), 0.0])
        vel = v_circ * np.array([-np.sin(angle), np.cos(angle), 0.0])
        
        class MockTrack:
            def __init__(self, tid, p, v):
                self.id = tid
                self.state_estimate = np.concatenate([p, v])
                self.last_update_time = datetime.now(timezone.utc)
                class MockFilter:
                    def __init__(self, state):
                        self.particles = np.random.multivariate_normal(
                            mean=state,
                            cov=np.diag([80**2, 80**2, 80**2, 2**2, 2**2, 2**2]),
                            size=200
                        )
                self.filter = MockFilter(self.state_estimate)
        
        tracks.append(MockTrack(i, pos, vel))
    
    # Check all pairs
    print("\n" + "="*60)
    print("MULTI-TRACK CONJUNCTION SCREENING")
    print("="*60)
    
    conjunction_count = 0
    for i in range(len(tracks)):
        for j in range(i+1, len(tracks)):
            miss_dist, tca, alerts, pc, risk = ca.get_close_approaches(
                tracks[i], tracks[j],
                lookahead_hours=6,
                threshold_km=200
            )
            
            if risk != 'GREEN':
                conjunction_count += 1
                print(f"\nTrack {i} vs Track {j}:")
                print(f"  Miss Distance: {miss_dist:.2f} km")
                print(f"  Pc: {pc:.2e}")
                print(f"  Risk: {risk}")
    
    if conjunction_count == 0:
        print("\n✅ No conjunctions detected - All clear!")
    else:
        print(f"\n⚠️  {conjunction_count} conjunction(s) detected")
    
    print("="*60 + "\n")
    
    # Generate report
    ca.generate_conjunction_report('conjunction_example_report.txt')
    
    # Print statistics
    stats = ca.get_statistics()
    print("\nStatistics:")
    print(f"  Total Events: {stats['total_events']}")
    print(f"  Red: {stats['red_events']}")
    print(f"  Yellow: {stats['yellow_events']}")
    print(f"  Green: {stats['green_events']}")

# Example 3: Visualize Conjunction Geometry
def example_visualization():
    """Create conjunction visualization"""
    
    ca = ConjunctionAssessment(hard_body_radius_km=0.015)
    
    # Create two tracks on collision course
    class MockTrack:
        def __init__(self, tid, p, v):
            self.id = tid
            self.state_estimate = np.concatenate([p, v])
            self.last_update_time = datetime.now(timezone.utc)
            class MockFilter:
                def __init__(self, state):
                    # Smaller uncertainty for cleaner visualization
                    self.particles = np.random.multivariate_normal(
                        mean=state,
                        cov=np.diag([30**2, 30**2, 30**2, 1**2, 1**2, 1**2]),
                        size=200
                    )
            self.filter = MockFilter(self.state_estimate)
    
    track1 = MockTrack(0, np.array([7178.0, 0.0, 0.0]), np.array([0.0, 7.5, 0.0]))
    track2 = MockTrack(1, np.array([7180.0, 2.0, 0.0]), np.array([0.0, 7.5, 0.01]))
    
    # Calculate conjunction
    miss_dist, tca, alerts, pc, risk = ca.get_close_approaches(
        track1, track2,
        lookahead_hours=1,
        threshold_km=50
    )
    
    print(f"\nVisualizing conjunction: Pc = {pc:.2e}, Risk = {risk}")
    
    # Plot 3D uncertainty ellipsoid
    ca.plot_conjunction_ellipsoid(track1, track2, tca, 
                                  save_path='conjunction_ellipsoid.png')
    
    # Plot Pc evolution (need multiple observations for this)
    # ca.plot_pc_evolution(0, 1, save_path='pc_evolution.png')

# Example 4: Integration with Tracking System
def example_tracking_integration():
    """Show how to integrate with your existing tracker"""
    
    print("\n" + "="*60)
    print("TRACKING SYSTEM INTEGRATION EXAMPLE")
    print("="*60)
    
    code_example = """
# In your tracking_system.py:

from conjunction_PRODUCTION import ConjunctionAssessment

class MultiObjectTracker:
    def __init__(self):
        self.tracks = []
        self.ca = ConjunctionAssessment(hard_body_radius_km=0.015)
        self.conj_counter = 0
    
    def _check_all_conjunctions(self):
        active_tracks = [t for t in self.tracks if t.missed_detections == 0]
        n = len(active_tracks)
        if n < 2:
            return
        
        # Only check every 10 frames to save computation
        self.conj_counter += 1
        if self.conj_counter % 10 != 0:
            return
        
        print(f"   🔍 Running conjunction assessment on {n} tracks...")
        
        for i in range(n):
            for j in range(i + 1, n):
                t1, t2 = active_tracks[i], active_tracks[j]
                
                # Quick distance screen
                curr_dist = np.linalg.norm(t1.state_estimate[:3] - t2.state_estimate[:3])
                if curr_dist > 1000:  # Skip if far apart
                    continue
                
                # Full conjunction assessment with Pc
                miss_dist, tca, alerts, pc, risk = self.ca.get_close_approaches(
                    t1, t2,
                    lookahead_hours=3,
                    threshold_km=100
                )
                
                # Alert based on risk level
                if risk == 'RED':
                    print(f"   🚨 CRITICAL CONJUNCTION!")
                    print(f"      Tracks {t1.id} vs {t2.id}")
                    print(f"      Pc = {pc:.2e}")
                    print(f"      Miss Distance = {miss_dist:.2f} km")
                    print(f"      TCA = {tca/3600:.2f} hours")
                    for alert in alerts:
                        print(f"      {alert}")
                
                elif risk == 'YELLOW':
                    print(f"   ⚠️  CAUTION: Tracks {t1.id} vs {t2.id}, Pc = {pc:.2e}")
    """
    
    print(code_example)
    print("="*60 + "\n")

# Run all examples
if __name__ == "__main__":
    print("\n" + "🚀 CONJUNCTION ASSESSMENT EXAMPLES" + "\n")
    
    print("Example 1: Basic Conjunction Check")
    example_basic_check()
    
    print("\n" + "-"*60 + "\n")
    
    print("Example 2: Continuous Multi-Track Monitoring")
    example_continuous_monitoring()
    
    print("\n" + "-"*60 + "\n")
    
    print("Example 3: Visualization")
    example_visualization()
    
    print("\n" + "-"*60 + "\n")
    
    print("Example 4: Tracking System Integration")
    example_tracking_integration()
    
    print("\n✅ All examples completed!\n")