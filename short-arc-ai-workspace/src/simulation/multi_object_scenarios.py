import numpy as np
import random
from src.simulation.radar_sim import RadarSimulator

class ScenarioGenerator:
    def __init__(self):
        # Global Multi-Radar Network
        self.radars = [
            RadarSimulator(lat=12.9716, lon=77.5946, alt_m=920),     # ISTRAC Bangalore (Equatorial)
            RadarSimulator(lat=78.2232, lon=15.6267, alt_m=460),     # SvalSat, Norway (North Polar)
            RadarSimulator(lat=-77.8463, lon=166.6682, alt_m=10)     # McMurdo, Antarctica (South Polar)
        ]
        
    def load_tle_file(self, filepath):
        """Reads a 3-line TLE file and returns a list of (L1, L2) tuples"""
        with open(filepath, 'r') as f:
            lines = f.readlines()
            
        tles = []
        # TLEs come in sets of 3 lines (Name, Line 1, Line 2)
        for i in range(0, len(lines), 3):
            if i+2 < len(lines):
                l1 = lines[i+1].strip()
                l2 = lines[i+2].strip()
                tles.append((l1, l2))
        return tles

    def generate_scenario(self, n_objects=5, duration_sec=60):
        """
        Picks N random objects and generates a mixed stream of measurements.
        """
        print(f"🌌 Generating scenario with {n_objects} debris objects...")
        
        # 1. Load Real Debris Data
        all_tles = self.load_tle_file('data/fengyun_1c.txt')
        
        if len(all_tles) < n_objects:
            print(f"⚠️  Not enough TLEs found. Using all {len(all_tles)} objects.")
            selected_tles = all_tles
        else:
            # Pick random objects to track
            selected_tles = random.sample(all_tles, n_objects)
            
        # 2. Generate Observations for Each Object
        # We use a fixed start time for everyone so they fly together
        from datetime import datetime, timezone
        start_time = datetime.now(timezone.utc)
        
        all_measurements = []
        ground_truth_tracks = {} # To verify accuracy later
        
        for obj_id, (l1, l2) in enumerate(selected_tles):
            print(f"   Simulating Object #{obj_id+1} across global network...")
            
            obj_measurements = []
            for radar in self.radars:
                # Generate Arc using our existing simulator
                obs_list = radar.generate_arc(l1, l2, start_time, duration_sec, step_sec=5)
                
                # Tag observations with the TRUE object ID (for debugging/grading)
                # In the real world, the tracker WON'T see this ID!
                for obs in obs_list:
                    obs['true_object_id'] = obj_id 
                    obj_measurements.append(obs)
            
            all_measurements.extend(obj_measurements)
            
            # Store ground truth (Initial state)
            if obj_measurements:
                # Sort this object's measurements by time to get the very first observation
                obj_measurements.sort(key=lambda x: x['time'])
                ground_truth_tracks[obj_id] = {
                    'tle': (l1, l2),
                    'initial_obs': obj_measurements[0]
                }
            else:
                ground_truth_tracks[obj_id] = {
                    'tle': (l1, l2),
                    'initial_obs': None
                }

        # 3. Sort by Time
        # The radar receives blips chronologically, not sorted by object
        all_measurements.sort(key=lambda x: x['time'])
        
        print(f"✅ Scenario Generated: {len(all_measurements)} total measurements.")
        return all_measurements, ground_truth_tracks
