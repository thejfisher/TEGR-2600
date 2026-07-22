"""
Phase 5 v3: Robustness Check + Isolation Test
===============================================

TWO CRITICAL TESTS:

1. DEGREE-3 ROBUSTNESS CHECK:
   If the cross-coupling terms (y*vx, x*vy) persist with a richer library,
   they are NOT artifacts of underfitting. If they vanish, they were.

2. CONFOUND ISOLATION TEST:
   Run SINDy with Pauli OFF and Pilot Wave OFF. If the cross-coupling
   survives, it comes from the c^2 gradient (pure emergent curvature).
   If it vanishes, it was from inter-particle forces, not geometry.

   This is the key test. The Christoffel interpretation demands that
   the curvature coupling comes from the FIELD, not from particle-particle
   interactions.

ALL OTHER PARAMETERS IDENTICAL TO v2.
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'Z:\HOLO DECK\innyouty')

import torch
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from itertools import combinations_with_replacement

from config_schema import SimulationConfig
from engine import TEGR2600Engine

OUT_DIR = r'C:\Users\Myna Bird\.gemini\antigravity\brain\5c68d86f-771c-459b-a71a-dc279a192415'

ALPHA       = 20
S           = 0.01
GAMMA       = 0.075
C_BASE      = 65.0
DECAY_BASE  = 0.999
IMP_COEFF   = 0.01
M0_SINK     = 10000.0
N_OUTER     = 20
N_INNER     = 20
N_TOTAL     = 1 + N_OUTER + N_INNER


# =========================================================================
# STLSQ
# =========================================================================
def build_polynomial_library(X, degree=2):
    n_samples, n_features = X.shape
    feature_names = ['1']
    features = [np.ones(n_samples)]
    var_names = ['x', 'y', 'z', 'vx', 'vy', 'vz'][:n_features]

    for i, name in enumerate(var_names):
        features.append(X[:, i])
        feature_names.append(name)

    if degree >= 2:
        for i, j in combinations_with_replacement(range(n_features), 2):
            features.append(X[:, i] * X[:, j])
            feature_names.append(f'{var_names[i]}*{var_names[j]}')

    if degree >= 3:
        for i, j, k in combinations_with_replacement(range(n_features), 3):
            features.append(X[:, i] * X[:, j] * X[:, k])
            feature_names.append(f'{var_names[i]}*{var_names[j]}*{var_names[k]}')

    return np.column_stack(features), feature_names


def stlsq(Theta, dXdt, threshold, max_iter=20, alpha_ridge=1e-5):
    n_terms = Theta.shape[1]
    xi = np.linalg.lstsq(
        Theta.T @ Theta + alpha_ridge * np.eye(n_terms),
        Theta.T @ dXdt, rcond=None
    )[0]
    for _ in range(max_iter):
        small = np.abs(xi) < threshold
        xi[small] = 0.0
        big_idx = np.where(~small)[0]
        if len(big_idx) == 0:
            break
        Theta_big = Theta[:, big_idx]
        xi_big = np.linalg.lstsq(
            Theta_big.T @ Theta_big + alpha_ridge * np.eye(len(big_idx)),
            Theta_big.T @ dXdt, rcond=None
        )[0]
        xi[big_idx] = xi_big
    return xi


def extract_sindy(trajectory, particle_indices, dt, label,
                   poly_degree=2, threshold_frac=0.05):
    T = trajectory.shape[0]
    all_X, all_dXdt = [], []

    for pid in particle_indices:
        pos = trajectory[:, pid, 1:4]
        mom = trajectory[:, pid, 4:7]
        m0  = trajectory[:, pid, 7]
        gamma = trajectory[:, pid, 9]
        gamma_safe = np.maximum(gamma, 1.0)
        m0_safe = np.maximum(m0, 1e-8)
        vel = mom / (gamma_safe[:, None] * m0_safe[:, None])
        state = np.hstack([pos, vel])
        acc = np.zeros_like(vel)
        acc[1:-1] = (vel[2:] - vel[:-2]) / (2 * dt)
        all_X.append(state[1:-1])
        all_dXdt.append(acc[1:-1])

    X = np.vstack(all_X)
    dXdt = np.vstack(all_dXdt)
    valid = np.isfinite(X).all(axis=1) & np.isfinite(dXdt).all(axis=1)
    X, dXdt = X[valid], dXdt[valid]

    Theta, feature_names = build_polynomial_library(X, degree=poly_degree)
    n_terms = len(feature_names)
    print(f"\n  [{label}] Samples: {X.shape[0]} | Library: {n_terms} terms")

    results = {'label': label, 'feature_names': feature_names, 'coeffs': {}, 'r2': {}}

    for ax_idx, ax_name in enumerate(['x', 'y', 'z']):
        target = dXdt[:, ax_idx]
        xi_init = np.linalg.lstsq(Theta, target, rcond=None)[0]
        threshold = threshold_frac * np.max(np.abs(xi_init))
        threshold = max(threshold, 1e-6)
        xi = stlsq(Theta, target, threshold=threshold)
        predicted = Theta @ xi
        ss_res = np.sum((target - predicted) ** 2)
        ss_tot = np.sum((target - target.mean()) ** 2)
        r2 = 1.0 - ss_res / max(ss_tot, 1e-12)
        results['coeffs'][ax_name] = xi
        results['r2'][ax_name] = r2

        active = np.where(np.abs(xi) > 1e-8)[0]
        sorted_active = sorted(active, key=lambda i: abs(xi[i]), reverse=True)
        print(f"    a_{ax_name} (R2={r2:.4f}): ", end='')
        if not sorted_active:
            print("(none)")
        else:
            terms = [f"{xi[i]:+.4f}*{feature_names[i]}" for i in sorted_active[:6]]
            print(' '.join(terms))

    return results


def place_probes(seed=42):
    """Create initial state tensor with reproducible probe placement."""
    np.random.seed(seed)
    state = torch.zeros(N_TOTAL, 10, dtype=torch.float32)
    state[0, 7] = M0_SINK
    state[0, 9] = 1.0

    for i in range(N_OUTER):
        pid = 1 + i
        theta_ang = np.arccos(1.0 - 2.0 * (i + 0.5) / N_OUTER)
        phi_ang = np.pi * (1 + 5**0.5) * i
        r = 6.0 + 4.0 * (i / max(N_OUTER - 1, 1))
        state[pid, 1] = r * np.sin(theta_ang) * np.cos(phi_ang)
        state[pid, 2] = r * np.sin(theta_ang) * np.sin(phi_ang)
        state[pid, 3] = r * np.cos(theta_ang)
        state[pid, 7] = 1.0
        state[pid, 9] = 1.0
        state[pid, 4] = np.random.uniform(-2.0, 2.0)
        state[pid, 5] = np.random.uniform(-2.0, 2.0)
        state[pid, 6] = np.random.uniform(-2.0, 2.0)

    for i in range(N_INNER):
        pid = 1 + N_OUTER + i
        theta_ang = np.arccos(1.0 - 2.0 * (i + 0.5) / N_INNER)
        phi_ang = np.pi * (1 + 5**0.5) * i
        r = 1.0 + 2.0 * (i / max(N_INNER - 1, 1))
        state[pid, 1] = r * np.sin(theta_ang) * np.cos(phi_ang)
        state[pid, 2] = r * np.sin(theta_ang) * np.sin(phi_ang)
        state[pid, 3] = r * np.cos(theta_ang)
        state[pid, 7] = 1.0
        state[pid, 9] = 1.0
        state[pid, 4] = np.random.uniform(-1.0, 1.0)
        state[pid, 5] = np.random.uniform(-1.0, 1.0)
        state[pid, 6] = np.random.uniform(-1.0, 1.0)

    return state


def make_config(pauli_on=True, pilot_on=True):
    """Create engine config with optional force toggles."""
    config = SimulationConfig()
    config.total_ticks = 3000
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

    config.pauli_enabled = pauli_on
    config.pauli_strength = 10.0
    config.pilot_wave = pilot_on
    config.pilot_wave_coupling = 50.0
    config.torsion_coupling = 1.0
    config.vacuum_enabled = True
    config.vacuum_damping = 0.001
    config.impedance_coupling_coeff = IMP_COEFF
    return config


def identify_cross_coupling_terms(results, feature_names):
    """Return the L2 norm of only the position*velocity cross-coupling terms."""
    # These are the "Christoffel-like" terms: x*vx, x*vy, x*vz, y*vx, etc.
    cross_terms = []
    pos_names = {'x', 'y', 'z'}
    vel_names = {'vx', 'vy', 'vz'}

    for idx, name in enumerate(feature_names):
        if '*' in name:
            parts = name.split('*')
            if len(parts) == 2:
                a, b = parts
                # One position, one velocity
                if (a in pos_names and b in vel_names) or (a in vel_names and b in pos_names):
                    cross_terms.append(idx)

    norms = {}
    for ax_name in ['x', 'y', 'z']:
        xi = results['coeffs'][ax_name]
        cross_vals = [xi[i] for i in cross_terms if abs(xi[i]) > 1e-8]
        norms[ax_name] = np.sqrt(sum(v**2 for v in cross_vals))
        active_names = [feature_names[i] for i in cross_terms if abs(xi[i]) > 1e-8]
        if active_names:
            print(f"    a_{ax_name} cross-coupling: {', '.join(active_names)}")
        else:
            print(f"    a_{ax_name} cross-coupling: (none)")

    total = np.sqrt(sum(v**2 for v in norms.values()))
    return total, norms


SKIP_TICKS = 1000
outer_indices = list(range(1, 1 + N_OUTER))
inner_indices = list(range(1 + N_OUTER, N_TOTAL))
adjacency = torch.zeros(N_TOTAL, N_TOTAL, dtype=torch.bool)


# =========================================================================
# TEST 1: DEGREE-3 ROBUSTNESS CHECK
# =========================================================================
print("=" * 74)
print("  TEST 1: DEGREE-3 ROBUSTNESS CHECK")
print("  If cross-coupling persists in a richer library, it is NOT")
print("  an artifact of underfitting.")
print("=" * 74)

config_d3 = make_config(pauli_on=True, pilot_on=True)
state_d3 = place_probes(seed=42)

print("\n  Running simulation (degree-3 test)...")
engine_d3 = TEGR2600Engine(config_d3)
traj_d3 = engine_d3.run(state_d3, adjacency)
traj_d3_stable = traj_d3[SKIP_TICKS:]

print("\n  --- Degree 2 (baseline, v2 replication) ---")
outer_d2 = extract_sindy(traj_d3_stable, outer_indices, config_d3.dt,
                          "OUTER deg2", poly_degree=2)
inner_d2 = extract_sindy(traj_d3_stable, inner_indices, config_d3.dt,
                          "INNER deg2", poly_degree=2)

print("\n  --- Degree 3 (robustness check) ---")
outer_d3 = extract_sindy(traj_d3_stable, outer_indices, config_d3.dt,
                          "OUTER deg3", poly_degree=3)
inner_d3 = extract_sindy(traj_d3_stable, inner_indices, config_d3.dt,
                          "INNER deg3", poly_degree=3)

print("\n  Cross-coupling analysis (degree 2):")
print("  Outer:")
cc_outer_d2, _ = identify_cross_coupling_terms(outer_d2, outer_d2['feature_names'])
print("  Inner:")
cc_inner_d2, _ = identify_cross_coupling_terms(inner_d2, inner_d2['feature_names'])
print(f"  Cross-coupling L2: outer={cc_outer_d2:.4f}, inner={cc_inner_d2:.4f}")

print("\n  Cross-coupling analysis (degree 3):")
print("  Outer:")
cc_outer_d3, _ = identify_cross_coupling_terms(outer_d3, outer_d3['feature_names'])
print("  Inner:")
cc_inner_d3, _ = identify_cross_coupling_terms(inner_d3, inner_d3['feature_names'])
print(f"  Cross-coupling L2: outer={cc_outer_d3:.4f}, inner={cc_inner_d3:.4f}")

d3_verdict = "PERSISTS" if cc_inner_d3 > 0.05 else "VANISHES"
print(f"\n  >>> DEGREE-3 VERDICT: Cross-coupling {d3_verdict} <<<")


# =========================================================================
# TEST 2: CONFOUND ISOLATION (Pauli OFF, Pilot Wave OFF)
# =========================================================================
print("\n" + "=" * 74)
print("  TEST 2: CONFOUND ISOLATION")
print("  Pauli exclusion OFF, Pilot wave OFF.")
print("  Only impedance coupling + torsion + damping remain.")
print("  If cross-coupling survives, it comes from the c^2 gradient")
print("  (pure emergent curvature), NOT inter-particle forces.")
print("=" * 74)

config_iso = make_config(pauli_on=False, pilot_on=False)
state_iso = place_probes(seed=42)

print("\n  Running isolation simulation...")
engine_iso = TEGR2600Engine(config_iso)
traj_iso = engine_iso.run(state_iso, adjacency)
traj_iso_stable = traj_iso[SKIP_TICKS:]

# Field check
c_sq_iso = engine_iso._c_sq_grid.cpu().numpy().squeeze()
G = config_iso.grid_resolution
center = G // 2
c_origin_iso = np.sqrt(max(c_sq_iso[center, center, center], 0))
print(f"\n  Field at origin: c = {c_origin_iso:.2f} (with Pauli/Pilot OFF)")

outer_iso = extract_sindy(traj_iso_stable, outer_indices, config_iso.dt,
                           "OUTER isolated", poly_degree=2)
inner_iso = extract_sindy(traj_iso_stable, inner_indices, config_iso.dt,
                           "INNER isolated", poly_degree=2)

print("\n  Cross-coupling analysis (isolated):")
print("  Outer:")
cc_outer_iso, _ = identify_cross_coupling_terms(outer_iso, outer_iso['feature_names'])
print("  Inner:")
cc_inner_iso, _ = identify_cross_coupling_terms(inner_iso, inner_iso['feature_names'])
print(f"  Cross-coupling L2: outer={cc_outer_iso:.4f}, inner={cc_inner_iso:.4f}")

iso_verdict = "SURVIVES (PURE CURVATURE)" if cc_inner_iso > 0.03 else "VANISHES (was Pauli/Pilot artifact)"
print(f"\n  >>> ISOLATION VERDICT: Cross-coupling {iso_verdict} <<<")


# =========================================================================
# SUMMARY TABLE
# =========================================================================
print("\n" + "=" * 74)
print("  SUMMARY: CHRISTOFFEL SYMBOL VALIDATION")
print("=" * 74)
print(f"  {'Test':<30s}  {'Outer CC':>10s}  {'Inner CC':>10s}  {'Verdict':>20s}")
print(f"  {'-'*74}")
print(f"  {'Degree-2 (v2 baseline)':<30s}  {cc_outer_d2:>10.4f}  {cc_inner_d2:>10.4f}  {'present':>20s}")
print(f"  {'Degree-3 (robustness)':<30s}  {cc_outer_d3:>10.4f}  {cc_inner_d3:>10.4f}  {d3_verdict:>20s}")
print(f"  {'Isolated (no Pauli/Pilot)':<30s}  {cc_outer_iso:>10.4f}  {cc_inner_iso:>10.4f}  {iso_verdict:>20s}")
print("=" * 74)


# =========================================================================
# VISUALIZATION
# =========================================================================
fig, axes = plt.subplots(1, 3, figsize=(21, 7))
fig.suptitle('Phase 5 v3: Christoffel Symbol Validation\n'
             'Cross-coupling L2 norm across tests',
             fontsize=15, fontweight='bold')

tests = ['Degree-2\n(baseline)', 'Degree-3\n(robustness)', 'Isolated\n(no Pauli/Pilot)']
outer_cc = [cc_outer_d2, cc_outer_d3, cc_outer_iso]
inner_cc = [cc_inner_d2, cc_inner_d3, cc_inner_iso]

for idx, (ax, test_name) in enumerate(zip(axes, tests)):
    x_pos = np.arange(2)
    vals = [outer_cc[idx], inner_cc[idx]]
    colors = ['#2196F3', '#F44336']
    bars = ax.bar(x_pos, vals, color=colors, alpha=0.85, width=0.5)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(['Outer\n(r=6-10)', 'Inner\n(r=1-3)'])
    ax.set_ylabel('Cross-Coupling L2 Norm')
    ax.set_title(test_name, fontsize=13)
    ax.grid(True, alpha=0.3, axis='y')
    # Add value labels on bars
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
                f'{val:.3f}', ha='center', fontsize=11, fontweight='bold')

plt.tight_layout()
plot_path = f'{OUT_DIR}\\phase5_christoffel_validation.png'
plt.savefig(plot_path, dpi=150, bbox_inches='tight')
print(f"\n  Plot saved: {plot_path}")
plt.close()

print("\n  PHASE 5 v3 COMPLETE")
