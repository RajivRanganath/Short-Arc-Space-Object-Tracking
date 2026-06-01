/**
 * Full-screen overlay explaining the simulation in plain language.
 * Triggered by "Pause & Explain" button.
 */
export default function ExplainModal({ onClose }) {
    return (
        <div className="explain-overlay" onClick={onClose}>
            <div className="explain-modal" onClick={(e) => e.stopPropagation()}>
                <h2 className="explain-heading">What You're Watching</h2>
                <p className="explain-lead">
                    This is a <strong>real-time space debris tracking simulation</strong>.
                    You are watching an AI system detect, track, and predict the orbits of
                    objects flying through Low Earth Orbit at ~7.5 km/s (27,000 km/h).
                </p>

                <div className="explain-sections">
                    <div className="explain-section">
                        <h3>📡 How It Works</h3>
                        <ol className="explain-steps">
                            <li><strong>Radar Scanning</strong> — Simulated ground stations (like ISTRAC, India)
                                scan the sky and detect objects passing overhead.</li>
                            <li><strong>Smart Matching</strong> — When multiple objects are in view, the AI
                                uses probabilistic algorithms to figure out which radar blip belongs
                                to which object. (Technically: Joint Probabilistic Data Association)</li>
                            <li><strong>Position Prediction</strong> — For each object, a cloud of possible
                                positions is maintained. Bad guesses are discarded as new radar data
                                arrives, until the system locks on. (Technically: Ensemble Kalman Filter)</li>
                            <li><strong>Collision Detection</strong> — The system constantly checks if any
                                two predicted paths will cross dangerously close, and calculates the
                                probability of collision.</li>
                        </ol>
                    </div>

                    <div className="explain-section">
                        <h3>🎯 What the Visuals Mean</h3>
                        <div className="explain-grid">
                            <div className="explain-visual">
                                <span className="explain-icon" style={{ background: '#00ff88', boxShadow: '0 0 8px #00ff88' }} />
                                <div>
                                    <strong>Green Dot</strong>
                                    <span>Stable track — the AI is confident about this object's position</span>
                                </div>
                            </div>
                            <div className="explain-visual">
                                <span className="explain-icon" style={{ background: '#ffb800', boxShadow: '0 0 8px #ffb800' }} />
                                <div>
                                    <strong>Amber Dot</strong>
                                    <span>Acquiring — just detected, still building confidence</span>
                                </div>
                            </div>
                            <div className="explain-visual">
                                <span className="explain-icon explain-icon-halo" />
                                <div>
                                    <strong>Glowing Halo</strong>
                                    <span>Position uncertainty — wider halo = less confident about exact location</span>
                                </div>
                            </div>
                            <div className="explain-visual">
                                <span className="explain-icon explain-icon-line" />
                                <div>
                                    <strong>Trailing Line</strong>
                                    <span>Predicted orbit path based on physics and radar data</span>
                                </div>
                            </div>
                            <div className="explain-visual">
                                <span className="explain-icon explain-icon-danger" />
                                <div>
                                    <strong>Red Dashed Line</strong>
                                    <span>Collision warning — two objects on a dangerously close path</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="explain-section">
                        <h3>📊 Understanding the Numbers</h3>
                        <div className="explain-terms">
                            <div className="explain-term">
                                <strong>Confidence %</strong>
                                <span>How certain the AI is about an object's position (100% = locked on)</span>
                            </div>
                            <div className="explain-term">
                                <strong>Association Density %</strong>
                                <span>What fraction of radar blips were successfully matched to known objects</span>
                            </div>
                            <div className="explain-term">
                                <strong>TCA (T-XXs)</strong>
                                <span>Time to Closest Approach — countdown to when two objects will be nearest</span>
                            </div>
                            <div className="explain-term">
                                <strong>Pc</strong>
                                <span>Probability of Collision — a number like 1.2e-04 means ~0.012% chance of impact</span>
                            </div>
                        </div>
                    </div>
                </div>

                <button className="explain-close-btn" onClick={onClose}>
                    ▶ Resume Simulation
                </button>
            </div>
        </div>
    )
}
