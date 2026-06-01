import numpy as np
from src.tracking.track_hypothesis import Track, Measurement
from src.association.gnn_associator import GlobalNearestNeighbor
from src.association.jpda_associator import JPDAAssociator
from src.tracking.conjunction import ConjunctionAssessment
from src.tracking.catalog import TLECatalog
from collections import Counter
from src.constants import get_logger

logger = get_logger("MultiObjectTracker")

class MultiObjectTracker:
    def __init__(self, association_method='gnn'):
        self.tracks = []
        self.next_track_id = 0
        self.ca = ConjunctionAssessment()
        self.catalog = TLECatalog()
        self.conj_counter = 0
        self.active_conjunctions = []

        # Tentative track buffer — requires 2nd correlated measurement to promote
        self.tentative_tracks = []
        
        # Ground truth tracking: {track_id: Counter[true_object_id]}
        self.ground_truth_map = {}
        # Known object identification: {track_id: (obj_id, name, confidence)}
        self.identifications = {}

        # Select associator (using the strict 16.27 math validation gate!)
        if association_method == 'jpda':
            self.associator = JPDAAssociator()
            self.use_jpda = True
        else:
            self.associator = GlobalNearestNeighbor()
            self.use_jpda = False

        # Performance counters
        self.total_frames = 0
        self.total_measurements = 0
        self.total_matches = 0
        self.total_new_tracks = 0
        self.total_missed = 0
        self.total_pruned = 0
        self.conjunction_warnings = 0
        self.maneuver_detections = 0

    def process_frame(self, current_time, raw_measurements):
        self.total_frames += 1
        self.total_measurements += len(raw_measurements)

        logger.info(f"\n🕒 Processing Frame: {current_time} "
              f"| Tracks: {len(self.tracks)} "
              f"| Meas: {len(raw_measurements)}")

        # 1. Predict all tracks to current_time ONCE
        for track in self.tracks:
            track.predict(current_time)

        if not raw_measurements:
            # Handle empty frame case
            for track in self.tracks:
                track.missed_detections += 1
            self.total_missed += len(self.tracks)
            self._prune_tracks()
            self._check_all_conjunctions()
            return

        # Group measurements by radar site (multi-radar fusion)
        measurements_by_site = {}
        for m in raw_measurements:
            # Round site_eci slightly to group identical sites dynamically
            site_key = tuple(np.round(m['site_eci'], decimals=2))
            if site_key not in measurements_by_site:
                measurements_by_site[site_key] = []
            measurements_by_site[site_key].append(m)

        updated_track_ids = set()

        # 2. Process each sensor's observations sequentially
        for site_key, site_raw_meas in measurements_by_site.items():
            measurements = []
            for m in site_raw_meas:
                range_km = m.get('range', 0)
                if range_km > 0:
                    R_noise = np.diag([np.deg2rad(0.2)**2, np.deg2rad(0.2)**2, 5.0**2])
                else:
                    R_noise = np.diag([np.deg2rad(0.2)**2, np.deg2rad(0.2)**2])

                meas_obj = Measurement(
                    time=current_time,
                    radar_site_eci=np.array(m['site_eci']),
                    range_m=range_km * 1000.0,
                    ra_rad=m['ra'],
                    dec_rad=m['dec'],
                    noise_matrix=R_noise,
                    range_km=range_km,
                    true_object_id=m.get('true_object_id', -1)
                )
                measurements.append(meas_obj)

            assignments, unassigned_tracks, unassigned_meas = \
                self.associator.associate(self.tracks, measurements)

            if self.use_jpda:
                self._update_jpda(assignments, measurements)
            else:
                self._update_gnn(assignments, measurements)

            # Record which tracks were updated this frame
            unique_matched_tracks = set()
            for assignment in assignments:
                t_idx = assignment[0]  # First element is always track index
                updated_track_ids.add(self.tracks[t_idx].id)
                unique_matched_tracks.add(t_idx)

            self.total_matches += len(unique_matched_tracks)
            self.total_new_tracks += len(unassigned_meas)

            logger.info(f"   📡 Site {site_key[:2]}... | "
                  f"🔗 Matches: {len(unique_matched_tracks)} "
                  f"| 🆕 New: {len(unassigned_meas)}")

            for m_idx in unassigned_meas:
                self._try_tentative_or_initiate(measurements[m_idx])

        # 3. Handle missed detections globally across all sensors
        frame_misses = 0
        for track in self.tracks:
            if track.id not in updated_track_ids:
                track.missed_detections += 1
                frame_misses += 1
            else:
                track.missed_detections = 0
                
        self.total_missed += frame_misses
        logger.info(f"   ❌ Total Missed across network: {frame_misses}")
        
        # Calculate validated tracking score (based on dominant true object per track)
        self.validated_matches = 0
        for track_id, match_counter in self.ground_truth_map.items():
            if match_counter:
                # The dominant object ID determines if the track is "correct"
                dominant_obj, count = match_counter.most_common(1)[0]
                self.validated_matches += count

        self._prune_tracks()
        self._age_tentative_tracks()
        self._check_all_conjunctions()
        self._correlate_tracks()

    def _correlate_tracks(self):
        """
        Check established tracks against the known catalog.
        """
        for t in self.tracks:
            # Only correlate robust tracks (e.g. > 10 updates)
            updates = getattr(t.filter, 'update_count', 0)
            if updates > 10 and t.id not in self.identifications:
                state = t.state_estimate
                r_vec = state[:3]
                v_vec = state[3:]
                match = self.catalog.correlate_track(r_vec, v_vec)
                
                if match:
                    self.identifications[t.id] = match
                    logger.info(f"   🎯 Track {t.id} correlated to {match[1]} (Confidence: {match[2]*100:.1f}%)")

    def _update_gnn(self, assignments, measurements):
        for t_idx, m_idx in assignments:
            track = self.tracks[t_idx]
            meas = measurements[m_idx]
            track.update(meas)
            
            # Record ground truth association
            if meas.true_object_id != -1:
                if track.id not in self.ground_truth_map:
                    self.ground_truth_map[track.id] = Counter()
                self.ground_truth_map[track.id][meas.true_object_id] += 1

    def _update_jpda(self, assignments, measurements):
        track_updates = {}
        for t_idx, m_idx, prob in assignments:
            if t_idx not in track_updates:
                track_updates[t_idx] = []
            track_updates[t_idx].append((m_idx, prob))

        for t_idx, meas_probs in track_updates.items():
            track = self.tracks[t_idx]
            if len(meas_probs) == 1:
                m_idx, prob = meas_probs[0]
                meas = measurements[m_idx]
                track.update(meas)
                
                # Record ground truth for unambiguous JPDA matches
                if meas.true_object_id != -1:
                    if track.id not in self.ground_truth_map:
                        self.ground_truth_map[track.id] = Counter()
                    self.ground_truth_map[track.id][meas.true_object_id] += 1
            else:
                self._weighted_update(
                    track,
                    [(measurements[m_idx], prob) for m_idx, prob in meas_probs]
                )

    def _weighted_update(self, track, measurement_prob_pairs):
        track.jpda_update(measurement_prob_pairs)

    def _try_tentative_or_initiate(self, measurement):
        """Check if this measurement correlates with any tentative track.
        If yes, promote that tentative track to a real track.
        If no, store it as a new tentative detection."""
        meas_pos = self._approx_position(measurement)
        if meas_pos is None:
            return

        TENTATIVE_GATE_KM = 150.0  # spatial gate for confirming tentative tracks

        for i, tent in enumerate(self.tentative_tracks):
            tent_pos = tent['position']
            dist = float(np.linalg.norm(meas_pos - tent_pos))
            if dist < TENTATIVE_GATE_KM:
                # Confirmed! Promote to a real track using original measurement
                new_track = Track(self.next_track_id, tent['measurement'])
                new_track.update(measurement)
                self.tracks.append(new_track)
                logger.info(f"   ✨ Confirmed Track ID {self.next_track_id} (correlated at {dist:.0f} km)")
                self.next_track_id += 1
                self.tentative_tracks.pop(i)
                return

        # No match — store as tentative
        self.tentative_tracks.append({
            'measurement': measurement,
            'position': meas_pos,
            'age': 0,
        })
        logger.info(f"   🔸 Tentative detection stored ({len(self.tentative_tracks)} pending)")

    def _approx_position(self, measurement):
        """Get approximate ECI position from a measurement (angles + range)."""
        try:
            ra = measurement.ra_rad
            dec = measurement.dec_rad
            r = measurement.range_km if measurement.range_km > 0 else 7000.0  # default LEO
            site = measurement.radar_site_eci
            direction = np.array([
                np.cos(dec) * np.cos(ra),
                np.cos(dec) * np.sin(ra),
                np.sin(dec),
            ])
            return site + direction * r
        except Exception:
            return None

    def _age_tentative_tracks(self):
        """Remove tentative detections that weren't confirmed within 5 frames."""
        surviving = []
        for tent in self.tentative_tracks:
            tent['age'] += 1
            if tent['age'] <= 5:
                surviving.append(tent)
            else:
                logger.info(f"   🔹 Expired tentative detection (aged out)")
        self.tentative_tracks = surviving

    def _initiate_track(self, measurement):
        new_track = Track(self.next_track_id, measurement)
        self.tracks.append(new_track)
        logger.info(f"   ✨ Created Track ID {self.next_track_id}")
        self.next_track_id += 1

    def _prune_tracks(self):
        valid_tracks = []
        for track in self.tracks:
            update_cnt = getattr(track.filter, 'update_count', 0)

            # 0. Aggressively prune young unconfirmed tracks (< 3 updates, missed 3 frames)
            if update_cnt < 3 and track.missed_detections > 3:
                logger.info(f"   💀 Pruning Track {track.id}: Unconfirmed (only {update_cnt} updates, missed {track.missed_detections}).")
                self.total_pruned += 1
                continue

            # 1. Prune if lost for a long time (> 10 minutes for confirmed tracks)
            if track.missed_detections > 120:
                logger.info(f"   💀 Pruning Track {track.id}: Unseen for 10+ mins.")
                self.total_pruned += 1
                continue
                
            # 2. Prune if the filter uncertainty explodes while coasting
            _, cov = track.filter.get_state_estimate()
            pos_cov_trace = float(np.trace(cov[:3, :3]))
            # Threshold: 1e6 km^2 means the particle cloud is spread out over 1000km wide
            if track.missed_detections > 5 and pos_cov_trace > 1e6:
                logger.info(f"   💀 Pruning Track {track.id}: Uncertainty exploded ({pos_cov_trace:.0f} km^2).")
                self.total_pruned += 1
                continue

            state = track.state_estimate
            alt = float(np.linalg.norm(state[:3])) - 6378.137
            speed = float(np.linalg.norm(state[3:]))
            update_cnt = getattr(track.filter, 'update_count', 0)

            if update_cnt < 5:
                if alt < -200 or alt > 6000:
                    logger.info(f"   💀 Pruning Track {track.id}: Alt={alt:.0f}km")
                    self.total_pruned += 1
                    continue
                if speed > 20.0 or speed < 1.0:
                    logger.info(f"   💀 Pruning Track {track.id}: Speed={speed:.1f}km/s")
                    self.total_pruned += 1
                    continue
            else:
                if alt < 150 or alt > 3000:
                    logger.info(f"   💀 Pruning Track {track.id}: Alt={alt:.0f}km")
                    self.total_pruned += 1
                    continue
                if speed > 10.0 or speed < 5.0:
                    logger.info(f"   💀 Pruning Track {track.id}: Speed={speed:.1f}km/s")
                    self.total_pruned += 1
                    continue

            valid_tracks.append(track)
        self.tracks = valid_tracks

    def _check_all_conjunctions(self):
        active = [t for t in self.tracks if t.missed_detections == 0]
        self.active_conjunctions = []

        if len(active) < 2:
            return

        self.conj_counter += 1

        for i in range(len(active)):
            for j in range(i + 1, len(active)):
                t1 = active[i]
                t2 = active[j]

                curr_dist = float(np.linalg.norm(t1.state_estimate[:3] - t2.state_estimate[:3]))
                if curr_dist > 1200:  # Wider threshold for more conjunction events
                    continue

                s1 = float(np.linalg.norm(t1.state_estimate[3:]))
                s2 = float(np.linalg.norm(t2.state_estimate[3:]))

                if 5.0 < s1 < 12.0 and 5.0 < s2 < 12.0:
                    dist, tca, alerts, pc, risk_level = self.ca.get_close_approaches(
                        t1, t2, lookahead_hours=3, threshold_km=200
                    )

                    is_red = pc > 1e-4
                    is_yellow = pc > 1e-6

                    if is_red or is_yellow or curr_dist < 400:
                        r_level = "RED" if is_red else ("YELLOW" if is_yellow else "SAFE")
                        self.active_conjunctions.append({
                            "t1": t1.id,
                            "t2": t2.id,
                            "distance": round(curr_dist, 1),
                            "miss_distance": round(dist, 1),
                            "pc": float(pc),
                            "risk_level": r_level,
                            "tca_seconds": round(float(tca), 0),
                        })

                        if is_red or is_yellow:
                            self.conjunction_warnings += 1

    def print_mission_report(self):
        logger.info("\n" + "=" * 60)
        logger.info("📊  ORBIT GUARD AI — MISSION REPORT")
        logger.info("=" * 60)
        logger.info(f"\n📌 OVERVIEW")
        logger.info(f"   Association method : {'JPDA' if self.use_jpda else 'GNN'}")
        logger.info(f"   Frames processed   : {self.total_frames}")
        logger.info(f"   Total measurements : {self.total_measurements}")
        logger.info(f"   Tracks created     : {self.next_track_id}")
        logger.info(f"   Active tracks      : {len(self.tracks)}")
        logger.info(f"   Tracks pruned      : {self.total_pruned}")

        logger.info(f"\n🔗 DATA ASSOCIATION")
        assoc_rate = self.total_matches / max(self.total_measurements, 1) * 100
        validated_rate = getattr(self, 'validated_matches', 0) / max(self.total_measurements, 1) * 100
        
        logger.info(f"   Raw matches        : {self.total_matches} (Rate: {assoc_rate:.1f}%)")
        logger.info(f"   Validated matches  : {getattr(self, 'validated_matches', 0)} (Rate: {validated_rate:.1f}%)")
        logger.info(f"   Missed detections  : {self.total_missed}")
        logger.info(f"   New initiations    : {self.total_new_tracks}")

        if validated_rate >= 85: tag = "✅ EXCELLENT"
        elif validated_rate >= 70: tag = "🟡 GOOD"
        else: tag = "⚠️  NEEDS TUNING"
        logger.info(f"   Rating             : {tag}")

        if self.use_jpda:
            stats = self.associator.get_statistics()
            logger.info(f"\n📊 JPDA STATISTICS")
            logger.info(f"   Ambiguous cases    : {stats['ambiguous_cases']}")
            logger.info(f"   Ambiguity rate     : {stats['ambiguity_rate']*100:.1f}%")

        logger.info(f"\n🛰️  TRACK DETAILS")
        logger.info(f"   {'ID':<6} {'Alt (km)':<12} {'Speed (km/s)':<15} {'Q':<10} {'Status':<15} Match")
        logger.info(f"   {'-'*70}")

        leo_count = 0
        for t in sorted(self.tracks, key=lambda x: x.id):
            state = t.state_estimate
            alt   = float(np.linalg.norm(state[:3])) - 6378.137
            speed = float(np.linalg.norm(state[3:]))
            
            q = t.quality_metric

            regime_info = getattr(t, 'regime_info', None)
            regime_str = regime_info['regime'] if regime_info else "UCT"
            
            if q < 0.3:
                status = "⚠️  DEGRADED"
            else:
                status = f"✅ {regime_str}"
                if regime_str == "LEO": leo_count += 1

            ident = self.identifications.get(t.id, None)
            match_str = f"🆔 {ident[1]}" if ident else "UCT"

            logger.info(f"   {t.id:<6} {alt:<12.0f} {speed:<15.2f} {q:<10.2f} {status:<15} {match_str}")

        score_pct = leo_count / max(len(self.tracks), 1) * 100
        logger.info(f"\n🎯 TRACKING SCORE : {leo_count}/{len(self.tracks)} stable ({score_pct:.0f}%)")
        logger.info("\n" + "=" * 60)