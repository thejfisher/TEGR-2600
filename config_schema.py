"""
HOLO DECK Configuration Schema
===============================
Defines all simulation parameters with defaults, types, valid ranges,
and descriptions using Python dataclasses. Forked from TEGR 2600.

Particles are localized geometric defects on a topological coordinate matrix.
No viscosity. No medium. Pure kinematic coupling and finite-difference gradients.
"""
from dataclasses import dataclass, field, asdict, fields
from typing import List, Tuple, Optional
import json
import tomllib  # stdlib since Python 3.11


@dataclass
class SimulationConfig:
    """HOLO DECK simulation parameters (forked from TEGR 2600).

    Particles are localized geometric defects on a topological coordinate matrix.
    No viscosity. No medium. Pure kinematic coupling and finite-difference gradients.
    """

    # --- System ---
    name: str = "Untitled Experiment"
    num_particles: int = 4
    max_particles: int = 5000  # For feeding black hole pre-allocation

    # --- Integration ---
    dt: float = 0.001
    total_ticks: int = 10000
    rindler_acceleration: float = 0.0

    # --- Black Hole Cosmology (Horizon Injection) ---
    horizon_injection_rate: int = 0      # Ticks between new particle injections (0 = closed system)
    horizon_injection_mass: float = 1.0  # Rest mass of incoming trace particles

    # --- FDTD Grid (3D Klein-Gordon) ---
    grid_resolution: int = 64    # cells per axis
    wave_speed: float = 65.0     # c in grid units
    wave_decay: float = 0.9999   # torsion decay multiplier per tick (1.0 = no decay)
    warm_grid_noise: float = 0.0 # amplitude of random Gaussian noise injected at start
    periodic_boundaries: bool = True # Use periodic boundaries (circular padding) for the FDTD grid

    # --- Pauli Exclusion ---
    pauli_strength: float = 10.0  # chi - exclusion coupling scalar
    pauli_power: int = 3          # force law: 1/r^n (2=Coulomb, 3=dipole)
    pauli_enabled: bool = True

    # --- Torsion ---
    torsion_coupling: float = 1.0  # structural restoring force

    # --- Damping ---
    vacuum_damping: float = 0.007  # spatial damping coefficient
    vacuum_enabled: bool = True

    # --- RAE (Relativistic Adler Equation) ---
    rae_mode: bool = True
    rae_kappa_scale: float = 1.0   # curvature sensitivity
    rae_grad_scale: float = 1.0    # field gradient sensitivity

    # --- Entanglement (Kuramoto) ---
    kuramoto_enabled: bool = False  # OFF by default (discovery mode — no circular forcing)
    kuramoto_k: float = 50.0  # sync coupling strength (only active when kuramoto_enabled=True)

    # --- Klein-Gordon Override ---
    kg_override: bool = False  # If True, overrides Kuramoto synchronization with Klein-Gordon topological floor coupling

    # --- Pilot Wave ---
    pilot_wave: bool = True
    pilot_wave_coupling: float = 50.0  # gradient force multiplier

    # --- 3-Tier Nested Universe (Grandparent -> Parent -> Child) ---
    nested_enabled: bool = False
    nested_sharpness: float = 5.0            # k — sigmoid steepness at both boundaries

    # Boundary radii
    nested_radius_parent: float = 12.0       # R_parent — outer event horizon
    nested_radius_child: float = 5.0         # R_child — inner event horizon

    # Grandparent Universe (r >> R_parent)
    c_gp: float = 130.0
    decay_gp: float = 0.9999
    pauli_gp: float = 5.0

    # Parent Universe (R_child << r << R_parent)  — THIS IS "OUR" UNIVERSE
    c_p: float = 65.0
    decay_p: float = 0.999
    pauli_p: float = 10.0

    # Child Universe (r << R_child)
    c_c: float = 30.0
    decay_c: float = 0.900
    pauli_c: float = 50.0

    # Impedance coupling: velocity-dependent force at boundary crossings
    impedance_coupling_coeff: float = 0.01

    # --- Emergent Horizons (Phase 3: Klein-Gordon field coupling) ---
    emergent_horizons: bool = False       # Enable φ-coupled impedance (replaces static sigmoid)
    emergent_alpha: float = 0.1           # Coupling strength: φ → c² via 1/(1+α|φ|)²
    emergent_c_base: float = 65.0         # Ambient vacuum wave speed (where φ ≈ 0)
    emergent_decay_base: float = 0.999    # Ambient vacuum damping (where φ ≈ 0)
    emergent_decay_gamma: float = 0.5     # Exponent coupling damping to impedance shift
    emergent_source_strength: float = 0.0  # Continuous mass sourcing rate (0 = seed-only)

    # --- Device ---
    device: str = "auto"  # 'auto', 'cuda', 'cpu'
    precision: str = "float32"  # 'float32' or 'float64' (double precision)

    # --- Output ---
    output_dir: str = "./output"
    save_trajectories: bool = True
    save_plots: bool = True
    plot_format: str = "png"  # 'png' or 'pdf'

    # ------------------------------------------------------------------
    # Derived constants
    # ------------------------------------------------------------------

    @property
    def C(self) -> float:
        """Speed of light in simulation grid units (alias for wave_speed)."""
        return self.wave_speed

    @property
    def C_SQUARED(self) -> float:
        """c² — used in relativistic kinematic expressions."""
        return self.wave_speed ** 2

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> List[str]:
        """Return list of validation errors. Empty list means valid."""
        errors: List[str] = []
        if self.num_particles < 2:
            errors.append("num_particles must be >= 2")
        if self.dt <= 0:
            errors.append("dt must be positive")
        if self.total_ticks < 1:
            errors.append("total_ticks must be >= 1")
        if self.grid_resolution < 8:
            errors.append("grid_resolution must be >= 8")
        if self.wave_speed <= 0:
            errors.append("wave_speed must be positive")
        if not (0 < self.wave_decay <= 1.0):
            errors.append("wave_decay must be in (0, 1.0]")
        if self.pauli_power not in [2, 3, 4]:
            errors.append("pauli_power must be 2, 3, or 4")
        if self.nested_enabled:
            if self.nested_radius_child <= 0 or self.nested_radius_parent <= 0:
                errors.append("radii must be positive")
            if self.nested_radius_parent <= self.nested_radius_child:
                errors.append("nested_radius_parent must be > nested_radius_child")
            if self.c_gp <= 0 or self.c_p <= 0 or self.c_c <= 0:
                errors.append("wave speeds must be positive")
            if not (0 < self.decay_gp <= 1.0) or not (0 < self.decay_p <= 1.0) or not (0 < self.decay_c <= 1.0):
                errors.append("decays must be in (0, 1.0]")
            if self.nested_sharpness <= 0:
                errors.append("nested_sharpness must be positive")
        if self.device not in ["auto", "cuda", "cpu"]:
            errors.append("device must be 'auto', 'cuda', or 'cpu'")
        if self.plot_format not in ["png", "pdf"]:
            errors.append("plot_format must be 'png' or 'pdf'")
        return errors

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    @classmethod
    def from_toml(cls, path: str) -> "SimulationConfig":
        """Load config from a TOML file, mapping nested sections to flat fields.

        TOML sections like ``[grid]`` or ``[pauli]`` are flattened so that
        their keys map directly to dataclass field names.
        """
        with open(path, "rb") as f:
            data = tomllib.load(f)

        flat: dict = {}
        # Collect top-level scalar keys first
        for k, v in data.items():
            if not isinstance(v, dict):
                flat[k] = v
        # Then flatten nested sections
        for section in data.values():
            if isinstance(section, dict):
                flat.update(section)

        # Filter to only known dataclass fields
        known = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in flat.items() if k in known}
        return cls(**filtered)

    def to_dict(self) -> dict:
        """Serialize to a plain dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
