"""
Phase 6: The Anisotropy Sweep -- The Sphere of Strain
======================================================

Tests whether the TEGR 2600 engine's discrete Eulerian grid imprints a
directional bias on relativistic probes traversing an emergent horizon.

Physics:
  If our universe is computationally nested in a parent lattice, the
  cubic grid "grain" should leak through as numerical dispersion.
  Probes traveling along the parent's cardinal axes (faces of voxels)
  should experience different topological impedance than probes traveling
  along body diagonals (corners of voxels).

Methodology:
  Phase 1 -- FORMATION
    Establish equilibrium emergent horizon (identical to Zip-Up Phase 1).

  Phase 2 -- INJECTION
    Fire 8 test probes radially from the origin at v = 0.9*c_base,
    each with a strictly normalized direction vector:
      Axial:    [1,0,0], [0,1,0], [0,0,1]
      Planar:   [1,1,0]/sqrt(2), [1,0,1]/sqrt(2), [0,1,1]/sqrt(2)
      3D Diag:  [1,1,1]/sqrt(3), [-1,-1,-1]/sqrt(3)

  Phase 3 -- PROPAGATION (3000 ticks)
    Track per-probe telemetry: speed, phase, radial distance.

  Phase 4 -- ANALYSIS
    3-panel plot:
      Panel 1: Velocity retention v(t)/c_base by direction category
      Panel 2: Phase clock divergence (differential: probe - axial avg)
      Panel 3: Radial distance traveled r(t)

Predictions:
  If grid anisotropy is present:
    1. Diagonal probes experience higher topological damping (Cubic Impedance Bias)
    2. Phase clocks scramble faster along diagonals (LIV signature)
    3. Radial reach is shorter along diagonals (Rounded Cube geometry)

References:
  * Manuscript 14, S2.2  (Emergent Horizon via Klein-Gordon Coupling)
  * Manuscript 14, S6    (Scale-Invariant Black Hole Battery)
  * Magueijo 2005        (Axis of Evil / CMB quadrupole alignment)
  * Amelino-Camelia 1998 (Lorentz Invariance Violation from QG)
"""

import sys
sys.path.insert(0, r'Z:\HOLO DECK\innyouty')

import torch
import numpy as np
import math
import time
import io
import contextlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from config_schema import SimulationConfig
from engine import TEGR2600Engine

# =========================================================================
# OUTPUT
# =========================================================================
OUT_DIR = r'C:\Users\Myna Bird\.gemini\antigravity\brain\5c68d86f-771c-459b-a71a-dc279a192415'

# =========================================================================
# FROZEN PARAMETERS (from Black Hole Battery v3, Manuscript 14 S6)
# =========================================================================
ALPHA       = 20       # Emergent field coupling
S_0         = 0.01     # Equilibrium mass source injection rate
GAMMA_EXP   = 0.075    # Damping exponent
C_BASE      = 65.0     # Ambient vacuum wave speed
DECAY_BASE  = 0.999    # Ambient vacuum damping per tick
IMP_COEFF   = 0.01     # Impedance coupling coefficient
M0_SINK     = 1.0e5    # Sink particle rest mass (creates deep well)

# =========================================================================
# EXPERIMENT PARAMETERS
# =========================================================================
FORMATION_TICKS   = 2000    # Ticks to establish equilibrium well
PROPAGATION_TICKS = 3000    # Ticks to track probes after injection
V_FRAC            = 0.9     # Probe speed as fraction of c_base
M0_PROBE          = 1.0     # Probe rest mass (light -- won't disturb well)
PROBE_OFFSET      = 0.1     # Initial offset from origin (avoids Pauli singularity)

