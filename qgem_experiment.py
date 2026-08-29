import os
import torch
import numpy as np
import matplotlib.pyplot as plt
from engine import TEGR2600Engine
from config_schema import SimulationConfig

# Ensure reproducibility and strict floating-point identity
torch.manual_seed(42)
np.random.seed(42)

def run_qgem_configuration(theta1_init, theta2_init, name, ticks=1000):
    # Base Configuration
    config = SimulationConfig(
        grid_resolution=64,
        total_ticks=ticks,
        dt=0.01,
        wave_speed=1.0,
        c_p=1.0,                # MUST MATCH wave_speed TO PREVENT FDTD INSTABILITY
        vacuum_enabled=False,
        vacuum_damping=0.0,
        pauli_enabled=True,
        pauli_strength=5.0,     # Strong coupling to simulate the "magnetic" Stern-Gerlach split via topology
        pauli_power=2.0,
        rae_mode=True,
        rae_kappa_scale=1.0,
        rae_grad_scale=1.0,
        pilot_wave=True,
        pilot_wave_coupling=1.0,
        torsion_coupling=1.0,
        kuramoto_enabled=False, # We want to prove entanglement emerges WITHOUT explicit Kuramoto sync
        nested_enabled=False,   # Flat space to isolate the particle-particle interaction
        emergent_horizons=False
    )
    
    engine = TEGR2600Engine(config)
    
    # Adjacency matrix (0s because we have no explicit Kuramoto sync)
    adjacency = torch.zeros(2, 2, dtype=torch.bool)
    
    # 10 parameters: [t, x, y, z, px, py, pz, m0, theta, gamma]
    # STRICT KINEMATIC IDENTITY: Same precise floats for all runs
    state = torch.zeros(2, 10, dtype=torch.float32)
    
    # Particle 1 (Left Nanodiamond)
    state[0, 1:4] = torch.tensor([-2.0, 0.0, 0.0]) # x, y, z
    state[0, 7] = 1.0                              # mass
    state[0, 8] = theta1_init                      # initial phase clock
    state[0, 9] = 1.0                              # gamma
    
    # Particle 2 (Right Nanodiamond)
    state[1, 1:4] = torch.tensor([2.0, 0.0, 0.0])
    state[1, 7] = 1.0
    state[1, 8] = theta2_init
    state[1, 9] = 1.0
    
    print(f"\n--- Running QGEM Config: {name} ---")
    print(f"Initial State | P1 theta: {theta1_init:.3f}, P2 theta: {theta2_init:.3f}")
    
    trajectory = engine.run(state, adjacency)
    
    # Calculate accumulated phase: sum of (theta_final - theta_initial)
    final_state = trajectory[-1]
    theta1_final = final_state[0, 8]
    theta2_final = final_state[1, 8]
    
    phi1_accum = theta1_final - theta1_init
    phi2_accum = theta2_final - theta2_init
    phi_sys = phi1_accum + phi2_accum
    
    # Also extract terminal positions to prove trajectory divergence (Stern-Gerlach equivalent)
    pos1_final = final_state[0, 1:4]
    pos2_final = final_state[1, 1:4]
    
    return {
        'name': name,
        'phi_sys': phi_sys,
        'theta1_final': theta1_final,
        'theta2_final': theta2_final,
        'pos1_final': pos1_final,
        'pos2_final': pos2_final,
        'traj': trajectory
    }

