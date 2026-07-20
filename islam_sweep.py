#!/usr/bin/env python3
"""
TEGR 2600  -  Islam et al. 2015 U/J Sweep
Replicates Figure 4: S2(half-chain) vs U/J for 4-site Bose-Hubbard

Runs the ground-state preset at 10 different U/J ratios and plots
the S2 curve for direct comparison against Islam et al. (Nature 528).

Usage:
    python islam_sweep.py
    
Output:
    output/islam_sweep_S2_vs_UJ.png
    output/islam_sweep_results.csv
"""

import sys, os, time
import numpy as np
import torch
import matplotlib
matplotlib.use('Agg')  # headless
import matplotlib.pyplot as plt

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_schema import SimulationConfig
from data_ingest import load_experiment
from engine import TEGR2600Engine
from entanglement_metrics import (
    compute_phase_coherence_matrix,
    compute_subsystem_purity,
    compute_renyi_entropy,
)

# ── Sweep Parameters ─────────────────────────────────────────────
UJ_VALUES = [0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 8.0, 10.0, 15.0, 20.0]
PRESET    = os.path.join(os.path.dirname(__file__), 
                         "presets", "bose_hubbard_islam2015.toml")
TICKS     = 20000
GRID      = 64
# ── Atari 2600 / NASA Punk Aesthetics ──────────────────────────────
DARK_BG   = '#000000'   # Pure black
PANEL_BG  = '#111111'   # Slightly lighter black for panels
ACCENT    = '#00FFFF'   # Cyan
HIGHLIGHT = '#FF00FF'   # Magenta
TEXT      = '#FFA500'   # Neon Orange
# ─────────────────────────────────────────────────────────────────

def run_single(uj_ratio: float) -> dict:
    """Run one simulation at the given U/J ratio with a deterministic micro-perturbation."""
    
    # Load ground-state preset fresh each time
    state, adjacency, meta = load_experiment(PRESET)
    N = int(meta['num_particles'])
    
    # ── Initial Phase Randomization ──────────────────────────────
    # A true quantum Mott insulator has perfect particle number certainty,
    # which by the uncertainty principle means perfect phase uncertainty.
    # We initialize the particles with a random, unsynchronized spread of phases.
    # We use a fixed seed so the starting state is identical across all U/J runs.
    # ──────────────────────────────────────────────────────────────
    rng = np.random.RandomState(1337)
    random_phases = rng.uniform(0, 2 * np.pi, size=N)
    state[:, 8] = torch.tensor(random_phases, dtype=state.dtype)
    
    # Give all particles a uniform tiny momentum so v_hat is well-defined.
    # The RAE phase coupling (term3) requires a non-zero velocity vector to 
    # project the field gradient. If v=0, they cannot "feel" the phase wave.
    state[:, 4] = 0.1
    state[:, 5:7] = 0.0
    
    # Recompute gamma 
    m0 = state[:, 7]
    p_sq = state[:, 4]**2
    C_SIM = 65.0
    state[:, 9] = torch.sqrt(1.0 + p_sq / (m0 * C_SIM)**2)
    
    # Configure
    cfg = SimulationConfig()
    cfg.pauli_strength   = uj_ratio
    cfg.torsion_coupling = 1.0
    cfg.total_ticks      = TICKS
    cfg.grid_resolution  = GRID
    cfg.rae_mode         = True
    cfg.pilot_wave       = True
    cfg.kuramoto_enabled = True        # Discovery mode
    cfg.kuramoto_K       = 0.005
    cfg.vacuum_damping   = 0.007
    cfg.vacuum_enabled   = True
    cfg.wave_speed       = 65.0
    cfg.wave_decay       = 0.9999
    cfg.dt               = 0.001
    cfg.num_particles    = N
    cfg.output_dir       = os.path.join(os.path.dirname(__file__), "output")
    
    # Run engine
    engine = TEGR2600Engine(cfg)
    trajectory = engine.run(state, adjacency)

    traj_np = trajectory.cpu().numpy() if isinstance(trajectory, torch.Tensor) else trajectory
    
    # Compute coherence matrix (with detrending)
    coherence = compute_phase_coherence_matrix(traj_np)
    
    # Half-chain partition: [0,1] | [2,3]
    half_a = [0, 1]
    
    purity_half = compute_subsystem_purity(coherence, half_a)
    s2_half     = compute_renyi_entropy(purity_half)
    
    # Single-site partition: [0] | [1,2,3]
    purity_single = compute_subsystem_purity(coherence, [0])
    s2_single     = compute_renyi_entropy(purity_single)
    
    # Full system
    full_purity = float(np.mean(coherence))
    full_s2     = -np.log(max(full_purity, 1e-10))
    
    return {
        'uj':            uj_ratio,
        's2_half':       s2_half,
        's2_single':     s2_single,
        'purity_half':   purity_half,
        'purity_single': purity_single,
        'full_purity':   full_purity,
        'full_s2':       full_s2,
    }