# =========================================================================
# DIRECTION VECTORS (all strictly normalized)
# =========================================================================
# Category labels and normalized direction vectors
PROBE_DIRS = {
    # Axial probes -- travel along voxel FACES
    'Axial +X':  np.array([1.0, 0.0, 0.0]),
    'Axial +Y':  np.array([0.0, 1.0, 0.0]),
    'Axial +Z':  np.array([0.0, 0.0, 1.0]),
    # Planar diagonals -- travel along voxel EDGES
    'Planar XY': np.array([1.0, 1.0, 0.0]) / np.sqrt(2),
    'Planar XZ': np.array([1.0, 0.0, 1.0]) / np.sqrt(2),
    'Planar YZ': np.array([0.0, 1.0, 1.0]) / np.sqrt(2),
    # 3D diagonals -- travel into voxel CORNERS
    'Diag +++':  np.array([1.0, 1.0, 1.0]) / np.sqrt(3),
    'Diag ---':  np.array([-1.0, -1.0, -1.0]) / np.sqrt(3),
}

# Category assignments for color coding
CATEGORIES = {
    'Axial':   ['Axial +X', 'Axial +Y', 'Axial +Z'],
    'Planar':  ['Planar XY', 'Planar XZ', 'Planar YZ'],
    '3D Diag': ['Diag +++', 'Diag ---'],
}

CAT_COLORS = {
    'Axial':   '#e63946',   # Red
    'Planar':  '#457b9d',   # Steel blue
    '3D Diag': '#2a9d8f',   # Teal
}


# =========================================================================
# HELPER FUNCTIONS
# =========================================================================

def make_config(total_ticks, num_particles=2):
    """Create engine config for emergent horizon mode."""
    config = SimulationConfig()
    config.total_ticks = total_ticks
    config.num_particles = num_particles
    config.dt = 0.001
    config.grid_resolution = 64
    config.wave_speed = C_BASE

    config.emergent_horizons = True
    config.emergent_alpha = ALPHA
    config.emergent_c_base = C_BASE
    config.emergent_decay_base = DECAY_BASE
    config.emergent_decay_gamma = GAMMA_EXP
    config.emergent_source_strength = S_0
    config.nested_enabled = False

    config.pauli_enabled = True
    config.pauli_strength = 10.0
    config.pilot_wave = True
    config.torsion_coupling = 1.0
    config.vacuum_enabled = True
    config.vacuum_damping = 0.001
    config.impedance_coupling_coeff = IMP_COEFF

    return config


def compute_probe_momentum(direction_hat, v_frac=V_FRAC, m0=M0_PROBE, c=C_BASE):
    """
    Compute relativistic 3-momentum for a probe with speed |v| = v_frac * c.

    CRITICAL: direction_hat MUST already be unit-normalized so that
    |v_vec| = v_frac * c exactly.  See the Strict Vector Normalization
    requirement in the experimental design.

    Returns (px, py, pz), gamma
    """
    v_mag = v_frac * c            # scalar speed
    beta = v_mag / c              # = v_frac
    gamma = 1.0 / math.sqrt(1.0 - beta**2)
    p_mag = gamma * m0 * v_mag    # |p|
    p_vec = p_mag * direction_hat
    return p_vec, gamma


# =========================================================================
# PHASE 1: FORMATION
# =========================================================================

def run_formation():
    """Establish equilibrium emergent horizon with massive sink."""
    print("=" * 74)
    print("  PHASE 6: ANISOTROPY SWEEP -- THE SPHERE OF STRAIN")
    print("=" * 74)
    print(f"\n  Phase 1: FORMATION (S={S_0}, M_sink={M0_SINK:.0e}, {FORMATION_TICKS} ticks)")
    print("  " + "-" * 68)

    config = make_config(FORMATION_TICKS, num_particles=2)
    adjacency = torch.zeros(2, 2, dtype=torch.bool)

    # State: sink at origin + anchor at r=20
    state = torch.zeros(2, 10, dtype=torch.float32)
    state[0, 7] = M0_SINK   # Sink mass
    state[0, 9] = 1.0       # gamma = 1
    state[1, 1] = 20.0      # Anchor at x=20
    state[1, 7] = 100.0     # Heavy enough to stay put
    state[1, 9] = 1.0

    engine = TEGR2600Engine(config)
    trajectory = engine.run(state, adjacency)

    # Measure formation well
    if engine.config.emergent_horizons:
        engine._update_emergent_impedance()
    c_sq = engine._c_sq_grid.cpu().numpy().squeeze()
    G = engine.config.grid_resolution
    center = G // 2
    lo = max(center - 2, 0)
    hi = min(center + 3, G)
    c_inner = np.sqrt(max(c_sq[lo:hi, lo:hi, lo:hi].mean(), 0))
    ratio = C_BASE / max(c_inner, 1e-6)

    print(f"\n  Formation Equilibrium:")
    print(f"    c_inner (5x5x5 avg) = {c_inner:.2f}")
    print(f"    c_base              = {C_BASE:.2f}")
    print(f"    Impedance Ratio R   = {ratio:.4f}")
    print(f"    Grid bounds         = [{engine.GRID_MIN:.1f}, {engine.GRID_MAX:.1f}]")

    return engine, trajectory


