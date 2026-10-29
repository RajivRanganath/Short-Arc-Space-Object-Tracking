# JPDA vs GNN stress test: seeded rerun (29 Oct 2026)

## Bottom line

The old resume claim "JPDA beat GNN by 11 to 14 points in 8-object clutter, 100% track stability" does not hold.

Over 100 seeds, in the Hard level (8 objects, 15 ghosts per frame), JPDA's association rate is **6.7 points higher** than GNN's (95% CI 5.9 to 7.4). JPDA is higher in 94 of the 95 usable seeds, and only 13 of those 95 seeds reach a gap of 11 points or more. Track stability is 95.0% for JPDA (704 of 741 tracks), not 100%. GNN is 97.0% (574 of 592).

There is also a problem with the metric itself in clutter. Half of JPDA's associations in Hard (52%) are to ghost measurements, against 25% for GNN. So part of JPDA's higher "association rate" comes from associating clutter, not from tracking better.

## Where the old claim came from

- No saved output exists for it. `results/` holds only `performance_report.png`. `papers/` holds one reading note, `notebooks/` is empty, and nothing in git history (all 9 commits, including the docs commit 7776507) contains "11 to 14", "100% track stability" or a JPDA gap of that size.
- The only other JPDA numbers in the project are in `DS(synopsis)/03_qa_bank.md`, `04_concept_map_analogies_demo.md` and `05_gotchas_alternatives_vocab.md`: "GNN 92% normal / 54% clutter, JPDA 92% normal / 88% clutter". That is a different and much larger claim (34 points), and no script output backs it either.
- The most likely source is one or two hand-copied runs of the unseeded `test_jpda_stress.py`. Single runs vary widely: the Hard gap over 95 seeds ranges from -1.9 to +16.8 points, so 11 to 14 is a plausible lucky draw. The "100% stable" figure matches a single run where every surviving track passed the stability check. That happens for JPDA in 63 of the 95 Hard seeds.

## Why the old test gave a different answer every run

Every random source in the run was unseeded:

| Source | Where | What it changes |
|---|---|---|
| `datetime.now()` scenario start | `src/simulation/multi_object_scenarios.py` | Where every satellite is relative to the 3 radars, so which objects are visible at all |
| `random.sample` | same file | Which Fengyun-1C fragments are picked |
| `np.random.normal` | `src/simulation/radar_sim.py` | RA, Dec and range measurement noise |
| `np.random.uniform` | `test_jpda_stress.py` | Ghost (clutter) positions |
| `random.shuffle` | `test_jpda_stress.py` | Order of measurements in each frame |
| `np.random` (8 calls) | `src/orbit_determination/ensemble_kalman_filter.py` | EnKF particle initialisation, process noise, perturbed observations |
| `np.random.normal` (3 calls) | `src/tracking/track_hypothesis.py` | Particle jitter after updates |
| `np.random` | `src/classification/regime_classifier.py` | Synthetic training data for the per-track regime classifier |
| `datetime.now()` tracker clock | `test_jpda_stress.py` | A second clock, separate from the scenario's |

The trackers have no randomness of their own beyond the EnKF and the classifier. The associators (`gnn_associator.py`, `jpda_associator.py`) are deterministic.

## What I changed

Two files, uncommitted. `git diff -w` shows the real change, because most of the test file's diff is just the old top-level code moving under `if __name__ == "__main__":`.

1. **`src/simulation/multi_object_scenarios.py`**: `generate_scenario` takes an optional `start_time`. It still defaults to `datetime.now()`, so the API, the demos and the other scripts behave exactly as before.
2. **`test_jpda_stress.py`**:
   - `run_difficulty_test(..., seed=0)` calls `random.seed(seed)` and `np.random.seed(seed)` at the start of each difficulty level. That one seed drives every source in the table above.
   - A constant `BASE_TIME = 2026-02-08 12:00 UTC` (half a day after the TLE epoch in `data/fengyun_1c.txt`). It is used for both the scenario start and the tracker clock, replacing the two `datetime.now()` calls. I picked this time before running any seeds and did not try others.
   - A warning when a scenario has no real measurements (see the next section).
   - `--seed N` runs the original single test reproducibly. `--seeds N` runs seeds 0 to N-1 per level and prints per-seed rows plus summary statistics.
   - The function also returns the real-measurement count and the stable/total counts, so the sweep can use them.

Nothing about the scenario, clutter levels, gates, metric definitions or tracker logic changed.

**Why global seeding and not a passed-through `np.random.Generator`.** The code draws from the global `random` and NumPy state at 34 call sites in 6 files (regime classifier 15, EnKF 8, Track 3, radar simulator 3, scenario generator 1, test 4). The regime classifier retrains on fresh synthetic data every time a track is created. Passing a Generator through would mean new parameters on `ScenarioGenerator`, `RadarSimulator`, `MultiObjectTracker`, `Track`, `EnsembleKalmanFilter` and `OrbitalRegimeClassifier`. That is a large diff touching tracker code, so seeding the two global generators is the smallest clean change.

Both trackers process the identical frames, real measurements and ghosts, because those are built before either tracker runs. They do not share particle noise: GNN runs first, and JPDA continues from wherever GNN left the global random state. This is still fully deterministic.

**Determinism check:** `--seed 0` run twice gives byte-identical results lines. Separately, a diagnostic that wraps the associators reproduced all 100 Hard-level rates exactly.

## The 0.0% runs

Root cause: **no satellite was in view.** The radar simulator only reports an object when it is more than 5 degrees above a station's horizon. Some combinations of start time and picked fragments have no object above any of the 3 radars during the 60 second window. Then there are no frames, so the ghost loop (which only adds ghosts to existing frames) adds nothing, and the test computes `0 / max(0, 1) = 0.0%`.