if __name__ == "__main__":
    print("======================================================")
    print(" TEGR 2600 : CLASSICAL QGEM ENTANGLEMENT SIMULATION ")
    print("======================================================")
    
    TICKS = 500
    
    # UP = 0, DOWN = pi
    UP = 0.0
    DOWN = np.pi
    
    # Run the 4 branch configurations with IDENTICAL initial kinematics
    res_UU = run_qgem_configuration(UP, UP, "UU", ticks=TICKS)
    res_UD = run_qgem_configuration(UP, DOWN, "UD", ticks=TICKS)
    res_DU = run_qgem_configuration(DOWN, UP, "DU", ticks=TICKS)
    res_DD = run_qgem_configuration(DOWN, DOWN, "DD", ticks=TICKS)
    
    # ---------------------------------------------------------
    # 1. Evaluate Trajectory Divergence (Stern-Gerlach Analog)
    # ---------------------------------------------------------
    # Distance between the two particles at the end of the simulation
    dist_UU = np.linalg.norm(res_UU['pos1_final'] - res_UU['pos2_final'])
    dist_UD = np.linalg.norm(res_UD['pos1_final'] - res_UD['pos2_final'])
    dist_DU = np.linalg.norm(res_DU['pos1_final'] - res_DU['pos2_final'])
    dist_DD = np.linalg.norm(res_DD['pos1_final'] - res_DD['pos2_final'])
    
    print("\n======================================================")
    print(" 1. GEOMETRIC DIVERGENCE (STERN-GERLACH ANALOG)")
    print("======================================================")
    print(f"Terminal Distance (UU): {dist_UU:.6f}")
    print(f"Terminal Distance (DD): {dist_DD:.6f}")
    print(f"Terminal Distance (UD): {dist_UD:.6f}")
    print(f"Terminal Distance (DU): {dist_DU:.6f}")
    
    # ---------------------------------------------------------
    # 2. Evaluate QGEM Entangling Phase 
    # ---------------------------------------------------------
    phi_UU = res_UU['phi_sys']
    phi_UD = res_UD['phi_sys']
    phi_DU = res_DU['phi_sys']
    phi_DD = res_DD['phi_sys']
    
    delta_phi_tegr = phi_UD + phi_DU - phi_UU - phi_DD
    
    print("\n======================================================")
    print(" 2. PHASE ACCUMULATION & ENTANGLEMENT METRIC")
    print("======================================================")
    print(f"System Phase UU: {phi_UU:.6f} rad")
    print(f"System Phase DD: {phi_DD:.6f} rad")
    print(f"System Phase UD: {phi_UD:.6f} rad")
    print(f"System Phase DU: {phi_DU:.6f} rad")
    print("-" * 54)
    print(f"dPhi_TEGR = Phi_UD + Phi_DU - Phi_UU - Phi_DD = {delta_phi_tegr:.8f} rad")
    
    if abs(delta_phi_tegr) > 1e-5:
        print("\n>>> RESULT: NON-ZERO dPhi. CLASSICAL ENTANGLEMENT GENERATED. <<<")
    else:
        print("\n>>> RESULT: ZERO dPhi. NO ENTANGLEMENT. <<<")
        
    # ---------------------------------------------------------
    # 3. Plotting
    # ---------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot 1: Trajectory Divergence (x vs t)
    t_vals = np.arange(TICKS) * 0.01
    
    axes[0].plot(t_vals, res_UU['traj'][:, 0, 1], 'b-', label='P1 (UU)')
    axes[0].plot(t_vals, res_UU['traj'][:, 1, 1], 'b--', label='P2 (UU)')
    
    axes[0].plot(t_vals, res_UD['traj'][:, 0, 1], 'r-', label='P1 (UD)')
    axes[0].plot(t_vals, res_UD['traj'][:, 1, 1], 'r--', label='P2 (UD)')
    
    axes[0].set_title('Trajectory Divergence (Stern-Gerlach Analog)')
    axes[0].set_xlabel('Time (s)')
    axes[0].set_ylabel('X Position')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    
    # Plot 2: RAE Phase Evolution (theta vs t)
    axes[1].plot(t_vals, res_UU['traj'][:, 0, 8], 'b-', label='P1 θ (UU)')
    axes[1].plot(t_vals, res_UU['traj'][:, 1, 8], 'b--', label='P2 θ (UU)')
    
    axes[1].plot(t_vals, res_UD['traj'][:, 0, 8], 'r-', label='P1 θ (UD)')
    axes[1].plot(t_vals, res_UD['traj'][:, 1, 8], 'r--', label='P2 θ (UD)')
    
    axes[1].set_title('Relativistic Adler Equation (RAE) Phase Clock')
    axes[1].set_xlabel('Time (s)')
    axes[1].set_ylabel('Phase θ (rad)')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('qgem_divergence.png', dpi=300)
    print("\nSaved plot to 'qgem_divergence.png'")
