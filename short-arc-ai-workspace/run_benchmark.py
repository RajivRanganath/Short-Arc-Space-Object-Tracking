import time
import numpy as np
from datetime import datetime, timezone, timedelta
from src.tracking_system import MultiObjectTracker

def benchmark():
    tracker = MultiObjectTracker()
    now = datetime.now(timezone.utc)
    
    # Generate 18 targets for 50 frames
    n_targets = 18
    n_frames = 50
    
    # Initialize all targets in one frame
    initial_measurements = []
    for i in range(n_targets):
        initial_measurements.append({
            'site_eci': [6378.0, 0, 0],
            'range': 1000.0 + i * 50,
            'ra': 0.1 * i,
            'dec': 0.1 * i
        })
    tracker.process_frame(now, initial_measurements)
    
    # Run benchmark
    latencies = []
    
    for _ in range(n_frames):
        now += timedelta(seconds=1)
        
        measurements = []
        for i in range(n_targets):
            measurements.append({
                'site_eci': [6378.0, 0, 0],
                'range': 1000.0 + i * 50,
                'ra': 0.1 * i + np.random.normal(0, 0.001),
                'dec': 0.1 * i + np.random.normal(0, 0.001)
            })
            
        t0 = time.time()
        tracker.process_frame(now, measurements)
        t1 = time.time()
        latencies.append((t1 - t0) * 1000)
    
    avg_latency = np.mean(latencies[5:])  # skip first 5 warmup frames
    max_latency = np.max(latencies[5:])
    
    print(f"BENCHMARK RESULT:")
    print(f"Targets: {n_targets}")
    print(f"Frames: {n_frames}")
    print(f"Average Latency: {avg_latency:.2f} ms")
    print(f"Max Latency: {max_latency:.2f} ms")
    
if __name__ == "__main__":
    benchmark()
