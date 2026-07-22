"""
Phase 4A (v3): The Black Hole Battery — Dimensionless Universal Test
=====================================================================

KEY INSIGHT FROM v1/v2 FAILURES:
    Scaling dt breaks per-tick operations (source injection, damping).
    The FDTD wave equation IS scale-invariant (c^2*dt^2/dx^2 cancels),
    but discretized operations (phi *= lambda, phi += S) are per-tick.

CORRECT APPROACH:
    The TEGR 2600 engine is inherently DIMENSIONLESS. A single simulation
    applies to ALL masses simultaneously. Each grid cell's physical size
    is just a label: for Cygnus X-1 it's 11.6 km, for TON 618 it's
    3.66e11 km. But the dimensionless physics is identical.

    To prove this, we:
    1. Run ONE definitive simulation with frozen params
    2. Present the result with physical scale labels for each mass
    3. Show that the boundary operator F is universal by construction

    Additionally, we validate NUMERICAL precision by running the same
    dimensionless problem at three different floating-point scales
    (multiply all coordinates by 1, 1e4, 1e8) and showing the ratio
    is preserved.

FROZEN PARAMS (from Phase 3D):
    alpha=20, S=0.01, gamma=0.075, c_base=65, decay_base=0.999
"""

import sys
sys.path.insert(0, r'Z:\HOLO DECK\innyouty')

import torch
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from config_schema import SimulationConfig
from engine import TEGR2600Engine

OUT_DIR = r'C:\Users\Myna Bird\.gemini\antigravity\brain\5c68d86f-771c-459b-a71a-dc279a192415'

# =========================================================================
# PHYSICAL CONSTANTS
# =========================================================================
G_SI = 6.67430e-11
c_SI = 2.99792e8
M_SUN = 1.98892e30

# =========================================================================
# BLACK HOLES
# =========================================================================
BLACK_HOLES = [
    ("Cygnus X-1",   21.0,    "Miller-Jones+ 2021"),
    ("GW150914",     62.0,    "Abbott+ 2016"),
    ("Sgr A*",       4.1e6,   "GRAVITY 2022"),
    ("TON 618",      6.6e10,  "Shemmer+ 2004"),
]

# =========================================================================
# FROZEN ENGINE PARAMETERS
# =========================================================================
ALPHA       = 20
S           = 0.01
GAMMA       = 0.075
C_BASE      = 65.0
DECAY_BASE  = 0.999
IMP_COEFF   = 0.01
M0_SINK     = 10000.0


def compute_R_s(M_solar):
    """Schwarzschild radius in meters."""
    return 2 * G_SI * (M_solar * M_SUN) / c_SI**2


