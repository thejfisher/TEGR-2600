"""
CLEAN GEOMETRIC TEST — isolate the impedance boundary
=====================================================
- Uniform Pauli (10.0 everywhere) removes tier-specific forces
- Measure velocity JUST BEFORE and JUST AFTER each boundary crossing
- Quadratic impedance coupling + log-gradient + geometric wave speeds
"""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_schema import SimulationConfig
from data_ingest import load_experiment
from engine import TEGR2600Engine
from generate_3tier_probes import generate_3tier_preset

# --- Geometric wave speeds, UNIFORM Pauli ---
preset_path = generate_3tier_preset(
    c_gp=130.0, c_p=65.0, c_c=32.5,           # geometric ratio = 2.0
    decay_gp=0.9999, decay_p=0.999, decay_c=0.9,
    pauli_gp=10.0, pauli_p=10.0, pauli_c=10.0, # UNIFORM — no Pauli confound
    r_parent=12.0, r_child=5.0, sharpness=5.0,
    ticks=5000,
    filename="geometric_clean_test.toml",
)

state, adjacency, metadata = load_experiment(preset_path)
config = SimulationConfig.from_toml(preset_path)
config.impedance_coupling_coeff = 0.5
config.output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output', 'geometric_clean')
os.makedirs(config.output_dir, exist_ok=True)

print(f"  c_gp/c_p = {config.c_gp/config.c_p:.4f}")
print(f"  c_p/c_c  = {config.c_p/config.c_c:.4f}")
print(f"  Pauli:     UNIFORM at 10.0 (no tier-specific confound)")

import time
t0 = time.time()
engine = TEGR2600Engine(config)
traj = engine.run(state, adjacency)
engine.save_results(config.output_dir)

# --- Precision measurement: velocity at boundary crossings ---
proj_idx = 61
proj_x = traj[:, proj_idx, 1]  # x position over time
proj_px = traj[:, proj_idx, 4]  # x momentum over time
proj_r = np.sqrt(traj[:, proj_idx, 1]**2 + traj[:, proj_idx, 2]**2 + traj[:, proj_idx, 3]**2)

R_PARENT = 12.0
R_CHILD = 5.0

# Find the tick where projectile crosses R_parent (r decreasing through 12.0)
cross_parent = None
cross_child = None
for t in range(1, len(proj_r)):
    if proj_r[t-1] > R_PARENT and proj_r[t] <= R_PARENT and cross_parent is None:
        cross_parent = t
    if proj_r[t-1] > R_CHILD and proj_r[t] <= R_CHILD and cross_child is None:
        cross_child = t

# Measure velocity in a small window around each crossing
WINDOW = 50  # ticks before/after to average

def velocity_at(tick, half_window=WINDOW):
    """Average px in a window around tick."""
    t_lo = max(0, tick - half_window)
    t_hi = min(len(proj_px), tick + half_window)
    return np.mean(proj_px[t_lo:tick]), np.mean(proj_px[tick:t_hi])

print(f"\n{'='*60}")
print(f"  CLEAN GEOMETRIC TEST — BOUNDARY CROSSING ANALYSIS")
print(f"{'='*60}")

if cross_parent is not None:
    v_before_p, v_after_p = velocity_at(cross_parent)
    frac_p = v_after_p / v_before_p
    print(f"\n  OUTER BOUNDARY (R_parent={R_PARENT}):")
    print(f"    Crossing at tick {cross_parent} (r={proj_r[cross_parent]:.2f})")
    print(f"    v_before = {v_before_p:.4f}")
    print(f"    v_after  = {v_after_p:.4f}")
    print(f"    Fraction retained: {frac_p:.6f} ({(1-frac_p)*100:.1f}% lost)")
else:
    print(f"\n  OUTER BOUNDARY: projectile never crossed R_parent={R_PARENT}")
    frac_p = None

if cross_child is not None:
    v_before_c, v_after_c = velocity_at(cross_child)
    frac_c = v_after_c / v_before_c
    print(f"\n  INNER BOUNDARY (R_child={R_CHILD}):")
    print(f"    Crossing at tick {cross_child} (r={proj_r[cross_child]:.2f})")
    print(f"    v_before = {v_before_c:.4f}")
    print(f"    v_after  = {v_after_c:.4f}")
    print(f"    Fraction retained: {frac_c:.6f} ({(1-frac_c)*100:.1f}% lost)")
else:
    print(f"\n  INNER BOUNDARY: projectile never crossed R_child={R_CHILD}")
    frac_c = None

if frac_p is not None and frac_c is not None:
    recursive = frac_c / frac_p
    deviation = abs(recursive - 1.0) * 100
    print(f"\n  {'='*50}")
    print(f"  RECURSIVE RATIO (frac_C / frac_P): {recursive:.6f}")
    print(f"  Deviation from 1.0: {deviation:.2f}%")
    print(f"  {'='*50}")
    if deviation < 5.0:
        print(f"\n  >>> SCALE-INVARIANT (deviation {deviation:.2f}%) <<<")
    elif deviation < 15.0:
        print(f"\n  >>> NEAR-INVARIANT (deviation {deviation:.2f}%) <<<")
    else:
        print(f"\n  >>> NOT SELF-SIMILAR (deviation {deviation:.2f}%) <<<")
elif frac_p is not None:
    print(f"\n  Cannot compute recursive ratio — projectile stopped before inner boundary")
    print(f"  Try increasing impedance_coupling_coeff or projectile velocity")

# Also print the old-style regional averages for comparison
gp_mask = proj_r > 14.0
p_mask = (proj_r > 6.0) & (proj_r < 11.0)
c_mask = proj_r < 4.0
v_gp_avg = np.mean(proj_px[gp_mask]) if np.any(gp_mask) else 0
v_p_avg = np.mean(proj_px[p_mask]) if np.any(p_mask) else 0
v_c_avg = np.mean(proj_px[c_mask]) if np.any(c_mask) else 0
print(f"\n  [Regional averages for comparison]")
print(f"    v_GP={v_gp_avg:.4f}  v_P={v_p_avg:.4f}  v_C={v_c_avg:.4f}")

elapsed = time.time() - t0
print(f"\n  Total time: {elapsed:.1f}s")