# =========================================================================
# PHASE 2: PROBE INJECTION + PROPAGATION
# =========================================================================

def run_propagation(formation_engine, formation_trajectory):
    """Inject directional probes and track through the impedance well."""

    print(f"\n  Phase 2: PROBE INJECTION + PROPAGATION ({PROPAGATION_TICKS} ticks)")
    print("  " + "-" * 68)

    # Save formation field state
    phi_formation = formation_engine._phi_curr.clone()
    phi_prev_formation = formation_engine._phi_prev.clone()
    grid_min_ref = formation_engine.GRID_MIN

    # Get final formation state for sink + anchor
    final_formation = torch.tensor(
        formation_trajectory[-1], dtype=torch.float32
    )

    # ------------------------------------------------------------------
    # Build the N=10 state: 2 formation particles + 8 probes
    # ------------------------------------------------------------------
    probe_names = list(PROBE_DIRS.keys())
    N_probes = len(probe_names)
    N_total = 2 + N_probes  # sink + anchor + 8 probes

    state = torch.zeros(N_total, 10, dtype=torch.float32)

    # Copy formation particles (sink at origin, anchor at r=20)
    state[0] = final_formation[0]
    state[1] = final_formation[1]

    # Inject probes
    print(f"\n  Injecting {N_probes} probes at v = {V_FRAC}*c_base = {V_FRAC*C_BASE:.1f}")
    print(f"  {'Probe':<12s} {'Direction':<22s} {'|p|':>8s} {'gamma':>8s}")
    print(f"  " + "-" * 54)

    for i, name in enumerate(probe_names):
        d_hat = PROBE_DIRS[name]

        # Verify normalization
        norm = np.linalg.norm(d_hat)
        assert abs(norm - 1.0) < 1e-10, f"Direction {name} not normalized: |d|={norm}"

        p_vec, gamma = compute_probe_momentum(d_hat)

        idx = 2 + i  # state index

        # Position: slightly offset from origin in launch direction
        state[idx, 1:4] = torch.tensor(PROBE_OFFSET * d_hat, dtype=torch.float32)

        # Momentum
        state[idx, 4:7] = torch.tensor(p_vec, dtype=torch.float32)

        # Rest mass
        state[idx, 7] = M0_PROBE

        # Phase clock: all start at 0
        state[idx, 8] = 0.0

        # Gamma
        state[idx, 9] = gamma

        print(f"  {name:<12s} [{d_hat[0]:+.4f}, {d_hat[1]:+.4f}, {d_hat[2]:+.4f}]"
              f"  {np.linalg.norm(p_vec):8.2f}  {gamma:8.4f}")

    # ------------------------------------------------------------------
    # Create propagation engine
    # ------------------------------------------------------------------
    config = make_config(PROPAGATION_TICKS, num_particles=N_total)
    engine = TEGR2600Engine(config)

    # Patch seed function to restore formation phi field
    phi_to_restore = phi_formation.clone()
    phi_prev_to_restore = phi_prev_formation.clone()

    def _restore_field(state_arg):
        engine._phi_curr.copy_(phi_to_restore)
        engine._phi_prev.copy_(phi_prev_to_restore)

    engine._seed_field_from_particles = _restore_field

    # Adjacency: no entanglement between probes
    adjacency = torch.zeros(N_total, N_total, dtype=torch.bool)

    # Run propagation
    print(f"\n  Running propagation ({PROPAGATION_TICKS} ticks, {N_total} particles)...")
    sweep_start = time.time()

    with contextlib.redirect_stdout(io.StringIO()):
        trajectory = engine.run(state, adjacency)

    elapsed = time.time() - sweep_start
    print(f"  Propagation complete in {elapsed:.1f}s")

    # Grid consistency check
    if abs(engine.GRID_MIN - grid_min_ref) > 2.0:
        print(f"  ! Grid drift: [{grid_min_ref:.1f}] -> [{engine.GRID_MIN:.1f}]")

    return trajectory, probe_names


