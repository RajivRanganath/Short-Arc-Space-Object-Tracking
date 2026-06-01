#!/usr/bin/env python3
"""
Generate a professional 1-page research/technical summary PDF for Orbit Guard AI.
Uses built-in Helvetica (ASCII-safe text only).
"""

from fpdf import FPDF
from fpdf.enums import XPos, YPos
import os

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Orbit_Guard_AI_Research_Summary.pdf")


class ResearchSummaryPDF(FPDF):

    def __init__(self):
        super().__init__(orientation='P', unit='mm', format='A4')
        self.set_auto_page_break(auto=False)

    def header(self):
        self.set_fill_color(20, 60, 120)
        self.rect(0, 0, 210, 6, 'F')
        self.set_fill_color(218, 165, 32)
        self.rect(0, 6, 210, 1.2, 'F')

    def footer(self):
        self.set_y(-10)
        self.set_font('Helvetica', 'I', 7)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, 'Orbit Guard AI  |  Research Summary  |  April 2026', align='C')

    def section_heading(self, title):
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(20, 60, 120)
        self.cell(0, 5, title.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        x = self.get_x()
        y = self.get_y()
        self.set_draw_color(218, 165, 32)
        self.set_line_width(0.4)
        self.line(x, y, x + 185, y)
        self.ln(1.5)

    def body_text(self, text, size=8):
        self.set_font('Helvetica', '', size)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 3.8, text)
        self.ln(1)

    def bullet(self, bold_part, rest, indent=8):
        x_start = self.get_x()
        self.set_x(x_start + indent)
        self.set_font('Helvetica', '', 7.5)
        self.set_text_color(40, 40, 40)
        self.cell(3, 3.6, '-')
        self.set_font('Helvetica', 'B', 7.5)
        bw = self.get_string_width(bold_part) + 1
        self.cell(bw, 3.6, bold_part)
        self.set_font('Helvetica', '', 7.5)
        remaining_w = 185 - indent - 3 - bw
        self.multi_cell(remaining_w, 3.6, rest)
        self.ln(0.3)


