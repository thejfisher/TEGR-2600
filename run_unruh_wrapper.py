import sys
import numpy as np
import torch
import time
from config_schema import SimulationConfig
from engine import TEGR2600Engine
from data_ingest import load_experiment
from entanglement_metrics import full_entanglement_report
from tegr2600_ui import EntropyCanvas, CoherenceCanvas
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PyQt6.QtWidgets import QApplication

def run_accelerated_unruh_experiment(config_path: str, acceleration: float = 15.0):
    print(f"Loading experiment from: {config_path}")
    print(f"Applying constant acceleration: {acceleration} to Particle 0")
    
    # Load configuration and initial state
    cfg = SimulationConfig.from_toml(config_path)
    initial_state, adjacency, _ = load_experiment(config_path)
    
    # Initialize Engine
    engine = TEGR2600Engine(cfg)
    device = engine.device
    
    # Reset engine to initialize SimulationState internal object
    engine.reset(initial_state, adjacency)
    
    history = []
    
    print("Running simulation (Rindler Trajectory Wrapper)...")
    start_time = time.time()
    
    # Run the loop and hook in the acceleration
    for tick in range(cfg.total_ticks):
        # 1. Step the engine
        engine.step()
        
        # 2. Hook: Apply continuous Rindler acceleration to Particle 0
        # State layout: [t, x, y, z, px, py, pz, m0, theta, gamma]
        # We add a * dt to the momentum (px) of Particle 0
        dp = acceleration * cfg.dt
        engine._state[0, 4] += dp  # Update px
        
        # 3. Save trajectory
        hist_frame = engine._state[:engine.active_count].cpu().numpy().copy()
        history.append(hist_frame)
        
        if (tick + 1) % 5000 == 0:
            print(f"  Progress: {tick + 1}/{cfg.total_ticks} ticks")
            
    elapsed = time.time() - start_time
    print(f"Simulation complete: {cfg.total_ticks} ticks in {elapsed:.2f} seconds")
    
    trajectory = np.stack(history)  # (T, N, 10)
    
    # Generate the entanglement report
    report = full_entanglement_report(trajectory, 2)
    
    print("\n--- Entanglement Report ---")
    print(f"Full system purity: {report['purities']['[0, 1]']:.4f}")
    print(f"Full system S2:     {report['entropies']['[0, 1]']:.4f}")
    print(f"  Subsystem [0]: purity={report['purities']['[0]']:.4f}, S2={report['entropies']['[0]']:.4f}")
    print(f"  Subsystem [1]: purity={report['purities']['[1]']:.4f}, S2={report['entropies']['[1]']:.4f}")
    print(f"  MI([0], [1]) = {report['mutual_info']['([0], [1])']:.4f}")

    # Generate and save plots to mirror UI
    app = QApplication(sys.argv)
    
    entropy_canvas = EntropyCanvas()
    entropy_canvas.plot_entropy_timeseries(trajectory, [0], [1])
    entropy_canvas.fig.savefig(f"entropy_analysis_accel.png", dpi=300, bbox_inches='tight')
    
    coherence_canvas = CoherenceCanvas()
    coherence_canvas.update_plot(report['coherence_matrix'])
    coherence_canvas.fig.savefig(f"coherence_matrix_accel.png", dpi=300, bbox_inches='tight')
    
    print("\nPlots saved as 'entropy_analysis_accel.png' and 'coherence_matrix_accel.png'")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        config_path = "presets/unruh_pauli_regularized.toml"
        
    run_accelerated_unruh_experiment(config_path)