# =========================================================================
# PHASE 3: TELEMETRY EXTRACTION
# =========================================================================

def extract_telemetry(trajectory, probe_names):
    """Extract per-probe telemetry from the trajectory array."""

    print(f"\n  Phase 3: TELEMETRY EXTRACTION")
    print("  " + "-" * 68)

    T = trajectory.shape[0]
    telemetry = {}

    for i, name in enumerate(probe_names):
        idx = 2 + i  # state index (skip sink + anchor)

        pos = trajectory[:, idx, 1:4]       # (T, 3)
        mom = trajectory[:, idx, 4:7]       # (T, 3)
        m0  = trajectory[:, idx, 7]         # (T,)
        theta = trajectory[:, idx, 8]       # (T,)
        gamma = trajectory[:, idx, 9]       # (T,)

        # Speed: |v| = |p| / (gamma * m0)
        p_mag = np.linalg.norm(mom, axis=1)
        gamma_safe = np.maximum(gamma, 1.0)
        m0_safe = np.maximum(m0, 1e-8)
        speed = p_mag / (gamma_safe * m0_safe)  # |v|

        # Radial distance from origin
        r = np.linalg.norm(pos, axis=1)

        telemetry[name] = {
            'pos': pos,
            'speed': speed,
            'speed_frac': speed / C_BASE,   # v / c_base
            'theta': theta,
            'gamma': gamma,
            'r': r,
        }

    # Print summary at final tick
    print(f"\n  Final Telemetry (tick {T}):")
    print(f"  {'Probe':<12s} {'v/c':>8s} {'r_final':>10s} {'theta':>8s} {'gamma':>8s}")
    print(f"  " + "-" * 52)

    for name in probe_names:
        d = telemetry[name]
        print(f"  {name:<12s} {d['speed_frac'][-1]:8.4f} {d['r'][-1]:10.4f}"
              f" {d['theta'][-1]:8.4f} {d['gamma'][-1]:8.4f}")

    return telemetry


# =========================================================================
# PHASE 4: VISUALIZATION
# =========================================================================

