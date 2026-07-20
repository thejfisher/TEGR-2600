import os
import toml

def export_bose_hubbard_to_tegr(particles, sites, U, J, filename, spacing=32.0):
    """
    Utility for quantum physicists to export standard Bose-Hubbard parameters
    (from QuTiP or NetKet workflows) into a TEGR 2600 TOML preset.
    """
    
    # Calculate lattice positions
    # For a 1D chain centered on the grid
    pos_x = []
    start_x = 32.0 - (sites - 1) * (spacing / 2.0)
    for i in range(sites):
        pos_x.append(start_x + i * spacing)
        
    preset = {
        "metadata": {
            "name": f"Bose-Hubbard {particles} Particles",
            "description": f"Generated from standard Q-Physics export. U={U}, J={J}"
        },
        "system": {
            "particles": particles,
            "mass": 1.0,         # Dimensionless mass for proper relativistic detuning
            "charge": 1.0,
            "wave_speed": 65.0,  # FDTD stable wave speed
            "wave_decay": 0.9999,
            "grid_size": 64
        },
        "physics": {
            "pauli_repulsion": U,     # U parameter
            "torsion_coupling": J,    # J parameter
            "pilot_wave": True,
            "rae_clock": True,
            "kuramoto_sync": True,
            "kuramoto_K": 0.005,      # Calibrated for phase detuning
            "vacuum_damping": 0.007
        },
        "initial_state": {
            # Start particles in a perfect 1D lattice arrangement
            "pos_x": pos_x[:particles],
            "pos_y": [32.0] * particles,
            "pos_z": [32.0] * particles,
            "vel_x": [0.0] * particles,
            "vel_y": [0.0] * particles,
            "vel_z": [0.0] * particles,
            "phase": [0.0] * particles
        }
    }
    
    out_path = os.path.join(os.path.dirname(__file__), "presets", filename)
    with open(out_path, 'w') as f:
        toml.dump(preset, f)
        
    print(f"Exported {particles}-particle Hamiltonian to {out_path}")

if __name__ == "__main__":
    # Example usage mimicking a physicist's workflow
    print("Simulating QuTiP / NetKet Hamiltonian export...")
    export_bose_hubbard_to_tegr(particles=16, sites=16, U=10.0, J=1.0, filename="bh_16_site_export.toml")
