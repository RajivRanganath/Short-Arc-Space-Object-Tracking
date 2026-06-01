import numpy as np

class Radar:
    def __init__(self, name, lat, lon):
        self.name = name
        self.lat = lat
        self.lon = lon
        # Precompute position approximating ECI for simple visibility
        Re = 6378.137
        rad_lat = np.deg2rad(lat)
        rad_lon = np.deg2rad(lon)
        self.pos = np.array([
            Re * np.cos(rad_lat) * np.cos(rad_lon),
            Re * np.cos(rad_lat) * np.sin(rad_lon),
            Re * np.sin(rad_lat)
        ])

class MockTrack:
    def __init__(self, track_id, uncertainty, speed):
        self.id = track_id
        self.uncertainty = uncertainty
        self.speed = speed
        self.missed_detections = 0
        
        # Give it a fake state_estimate so visibility math doesn't crash
        # Place it right above the first radar (e.g. Bangalore)
        Re = 6378.137
        lat, lon = np.deg2rad(12.97), np.deg2rad(77.59)
        self.state_estimate = np.array([
            (Re + 800) * np.cos(lat) * np.cos(lon),
            (Re + 800) * np.cos(lat) * np.sin(lon),
            (Re + 800) * np.sin(lat),
            0, 0, 0
        ])

class InformationDrivenScheduler:
    def __init__(self, radars):
        self.radars = radars

    def compute_information_gain(self, track):
        if hasattr(track, 'filter') and track.filter is not None:
            # Real Track: Use trace of position covariance
            _, cov = track.filter.get_state_estimate()
            pos_var = np.trace(cov[:3, :3])
            S_approx = max(pos_var, 1e-6)
        else:
            # MockTrack
            S_approx = track.uncertainty ** 2
            
        R_approx = 5.0 ** 2  
        ig = np.log(S_approx) - np.log(R_approx)
        
        # Add boosts for tracks we are losing
        age_boost = track.missed_detections * 0.5
        return ig + age_boost

    def _is_visible(self, track, radar):
        """Simple dot product horizon check."""
        Re = 6378.137
        target_pos = track.state_estimate[:3]
        target_r = max(np.linalg.norm(target_pos), 1e-6)
        
        cos_theta = np.dot(radar.pos, target_pos) / (Re * target_r)
        min_cos_theta = Re / target_r
        
        # Return True if target is above the horizon
        return cos_theta > min_cos_theta

    def schedule_next_observation(self, active_tracks):
        best_ig = -float('inf')
        best_track = None
        best_radar = None

        for track in active_tracks:
            ig = self.compute_information_gain(track)
            
            # Find which radars can see it
            visible_radars = [r for r in self.radars if self._is_visible(track, r)]
            
            if not visible_radars:
                continue
                
            if ig > best_ig:
                best_ig = ig
                best_track = track
                # Pick the radar with the best elevation (highest dot product)
                best_radar = max(visible_radars, key=lambda r: np.dot(r.pos, track.state_estimate[:3]))

        return best_radar, best_track, best_ig