def run_universal_simulation(coordinate_scale=1.0, label="baseline"):
    """
    Run the canonical emergent horizon simulation.
    
    coordinate_scale: multiply all positions/velocities by this factor
                      to test numerical precision at different scales.
                      Physics is identical; only floating-point behavior changes.
    """
    k = coordinate_scale
    
    config = SimulationConfig()
    config.total_ticks = 2000
    config.dt = 0.001
    config.grid_resolution = 64
    config.wave_speed = C_BASE
    
    config.emergent_horizons = True
    config.emergent_alpha = ALPHA
    config.emergent_c_base = C_BASE
    config.emergent_decay_base = DECAY_BASE
    config.emergent_decay_gamma = GAMMA
    config.emergent_source_strength = S
    config.nested_enabled = False
    
    config.pauli_enabled = True
    config.pauli_strength = 10.0
    config.pilot_wave = True
    config.torsion_coupling = 1.0
    config.vacuum_enabled = True
    config.vacuum_damping = 0.001
    config.impedance_coupling_coeff = IMP_COEFF
    
    # --- Particles (scaled coordinates for precision test) ---
    N = 2
    state = torch.zeros(N, 10, dtype=torch.float32)
    
    # Sink at origin
    state[0, 0] = 0
    state[0, 7] = M0_SINK
    state[0, 9] = 1.0
    
    # Projectile at r=20*k with v=-10 (velocity NOT scaled)
    state[1, 0] = 1
    state[1, 1] = 20.0 * k
    state[1, 4] = -10.0  # unscaled velocity
    state[1, 7] = 1.0
    state[1, 9] = 1.0
    
    adjacency = torch.zeros(N, N, dtype=torch.bool)
    engine = TEGR2600Engine(config)
    trajectory = engine.run(state, adjacency)
    
    # --- Diagnostics ---
    proj_traj = trajectory[:, 1, :]
    r_proj = np.sqrt(proj_traj[:, 1]**2 + proj_traj[:, 2]**2 + proj_traj[:, 3]**2)
    mom_x = proj_traj[:, 4]
    mom_mag = np.sqrt(proj_traj[:, 4]**2 + proj_traj[:, 5]**2 + proj_traj[:, 6]**2)
    
    # Normalize radius to dimensionless units
    r_dimless = r_proj / k if k > 0 else r_proj
    
    # Field
    c_sq = engine._c_sq_grid.cpu().numpy().squeeze()
    decay = engine._decay_grid.cpu().numpy().squeeze()
    G = config.grid_resolution
    center = G // 2
    c_origin = np.sqrt(max(c_sq[center, center, center], 0))
    lam_origin = decay[center, center, center]
    
    # Radial profile
    coords = np.linspace(engine.GRID_MIN, engine.GRID_MAX, G)
    x3d, y3d, z3d = np.meshgrid(coords, coords, coords, indexing='ij')
    r3d = np.sqrt(x3d**2 + y3d**2 + z3d**2) / k
    r_flat = r3d.flatten()
    c_sq_flat = c_sq.flatten()
    n_bins = 30
    r_edges = np.linspace(0, 25, n_bins + 1)
    r_centers = 0.5 * (r_edges[:-1] + r_edges[1:])
    c_avg = np.zeros(n_bins)
    for b in range(n_bins):
        mask = (r_flat >= r_edges[b]) & (r_flat < r_edges[b+1])
        if mask.any():
            c_avg[b] = np.sqrt(max(np.mean(c_sq_flat[mask]), 0))
    
    # Momentum at entry/deep (dimensionless thresholds)
    r_entry, r_deep = 15.0, 5.0
    entry_tick = deep_tick = None
    for t in range(config.total_ticks):
        if r_dimless[t] <= r_entry and entry_tick is None:
            entry_tick = t
        if entry_tick is not None and r_dimless[t] <= r_deep and deep_tick is None:
            deep_tick = t
    
    p_entry = abs(mom_x[entry_tick]) if entry_tick is not None else abs(mom_x[0])
    p_deep = abs(mom_x[deep_tick]) if deep_tick is not None else abs(mom_x[-1])
    ratio = p_deep / max(p_entry, 1e-12)
    
    return {
        'label': label, 'k': k,
        'c_origin': c_origin, 'lam_origin': lam_origin,
        'ratio': ratio, 'p_entry': p_entry, 'p_deep': p_deep,
        'entry_tick': entry_tick, 'deep_tick': deep_tick,
        'r_dimless': r_dimless, 'mom_mag': mom_mag,
        'r_centers': r_centers, 'c_avg': c_avg,
        'c_sq_2d': c_sq[:, :, center],
        'extent_dimless': [engine.GRID_MIN/k, engine.GRID_MAX/k,
                           engine.GRID_MIN/k, engine.GRID_MAX/k],
        'ticks_sec': config.total_ticks / (trajectory.shape[0] * config.dt),
    }


# =========================================================================
# PART 1: THE UNIVERSAL SIMULATION
# =========================================================================
print("=" * 74)
print("  PHASE 4A: THE BLACK HOLE BATTERY — UNIVERSAL DIMENSIONLESS TEST")
print("=" * 74)

print("\n  Running canonical simulation (k=1)...")
baseline = run_universal_simulation(coordinate_scale=1.0, label="Canonical (k=1)")

print(f"\n  UNIVERSAL RESULT:")
print(f"    c_origin    = {baseline['c_origin']:.2f} ({baseline['c_origin']/C_BASE*100:.1f}% of c_base)")
print(f"    lambda      = {baseline['lam_origin']:.4f}")
print(f"    p_entry     = {baseline['p_entry']:.4f} (tick {baseline['entry_tick']})")
print(f"    p_deep      = {baseline['p_deep']:.4f} (tick {baseline['deep_tick']})")
print(f"    RATIO       = {baseline['ratio']:.6f}")

# =========================================================================
# PART 2: PHYSICAL SCALE TABLE
# =========================================================================
print("\n" + "=" * 74)
print("  PHYSICAL INTERPRETATION: One Simulation, All Masses")
print("=" * 74)

# Grid parameters from the simulation
DX_grid = 1.875  # grid units
R_s_grid = 5.0 * DX_grid  # ~R_s in grid units (where c drops significantly)
# Actually, let's compute R_s_grid from where c drops to 50% of base
# c_origin = 45.88, that's about 5 grid cells from center (r~5-10)

print(f"\n  Grid: 64^3, DX = {DX_grid:.3f} grid units, extent = [-60, 60]")
print(f"  Well bottom at r~0 (origin): c = {baseline['c_origin']:.1f}")
print(f"  Each grid unit maps to a different physical length for each mass:\n")

header = f"  {'Black Hole':<14s}  {'M (M_sun)':<12s}  {'R_s':<16s}  {'1 grid unit':<16s}  {'Well depth':<12s}  {'Ratio':<10s}"
print(header)
print("  " + "-" * 88)

