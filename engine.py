"""
TEGR 2600 Physics Engine
========================
Core integration loop implementing:
    1. Damped Klein-Gordon (FDTD wave propagation on 3D Eulerian grid)
    2. Relativistic Adler Equation (RAE phase clock)
    3. Pauli exclusion force (phase-coupled repulsion)
    4. Kuramoto synchronization (entanglement coupling)
    5. Pilot wave guidance (field gradient → force)

Particles are localized geometric defects on a topological coordinate matrix.
No viscosity. No medium. Pure kinematic coupling and finite-difference gradients.
"""
import time
import numpy as np
import torch
import torch.nn.functional as F
from pathlib import Path
from typing import Optional, Tuple, Callable

from config_schema import SimulationConfig
from utils import trilinear_interpolate_gradient


class TEGR2600Engine:
    """
    Forward-time Verlet integrator for the TEGR 2600 simulation.

    The engine takes an initial state vector (N, 10) and an entanglement
    adjacency matrix (N, N), then integrates forward in time using the
    Klein-Gordon FDTD wave equation and the Relativistic Adler Equation.
    """

    def __init__(self, config: SimulationConfig):
        self.config = config

        # Resolve device
        if config.device == 'auto':
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(config.device)

        # Constants
        self.C = config.wave_speed
        self.C_SQ = self.C ** 2
        self.DT = config.dt
        self.GRID_RES = config.grid_resolution

        # Grid bounds: symmetric around origin
        # We will resize this in run() based on actual particle positions.
        self.GRID_MIN = -10.0
        self.GRID_MAX = 10.0
        self.DX = (self.GRID_MAX - self.GRID_MIN) / self.GRID_RES

        # FDTD wave field buffers (allocated on first run)
        self._phi_curr = None
        self._phi_prev = None
        self._phi_next = None
        self._laplacian_kernel = None

        # Trajectory recording
        self.trajectory = None

        # Progress callback
        self._progress_callback: Optional[Callable] = None

    def set_progress_callback(self, callback: Callable[[int, int, dict], None]):
        """Set a callback for progress updates: callback(tick, total_ticks, stats)."""
        self._progress_callback = callback

    def _init_grid(self, state: torch.Tensor):
        """Initialize FDTD grid, Laplacian kernel, and scale grid to particle bounds."""
        N = state.shape[0]
        pos = state[:, 1:4]

        # Auto-scale grid to particle positions with 3x margin
        pos_min = pos.min().item()
        pos_max = pos.max().item()
        span = max(abs(pos_min), abs(pos_max), 1.0) * 3.0
        self.GRID_MIN = -span
        self.GRID_MAX = span
        self.DX = (self.GRID_MAX - self.GRID_MIN) / self.GRID_RES

        G = self.GRID_RES
        device = self.device

        self._phi_curr = torch.zeros((1, 1, G, G, G), device=device, dtype=torch.float32)
        self._phi_prev = torch.zeros((1, 1, G, G, G), device=device, dtype=torch.float32)
        self._phi_next = torch.zeros((1, 1, G, G, G), device=device, dtype=torch.float32)

        # 7-point Laplacian stencil
        self._laplacian_kernel = torch.zeros((1, 1, 3, 3, 3), device=device, dtype=torch.float32)
        self._laplacian_kernel[0, 0, 1, 1, 1] = -6.0
        self._laplacian_kernel[0, 0, 1, 1, 0] = 1.0
        self._laplacian_kernel[0, 0, 1, 1, 2] = 1.0
        self._laplacian_kernel[0, 0, 1, 0, 1] = 1.0
        self._laplacian_kernel[0, 0, 1, 2, 1] = 1.0
        self._laplacian_kernel[0, 0, 0, 1, 1] = 1.0
        self._laplacian_kernel[0, 0, 2, 1, 1] = 1.0

        # Seed initial field from particle positions
        self._seed_field_from_particles(state)

    def _seed_field_from_particles(self, state: torch.Tensor):
        """Seed the FDTD grid with Gaussian bumps at each particle position."""
        pos = state[:, 1:4]
        m0 = state[:, 7]
        G = self.GRID_RES
        device = self.device

        # Create coordinate grids
        coords = torch.linspace(self.GRID_MIN, self.GRID_MAX, G, device=device)
        x_grid, y_grid, z_grid = torch.meshgrid(coords, coords, coords, indexing='ij')

        for i in range(state.shape[0]):
            px, py, pz = pos[i, 0].item(), pos[i, 1].item(), pos[i, 2].item()
            amplitude = m0[i].item() / (m0.max().item() + 1e-8)  # normalize
            sigma = self.DX * 3  # 3-cell Gaussian width

            gaussian = amplitude * torch.exp(
                -((x_grid - px)**2 + (y_grid - py)**2 + (z_grid - pz)**2) / (2 * sigma**2)
            )
            self._phi_curr[0, 0] += gaussian

        # Set phi_prev = phi_curr for initial condition (zero velocity start)
        self._phi_prev.copy_(self._phi_curr)

    def run(
        self,
        initial_state: torch.Tensor,
        adjacency: torch.Tensor,
    ) -> np.ndarray:
        """
        Run the full simulation.

        Parameters
        ----------
        initial_state : torch.Tensor, shape (N, 10)
            Initial state vector.
        adjacency : torch.Tensor, shape (N, N)
            Boolean entanglement adjacency matrix.

        Returns
        -------
        trajectory : np.ndarray, shape (T, N, 10)
            Full state history over all ticks.
        """
        cfg = self.config
        N = initial_state.shape[0]
        T = cfg.total_ticks
        device = self.device

        print(f"\n{'='*60}")
        print(f"  TEGR 2600 Engine")
        print(f"  Particles: {N} | Ticks: {T} | Device: {device}")
        print(f"  Grid: {self.GRID_RES}^3 | Wave Speed: {self.C}")
        print(f"  RAE: {'ON' if cfg.rae_mode else 'OFF'} | Pilot Wave: {'ON' if cfg.pilot_wave else 'OFF'}")
        print(f"  Pauli: {cfg.pauli_strength} (1/r^{cfg.pauli_power})")
        print(f"  Kuramoto K: {cfg.kuramoto_K}")
        print(f"{'='*60}\n")

        # Move tensors to device
        state = initial_state.clone().to(device)
        W_mat = adjacency.to(device)

        # Initialize FDTD grid
        self._init_grid(state)

        # Allocate trajectory buffer
        trajectory = np.zeros((T, N, 10), dtype=np.float32)

        # Precompute constants
        DT = self.DT
        C_SQ = self.C_SQ
        TORSION_DECAY = cfg.wave_decay
        PAULI = cfg.pauli_strength
        LAMBDA_VAC = cfg.vacuum_damping
        K_SYNC = cfg.kuramoto_K
        TORSION = cfg.torsion_coupling

        start_time = time.time()
        
        alpha = C_SQ * DT * DT / (self.DX * self.DX)

        for tick in range(T):
            # Record state
            trajectory[tick] = state.cpu().numpy()

            # =====================================================
            # 1. FDTD WAVE PROPAGATION (Damped Klein-Gordon)
            # =====================================================
            laplacian = F.conv3d(self._phi_curr, self._laplacian_kernel, padding=1)
            torch.mul(self._phi_curr, 2.0, out=self._phi_next)
            self._phi_next.sub_(self._phi_prev)
            self._phi_next.add_(laplacian, alpha=C_SQ * DT * DT / (self.DX * self.DX))
            self._phi_next.mul_(TORSION_DECAY)

            # Shift buffers
            temp = self._phi_prev
            self._phi_prev = self._phi_curr
            self._phi_curr = self._phi_next
            self._phi_next = temp

            # =====================================================
            # 2. EXTRACT PARTICLE STATE
            # =====================================================
            pos = state[:, 1:4]
            mom = state[:, 4:7]
            m0 = state[:, 7]
            theta = state[:, 8]
            gamma = state[:, 9]

            # Velocity from momentum
            gamma_safe = gamma.clamp(min=1.0)
            vel = mom / (gamma_safe.unsqueeze(1) * m0.unsqueeze(1).clamp(min=1e-8))

            # =====================================================
            # 3. PAULI EXCLUSION FORCE
            # =====================================================
            if cfg.pauli_enabled and N > 1:
                diff = pos.unsqueeze(1) - pos.unsqueeze(0)         # (N, N, 3)
                dist_sq = torch.sum(diff**2, dim=2) + 1e-6         # (N, N)

                # Phase coupling: cos(theta_i - theta_j)
                hue_diff = theta.unsqueeze(1) - theta.unsqueeze(0)  # (N, N)
                phase_coupling = torch.cos(hue_diff)

                # Force law: chi * cos(dtheta) * r_hat / r^n
                power_exp = (cfg.pauli_power + 1) / 2.0
                pauli_force = PAULI * phase_coupling.unsqueeze(2) * diff / dist_sq.unsqueeze(2) ** power_exp
                pauli_force = torch.sum(pauli_force, dim=1)         # (N, 3)
            else:
                pauli_force = torch.zeros_like(pos)

            # =====================================================
            # 4. TORSION FORCE (from Eulerian field gradient)
            # =====================================================
            torsion_force = torch.zeros_like(pos)
            if TORSION > 0:
                grad = trilinear_interpolate_gradient(
                    self._phi_curr, pos, self.GRID_MIN, self.GRID_MAX,
                    self.GRID_RES, self.DX
                )
                torsion_force = TORSION * grad

            # =====================================================
            # 5. DAMPING
            # =====================================================
            damping_force = torch.zeros_like(pos)
            if cfg.vacuum_enabled:
                damping_force = -LAMBDA_VAC * vel

            # =====================================================
            # 6. PILOT WAVE GUIDANCE
            # =====================================================
            pilot_wave_force = torch.zeros_like(pos)
            if cfg.pilot_wave:
                grad_at_particle = trilinear_interpolate_gradient(
                    self._phi_curr, pos, self.GRID_MIN, self.GRID_MAX,
                    self.GRID_RES, self.DX
                )
                m0_safe = m0.clamp(min=1e-6)
                pilot_wave_force = (cfg.pilot_wave_coupling / m0_safe).unsqueeze(1) * grad_at_particle

            # =====================================================
            # 7. TOTAL FORCE → MOMENTUM UPDATE
            # =====================================================
            total_force = pauli_force + torsion_force + damping_force + pilot_wave_force

            # Verlet: p_new = p + F * dt
            mom_new = mom + total_force * DT
            
            if torch.isnan(mom_new).any():
                print(f"DEBUG: mom_new NaN at tick {tick}!")
                print(f"pauli_force: {pauli_force}")
                print(f"torsion_force: {torsion_force}")
                print(f"damping_force: {damping_force}")
                print(f"pilot_wave_force: {pilot_wave_force}")
                
            state[:, 4:7] = mom_new

            # Update gamma from new momentum
            p_sq = torch.sum(mom_new**2, dim=1)
            m0_sq = (m0 * self.C) ** 2
            gamma_new = torch.sqrt(1.0 + p_sq / m0_sq.clamp(min=1e-8))
            state[:, 9] = gamma_new

            # Update velocity and position
            vel_new = mom_new / (gamma_new.unsqueeze(1) * m0.unsqueeze(1).clamp(min=1e-8))
            pos_new = pos + vel_new * DT
            state[:, 1:4] = pos_new
            
            phi_max = self._phi_curr.abs().max().item()
            if phi_max > 1000.0:
                print(f"DEBUG: phi_max blown up at tick {tick}: {phi_max}")

            # =====================================================
            # 8. PHASE CLOCK UPDATE (RAE or simple)
            # =====================================================
            if cfg.rae_mode:
                # --- Term 1: Kinematic Baseline m0/gamma ---
                term1 = m0 / gamma_new

                # --- Term 2: Topological Restoring ---
                # kappa from gamma gradient projected onto velocity
                if N > 1:
                    gamma_diff = gamma_new.unsqueeze(0) - gamma_new.unsqueeze(1)
                    r_hat = diff / (torch.sqrt(dist_sq).unsqueeze(2) + 1e-8)
                    grad_gamma = torch.sum(gamma_diff.unsqueeze(2) * r_hat, dim=1)
                    v_mag = torch.norm(vel_new, dim=1, keepdim=True).clamp(min=1e-8)
                    v_hat = vel_new / v_mag
                    kappa = cfg.rae_kappa_scale * torch.sum(grad_gamma * v_hat, dim=1) / (N - 1)
                else:
                    kappa = torch.zeros_like(gamma_new)

                term2 = kappa * theta - kappa * torch.sin(theta)

                # --- Term 3: Field gradient projection ---
                grad_phi = trilinear_interpolate_gradient(
                    self._phi_curr, pos_new, self.GRID_MIN, self.GRID_MAX,
                    self.GRID_RES, self.DX
                )
                v_mag = torch.norm(vel_new, dim=1, keepdim=True).clamp(min=1e-8)
                v_hat = vel_new / v_mag
                term3 = cfg.rae_grad_scale * torch.sum(grad_phi * v_hat, dim=1)

                theta_dot = term1 + term2 + term3
                state[:, 8] = (theta + theta_dot * DT) % (2 * np.pi)
            else:
                # Simple Compton clock: d(theta)/dt = m0/gamma
                state[:, 8] = (theta + (m0 / gamma_new) * DT) % (2 * np.pi)

            # =====================================================
            # 9. KURAMOTO ENTANGLEMENT SYNC (optional — off by default)
            #    When OFF: phases evolve purely from RAE + Pauli + FDTD
            #    When ON:  adjacency matrix forces phase correlation
            # =====================================================
            if cfg.kuramoto_enabled and W_mat.any():
                theta_curr = state[:, 8]
                # Correct Kuramoto sign: sin(theta_j - theta_i) to synchronize
                hue_diff_sync = theta_curr.unsqueeze(0) - theta_curr.unsqueeze(1)
                sync_force = torch.sum(W_mat.float() * torch.sin(hue_diff_sync), dim=1)
                state[:, 8] = (theta_curr + K_SYNC * sync_force * DT) % (2 * np.pi)

            # =====================================================
            # 10. PARTICLE EMISSION INTO GRID
            # =====================================================
            # Deposit phase-weighted amplitude at particle locations
            if tick % 10 == 0:
                self._deposit_particles(state)

            # Update time
            state[:, 0] = (tick + 1) * DT

            # Progress reporting
            if tick % 500 == 0 or tick == T - 1:
                elapsed = time.time() - start_time
                theta_std = state[:, 8].std().item()
                stats = {
                    'tick': tick,
                    'theta_std': theta_std,
                    'gamma_mean': state[:, 9].mean().item(),
                    'elapsed': elapsed,
                }
                print(
                    f"  [Tick {tick:>5}/{T}] "
                    f"theta_std={theta_std:.4f}  "
                    f"gamma_mean={state[:, 9].mean().item():.4f}  "
                    f"({elapsed:.1f}s)"
                )
                if self._progress_callback:
                    self._progress_callback(tick, T, stats)

        elapsed = time.time() - start_time
        print(f"\nSimulation complete: {T} ticks in {elapsed:.1f}s "
              f"({T/elapsed:.0f} ticks/sec)")

        self.trajectory = trajectory
        return trajectory

    def _deposit_particles(self, state: torch.Tensor):
        """Deposit particle phase into the FDTD grid (Eulerian emission)."""
        pos = state[:, 1:4]
        if torch.isnan(pos).any():
            print(f"DEBUG: NaN detected in pos!\npos={pos}\nmom={state[:, 4:7]}\ngamma={state[:, 9]}")
        theta = state[:, 8]
        N = state.shape[0]
        G = self.GRID_RES

        for i in range(N):
            # Map particle position to grid index
            px = pos[i, 0].item()
            py = pos[i, 1].item()
            pz = pos[i, 2].item()

            ix = int((px - self.GRID_MIN) / self.DX)
            iy = int((py - self.GRID_MIN) / self.DX)
            iz = int((pz - self.GRID_MIN) / self.DX)

            # Clamp to grid bounds
            ix = max(0, min(G - 1, ix))
            iy = max(0, min(G - 1, iy))
            iz = max(0, min(G - 1, iz))

            # Deposit phase-weighted amplitude
            self._phi_curr[0, 0, ix, iy, iz] += 0.1 * torch.sin(theta[i])

    def save_results(self, output_dir: str = './output'):
        """Save trajectory and summary to disk."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        if self.trajectory is not None:
            np.save(out / 'trajectory.npy', self.trajectory)
            print(f"  Saved trajectory: {out / 'trajectory.npy'} "
                  f"({self.trajectory.nbytes / 1e6:.1f} MB)")

            # Save final state as CSV for quick inspection
            final = self.trajectory[-1]
            header = 't,x,y,z,px,py,pz,m0,theta_hue,gamma'
            np.savetxt(
                out / 'final_state.csv', final,
                delimiter=',', header=header, comments='',
                fmt='%.6f'
            )
            print(f"  Saved final state: {out / 'final_state.csv'}")


# ---------------------------------------------------------------------------
# Standalone Runner
# ---------------------------------------------------------------------------
def run_from_file(filepath: str, config_overrides: Optional[dict] = None) -> np.ndarray:
    """
    One-shot runner: load experiment file, run simulation, return trajectory.
    """
    from data_ingest import load_experiment
    from config_schema import SimulationConfig

    state, adjacency, metadata = load_experiment(filepath)
    print(f"Loaded: {metadata.get('name', 'Unknown')} ({metadata['num_particles']} particles)")

    # Build config from file metadata or defaults
    if filepath.endswith('.toml'):
        config = SimulationConfig.from_toml(filepath)
    else:
        config = SimulationConfig(num_particles=metadata['num_particles'])

    # Apply any overrides
    if config_overrides:
        for k, v in config_overrides.items():
            if hasattr(config, k):
                setattr(config, k, v)

    # Validate
    errors = config.validate()
    if errors:
        raise ValueError(f"Config validation failed: {'; '.join(errors)}")

    engine = TEGR2600Engine(config)
    trajectory = engine.run(state, adjacency)
    engine.save_results(config.output_dir)

    return trajectory


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        # Default: run Islam preset
        filepath = str(Path(__file__).parent / 'presets' / 'bose_hubbard_islam2015.toml')

    trajectory = run_from_file(filepath)
    print(f"\nTrajectory shape: {trajectory.shape}")
    print("Done.")
