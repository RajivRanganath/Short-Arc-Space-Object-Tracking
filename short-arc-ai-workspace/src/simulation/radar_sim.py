import numpy as np
from skyfield.api import EarthSatellite, load, wgs84
from datetime import timedelta

class RadarSimulator:
    def __init__(self, lat=12.9716, lon=77.5946, alt_m=920):
        self.ts = load.timescale()
        self.station = wgs84.latlon(lat, lon, elevation_m=alt_m)
        self.angle_noise_deg = 0.01 
        
    def generate_arc(self, tle_line1, tle_line2, start_time_iso, duration_sec=15, step_sec=5):
        satellite = EarthSatellite(tle_line1, tle_line2, 'Target', self.ts)
        observations = []
        
        for i in range(0, duration_sec + 1, step_sec):
            t_current = self.ts.from_datetime(start_time_iso + timedelta(seconds=i))
            astrometric = (satellite - self.station).at(t_current)
            
            # Visibility Check (Elevation > 5.0 deg)
            alt, az, distance = astrometric.altaz()
            if alt.degrees <= 5.0:
                continue
                
            ra, dec, _ = astrometric.radec()
            
            # Add noise to angles
            ra_noisy = ra.radians + np.random.normal(0, np.deg2rad(self.angle_noise_deg))
            dec_noisy = dec.radians + np.random.normal(0, np.deg2rad(self.angle_noise_deg))
            
            # ADD: Range measurement with 5.0 km noise (typical for tracking radar)
            range_noise_km = 5.0
            range_noisy = distance.km + np.random.normal(0, range_noise_km)
            
            station_eci = self.station.at(t_current).position.km
            
            obs = {
                'time': i,
                'ra': ra_noisy, 
                'dec': dec_noisy,
                'range': range_noisy,      # <--- NEW FIELD
                'site_eci': station_eci, 
                'true_range_km': distance.km
            }
            observations.append(obs)
            
        return observations