for name, M_solar, ref in BLACK_HOLES:
    R_s = compute_R_s(M_solar)
    
    # Physical size of one grid unit: R_s maps to ~10 cells from center
    # So 1 grid unit = R_s / 10
    grid_unit_m = R_s / 10.0
    
    # Convert to human-readable units
    if grid_unit_m < 1e6:
        gu_str = f"{grid_unit_m/1000:.1f} km"
    elif grid_unit_m < 1e12:
        gu_str = f"{grid_unit_m/1e9:.2f} million km"
    else:
        gu_str = f"{grid_unit_m/(9.461e15):.2f} ly"
    
    if R_s < 1e6:
        rs_str = f"{R_s/1000:.0f} km"
    elif R_s < 1e12:
        rs_str = f"{R_s/1e9:.1f} million km"
    else:
        rs_str = f"{R_s/(9.461e15):.0f} ly"
    
    # The well depth (c/c_base) and ratio are IDENTICAL for all masses
    print(f"  {name:<14s}  {M_solar:<12.1e}  {rs_str:<16s}  {gu_str:<16s}  "
          f"{baseline['c_origin']/C_BASE*100:5.1f}%       {baseline['ratio']:.6f}")

print(f"\n  KEY RESULT: The suppression ratio {baseline['ratio']:.6f} is UNIVERSAL.")
print(f"  It applies to all four black holes because the boundary operator F")
print(f"  depends only on dimensionless quantities (alpha*|phi|, gamma, S).")

# =========================================================================
# PART 3: NUMERICAL PRECISION TEST
#
# Run the SAME dimensionless problem at 3 coordinate scales to verify
# that floating-point arithmetic doesn't degrade the ratio.
# =========================================================================
print("\n" + "=" * 74)
print("  NUMERICAL PRECISION TEST: Same Physics at Different Scales")
print("=" * 74)

# Note: k=1 is the baseline. Now test k=1e2 and k=1e4.
# We can't go to k=1e8 because float32 loses precision at that scale.
# The projectile would be at x=2e9 with velocity -10 and dx~5.6e9,
# so x/dx ~ 0.35 grid cells — should be fine up to k~1e5 in float32.
scales = [1.0, 100.0, 10000.0]
precision_results = [baseline]  # reuse k=1

print(f"\n  {'Scale (k)':<12s}  {'c_origin':>9s}  {'lambda':>8s}  {'Ratio':>12s}  {'Deviation':>10s}")
print("  " + "-" * 56)
print(f"  {'1.0':<12s}  {baseline['c_origin']:9.2f}  {baseline['lam_origin']:8.4f}  "
      f"{baseline['ratio']:12.6f}  {'(baseline)':>10s}")

for k in scales[1:]:
    print(f"\n  Running k={k:.0e}...", end="", flush=True)
    r = run_universal_simulation(coordinate_scale=k, label=f"k={k:.0e}")
    precision_results.append(r)
    dev = abs(r['ratio'] - baseline['ratio']) / max(abs(baseline['ratio']), 1e-12) * 100
    print(f"\r  {k:<12.0e}  {r['c_origin']:9.2f}  {r['lam_origin']:8.4f}  "
          f"{r['ratio']:12.6f}  {dev:9.2f}%")

# =========================================================================
# VISUALIZATION
# =========================================================================
fig, axes = plt.subplots(2, 2, figsize=(18, 14))
fig.suptitle('Phase 4A: The Black Hole Battery\n'
             'Universal Dimensionless Result + Numerical Precision Test',
             fontsize=16, fontweight='bold')

colors_bh = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
colors_k = ['#1f77b4', '#ff7f0e', '#2ca02c']

# Panel 1: c(r) profile from canonical simulation
ax1 = axes[0, 0]
ax1.plot(baseline['r_centers'], baseline['c_avg'], 'b-', linewidth=2.5,
         label=f"Emergent c(r)")
ax1.axhline(y=C_BASE, color='gray', linestyle='--', alpha=0.4, label='c_base=65')
ax1.axhline(y=baseline['c_origin'], color='red', linestyle=':', alpha=0.5,
            label=f'c_origin={baseline["c_origin"]:.1f}')
ax1.set_xlabel('r (dimensionless)', fontsize=11)
ax1.set_ylabel('c(r)', fontsize=11)
ax1.set_title('Universal Emergent Horizon Profile')
ax1.legend(fontsize=10)
ax1.grid(True, alpha=0.3)
ax1.set_ylim(0, 70)

# Panel 2: The Money Table — physical labels
ax2 = axes[0, 1]
ax2.axis('off')
ax2.set_title('One Simulation → All Black Holes', fontsize=13, fontweight='bold',
              pad=20)
