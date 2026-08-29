import torch
import numpy as np
import sys
from pathlib import Path

def debug_forces():
    if len(sys.argv) > 1:
        cfg_path = sys.argv[1]
    else:
        cfg_path = str(Path(__file__).parent.parent / 'Manuscripts' / '26_High_Z_and_Hubble_Flow' / 'ms26_cartesian_diver.toml')
    from config_schema import SimulationConfig
    from engine import TEGR2600Engine
    cfg = SimulationConfig.from_toml(cfg_path)
    cfg.emergent_horizons = False
    cfg.emergent_source_strength = 1.0
    cfg.emergent_c_base = 30.0
    cfg.c_p = 30.0  # ensure stable c_sq_grid when emergent_horizons=False
    cfg.grid_resolution = 64
    cfg.dt = 0.001  # very small dt to guarantee stability
    engine = TEGR2600Engine(cfg)
    
    # Initialize the engine FDTD grid
    state = torch.zeros((1, 10), dtype=torch.float32, device=engine.device)
    state[0, 1:4] = torch.tensor([0.0, 0.0, 0.0]) # pos
    state[0, 7] = 1.0 # m0
    engine._init_grid(state)

    for tick in range(200):
        pos_src = torch.tensor([[0.0, 0.0, 0.0]], dtype=torch.float32, device=engine.device)
        m0_src = torch.tensor([1.0], dtype=torch.float32, device=engine.device)
        engine._inject_mass_source(pos_src, m0_src)

        if engine.config.emergent_horizons:
            engine._update_emergent_impedance()

        # FDTD update
        laplacian = torch.nn.functional.conv3d(engine._phi_curr, engine._laplacian_kernel, padding=1)
        phi_next = 2 * engine._phi_curr - engine._phi_prev
        
        alpha_grid = engine._c_sq_grid * (engine.config.dt * engine.config.dt / (engine.DX * engine.DX))
        phi_next += laplacian * alpha_grid
        
        # Decay
        phi_next *= engine._decay_grid
        
        engine._phi_prev.copy_(engine._phi_curr)
        engine._phi_curr.copy_(phi_next)
        
        if torch.isnan(engine._phi_curr).any():
            print(f"NaN detected at tick {tick}!")
            break
    
    # Measure force at various X positions
    from utils import trilinear_interpolate_gradient
    print("X_pos | Phi Value  | Pilot Wave Force (X-component)")
    print("-" * 55)
    for x_step in range(0, 41):
        x = x_step * 0.1  # 0.0 to 4.0
        pos_test = torch.tensor([[x, 0.0, 0.0]], dtype=torch.float32, device=engine.device)
        grad = trilinear_interpolate_gradient(engine._phi_curr, pos_test, engine.GRID_MIN, engine.GRID_MAX, engine.GRID_RES, engine.DX)
        pwf = (engine.config.pilot_wave_coupling / 1.0) * grad
        
        # Also sample phi manually
        ix = int(round((x - engine.GRID_MIN) / engine.DX))
        iy = int(round((0.0 - engine.GRID_MIN) / engine.DX))
        iz = int(round((0.0 - engine.GRID_MIN) / engine.DX))
        if ix >= engine.GRID_RES or iy >= engine.GRID_RES or iz >= engine.GRID_RES or ix < 0 or iy < 0 or iz < 0:
            phi_val = float('nan')
        else:
            phi_val = engine._phi_curr[0, 0, iz, iy, ix].item()
        
        print(f"{x:5.1f} | {phi_val:12.4e} | {pwf[0, 0].item():12.4e}")

if __name__ == "__main__":
    debug_forces()