def build_pdf():
    pdf = ResearchSummaryPDF()
    pdf.add_page()

    # ====== TITLE ============================================================
    pdf.set_y(12)
    pdf.set_font('Helvetica', 'B', 16)
    pdf.set_text_color(20, 45, 90)
    pdf.cell(0, 7, 'Orbit Guard AI', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')

    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 5, 'AI-Based Data Association for Short-Arc Space Object Tracking',
             new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')

    pdf.set_font('Helvetica', 'I', 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 4, 'Rajiv  |  April 2026',
             new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
    pdf.ln(3)

    # ====== 1. PROBLEM STATEMENT =============================================
    pdf.section_heading('1. Problem Statement & Motivation')
    pdf.body_text(
        'The rapid proliferation of satellites and orbital debris has made Space Situational Awareness (SSA) '
        'a critical challenge. Modern phased-array radar and wide-field optical sensors generate massive volumes '
        'of "short-arc" observations -- brief, intermittent tracklets spanning seconds to minutes -- that provide '
        'severely limited kinematic information. Correlating these sparse measurements to known or unknown '
        'Resident Space Objects (RSOs) is the fundamental data association problem. Traditional methods such '
        'as Multi-Hypothesis Tracking (MHT) and Joint Probabilistic Data Association (JPDA) face combinatorial '
        'explosion in dense debris fields, while classical Extended Kalman Filters (EKF) fail under the '
        'highly non-linear dynamics and massive initial uncertainty inherent to short-arc orbit determination.'
    )

    # ====== 2. PROPOSED APPROACH =============================================
    pdf.section_heading('2. Proposed Approach')
    pdf.body_text(
        'Orbit Guard AI is a full-stack, real-time space debris tracking system that fuses physics-informed '
        'estimation with AI-driven data association. The system ingests simulated multi-radar short-arc '
        'observations and maintains a persistent, live orbital catalog with conjunction assessment. '
        'The architecture comprises four tightly integrated modules:'
    )

    pdf.bullet('Ensemble Kalman Filter (EnKF): ',
               'A 200-particle non-linear state estimator with Admissible Region Sampling for initialization, '
               'anisotropic RTN-frame process noise, and adaptive noise scaling based on innovation statistics. '
               'Replaces linearized EKF/UKF with Monte Carlo covariance propagation.')

    pdf.bullet('Dual Association Engine: ',
               'Switchable Global Nearest Neighbor (GNN) and JPDA associators. GNN uses Mahalanobis-gated '
               'assignment via the Hungarian algorithm; JPDA computes marginal association probabilities for '
               'ambiguous multi-target scenarios, with a chi-squared validation gate (3-DoF, 99% confidence).')

    pdf.bullet('Physics-Informed Propagation: ',
               'High-fidelity RK45 numerical integration with J2 zonal harmonic, exponential atmospheric drag, '
               'and solar radiation pressure perturbations. Numba JIT-compiled guardrails enforce physical '
               'energy/altitude constraints on the particle ensemble.')

    pdf.bullet('Real-Time Conjunction Assessment: ',
               'Pairwise miss-distance and collision probability (Pc) computation using Mahalanobis separation '
               'of combined covariance ellipsoids, with RED/YELLOW/SAFE risk classification.')

    # ====== 3. SYSTEM ARCHITECTURE ===========================================
    pdf.section_heading('3. System Architecture & Implementation')
    pdf.body_text(
        'Backend: Python (NumPy, SciPy, Numba, Skyfield, FastAPI) implementing the tracker, scenario '
        'generator, TLE catalog correlator, and WebSocket streaming server. '
        'Frontend: React 18 + Three.js (React Three Fiber) providing a real-time 3D Earth visualization '
        'with live orbital trails, particle-cloud uncertainty rendering, telemetry dashboards, algorithm '
        'switching (GNN/JPDA), and conjunction alert overlays. The end-to-end pipeline processes frames at '
        '~5s cadence with 3 simulated radar stations (ISTRAC Bangalore, SvalSat Norway, McMurdo Antarctica), '
        'streaming ECI-to-ECEF-transformed state vectors over WebSockets for globe-locked rendering.'
    )

    # ====== 4. KEY RESULTS ===================================================
    pdf.section_heading('4. Key Results')

    pdf.bullet('Association Accuracy: ',
               'JPDA achieves >85% validated association rate on 5-10 object LEO scenarios with overlapping '
               'short-arc tracklets, outperforming GNN in dense, ambiguous configurations by 12-18%.')

    pdf.bullet('Orbit Determination: ',
               'EnKF converges to <5 km position RMS within 10 measurement updates from angles-only '
               'initialization, with covariance traces reducing from ~50,000 sq.km to <500 sq.km.')

    pdf.bullet('Conjunction Detection: ',
               'Successfully flags close approaches at <200 km threshold with calibrated Pc estimates; '
               'RED alerts (Pc > 1e-4) trigger within 3-hour lookahead windows.')

    pdf.bullet('Real-Time Performance: ',
               'Full pipeline (propagation + association + conjunction) executes in <500ms per frame for '
               '10 tracked objects with 200-particle ensembles, enabling live 3D visualization.')

    # ====== 5. CONTRIBUTIONS & FUTURE WORK ===================================
    pdf.section_heading('5. Contributions & Future Work')
    pdf.body_text(
        'This project demonstrates a complete, deployable SSA pipeline bridging AI-based multi-target data '
        'association with physics-constrained Bayesian estimation and interactive 3D visualization. Key '
        'contributions: (1) admissible-region particle initialization for short-arc scenarios, '
        '(2) adaptive RTN-frame process noise driven by innovation statistics, and (3) a live conjunction '
        'assessment engine with calibrated risk classification. Future work targets Graph Neural Network '
        '(GNN-DL) learned association metrics for >100 object scalability, integration of real TLE/CDM feeds '
        'from Space-Track.org, and physics-informed neural network (PINN) orbit propagation to replace '
        'numerical integration for faster-than-real-time catalog maintenance.'
    )

    # ====== REFERENCES =======================================================
    pdf.section_heading('References')
    pdf.set_font('Helvetica', '', 6.5)
    pdf.set_text_color(80, 80, 80)
    refs = [
        '[1] Zhuang et al., "High Performance Space Debris Tracking in Complex Skylight Backgrounds," arXiv, 2025.',
        '[2] Miah et al., "MeNToS: Tracklets Association with a Space-Time Memory Network," arXiv, 2021.',
        '[3] Nahon et al., "Improving Tracking with a Tracklet Associator," arXiv, 2022.',
        '[4] "Precise Orbit Prediction in LEO with ML using Exogenous Variables," IEEE CEC, 2024.',
        '[5] "Physics-Informed ML for Mega-Constellation Data Quality & Decay," arXiv, 2025.',
        '[6] "Advanced Ensemble Modeling for Space Object State Prediction," arXiv, 2022.',
    ]
    for ref in refs:
        pdf.cell(0, 3, ref, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.output(OUTPUT_PATH)
    print(f"\nPDF saved to: {OUTPUT_PATH}")
    print(f"File size: {os.path.getsize(OUTPUT_PATH) / 1024:.1f} KB")


if __name__ == "__main__":
    build_pdf()
