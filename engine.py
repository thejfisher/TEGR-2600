"""
INNYOUTY 3-Tier Nested Universe Engine
======================================
Forked from TEGR 2600 with spatially-dependent FDTD support
for double-sigmoid nested universe simulations.

Core integration loop implementing:
    1. Damped Klein-Gordon (FDTD wave propagation on 3D Eulerian grid)
       - Supports spatially varying c^2(r) and decay(r) via sigmoid impedance tensors
    2. Relativistic Adler Equation (RAE phase clock)
    3. Pauli exclusion force (phase-coupled repulsion)
    4. Kuramoto synchronization (entanglement coupling)
    5. Pilot wave guidance (field gradient -> force)

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


def build_impedance_tensors_3tier(G, grid_min, grid_max, config, device):
    coords = torch.linspace(grid_min, grid_max, G, device=device)
    x, y, z = torch.meshgrid(coords, coords, coords, indexing='ij')
    r_tensor = torch.sqrt(x**2 + y**2 + z**2)
    
    R_c = config.nested_radius_child
    R_p = config.nested_radius_parent
    k = config.nested_sharpness
    
    # Double sigmoid masks
    mask_child = 1.0 / (1.0 + torch.exp(-k * (r_tensor - R_c)))
    mask_parent = 1.0 / (1.0 + torch.exp(-k * (r_tensor - R_p)))
    
    # Wave speed
    c_grid = config.c_c + (config.c_p - config.c_c) * mask_child + (config.c_gp - config.c_p) * mask_parent
    c_sq_grid = (c_grid ** 2).view(1, 1, G, G, G)
    
    # Wave decay
    decay_grid = (config.decay_c + (config.decay_p - config.decay_c) * mask_child + (config.decay_gp - config.decay_p) * mask_parent).view(1, 1, G, G, G)
    
    # Pauli exclusion (reshaped for grid_sample compatibility)
    pauli_grid = (config.pauli_c + (config.pauli_p - config.pauli_c) * mask_child + (config.pauli_gp - config.pauli_p) * mask_parent).view(1, 1, G, G, G)
    
    return c_sq_grid, decay_grid, pauli_grid


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

        # Tensor precision (float32 or float64)
        self.dtype = torch.float64 if config.precision == 'float64' else torch.float32

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

        self._phi_curr = torch.zeros((1, 1, G, G, G), device=device, dtype=self.dtype)
        self._phi_prev = torch.zeros((1, 1, G, G, G), device=device, dtype=self.dtype)
        self._phi_next = torch.zeros((1, 1, G, G, G), device=device, dtype=self.dtype)

        # 7-point Laplacian stencil
        self._laplacian_kernel = torch.zeros((1, 1, 3, 3, 3), device=device, dtype=self.dtype)
        self._laplacian_kernel[0, 0, 1, 1, 1] = -6.0
        self._laplacian_kernel[0, 0, 1, 1, 0] = 1.0
        self._laplacian_kernel[0, 0, 1, 1, 2] = 1.0
        self._laplacian_kernel[0, 0, 1, 0, 1] = 1.0
        self._laplacian_kernel[0, 0, 1, 2, 1] = 1.0
        self._laplacian_kernel[0, 0, 0, 1, 1] = 1.0
        self._laplacian_kernel[0, 0, 2, 1, 1] = 1.0

        # Seed initial field from particle positions
        self._seed_field_from_particles(state)

        # --- Impedance Tensor Initialization ---
        if self.config.emergent_horizons:
            # Emergent mode: c² and λ derived dynamically from φ field
            # Start with uniform base values; first _update_emergent_impedance() call
            # in the hot loop will couple them to the seeded field.
            c_base_sq = self.config.emergent_c_base ** 2
            self._c_sq_grid = torch.full((1, 1, G, G, G), c_base_sq, device=device, dtype=self.dtype)
            self._decay_grid = torch.full((1, 1, G, G, G), self.config.emergent_decay_base, device=device, dtype=self.dtype)
            self._pauli_grid = None
            # Precompute CFL ceiling: c_max² = (DX / (DT * sqrt(3)))²
            self._c_sq_max = (self.DX / (self.DT * 3.0**0.5)) ** 2
            # Run initial coupling so tick 0 already sees the seeded field
            self._update_emergent_impedance()
            print(f"  [EMERGENT HORIZONS] phi-coupled impedance active\n"
                  f"    c_base={self.config.emergent_c_base}, alpha={self.config.emergent_alpha}\n"
                  f"    decay_base={self.config.emergent_decay_base}, gamma={self.config.emergent_decay_gamma}\n"
                  f"    CFL ceiling: c_max={self._c_sq_max**0.5:.2f}")
        elif self.config.nested_enabled:
            self._c_sq_grid, self._decay_grid, self._pauli_grid = build_impedance_tensors_3tier(
                G, self.GRID_MIN, self.GRID_MAX, self.config, device
            )
            print(f"  [3-TIER NESTED] Impedance tensors built\n"
                  f"    Grandparent: c={self.config.c_gp}, decay={self.config.decay_gp}, U={self.config.pauli_gp}\n"
                  f"    Parent:      c={self.config.c_p},  decay={self.config.decay_p},  U={self.config.pauli_p}\n"
                  f"    Child:       c={self.config.c_c},  decay={self.config.decay_c},    U={self.config.pauli_c}\n"
                  f"    R_parent={self.config.nested_radius_parent} | R_child={self.config.nested_radius_child} | k={self.config.nested_sharpness}")
        else:
            # Scalar constants as 1x1x1x1x1 tensors for uniform broadcasting (no branching in hot loop)
            self._c_sq_grid = torch.full((1, 1, 1, 1, 1), self.config.c_p**2, device=device, dtype=self.dtype)
            self._decay_grid = torch.full((1, 1, 1, 1, 1), self.config.decay_p, device=device, dtype=self.dtype)
            self._pauli_grid = None

    def _update_emergent_impedance(self):
        """
        Recompute c²(r) and λ(r) from the live Klein-Gordon field φ.

        Uses a rational approximation (zero transcendentals):
            c²(φ) = c_base² / (1 + α|φ|)²
            λ(φ)  = λ_base * (c²/c_base²)^γ

        As φ accumulates (mass → topological strain), c² drops and
        damping increases — an event horizon emerges dynamically.
        """
        cfg = self.config
        c_base_sq = cfg.emergent_c_base ** 2
        alpha = cfg.emergent_alpha

        # Rational approximation: c² = c_base² / (1 + α|φ|)²
        phi_abs = self._phi_curr.abs()
        denominator = (1.0 + alpha * phi_abs).square()
        self._c_sq_grid = c_base_sq / denominator

        # CFL safety clamp (prevent numerical blowup)
        self._c_sq_grid.clamp_(min=1.0, max=self._c_sq_max)

        # Couple damping to impedance: as c² drops, damping increases
        # decay = decay_base * (c²/c_base²)^γ   →   dense regions decay faster
        decay_ratio = self._c_sq_grid / c_base_sq
        self._decay_grid = cfg.emergent_decay_base * decay_ratio.pow(cfg.emergent_decay_gamma)
        self._decay_grid.clamp_(min=0.5, max=1.0)  # relaxed floor: gamma=0.075 keeps lambda~0.9

    def _inject_mass_source(self, pos: torch.Tensor, m0: torch.Tensor):
        """
        Continuously inject Klein-Gordon field energy at particle positions.

        Mass is a permanent spring, not a one-time impulse. Each tick,
        particles pump phi proportional to their rest mass:
            phi += S * sum_i (m_i / m_max) * G(r - r_i, sigma)

        Uses nearest-cell injection for speed (no Gaussian kernel in hot loop).
        The FDTD diffusion naturally smooths the injected energy over time.
        """
        S = self.config.emergent_source_strength
        if S <= 0:
            return

        G_res = self.GRID_RES
        m_max = m0.max().clamp(min=1e-8)

        # Convert particle positions to grid indices
        grid_idx = ((pos - self.GRID_MIN) / self.DX).long()
        grid_idx = grid_idx.clamp(1, G_res - 2)  # stay 1 cell from boundary

        # Inject at each particle's nearest cell (O(N) — no grid sweep)
        for i in range(pos.shape[0]):
            ix, iy, iz = grid_idx[i, 0].item(), grid_idx[i, 1].item(), grid_idx[i, 2].item()
            amplitude = S * (m0[i].item() / m_max.item())
            # Inject into a 3x3x3 neighborhood for smoothness
            self._phi_curr[0, 0, ix-1:ix+2, iy-1:iy+2, iz-1:iz+2] += amplitude / 27.0

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
        print(f"  Kuramoto K: {cfg.kuramoto_k}")
        if cfg.nested_enabled:
            print(f"  [NESTED UNIVERSE] 3-Tier Architecture | R_parent={cfg.nested_radius_parent} | R_child={cfg.nested_radius_child} | k={cfg.nested_sharpness}")
            print(f"    Grandparent: c={cfg.c_gp}, decay={cfg.decay_gp}, U={cfg.pauli_gp}")
            print(f"    Parent:      c={cfg.c_p},  decay={cfg.decay_p},  U={cfg.pauli_p}")
            print(f"    Child:       c={cfg.c_c},  decay={cfg.decay_c},    U={cfg.pauli_c}")
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
        PAULI = cfg.pauli_strength
        LAMBDA_VAC = cfg.vacuum_damping
        K_SYNC = cfg.kuramoto_k
        TORSION = cfg.torsion_coupling

        start_time = time.time()

        for tick in range(T):
            # Record state
            trajectory[tick] = state.cpu().numpy()

            # =====================================================
            # 0. EMERGENT IMPEDANCE UPDATE (every tick)
            #    c²(φ) = c_base² / (1 + α|φ|)²   [rational approx]
            #    Recomputes c² and λ from live Klein-Gordon field.
            #    Cost: ~15µs (3 element-wise CUDA ops on 64³ grid)
            # =====================================================
            if self.config.emergent_horizons:
                self._update_emergent_impedance()

            # =====================================================
            # 1. FDTD WAVE PROPAGATION (Damped Klein-Gordon)
            #    Spatially varying c²(r) and λ(r) for nested universe
            # =====================================================
            laplacian = F.conv3d(self._phi_curr, self._laplacian_kernel, padding=1)
            torch.mul(self._phi_curr, 2.0, out=self._phi_next)
            self._phi_next.sub_(self._phi_prev)
            alpha_grid = self._c_sq_grid * (DT * DT / (self.DX * self.DX))
            self._phi_next.add_(laplacian * alpha_grid)
            self._phi_next.mul_(self._decay_grid)

            # Shift buffers
            temp = self._phi_prev
            self._phi_prev = self._phi_curr
            self._phi_curr = self._phi_next
            self._phi_next = temp

            # =====================================================
            # 1b. CONTINUOUS MASS SOURCING
            #     Mass is a permanent spring — particles pump phi
            #     proportional to rest mass every tick.
            # =====================================================
            if self.config.emergent_horizons and self.config.emergent_source_strength > 0:
                pos_for_source = state[:, 1:4]
                m0_for_source = state[:, 7]
                self._inject_mass_source(pos_for_source, m0_for_source)

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
            # Pairwise vectors needed by both Pauli AND RAE phase clock
            if N > 1:
                diff = pos.unsqueeze(1) - pos.unsqueeze(0)         # (N, N, 3)
                dist_sq = torch.sum(diff**2, dim=2) + 1e-6         # (N, N)

            if cfg.pauli_enabled and N > 1:
                # Phase coupling: cos(theta_i - theta_j)
                hue_diff = theta.unsqueeze(1) - theta.unsqueeze(0)  # (N, N)
                phase_coupling = torch.cos(hue_diff)

                # Force law: chi * cos(dtheta) * r_hat / r^n
                power_exp = (cfg.pauli_power + 1) / 2.0

                # FIX 1: Spatially-varying Pauli from double-sigmoid grid
                if self.config.nested_enabled and self._pauli_grid is not None:
                    pauli_at_particle = self._sample_field_at_positions(self._pauli_grid, pos)
                    pauli_local = pauli_at_particle.unsqueeze(1).unsqueeze(2)  # (N, 1, 1)
                else:
                    pauli_local = PAULI

                pauli_force = pauli_local * phase_coupling.unsqueeze(2) * diff / dist_sq.unsqueeze(2) ** power_exp
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
            # 5b. IMPEDANCE COUPLING (quadratic, velocity-dependent)
            #     F_imp = -beta * |grad(ln c^2)| * |v| * v
            #     Quadratic coupling ensures CONSTANT FRACTIONAL retention:
            #       dv/dx = -k*v  =>  v_out = v_in * exp(-∫k dx)
            #     The fraction retained is independent of entry speed.
            # =====================================================
            impedance_force = torch.zeros_like(pos)
            if self._c_sq_grid is not None:
                c_sq_grad = trilinear_interpolate_gradient(
                    self._c_sq_grid, pos, self.GRID_MIN, self.GRID_MAX,
                    self.GRID_RES, self.DX
                )  # (N, 3)
                # Log-gradient for scale-invariance
                c_sq_local = self._sample_field_at_positions(self._c_sq_grid, pos)  # (N,)
                c_sq_local = c_sq_local.clamp(min=1.0).unsqueeze(1)  # (N, 1)
                log_grad_magnitude = torch.norm(c_sq_grad / c_sq_local, dim=1, keepdim=True)  # (N, 1)
                # Quadratic impedance coupling: F = -beta * |grad(ln c^2)| * |v| * v
                v_magnitude = torch.norm(vel, dim=1, keepdim=True).clamp(min=1e-8)  # (N, 1)
                impedance_force = -self.config.impedance_coupling_coeff * log_grad_magnitude * v_magnitude * vel

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
            total_force = pauli_force + torsion_force + damping_force + impedance_force + pilot_wave_force

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

    def _sample_field_at_positions(self, field: torch.Tensor, pos: torch.Tensor) -> torch.Tensor:
        """Sample a (1, 1, G, G, G) scalar field at particle positions using trilinear interpolation.
        
        Returns: (N,) tensor of field values at each particle's position.
        """
        if field.dim() == 3:
            field = field.unsqueeze(0).unsqueeze(0)
        norm = 2.0 * (pos - self.GRID_MIN) / (self.GRID_MAX - self.GRID_MIN) - 1.0
        grid = norm.flip(-1).unsqueeze(0).unsqueeze(0).unsqueeze(0)  # (1, 1, 1, N, 3)
        grid = grid.to(dtype=field.dtype)
        sampled = F.grid_sample(
            field, grid,
            mode='bilinear', padding_mode='border', align_corners=True,
        )
        return sampled[0, 0, 0, 0, :]  # (N,)

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
