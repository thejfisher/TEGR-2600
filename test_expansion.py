import sys
import torch
from engine import TEGR2600Engine
from config_schema import SimulationConfig
from data_ingest import load_experiment

def run_test(emergent_horizons=False, emergent_source_strength=1.0):
    print(f"\n--- Testing with emergent_horizons={emergent_horizons}, source_strength={emergent_source_strength} ---")
    filepath = '../Manuscripts/26_High_Z_and_Hubble_Flow/ms26_cartesian_diver.toml'
    cfg = SimulationConfig.from_toml(filepath)
    cfg.save_trajectories = False
    cfg.total_ticks = 200  # Run for 200 ticks to see expansion clearly
    
    # Overrides
    cfg.emergent_horizons = emergent_horizons
    cfg.emergent_source_strength = emergent_source_strength
    
    state, adj, _ = load_experiment(filepath)
    engine = TEGR2600Engine(cfg)
    
    try:
        trajectory = engine.run(state, adj)
    except Exception as e:
        print(f"Error during run: {e}")
        return
        
    r_initial = torch.norm(torch.tensor(trajectory[0, :, 1:4]), dim=1).mean().item()
    print(f'Initial Mean Radius: {r_initial:.3f}')
    
    r_final = torch.norm(torch.tensor(trajectory[-1, :, 1:4]), dim=1).mean().item()
    print(f'Final Mean Radius: {r_final:.3f}')

if __name__ == '__main__':
    run_test(emergent_horizons=False, emergent_source_strength=1.0)
    run_test(emergent_horizons=True, emergent_source_strength=1.0)
    run_test(emergent_horizons=False, emergent_source_strength=0.0)
    run_test(emergent_horizons=True, emergent_source_strength=0.0)