def generate_plots(telemetry, probe_names):
    """Generate the 3-panel anisotropy diagnostic plot."""

    print(f"\n  Phase 4: GENERATING PLOTS")
    print("  " + "-" * 68)

    T = len(telemetry[probe_names[0]]['speed'])
    ticks = np.arange(T)

    fig, axes = plt.subplots(2, 2, figsize=(20, 16))
    fig.suptitle(
        'Phase 6: The Anisotropy Sweep -- The Sphere of Strain\n'
        'Searching for the Parent Lattice Fingerprint',
        fontsize=16, fontweight='bold', y=0.98
    )

    # ------------------------------------------------------------------
    # Panel 1: Velocity Retention v(t)/c_base
    # ------------------------------------------------------------------
    ax1 = axes[0, 0]

    for cat_name, cat_probes in CATEGORIES.items():
        color = CAT_COLORS[cat_name]
        for j, pname in enumerate(cat_probes):
            d = telemetry[pname]
            label = f'{cat_name}' if j == 0 else None
            alpha = 1.0 if j == 0 else 0.5
            ax1.plot(ticks, d['speed_frac'], '-', color=color,
                     linewidth=1.5, alpha=alpha, label=label)

    ax1.axhline(y=V_FRAC, color='gold', linewidth=1, linestyle='--',
                alpha=0.6, label=f'v_0 = {V_FRAC}c')
    ax1.set_xlabel('Propagation Ticks', fontsize=12)
    ax1.set_ylabel('Speed Fraction v(t) / c_base', fontsize=12)
    ax1.set_title('Velocity Retention: Cubic Impedance Bias Test', fontsize=13,
                  fontweight='bold')
    ax1.legend(fontsize=10, loc='best')
    ax1.grid(True, alpha=0.3)

    # ------------------------------------------------------------------
    # Panel 2: Phase Clock Divergence (differential)
    # ------------------------------------------------------------------
    ax2 = axes[0, 1]

    # Compute axial average phase as reference
    axial_thetas = np.array([telemetry[p]['theta'] for p in CATEGORIES['Axial']])
    theta_axial_avg = axial_thetas.mean(axis=0)

    for cat_name, cat_probes in CATEGORIES.items():
        color = CAT_COLORS[cat_name]
        for j, pname in enumerate(cat_probes):
            d = telemetry[pname]
            # Differential phase: |theta_probe - theta_axial_avg|
            # Handle 2pi wrapping
            delta_theta = d['theta'] - theta_axial_avg
            delta_theta = np.abs(np.arctan2(np.sin(delta_theta), np.cos(delta_theta)))

            label = f'{cat_name}' if j == 0 else None
            alpha = 1.0 if j == 0 else 0.5
            ax2.plot(ticks, delta_theta, '-', color=color,
                     linewidth=1.5, alpha=alpha, label=label)

    ax2.set_xlabel('Propagation Ticks', fontsize=12)
    ax2.set_ylabel('|delta_theta| = |theta_probe - theta_axial_avg| (rad)', fontsize=12)
    ax2.set_title('Phase Clock Divergence: LIV Signature\n'
                  '(differential phase vs axial average)',
                  fontsize=13, fontweight='bold')
    ax2.legend(fontsize=10, loc='best')
    ax2.grid(True, alpha=0.3)

    # ------------------------------------------------------------------
    # Panel 3: Radial Distance Traveled
    # ------------------------------------------------------------------
    ax3 = axes[1, 0]

    for cat_name, cat_probes in CATEGORIES.items():
        color = CAT_COLORS[cat_name]
        for j, pname in enumerate(cat_probes):
            d = telemetry[pname]
            label = f'{cat_name}' if j == 0 else None
            alpha = 1.0 if j == 0 else 0.5
            ax3.plot(ticks, d['r'], '-', color=color,
                     linewidth=1.5, alpha=alpha, label=label)

    ax3.set_xlabel('Propagation Ticks', fontsize=12)
    ax3.set_ylabel('Radial Distance from Origin r(t)', fontsize=12)
    ax3.set_title('Escape Radius: The Rounded Cube Test', fontsize=13,
                  fontweight='bold')
    ax3.legend(fontsize=10, loc='best')
    ax3.grid(True, alpha=0.3)

    # ------------------------------------------------------------------
    # Panel 4: Summary Statistics Table
    # ------------------------------------------------------------------
    ax4 = axes[1, 1]
    ax4.axis('off')

    # Compute category averages for final tick
    summary_data = []
    for cat_name, cat_probes in CATEGORIES.items():
        speeds = [telemetry[p]['speed_frac'][-1] for p in cat_probes]
        radii = [telemetry[p]['r'][-1] for p in cat_probes]
        gammas = [telemetry[p]['gamma'][-1] for p in cat_probes]
        thetas = [telemetry[p]['theta'][-1] for p in cat_probes]

        summary_data.append([
            cat_name,
            f'{np.mean(speeds):.6f}',
            f'{np.mean(radii):.4f}',
            f'{np.mean(gammas):.4f}',
            f'{np.mean(thetas):.4f}',
        ])

    # Add anisotropy delta row
    axial_v = np.mean([telemetry[p]['speed_frac'][-1] for p in CATEGORIES['Axial']])
    diag_v = np.mean([telemetry[p]['speed_frac'][-1] for p in CATEGORIES['3D Diag']])
    axial_r = np.mean([telemetry[p]['r'][-1] for p in CATEGORIES['Axial']])
    diag_r = np.mean([telemetry[p]['r'][-1] for p in CATEGORIES['3D Diag']])

    delta_v = diag_v - axial_v
    delta_r = diag_r - axial_r

    summary_data.append([
        'Delta (Diag-Axial)',
        f'{delta_v:+.6f}',
        f'{delta_r:+.4f}',
        '--',
        '--',
    ])

    # Percentage anisotropy
    if axial_v > 0:
        pct_v = 100.0 * delta_v / axial_v
    else:
        pct_v = 0.0
    if axial_r > 0:
        pct_r = 100.0 * delta_r / axial_r
    else:
        pct_r = 0.0

    summary_data.append([
        'Anisotropy %',
        f'{pct_v:+.4f}%',
        f'{pct_r:+.4f}%',
        '--',
        '--',
    ])

    col_labels = ['Category', 'v_final/c', 'r_final', 'gamma_final', 'theta_final']
    table = ax4.table(
        cellText=summary_data,
        colLabels=col_labels,
        cellLoc='center',
        loc='center',
    )
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.0, 1.8)

    # Color the header row
    for j in range(len(col_labels)):
        table[0, j].set_facecolor('#2d3436')
        table[0, j].set_text_props(color='white', fontweight='bold')

    # Color data rows by category
    for i, row in enumerate(summary_data):
        if row[0] in CAT_COLORS:
            for j in range(len(col_labels)):
                table[i + 1, j].set_facecolor(CAT_COLORS[row[0]] + '20')  # 20 = alpha hex

    ax4.set_title('Anisotropy Summary (Final Tick)',
                  fontsize=13, fontweight='bold', pad=20)

    plt.tight_layout(rect=[0, 0, 1, 0.94])

    outpath = f'{OUT_DIR}/anisotropy_sweep.png'
    fig.savefig(outpath, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  Plot saved: {outpath}")

    return delta_v, delta_r, pct_v, pct_r


# =========================================================================
# MAIN
# =========================================================================

def main():
    print("\n")

    # Phase 1: Formation
    formation_engine, formation_trajectory = run_formation()

    # Phase 2: Propagation
    trajectory, probe_names = run_propagation(formation_engine, formation_trajectory)

    # Phase 3: Telemetry
    telemetry = extract_telemetry(trajectory, probe_names)

    # Phase 4: Plots
    delta_v, delta_r, pct_v, pct_r = generate_plots(telemetry, probe_names)

    # Final report
    print("\n" + "=" * 74)
    print("  PHASE 6 RESULTS: ANISOTROPY SWEEP")
    print("=" * 74)

    print(f"\n  Experimental Setup:")
    print(f"    Formation:   {FORMATION_TICKS} ticks, M_sink = {M0_SINK:.0e}")
    print(f"    Probes:      {len(PROBE_DIRS)} directions, v = {V_FRAC}*c_base = {V_FRAC*C_BASE:.1f}")
    print(f"    Propagation: {PROPAGATION_TICKS} ticks")

    print(f"\n  Anisotropy Detection:")
    print(f"    Delta v (Diag - Axial):  {delta_v:+.6f} c_base  ({pct_v:+.4f}%)")
    print(f"    Delta r (Diag - Axial):  {delta_r:+.4f} units  ({pct_r:+.4f}%)")

    if abs(pct_v) > 0.01 or abs(pct_r) > 0.01:
        print(f"\n  +===========================================================+")
        print(f"  |  GRID ANISOTROPY DETECTED                                |")
        print(f"  |  The Parent Lattice has left a fingerprint.               |")
        print(f"  |  Diagonal probes experience different impedance than axial.|")
        print(f"  |  This is the computational Axis of Evil.                  |")
        print(f"  +===========================================================+")
    else:
        print(f"\n  Result: No significant anisotropy detected (< 0.01%)")
        print(f"  The grid appears isotropic at this resolution / energy.")

    print(f"\n  INTERPRETATION:")
    print(f"  If delta_v < 0: diagonal probes decelerate MORE (higher impedance bias)")
    print(f"  If delta_v > 0: diagonal probes decelerate LESS (lower impedance bias)")
    print(f"  The 7-point Laplacian stencil naturally introduces directional bias")
    print(f"  because diagonal paths cross more grid boundaries per unit distance.")

    print("\n" + "=" * 74)
    print("  PHASE 6 COMPLETE")
    print("=" * 74)


if __name__ == '__main__':
    main()