def main():
    print("=" * 60)
    print("  TEGR 2600  -  Islam et al. 2015 U/J Sweep")
    print("  Replicating Figure 4: S2(half-chain) vs U/J")
    print(f"  Preset: {os.path.basename(PRESET)}")
    print(f"  U/J values: {UJ_VALUES}")
    N_SAMPLES = 3
    print(f"  Ticks per run: {TICKS}")
    print("=" * 60)
    
    results = []
    t0 = time.time()
    
    for i, uj in enumerate(UJ_VALUES):
        print(f"\n[{i+1}/{len(UJ_VALUES)}] U/J = {uj:.1f} ...", end=" ", flush=True)
        t1 = time.time()
        r = run_single(uj)
        dt = time.time() - t1
        print(f"done ({dt:.1f}s)  S2(half)={r['s2_half']:.4f}  purity={r['purity_half']:.4f}")
        results.append(r)
    
    total_time = time.time() - t0
    print(f"\nAll {len(UJ_VALUES)} runs complete in {total_time:.1f}s")
    
    # ── Save CSV ──────────────────────────────────────────────────
    out_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(out_dir, exist_ok=True)
    
    csv_path = os.path.join(out_dir, "islam_sweep_results.csv")
    with open(csv_path, 'w') as f:
        f.write("U/J,S2_half_chain,S2_single_site,purity_half,purity_single,full_purity,full_S2\n")
        for r in results:
            f.write(f"{r['uj']:.1f},{r['s2_half']:.6f},{r['s2_single']:.6f},"
                    f"{r['purity_half']:.6f},{r['purity_single']:.6f},"
                    f"{r['full_purity']:.6f},{r['full_s2']:.6f}\n")
    print(f"Saved: {csv_path}")
    
    # ── Plot: S2 vs U/J ──────────────────────────────────────────
    uj_arr   = [r['uj'] for r in results]
    s2_half  = [r['s2_half'] for r in results]
    s2_single = [r['s2_single'] for r in results]
    
    # Atari 2600 / NASA Punk Theme
    DARK_BG   = '#000000'   # Pure black
    PANEL_BG  = '#111111'   # Deep terminal gray
    TEXT      = '#FFA500'   # Neon orange / amber
    HIGHLIGHT = '#FF00FF'   # Magenta
    CYAN      = '#00FFFF'   # Cyan
    ACCENT    = '#444444'   # Grid lines
    GREEN     = '#00FF00'   # Matrix green
    
    plt.rcParams['font.family'] = 'monospace'
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor(DARK_BG)
    
    for ax in (ax1, ax2):
        ax.set_facecolor(PANEL_BG)
        ax.tick_params(colors=TEXT)
        for spine in ax.spines.values():
            spine.set_color(ACCENT)
    
    # Left: S2 vs U/J
    ax1.plot(uj_arr, s2_half, 'o-', color=HIGHLIGHT, linewidth=2.5, 
             markersize=8, label='S2 (half-chain [0,1]|[2,3])', zorder=5)
    ax1.plot(uj_arr, s2_single, 's--', color=CYAN, linewidth=2, 
             markersize=6, label='S2 (single-site [0]|[1,2,3])', alpha=0.8, zorder=4)
    ax1.axhline(y=np.log(2), color=GREEN, linestyle=':', alpha=0.5, 
                label=f'ln(2) = {np.log(2):.3f}')
    ax1.set_xlabel("U/J", color=TEXT, fontsize=12)
    ax1.set_ylabel("S2 (Rényi Entropy)", color=TEXT, fontsize=12)
    ax1.set_title("Islam et al. 2015  -  Fig. 4 Replication", 
                  color=HIGHLIGHT, fontsize=13, fontweight='bold')
    ax1.legend(facecolor=PANEL_BG, edgecolor=ACCENT, labelcolor=TEXT, fontsize=9)
    ax1.set_xlim(0, max(uj_arr) + 1)
    ax1.set_ylim(-0.05, max(max(s2_half) + 0.1, 0.8))
    
    # Right: Purity vs U/J  
    purity_half  = [r['purity_half'] for r in results]
    purity_single = [r['purity_single'] for r in results]
    
    ax2.plot(uj_arr, purity_half, 'o-', color=HIGHLIGHT, linewidth=2.5, 
             markersize=8, label='Purity (half-chain)', zorder=5)
    ax2.plot(uj_arr, purity_single, 's--', color=CYAN, linewidth=2, 
             markersize=6, label='Purity (single-site)', alpha=0.8, zorder=4)
    ax2.axhline(y=0.5, color=GREEN, linestyle=':', alpha=0.5, label='Thermal limit (0.5)')
    ax2.set_xlabel("U/J", color=TEXT, fontsize=12)
    ax2.set_ylabel("Tr(ρ^2)", color=TEXT, fontsize=12)
    ax2.set_title("Purity vs U/J", color=HIGHLIGHT, fontsize=13, fontweight='bold')
    ax2.legend(facecolor=PANEL_BG, edgecolor=ACCENT, labelcolor=TEXT, fontsize=9)
    ax2.set_xlim(0, max(uj_arr) + 1)
    ax2.set_ylim(-0.05, 1.1)
    
    fig.tight_layout()
    
    plot_path = os.path.join(out_dir, "islam_sweep_S2_vs_UJ.png")
    fig.savefig(plot_path, dpi=150, facecolor=DARK_BG)
    print(f"Saved: {plot_path}")
    
    # ── Summary Table ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  RESULTS SUMMARY")
    print("=" * 60)
    print(f"  {'U/J':>5}  {'S2(half)':>10}  {'S2(single)':>12}  {'Purity(half)':>14}")
    print("-" * 60)
    for r in results:
        print(f"  {r['uj']:5.1f}  {r['s2_half']:10.4f}  {r['s2_single']:12.4f}  {r['purity_half']:14.4f}")
    print("=" * 60)
    print(f"\nIslam prediction: S2 peaks at U/J ~ 1-3, drops to 0 by U/J ~ 10")
    print(f"ln(2) = {np.log(2):.4f}")


if __name__ == '__main__':
    main()