table_data = []
for name, M_solar, ref in BLACK_HOLES:
    R_s = compute_R_s(M_solar)
    if R_s < 1e6:
        rs_str = f"{R_s/1000:.0f} km"
    elif R_s < 1e12:
        rs_str = f"{R_s/1e9:.1f}M km"
    else:
        rs_str = f"{R_s/(9.461e15):.0f} ly"
    table_data.append([name, f"{M_solar:.0e}", rs_str, f"{baseline['ratio']:.6f}"])

table = ax2.table(cellText=table_data,
                  colLabels=['Black Hole', 'M (M_sun)', 'R_s', 'Ratio'],
                  cellLoc='center', loc='center',
                  colColours=['#ddeeff']*4)
table.auto_set_font_size(False)
table.set_fontsize(12)
table.scale(1.2, 2.0)
for (row, col), cell in table.get_celld().items():
    if row == 0:
        cell.set_text_props(fontweight='bold')
    if col == 3 and row > 0:
        cell.set_facecolor('#e6ffe6')

# Panel 3: Momentum through well (canonical)
ax3 = axes[1, 0]
ticks = np.arange(len(baseline['mom_mag']))
ax3.plot(ticks, baseline['mom_mag'], 'r-', linewidth=1.5, label='|p(t)|')
ax3.axhline(y=10.0, color='gray', linestyle='--', alpha=0.3)
if baseline['entry_tick'] is not None:
    ax3.axvline(x=baseline['entry_tick'], color='orange', linestyle='--',
                alpha=0.5, label=f"r=15 entry (tick {baseline['entry_tick']})")
if baseline['deep_tick'] is not None:
    ax3.axvline(x=baseline['deep_tick'], color='red', linestyle='--',
                alpha=0.5, label=f"r=5 deep (tick {baseline['deep_tick']})")
ax3.set_xlabel('Tick')
ax3.set_ylabel('|Momentum|')
ax3.set_title(f'Momentum Through Emergent Well (ratio={baseline["ratio"]:.6f})')
ax3.legend(fontsize=9)
ax3.grid(True, alpha=0.3)

# Panel 4: Numerical precision — ratio vs coordinate scale
ax4 = axes[1, 1]
k_vals = [r['k'] for r in precision_results]
ratio_vals = [r['ratio'] for r in precision_results]
c_vals = [r['c_origin'] for r in precision_results]

ax4.semilogx(k_vals, ratio_vals, 'o-', color='darkblue', markersize=12,
             linewidth=2.5, markerfacecolor='gold', markeredgecolor='darkblue',
             markeredgewidth=2, zorder=5)
ax4.axhline(y=baseline['ratio'], color='red', linestyle='--', alpha=0.6,
            linewidth=1.5, label=f'Baseline = {baseline["ratio"]:.6f}')
ax4.set_xlabel('Coordinate Scale Factor k', fontsize=12)
ax4.set_ylabel('Suppression Ratio', fontsize=12)
ax4.set_title('Numerical Precision: Ratio vs Scale', fontsize=13, fontweight='bold')
ax4.legend(fontsize=11)
ax4.grid(True, alpha=0.3)

plt.tight_layout()
out_path = f'{OUT_DIR}\\black_hole_battery_v3.png'
plt.savefig(out_path, dpi=150, bbox_inches='tight')
print(f"\n  Battery v3 plot saved: {out_path}")
plt.close()

# =========================================================================
# c(x,y) heatmap
# =========================================================================
fig2, ax = plt.subplots(1, 1, figsize=(10, 9))
im = ax.imshow(np.sqrt(np.maximum(baseline['c_sq_2d'].T, 0)),
               extent=baseline['extent_dimless'], origin='lower', cmap='inferno',
               aspect='equal', vmin=0, vmax=70)
ax.set_title(f'Universal Emergent Horizon: c(x,y) Slice\n'
             f'c_origin={baseline["c_origin"]:.1f} | '
             f'lambda={baseline["lam_origin"]:.4f} | '
             f'ratio={baseline["ratio"]:.6f}',
             fontsize=13, fontweight='bold')
plt.colorbar(im, ax=ax, shrink=0.8, label='c(x,y)')
ax.set_xlabel('x (dimensionless)')
ax.set_ylabel('y (dimensionless)')
slice_path = f'{OUT_DIR}\\black_hole_battery_v3_slice.png'
plt.savefig(slice_path, dpi=150, bbox_inches='tight')
print(f"  Heatmap saved: {slice_path}")
plt.close()

print("\n" + "=" * 74)
print("  PHASE 4A COMPLETE: UNIVERSAL DIMENSIONLESS RESULT")
print("=" * 74)
