"""
TEGR 2600 Configuration Schema
===============================
Defines all simulation parameters with defaults, types, valid ranges,
and descriptions using Python dataclasses.

Particles are localized geometric defects on a topological coordinate matrix.
No viscosity. No medium. Pure kinematic coupling and finite-difference gradients.
"""
from dataclasses import dataclass, field, asdict, fields
from typing import List, Tuple, Optional
import json
import tomllib  # stdlib since Python 3.11


@dataclass
class SimulationConfig:
    """TEGR 2600 simulation parameters.

    Particles are localized geometric defects on a topological coordinate matrix.
    No viscosity. No medium. Pure kinematic coupling and finite-difference gradients.
    """

    # --- System ---
    name: str = "Untitled Experiment"
    num_particles: int = 4

    # --- Integration ---
    dt: float = 0.001
    total_ticks: int = 10000

    # --- FDTD Grid (3D Klein-Gordon) ---
    grid_resolution: int = 64    # cells per axis
    wave_speed: float = 65.0     # c in grid units
    wave_decay: float = 0.9999   # torsion decay multiplier per tick (1.0 = no decay)

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
    kuramoto_K: float = 50.0  # sync coupling strength (only active when kuramoto_enabled=True)

    # --- Pilot Wave ---
    pilot_wave: bool = True
    pilot_wave_coupling: float = 50.0  # gradient force multiplier

    # --- Device ---
    device: str = "auto"  # 'auto', 'cuda', 'cpu'

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