This is real physics, not a tracker bug. The bug is in the test's reporting: an undefined 0/0 is shown as "0.0% association". How often it happens:

- With wall-clock start times (the old behaviour, sampled over 2 days): Easy 14/40, Medium 5/40, Hard 3/40 scenarios were empty.
- At the fixed `BASE_TIME`, seeds 0 to 99: Easy 41, Medium 15, Hard 5 empty.

The API already handles this case (`src/api/main.py` retries with a 600 second arc when it sees "No debris visible"). The stress test never did.

Fix: the test now prints a warning for an empty scenario, and the sweep leaves empty seeds out of the statistics (the per-seed table still lists them). Nothing else changed.

A second, rarer case: 3 non-empty seeds also show 0.0% for both trackers (Easy seed 9, Medium seeds 9 and 43). Each has exactly 2 real measurements. The tracker needs 2 correlated measurements to confirm a track, and those count as new detections rather than matches, so nothing is left to match. This is expected behaviour of the confirm-on-second-hit logic, and these seeds stay in the statistics.

## How to reproduce

```
cd short-arc-ai-workspace
./venv/bin/python test_jpda_stress.py --seed 0       # one run, original output
./venv/bin/python test_jpda_stress.py --seeds 100    # the numbers below, about 17 min
```

The full output of the 100-seed run is in `results/jpda_seeded_sweep.txt`.

## Results: 100 seeds per level, empty scenarios excluded

Association rate is the test's own metric: tracks matched in each site-frame, summed, divided by all measurements including ghosts. A track counts as stable, by the test's own definition, if its final altitude is 150 to 2000 km and its speed is 6 to 10 km/s.

| Level | Usable seeds | GNN mean (sd) | JPDA mean (sd) | JPDA minus GNN, mean [95% CI] | JPDA wins / ties / GNN wins | Stable tracks GNN | Stable tracks JPDA |
|---|---|---|---|---|---|---|---|
| Easy: 3 objects, no ghosts | 59 | 56.1 (32.4) | 75.9 (14.3) | +19.8 [+13.5, +26.1] | 31 / 27 / 1 | 91/94 (96.8%) | 98/104 (94.2%) |
| Medium: 5 objects, 5 ghosts/frame | 85 | 13.6 (8.3) | 18.7 (7.7) | +5.0 [+3.9, +6.2] | 62 / 23 / 0 | 207/212 (97.6%) | 241/254 (94.9%) |
| Hard: 8 objects, 15 ghosts/frame | 95 | 9.2 (5.1) | 15.9 (5.0) | +6.7 [+5.9, +7.4] | 94 / 0 / 1 | 574/592 (97.0%) | 704/741 (95.0%) |

The CI is a t-interval on the per-seed paired difference. A "tie" means exactly equal rates.

Other figures:

- Median gap: Easy +7.7, Medium +2.5, Hard +6.3 points.
- Seeds with a gap of 11 points or more: Easy 29/59, Medium 15/85, Hard 13/95.
- Seeds where every final track was stable: Hard GNN 78/95, JPDA 63/95.

## Caveats you should know before quoting any of this

1. **In clutter the metric counts ghosts.** I wrapped each associator, without changing it, to count which measurements it paired with tracks:

   | Level | GNN real / ghost pairs | JPDA real / ghost pairs |
   |---|---|---|
   | Medium | 972 / 42 (4% ghost) | 1286 / 166 (11% ghost) |
   | Hard | 1494 / 500 (25% ghost) | 2209 / 2417 (52% ghost) |

   JPDA does associate more real measurements than GNN (48% more in Hard). It also associates 4.8 times as many ghosts. The test's association rate rewards both, so it overstates JPDA's advantage in clutter. On some Hard seeds JPDA's rate exceeds what is possible from real measurements alone (for example seed 0: 13 real measurements against 195 ghosts caps a real-only rate near 6%, while GNN gets 12.0% and JPDA 21.2%). The diagnostic script is not in the repo; it is a 25-line wrapper and can be added if you want it.
2. **JPDA's biggest lead is with no clutter at all** (Easy, +19.8). That points away from "JPDA handles clutter better" and towards the two associators being configured differently. GNN gates on RA, Dec and range at chi-squared below 20. JPDA gates on RA and Dec only, at below 25, with its own fixed 0.05 degree noise. I did not test this further.
3. **One geometry snapshot.** Every seed uses the same start time, so the seeds vary the fragments picked and the noise, not the time of day. A different fixed epoch could shift the numbers. I did not try other epochs, so as not to pick a favourable one.
4. **Short arcs.** 60 seconds at 5 second steps is at most 13 frames per radar, so many seeds have a single visible object seen for a minute.

## Test suite before and after

`./venv/bin/python -m pytest` (as written in the task) stops at collection both before and after, with 2 errors: `tests/test_api.py` needs `httpx` (starlette's TestClient) and `tests/test_data_loader.py` needs `requests`. Neither is installed in the venv, and I did not install anything.

With `--continue-on-collection-errors`, both before and after the change: **15 passed, 1 failed, 2 errors.** The failure is `tests/test_tracking_system.py::test_tracking_system_pipeline`, a stale test unrelated to this change. It expects one measurement to create a track, but the tracker now holds a first detection as tentative until a second one confirms it.

## Resume line these numbers support

Built a seeded 100-scenario GNN vs JPDA benchmark (fixed epoch, 95% CIs); in 8-object clutter JPDA's association rate was 6.7 points higher (CI 5.9 to 7.4, higher in 94 of 95 scenarios), and a ghost-match audit showed half of JPDA's associations were clutter.

If that is too long for one bullet, the safe short form is: "JPDA associated 48% more real measurements than GNN in 8-object clutter over 100 seeded scenarios." Drop "100% track stability" entirely.
