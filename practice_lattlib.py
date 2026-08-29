import numpy as np
import tqdm
import sys
from pathlib import Path

# Add lattlib to path
import os
sys.path.append(os.path.abspath(r"C:\Users\Myna Bird\.gemini\antigravity\brain\3269c25f-d3d1-4abe-b2a7-46f098d00d85\scratch\lattlib"))

from schwinger.schwinger import ensemble_plaqs
from schwinger.schwinger_heatbath import SchwingerHBAction

def main():
    lattice_path = Path("output/thermalized_lattice.npy")
    
    if not lattice_path.exists():
        print(f"Error: {lattice_path} not found.")
        print("Please run a simulation in the TEGR 2600 GUI and click 'Export to Lattlib (.npy)'.")
        return

    # 1. Load the TEGR 2600 Thermalized Lattice
    # This is a 2D matrix of U(1) complex gauge links
    tegr_links = np.load(lattice_path)
    Lx, Lt = tegr_links.shape
    
    # 2. Map to Lattlib's 1+1D Schwinger Format
    # Schwinger requires a field dimension for each gauge direction (Nd, Lx, Lt).
    # Since Nd=2 for 2D, we seed both the spatial and temporal links with our thermalized field.
    cfg = np.zeros((2, Lx, Lt), dtype=complex)
    cfg[0, :, :] = tegr_links
    cfg[1, :, :] = tegr_links

    print(f"Loaded TEGR 2600 lattice of shape {tegr_links.shape}")
    print(f"Mapped to Schwinger gauge field of shape {cfg.shape}")

    # 3. Initialize Lattlib MCMC Heatbath
    beta = 1.0  # Coupling constant
    action = SchwingerHBAction(beta)

    # 4. Run MCMC Updates
    n_sweeps = 50
    plaqs = []
    
    print(f"\nRunning {n_sweeps} Heatbath sweeps starting from TEGR seed...")
    for i in tqdm.tqdm(range(n_sweeps)):
        action.heatbath_update(cfg)
        
        # Calculate Plaquette (Wilson Loop) energy
        current_plaq = np.mean(ensemble_plaqs(cfg))
        plaqs.append(current_plaq)
        
    print("\n--- Final Results ---")
    print(f"Initial Plaquette: {np.real(plaqs[0]):.4f}")
    print(f"Final Plaquette:   {np.real(plaqs[-1]):.4f}")
    print("Success! The Lattlib MCMC engine successfully accepted and stepped the TEGR lattice.")

if __name__ == "__main__":
    main()
