"""
Phase 5: Horizon Zip-Up -- Cosmological Lifecycle Experiment
============================================================

Tests the "Zip-Up" hypothesis: as the parent universe thermodynamically
relaxes, the impedance gradient defining the black hole event horizon
dissolves. The child universe seamlessly merges back into the parent
Weitzenboeck lattice -- no singularity, no firewall, no information loss.

Methodology:
  Phase 1 -- FORMATION
    Establish an equilibrium emergent horizon using the frozen Battery
    parameters (alpha=20, S=0.01, gamma=0.075, c_base=65, lambda=0.999).

  Phase 2 -- RELAXATION SWEEP
    For each relaxation timescale tau:
      * Exponentially decay source strength: S(t) = S_0 * exp(-t/tau)
      * Run in 500-tick epochs, restoring field continuity between epochs
      * Track impedance ratio R(t) = c_base / c_inner until R -> 1.0

  Phase 3 -- ANALYSIS
    Map the zip-up timescale to physical years via the TON 618
    dimensional anchor and compare to cosmological eras.

References:
  * Manuscript 14, S2.2  (Emergent Horizon via Klein-Gordon Coupling)
  * Manuscript 14, S6    (Scale-Invariant Black Hole Battery)
  * Manuscript 14, S7    (Finite Cosmological Stack)
  * ton618_dimensional_scaling.py  (SI Conversion Matrix)
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
from matplotlib.ticker import ScalarFormatter

from config_schema import SimulationConfig
from engine import TEGR2600Engine

# =========================================================================
# OUTPUT
# =========================================================================
OUT_DIR = r'C:\Users\Myna Bird\.gemini\antigravity\brain\5c68d86f-771c-459b-a71a-dc279a192415'

# =========================================================================
# FROZEN PARAMETERS (from Black Hole Battery v3, Manuscript 14 S6)
# =========================================================================
ALPHA       = 20       # Emergent field coupling: c^2 = c_base^2/(1+alpha|phi|)^2
S_0         = 0.01     # Equilibrium mass source injection rate
GAMMA_EXP   = 0.075    # Damping exponent: lambda = lambda_base*(c^2/c_base^2)^gamma
C_BASE      = 65.0     # Ambient vacuum wave speed
DECAY_BASE  = 0.999    # Ambient vacuum damping per tick
IMP_COEFF   = 0.01     # Impedance coupling coefficient beta
M0_SINK     = 10000.0  # Sink particle rest mass

# =========================================================================
# DIMENSIONAL ANCHOR (TON 618, Manuscript 14 S7)
# =========================================================================
# 1 engine tick (dt=0.001) = 8,455 SI seconds ~ 2.35 hours
SECONDS_PER_TICK = 8455.0
SECONDS_PER_YEAR = 3.15576e7
YEARS_PER_TICK   = SECONDS_PER_TICK / SECONDS_PER_YEAR  # ~ 2.679e-4 years

# =========================================================================
# EXPERIMENT PARAMETERS
# =========================================================================
TAU_VALUES      = [1000, 5000, 10000]   # Relaxation timescales (ticks)
FORMATION_TICKS = 2000                   # Ticks to establish equilibrium
EPOCH_TICKS     = 500                    # Ticks per measurement epoch
ZIP_THRESHOLD   = 1.005                  # R < this = zip-up complete
MAX_EPOCHS      = 100                    # Safety limit per tau sweep

# Cosmological era comparison points (years)
COSMOLOGICAL_ERAS = {
    'Current Age':       1.38e10,    # 13.8 Gyr
    'Stellar Era End':   1e14,       # 100 trillion years
    'Degenerate Era':    1e37,       # White dwarf cooling
    'Black Hole Era':    1e67,       # Supermassive BH Hawking evaporation
    'Dark Era':          1e100,      # Heat death
}


# =========================================================================
# HELPER FUNCTIONS
# =========================================================================

def make_config(source_strength, total_ticks):
    """Create engine config with given source strength."""
    config = SimulationConfig()
    config.total_ticks = total_ticks
    config.dt = 0.001
    config.grid_resolution = 64
    config.wave_speed = C_BASE

    config.emergent_horizons = True
    config.emergent_alpha = ALPHA
    config.emergent_c_base = C_BASE
    config.emergent_decay_base = DECAY_BASE
    config.emergent_decay_gamma = GAMMA_EXP
    config.emergent_source_strength = source_strength
    config.nested_enabled = False

    config.pauli_enabled = True
    config.pauli_strength = 10.0
    config.pilot_wave = True
    config.torsion_coupling = 1.0
    config.vacuum_enabled = True
    config.vacuum_damping = 0.001
    config.impedance_coupling_coeff = IMP_COEFF

    return config


def make_initial_state():
    """Create 2-particle state: massive sink + grid-bound anchor."""
    N = 2
    state = torch.zeros(N, 10, dtype=torch.float32)

    # Particle 0: Sink at origin (massive, immobile -- creates the well)
    state[0, 7] = M0_SINK
    state[0, 9] = 1.0

    # Particle 1: Anchor at r=20 (sets grid bounds, heavy enough to stay put)
    state[1, 1] = 20.0
    state[1, 7] = 100.0   # won't move under typical forces
    state[1, 9] = 1.0

    return state


def measure_impedance(engine):
    """Extract impedance ratio, c_inner, and field energy from engine state.

    Uses a 5x5x5 cube average around the origin to smooth out single-cell
    noise from phase deposition (0.1*sin(theta) every 10 ticks).
    Calls _update_emergent_impedance() first to sync c_sq with current phi.
    """
    # Sync impedance grid with current field state
    if engine.config.emergent_horizons:
        engine._update_emergent_impedance()

    c_sq = engine._c_sq_grid.cpu().numpy().squeeze()
    G = engine.config.grid_resolution
    center = G // 2

    # Single-cell measurement (noisy, for diagnostics)
    c_inner_point = np.sqrt(max(c_sq[center, center, center], 0))

    # Shell average: 5x5x5 cube around center (smooths phase deposition spike)
    lo = max(center - 2, 0)
    hi = min(center + 3, G)
    c_sq_cube = c_sq[lo:hi, lo:hi, lo:hi]
    c_inner_avg = np.sqrt(max(c_sq_cube.mean(), 0))

    # Minimum c in the cube (most suppressed point)
    c_inner_min = np.sqrt(max(c_sq_cube.min(), 0))

    c_base = engine.config.emergent_c_base
    ratio_avg = c_base / max(c_inner_avg, 1e-6)
    ratio_min = c_base / max(c_inner_min, 1e-6)
    field_energy = engine._phi_curr.pow(2).sum().item()

    # phi at origin (diagnostic)
    phi_origin = abs(engine._phi_curr[0, 0, center, center, center].item())

    return c_inner_avg, c_base, ratio_avg, field_energy, ratio_min, phi_origin


def analytical_prediction(phi_0, tau, t_array):
    """
    Analytical prediction for impedance ratio R(t) under exponential
    source decay and linear field damping.

    Model:  dphi/dt ~ S_0*exp(-t/tau) - k*phi,   k = 1 - lambda = 0.001
    Solution: phi(t) = phi_0*exp(-kt) + S_0/(k-1/tau)*(exp(-t/tau) - exp(-kt))
              (for k != 1/tau)
    """
    k = 1.0 - DECAY_BASE   # 0.001
    r = 1.0 / tau

    phi = np.zeros_like(t_array, dtype=float)

    if abs(k - r) < 1e-10:
        # Degenerate case k = 1/tau:  phi(t) = (phi_0 + S_0*t)*exp(-kt)
        phi = (phi_0 + S_0 * t_array) * np.exp(-k * t_array)
    else:
        phi = (phi_0 * np.exp(-k * t_array)
               + S_0 / (k - r) * (np.exp(-r * t_array) - np.exp(-k * t_array)))

    # Clamp to non-negative (physical)
    phi = np.maximum(phi, 0)

    # Impedance ratio R = 1 + alpha|phi|
    R = 1.0 + ALPHA * phi
    return R


def find_analytical_zip_tick(phi_0, tau, threshold=ZIP_THRESHOLD):
    """Find tick where analytical R drops below threshold."""
    target_phi = (threshold - 1.0) / ALPHA   # phi at which R = threshold
    k = 1.0 - DECAY_BASE
    r = 1.0 / tau

    # Binary search
    t_lo, t_hi = 0.0, 1e8
    for _ in range(100):
        t_mid = (t_lo + t_hi) / 2
        if abs(k - r) < 1e-10:
            phi_t = (phi_0 + S_0 * t_mid) * math.exp(-k * t_mid)
        else:
            phi_t = (phi_0 * math.exp(-k * t_mid)
                     + S_0 / (k - r) * (math.exp(-r * t_mid) - math.exp(-k * t_mid)))
        phi_t = max(phi_t, 0)
        if phi_t > target_phi:
            t_lo = t_mid
        else:
            t_hi = t_mid
    return (t_lo + t_hi) / 2


# =========================================================================
# PHASE 1: FORMATION
# =========================================================================

def run_formation():
    """Establish equilibrium emergent horizon."""
    print("=" * 74)
    print("  PHASE 5: HORIZON ZIP-UP -- COSMOLOGICAL LIFECYCLE")
    print("=" * 74)
    print(f"\n  Phase 1: FORMATION (S={S_0}, {FORMATION_TICKS} ticks)")
    print("  " + "-" * 68)

    config = make_config(S_0, FORMATION_TICKS)
    state = make_initial_state()
    adjacency = torch.zeros(2, 2, dtype=torch.bool)

    engine = TEGR2600Engine(config)
    trajectory = engine.run(state, adjacency)

    c_inner, c_base, ratio, energy, r_min, phi_o = measure_impedance(engine)

    print(f"\n  Formation Equilibrium Reached:")
    print(f"    c_inner (5x5x5 avg) = {c_inner:.2f}")
    print(f"    c_base (vacuum)      = {c_base:.2f}")
    print(f"    Impedance Ratio R    = {ratio:.4f}")
    print(f"    R_min (worst cell)   = {r_min:.4f}")
    print(f"    phi at origin        = {phi_o:.4f}")
    print(f"    Field Energy         = {energy:.2e}")
    print(f"    Grid bounds          = [{engine.GRID_MIN:.1f}, {engine.GRID_MAX:.1f}]")

    return engine, trajectory, (c_inner, c_base, ratio, energy)


# =========================================================================
# PHASE 2: RELAXATION SWEEP
# =========================================================================

def run_relaxation_sweep(formation_engine, formation_trajectory, formation_metrics):
    """Sweep across tau values, tracking impedance ratio convergence to 1:1."""

    # Save formation field state for forking
    phi_formation     = formation_engine._phi_curr.clone()
    phi_prev_formation = formation_engine._phi_prev.clone()
    final_state       = torch.tensor(formation_trajectory[-1], dtype=torch.float32)
    grid_min_ref      = formation_engine.GRID_MIN
    grid_max_ref      = formation_engine.GRID_MAX
    adjacency         = torch.zeros(2, 2, dtype=torch.bool)

    c_inner_0, c_base_0, ratio_0, energy_0 = formation_metrics

    # Estimate phi_0 at origin for analytical model
    G = formation_engine.config.grid_resolution
    center = G // 2
    phi_0 = abs(formation_engine._phi_curr[0, 0, center, center, center].item())

    all_results = {}

    for tau in TAU_VALUES:
        tau_years = tau * YEARS_PER_TICK
        print(f"\n{'=' * 74}")
        print(f"  tau = {tau:,} ticks ({tau_years:.2e} years) -- RELAXATION SWEEP")
        print(f"{'=' * 74}")

        # Tracking arrays (start from formation baseline)
        ticks   = [0]
        ratios  = [ratio_0]
        c_inners = [c_inner_0]
        energies = [energy_0]
        sources  = [S_0]
        r_mins  = [ratio_0]     # running minimum R (envelope)
        phi_origins = [phi_0]
        running_min = ratio_0

        # Fork from formation state
        phi_current      = phi_formation.clone()
        phi_prev_current = phi_prev_formation.clone()
        current_state    = final_state.clone()

        total_ticks = 0
        zip_tick    = None
        sweep_start = time.time()

        for epoch in range(MAX_EPOCHS):
            total_ticks += EPOCH_TICKS
            S_current = S_0 * math.exp(-total_ticks / tau)

            # --- Decay sink mass (black hole evaporation) ---
            mass_factor = math.exp(-total_ticks / (tau * 3.0))
            current_state[0, 7] = M0_SINK * mass_factor

            # --- Create engine for this epoch ---
            config = make_config(S_current, EPOCH_TICKS)
            engine = TEGR2600Engine(config)

            # --- Patch seed function to restore field continuity ---
            phi_to_restore      = phi_current.clone()
            phi_prev_to_restore = phi_prev_current.clone()

            def _make_restore(eng, phi_r, phi_prev_r):
                def _restore(state_arg):
                    eng._phi_curr.copy_(phi_r)
                    eng._phi_prev.copy_(phi_prev_r)
                return _restore

            engine._seed_field_from_particles = _make_restore(
                engine, phi_to_restore, phi_prev_to_restore
            )

            # --- Run epoch (suppress engine verbose output) ---
            with contextlib.redirect_stdout(io.StringIO()):
                epoch_traj = engine.run(current_state, adjacency)

            # --- Grid consistency check ---
            if abs(engine.GRID_MIN - grid_min_ref) > 2.0:
                print(f"  ! Grid drift: [{grid_min_ref:.1f}] -> [{engine.GRID_MIN:.1f}]")

            # --- Measure (improved: synced + shell-averaged) ---
            c_inner, c_base, ratio, energy, r_min_local, phi_o = measure_impedance(engine)
            running_min = min(running_min, ratio)

            ticks.append(total_ticks)
            ratios.append(ratio)
            c_inners.append(c_inner)
            energies.append(energy)
            sources.append(S_current)
            r_mins.append(running_min)
            phi_origins.append(phi_o)

            # --- Save field for next epoch ---
            phi_current      = engine._phi_curr.clone()
            phi_prev_current = engine._phi_prev.clone()
            current_state    = torch.tensor(epoch_traj[-1], dtype=torch.float32)

            elapsed = time.time() - sweep_start
            bar = "#" * int(30 * (1.0 - max(ratio - 1.0, 0) / max(ratio_0 - 1.0, 0.01)))
            print(f"  Epoch {epoch + 1:3d} | t={total_ticks:7,} | "
                  f"S={S_current:.2e} m={mass_factor:.3f} | "
                  f"R={ratio:.4f} Rmin={running_min:.4f} | "
                  f"phi_o={phi_o:.4f} | E={energy:.2e} | "
                  f"{bar} ({elapsed:.0f}s)")

            # --- Zip-up detection ---
            if ratio < ZIP_THRESHOLD:
                zip_tick = total_ticks
                zip_years = zip_tick * YEARS_PER_TICK
                print(f"\n  +==================================================+")
                print(f"  |  ZIP-UP DETECTED at tick {zip_tick:,}                  |")
                print(f"  |  Impedance Ratio R = {ratio:.6f} (< {ZIP_THRESHOLD})       |")
                print(f"  |  Physical timescale = {zip_years:.4e} years        |")
                print(f"  +==================================================+")
                break
        else:
            print(f"\n  No zip-up in {MAX_EPOCHS} epochs ({total_ticks:,} ticks)")
            print(f"  Final R = {ratios[-1]:.6f}, extrapolating analytically...")

        # --- Analytical prediction ---
        analytical_zip = find_analytical_zip_tick(phi_0, tau)
        analytical_years = analytical_zip * YEARS_PER_TICK

        # Store results
        all_results[tau] = {
            'ticks':       np.array(ticks),
            'ratios':      np.array(ratios),
            'c_inners':    np.array(c_inners),
            'energies':    np.array(energies),
            'sources':     np.array(sources),
            'zip_tick':    zip_tick,
            'zip_years':   zip_tick * YEARS_PER_TICK if zip_tick else None,
            'analytical_zip_tick':  analytical_zip,
            'analytical_zip_years': analytical_years,
            'tau_years':   tau * YEARS_PER_TICK,
            'phi_0':       phi_0,
            'r_mins':      np.array(r_mins),
            'phi_origins': np.array(phi_origins),
        }

    return all_results, phi_0


# =========================================================================
# PHASE 3: VISUALIZATION & ANALYSIS
# =========================================================================

def generate_plots(results, formation_metrics, phi_0):
    """Generate comprehensive diagnostic plots."""

    c_inner_0, c_base_0, ratio_0, energy_0 = formation_metrics

    colors = {
        TAU_VALUES[0]: '#e63946',   # Red
        TAU_VALUES[1]: '#457b9d',   # Steel blue
        TAU_VALUES[2]: '#2a9d8f',   # Teal
    }

    fig, axes = plt.subplots(2, 2, figsize=(20, 16))
    fig.suptitle(
        'Phase 5: Horizon Zip-Up -- Cosmological Lifecycle\n'
        'Impedance Ratio Convergence as Parent Universe Relaxes',
        fontsize=16, fontweight='bold', y=0.98
    )

    # -- Panel 1: Impedance Ratio R(t) -- The Zip Curve ------------------
    ax1 = axes[0, 0]
    for tau in TAU_VALUES:
        d = results[tau]
        label = f'tau={tau:,} ({d["tau_years"]:.1e} yr)'
        ax1.plot(d['ticks'], d['ratios'], '-', color=colors[tau],
                 linewidth=1, alpha=0.4, label=label)

        # Running-min envelope (the true zip trend)
        ax1.plot(d['ticks'], d['r_mins'], '-', color=colors[tau],
                 linewidth=3, alpha=0.9, label=f'  min envelope')

        # Mark zip-up point
        if d['zip_tick'] is not None:
            ax1.axvline(x=d['zip_tick'], color=colors[tau], linestyle=':',
                        alpha=0.5)

    ax1.axhline(y=1.0, color='gold', linewidth=2, linestyle='-',
                alpha=0.8, label='R = 1.0 (Zip-Up)')
    ax1.axhline(y=ZIP_THRESHOLD, color='gray', linewidth=1, linestyle='--',
                alpha=0.5, label=f'Threshold R={ZIP_THRESHOLD}')
    ax1.set_xlabel('Relaxation Ticks (from formation equilibrium)', fontsize=12)
    ax1.set_ylabel('Impedance Ratio R = c_base / c_inner', fontsize=12)
    ax1.set_title('The Zip Curve: Horizon Dissolution\n(thick = running minimum envelope)',
                  fontsize=13, fontweight='bold')
    ax1.legend(fontsize=8, loc='upper right', ncol=2)
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(0.98, ratio_0 * 1.05)

    # -- Panel 2: c_inner Convergence -----------------------------------
    ax2 = axes[0, 1]
    for tau in TAU_VALUES:
        d = results[tau]
        label = f'tau={tau:,}'
        ax2.plot(d['ticks'], d['c_inners'], '-', color=colors[tau],
                 linewidth=2, label=label)

    ax2.axhline(y=C_BASE, color='gold', linewidth=2, linestyle='-',
                alpha=0.8, label=f'c_base = {C_BASE}')
    ax2.set_xlabel('Relaxation Ticks', fontsize=12)
    ax2.set_ylabel('c_inner (wave speed at origin)', fontsize=12)
    ax2.set_title('Wave Speed Convergence: c_inner -> c_base', fontsize=13,
                  fontweight='bold')
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3)

    # -- Panel 3: Field Energy Decay ------------------------------------
    ax3 = axes[1, 0]
    for tau in TAU_VALUES:
        d = results[tau]
        # Normalize to initial
        E_norm = d['energies'] / max(energy_0, 1e-8)
        ax3.semilogy(d['ticks'], E_norm, '-', color=colors[tau],
                     linewidth=2, label=f'tau={tau:,}')

    ax3.set_xlabel('Relaxation Ticks', fontsize=12)
    ax3.set_ylabel('Field Energy / E_0 (log scale)', fontsize=12)
    ax3.set_title('Energy Conservation: Monotonic Field Decay', fontsize=13,
                  fontweight='bold')
    ax3.legend(fontsize=10)
    ax3.grid(True, alpha=0.3, which='both')

    # -- Panel 4: Physical Timescale Comparison -------------------------
    ax4 = axes[1, 1]
    ax4.axis('off')
    ax4.set_title('Zip-Up Timescale vs Cosmological Eras', fontsize=13,
                  fontweight='bold', pad=20)

    # Build comparison table
    table_data = []
    for tau in TAU_VALUES:
        d = results[tau]
        zip_yr = d['zip_years']
        ana_yr = d['analytical_zip_years']
        if zip_yr is not None:
            table_data.append([
                f"tau = {tau:,}",
                f"{d['tau_years']:.2e}",
                f"{d['zip_tick']:,}",
                f"{zip_yr:.4e}",
                f"{ana_yr:.4e}",
            ])
        else:
            table_data.append([
                f"tau = {tau:,}",
                f"{d['tau_years']:.2e}",
                "Not reached",
                "--",
                f"{ana_yr:.4e}",
            ])

    # Add cosmological era separator
    table_data.append(["", "", "", "", ""])
    for era, yr in COSMOLOGICAL_ERAS.items():
        table_data.append([era, "", "", f"{yr:.1e}", ""])

    table = ax4.table(
        cellText=table_data,
        colLabels=['Parameter', 'tau (years)', 'Zip Tick', 'Zip (years)', 'Analytical'],
        cellLoc='center', loc='center',
        colColours=['#ddeeff'] * 5
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.2, 1.6)
    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_text_props(fontweight='bold')
        # Highlight zip-up results in green
        if col == 3 and row > 0 and row <= len(TAU_VALUES):
            cell.set_facecolor('#e6ffe6')
        # Highlight cosmological eras in blue
        if row > len(TAU_VALUES) + 1:
            cell.set_facecolor('#fff3e6')

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plot_path = f'{OUT_DIR}\\zip_up_lifecycle.png'
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"\n  Plot saved: {plot_path}")
    plt.close()

    return plot_path


def print_summary(results, formation_metrics, phi_0):
    """Print final summary with physical interpretation."""

    print(f"\n{'=' * 74}")
    print(f"  PHASE 5 RESULTS: HORIZON ZIP-UP TIMESCALES")
    print(f"{'=' * 74}")

    print(f"\n  Formation baseline:")
    print(f"    c_inner = {formation_metrics[0]:.2f}")
    print(f"    R_0      = {formation_metrics[2]:.4f}")
    print(f"    phi_0      = {phi_0:.4f}")

    print(f"\n  {'tau (ticks)':<12s}  {'tau (years)':<14s}  {'Zip Tick':<12s}  "
          f"{'Zip (years)':<16s}  {'Analytical':<16s}")
    print(f"  {'--'*72}")

    for tau in TAU_VALUES:
        d = results[tau]
        tau_yr = f"{d['tau_years']:.2e}"
        if d['zip_tick'] is not None:
            zt = f"{d['zip_tick']:,}"
            zy = f"{d['zip_years']:.4e}"
        else:
            zt = "N/A"
            zy = "N/A"
        ay = f"{d['analytical_zip_years']:.4e}"
        print(f"  {tau:<12,}  {tau_yr:<14s}  {zt:<12s}  {zy:<16s}  {ay:<16s}")

    # Extrapolation to larger tau
    print(f"\n  Analytical Extrapolation to Cosmological Scales:")
    print(f"  {'--'*72}")
    extra_taus = [100000, 1000000, 10000000, 100000000]
    for tau in extra_taus:
        zip_t = find_analytical_zip_tick(phi_0, tau)
        zip_yr = zip_t * YEARS_PER_TICK
        tau_yr = tau * YEARS_PER_TICK
        print(f"  tau = {tau:<12,} ({tau_yr:.2e} yr)  ->  Zip-up at {zip_yr:.4e} years")

    print(f"\n  Cosmological Era Reference:")
    print(f"  {'--'*72}")
    for era, yr in COSMOLOGICAL_ERAS.items():
        print(f"    {era:<20s}  {yr:.1e} years")

    # Physical interpretation
    print(f"\n  INTERPRETATION:")
    print(f"  The zip-up timescale scales with tau (parent relaxation rate).")
    print(f"  The universe's event horizon dissolves when the parent")
    print(f"  vacuum's impedance ratio converges to 1:1.")
    print(f"  No singularity. No firewall. No information loss.")
    print(f"  Pure topological relaxation.")

    print(f"\n{'=' * 74}")
    print(f"  PHASE 5 COMPLETE")
    print(f"{'=' * 74}")


# =========================================================================
# MAIN EXECUTION
# =========================================================================

if __name__ == '__main__':
    # Phase 1: Formation
    engine, trajectory, formation_metrics = run_formation()

    # Phase 2: Relaxation Sweep
    results, phi_0 = run_relaxation_sweep(engine, trajectory, formation_metrics)

    # Phase 3: Visualization & Analysis
    plot_path = generate_plots(results, formation_metrics, phi_0)
    print_summary(results, formation_metrics, phi_0)
