"""
Phase 3 Validation: Emergent Horizon from Single Massive Sink

Places a massive particle at origin. Enables emergent_horizons=True.
Runs 1000 ticks and measures the radial profile of c² and λ in the
FDTD grid to verify that an event horizon self-organizes from the
Klein-Gordon field density — no sigmoid, no hardcoded geometry.

Success criteria:
  - c² drops significantly near origin (mass warps local wave speed)
  - A clear radial gradient in c² forms concentrically around the mass
  - λ (damping) increases near origin (tighter vacuum = higher impedance)
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

# =========================================
# Configure: Single sink, emergent horizons
# =========================================
config = SimulationConfig()
config.total_ticks = 1000
config.dt = 0.001
config.grid_resolution = 64
config.wave_speed = 65.0

# Enable emergent horizons
config.emergent_horizons = True
config.emergent_alpha = 0.1       # coupling strength
config.emergent_c_base = 65.0     # ambient c
config.emergent_decay_base = 0.999
config.emergent_decay_gamma = 0.5

# Disable static sigmoid
config.nested_enabled = False

# Physics
config.pauli_enabled = True
config.pauli_strength = 10.0
config.pilot_wave = True
config.torsion_coupling = 1.0
config.vacuum_enabled = True
config.vacuum_damping = 0.001

# =========================================
# Create particles: 1 massive sink + 20 light probes
# =========================================
N = 21
state = torch.zeros(N, 10, dtype=torch.float32)

# Particle 0: massive sink at origin (m0 = 10000)
state[0, 0] = 0  # id
state[0, 1:4] = torch.tensor([0.0, 0.0, 0.0])  # position at origin
state[0, 4:7] = torch.tensor([0.0, 0.0, 0.0])  # zero momentum
state[0, 7] = 10000.0  # MASSIVE rest mass
state[0, 8] = 0.0      # phase
state[0, 9] = 1.0      # gamma

# Particles 1-20: lightweight probes at various radii
np.random.seed(42)
for i in range(1, N):
    r = 3.0 + np.random.uniform(0, 15)  # radius 3-18
    theta = np.random.uniform(0, 2*np.pi)
    phi_angle = np.random.uniform(0, np.pi)
    x = r * np.sin(phi_angle) * np.cos(theta)
    y = r * np.sin(phi_angle) * np.sin(theta)
    z = r * np.cos(phi_angle)
    state[i, 0] = i
    state[i, 1:4] = torch.tensor([x, y, z])
    state[i, 4:7] = torch.tensor([0.0, 0.0, 0.0])
    state[i, 7] = 1.0   # light probe mass
    state[i, 8] = np.random.uniform(0, 2*np.pi)
    state[i, 9] = 1.0

# Adjacency (no entanglement for this test)
adjacency = torch.zeros(N, N, dtype=torch.bool)

# =========================================
# Run simulation
# =========================================
print("=" * 60)
print("  PHASE 3 VALIDATION: Emergent Horizon Test")
print("  Single sink (m0=10000) at origin")
print("  Emergent horizons ON — no sigmoid, no hardcoded geometry")
print("=" * 60)

engine = TEGR2600Engine(config)
trajectory = engine.run(state, adjacency)

# =========================================
# Extract radial profile of c² and lambda from final grid
# =========================================
c_sq_grid = engine._c_sq_grid.cpu().numpy().squeeze()  # (G, G, G)
decay_grid = engine._decay_grid.cpu().numpy().squeeze()
phi_grid = engine._phi_curr.cpu().numpy().squeeze()

G = config.grid_resolution
coords = np.linspace(engine.GRID_MIN, engine.GRID_MAX, G)
x3d, y3d, z3d = np.meshgrid(coords, coords, coords, indexing='ij')
r3d = np.sqrt(x3d**2 + y3d**2 + z3d**2)

center = G // 2

# Compute radial average (azimuthal average in spherical bins)
r_flat = r3d.flatten()
c_sq_flat = c_sq_grid.flatten()
decay_flat = decay_grid.flatten()
phi_flat = np.abs(phi_grid.flatten())

n_bins = 30
r_edges = np.linspace(0, r3d.max() * 0.8, n_bins + 1)
r_centers = 0.5 * (r_edges[:-1] + r_edges[1:])
c_sq_avg = np.zeros(n_bins)
decay_avg = np.zeros(n_bins)
phi_avg = np.zeros(n_bins)

for i in range(n_bins):
    mask = (r_flat >= r_edges[i]) & (r_flat < r_edges[i+1])
    if mask.any():
        c_sq_avg[i] = np.mean(c_sq_flat[mask])
        decay_avg[i] = np.mean(decay_flat[mask])
        phi_avg[i] = np.mean(phi_flat[mask])

c_base_sq = config.emergent_c_base ** 2

# =========================================
# Print diagnostics
# =========================================
print("\n" + "=" * 60)
print("  RADIAL PROFILE DIAGNOSTICS")
print("=" * 60)
print(f"  c_sq at origin:     {c_sq_grid[center, center, center]:.2f}  (base: {c_base_sq:.2f})")
print(f"  c_sq at r=max/2:    {c_sq_avg[n_bins//2]:.2f}")
print(f"  c_sq at edge:       {c_sq_avg[-1]:.2f}")
print(f"  c at origin:        {np.sqrt(max(c_sq_grid[center, center, center], 0)):.2f}  (base: {config.emergent_c_base:.2f})")
print(f"  lambda at origin:   {decay_grid[center, center, center]:.6f}  (base: {config.emergent_decay_base:.6f})")
print(f"  lambda at edge:     {decay_avg[-1]:.6f}")
print(f"  |phi| at origin:    {abs(phi_grid[center, center, center]):.6f}")
print(f"  |phi| at edge:      {phi_avg[-1]:.6f}")

# Check: did the horizon form?
c_ratio = c_sq_grid[center, center, center] / c_base_sq
if c_ratio < 0.5:
    print(f"\n  HORIZON DETECTED: c_sq dropped to {c_ratio*100:.1f}% of base at origin")
elif c_ratio < 0.9:
    print(f"\n  PARTIAL WELL: c_sq at {c_ratio*100:.1f}% of base (need stronger alpha or more mass)")
else:
    print(f"\n  NO HORIZON: c_sq at {c_ratio*100:.1f}% of base (field too weak, try alpha={config.emergent_alpha * 5})")

# =========================================
# Plot 4-panel analysis
# =========================================
fig, axes = plt.subplots(2, 2, figsize=(14, 12))
fig.suptitle('Phase 3: Emergent Horizon - Single Sink Validation', fontsize=16, fontweight='bold')

# Panel 1: c(r) radial profile (azimuthal average)
ax1 = axes[0, 0]
ax1.plot(r_centers, np.sqrt(np.maximum(c_sq_avg, 0)), 'b-', linewidth=2, label='c(r) avg')
ax1.axhline(y=config.emergent_c_base, color='gray', linestyle='--', alpha=0.5, label=f'c_base = {config.emergent_c_base}')
ax1.set_xlabel('Radial Distance (r)', fontsize=12)
ax1.set_ylabel('Wave Speed c(r)', fontsize=12)
ax1.set_title('Emergent Wave Speed Profile', fontsize=13)
ax1.legend(fontsize=10)
ax1.grid(True, alpha=0.3)

# Panel 2: lambda(r) radial profile
ax2 = axes[0, 1]
ax2.plot(r_centers, decay_avg, 'r-', linewidth=2, label='lambda(r) avg')
ax2.axhline(y=config.emergent_decay_base, color='gray', linestyle='--', alpha=0.5, label=f'lambda_base = {config.emergent_decay_base}')
ax2.set_xlabel('Radial Distance (r)', fontsize=12)
ax2.set_ylabel('Damping lambda(r)', fontsize=12)
ax2.set_title('Emergent Damping Profile', fontsize=13)
ax2.legend(fontsize=10)
ax2.grid(True, alpha=0.3)

# Panel 3: |phi|(r) - field density profile
ax3 = axes[1, 0]
ax3.plot(r_centers, phi_avg, 'g-', linewidth=2, label='|phi(r)| avg')
ax3.set_xlabel('Radial Distance (r)', fontsize=12)
ax3.set_ylabel('Field Density |phi|', fontsize=12)
ax3.set_title('Klein-Gordon Field Density', fontsize=13)
ax3.legend(fontsize=10)
ax3.grid(True, alpha=0.3)

# Panel 4: 2D slice through center showing c
ax4 = axes[1, 1]
c_sq_2d = c_sq_grid[:, :, center]
extent = [engine.GRID_MIN, engine.GRID_MAX, engine.GRID_MIN, engine.GRID_MAX]
im = ax4.imshow(np.sqrt(np.maximum(c_sq_2d.T, 0)), extent=extent, origin='lower', cmap='inferno', aspect='equal')
ax4.set_xlabel('x', fontsize=12)
ax4.set_ylabel('y', fontsize=12)
ax4.set_title('c(x,y) - Central Slice (z=0)', fontsize=13)
plt.colorbar(im, ax=ax4, label='c (wave speed)')

plt.tight_layout()
out_path = r'C:\Users\Myna Bird\.gemini\antigravity\brain\5c68d86f-771c-459b-a71a-dc279a192415\emergent_horizon_test.png'
plt.savefig(out_path, dpi=150, bbox_inches='tight')
print(f"\n  Plot saved: {out_path}")
plt.close()
