import sys
import re

with open('Z:/TryTri/TEGR 2600/engine.py', 'r') as f:
    code = f.read()

run_start = code.find('def run(')
loop_start = code.find('for tick in range(T):', run_start)

before_loop = code[:loop_start]
loop_body = code[loop_start:]

loop_body = re.sub(r'state\[:,', 'state_active[:,', loop_body)
loop_body = re.sub(r'state\[\s*idx', 'state_active[idx', loop_body) # if any
loop_body = re.sub(r'\bN - 1\b', 'act_N - 1', loop_body)
loop_body = re.sub(r'W_mat\.float\(\)', 'W_mat[:act_N, :act_N].float()', loop_body)
loop_body = re.sub(r'_deposit_particles\(state\)', '_deposit_particles(state_active)', loop_body)
loop_body = re.sub(r'W_mat\.any\(\)', 'W_mat[:act_N, :act_N].any()', loop_body)

old_loop_start = '''for tick in range(T):
            # Record state
            trajectory[tick] = state.cpu().numpy()'''

new_loop_start = '''for tick in range(T):
            # 0. INJECT MASS AT HORIZON (if configured)
            self._inject_horizon_mass(state, tick)
            
            act_N = self.active_count
            state_active = state[:act_N]

            # Record state
            trajectory[tick, :act_N] = state_active.cpu().numpy()'''

if old_loop_start in loop_body:
    loop_body = loop_body.replace(old_loop_start, new_loop_start)
else:
    print("Could not find old_loop_start in loop_body!")

old_run_top = '''        cfg = self.config
        N = initial_state.shape[0]
        T = cfg.total_ticks
        device = self.device

        print(f"\\n{'='*60}")
        print(f"  TEGR 2600 Engine")
        print(f"  Particles: {N} | Ticks: {T} | Device: {device}")'''

new_run_top = '''        cfg = self.config
        N_init = initial_state.shape[0]
        self.active_count = N_init
        N = max(cfg.max_particles, N_init)
        T = cfg.total_ticks
        device = self.device

        print(f"\\n{'='*60}")
        print(f"  TEGR 2600 Engine")
        print(f"  Particles: {N_init} (Max: {N}) | Ticks: {T} | Device: {device}")'''

if old_run_top in before_loop:
    before_loop = before_loop.replace(old_run_top, new_run_top)
else:
    print("Could not find old_run_top in before_loop!")

old_state_init = '''        # Move tensors to device
        state = initial_state.clone().to(device)
        W_mat = adjacency.to(device)

        # Initialize FDTD grid
        self._init_grid(state)

        # Allocate trajectory buffer
        try:
            trajectory = np.zeros((T, N, 10), dtype=np.float32)
        except MemoryError:
            raise EngineMemoryError(f"Cannot allocate {T} ticks x {N} particles. Array size too large.")'''

new_state_init = '''        # Move tensors to device
        padded_state = torch.zeros((N, 10), dtype=initial_state.dtype)
        padded_state[:N_init] = initial_state
        state = padded_state.to(device)
        
        padded_W = torch.zeros((N, N), dtype=adjacency.dtype)
        padded_W[:N_init, :N_init] = adjacency
        W_mat = padded_W.to(device)

        # Initialize FDTD grid (only with initial active particles)
        self._init_grid(state[:N_init])

        # Allocate trajectory buffer
        try:
            trajectory = np.full((T, N, 10), np.nan, dtype=np.float32)
        except MemoryError:
            raise EngineMemoryError(f"Cannot allocate {T} ticks x {N} particles. Array size too large.")'''

if old_state_init in before_loop:
    before_loop = before_loop.replace(old_state_init, new_state_init)
else:
    print("Could not find old_state_init in before_loop!")

inject_method = '''
    def _inject_horizon_mass(self, state: torch.Tensor, tick: int):
        cfg = self.config
        if cfg.horizon_injection_rate > 0 and tick > 0 and tick % cfg.horizon_injection_rate == 0:
            if self.active_count < state.shape[0]:
                idx = self.active_count
                
                # Spawn at a random position on the boundary sphere
                L = self.GRID_MAX - self.GRID_MIN
                center = self.GRID_MIN + L / 2
                
                # Random direction
                import numpy as np
                theta = np.random.uniform(0, 2*np.pi)
                phi = np.arccos(np.random.uniform(-1, 1))
                r = (L/2) * 0.95  # Spawn just inside the boundary
                
                x = center + r * np.sin(phi) * np.cos(theta)
                y = center + r * np.sin(phi) * np.sin(theta)
                z = center + r * np.cos(phi)
                
                state[idx, 0] = tick * self.DT
                state[idx, 1:4] = torch.tensor([x, y, z], device=self.device)
                state[idx, 4:7] = 0.0  # Zero momentum initially
                state[idx, 7] = cfg.horizon_injection_mass
                state[idx, 8] = np.random.uniform(0, 2*np.pi)  # random phase
                state[idx, 9] = 1.0  # gamma
                
                self.active_count += 1
                print(f"  [HORIZON INJECTION] New particle spawned at tick {tick}. Active count: {self.active_count}")

'''

before_loop = before_loop.replace('    def run(', inject_method + '    def run(')

with open('Z:/TryTri/TEGR 2600/engine.py', 'w') as f:
    f.write(before_loop + loop_body)

print('Update successful')
