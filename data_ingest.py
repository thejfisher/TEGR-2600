"""
TEGR 2600 Data Ingest
=====================
Parses researcher input files (CSV, TOML, Markdown lab notebooks)
and converts them into the 10-dimensional state vector used by the engine.

State Vector Layout:
    X^M = [t, x, y, z, px, py, pz, m0, theta_hue, gamma]

Supported formats:
    - CSV:  Flat table with header row specifying columns and units
    - TOML: Structured sections for particles, coupling, entanglement
    - MD:   Markdown tables with YAML frontmatter and edge-list connections
"""
import csv
import re
import numpy as np
import torch
from pathlib import Path
from typing import Tuple, Dict, List, Optional


# ---------------------------------------------------------------------------
# Unit Conversion Constants
# ---------------------------------------------------------------------------
AMU_TO_MEV = 931.494       # 1 atomic mass unit = 931.494 MeV/c^2
C_SIM = 65.0               # speed of light in simulation units


def amu_to_mev(mass_amu: float) -> float:
    """Convert atomic mass units to MeV/c^2."""
    return mass_amu * AMU_TO_MEV


def kg_to_mev(mass_kg: float) -> float:
    """Convert kilograms to MeV/c^2."""
    return mass_kg * 5.609e29  # 1 kg ≈ 5.609×10²⁹ MeV/c²


def nm_to_sim(pos_nm: float, scale: float = 1.0) -> float:
    """Convert nanometers to simulation units (divide by scale factor)."""
    return pos_nm / scale if scale != 0 else pos_nm


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def load_experiment(filepath: str) -> Tuple[torch.Tensor, torch.Tensor, dict]:
    """
    Load experiment data from CSV, TOML, or Markdown file.

    Returns
    -------
    state_vector : torch.Tensor, shape (N, 10)
        Initial state: [t, x, y, z, px, py, pz, m0, theta_hue, gamma]
    adjacency : torch.Tensor, shape (N, N)
        Boolean entanglement adjacency matrix.
    metadata : dict
        Experiment name, units, source file, etc.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Experiment file not found: {filepath}")

    ext = path.suffix.lower()
    if ext == '.csv':
        return _parse_csv(filepath)
    elif ext == '.toml':
        return _parse_toml(filepath)
    elif ext == '.md':
        return _parse_markdown(filepath)
    elif ext == '.npy':
        return _parse_npy(filepath)
    else:
        raise ValueError(
            f"Unsupported file format '{ext}'. Use .csv, .toml, .md, or .npy"
        )


# ---------------------------------------------------------------------------
# CSV Parser
# ---------------------------------------------------------------------------
def _parse_csv(filepath: str) -> Tuple[torch.Tensor, torch.Tensor, dict]:
    """
    Parse a flat CSV file.

    Expected columns (order-independent, detected by header keywords):
        node_id, mass_<unit>, pos_x_<unit>, pos_y, pos_z,
        vel_x, vel_y, vel_z, phase_rad, spin_vorticity

    Unit suffixes on column headers: _amu, _mev, _kg, _nm, _um
    """
    rows = []
    header = []

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        for line in reader:
            # Skip comment lines
            if not line or line[0].strip().startswith('#'):
                continue
            if not header:
                header = [col.strip().lower() for col in line]
                continue
            rows.append([col.strip() for col in line])

    if not header:
        raise ValueError(f"CSV file {filepath} has no header row")
    if not rows:
        raise ValueError(f"CSV file {filepath} has no data rows")

    n = len(rows)

    # Detect unit from header names
    mass_unit = _detect_unit(header, 'mass', default='mev')
    pos_unit = _detect_unit(header, 'pos_x', default='sim')

    # Column index lookup (flexible matching)
    def find_col(keywords: list, default_val: float = 0.0) -> List[float]:
        for kw in keywords:
            for i, h in enumerate(header):
                if kw in h:
                    return [float(rows[r][i]) for r in range(n)]
        return [default_val] * n

    masses_raw = find_col(['mass'], default_val=1.0)
    pos_x = find_col(['pos_x', 'x_nm', 'x_um', 'x_sim', 'x '])
    pos_y = find_col(['pos_y', 'y_nm', 'y_um', 'y_sim', 'y '])
    pos_z = find_col(['pos_z', 'z_nm', 'z_um', 'z_sim', 'z '])
    vel_x = find_col(['vel_x', 'vx'])
    vel_y = find_col(['vel_y', 'vy'])
    vel_z = find_col(['vel_z', 'vz'])
    phases = find_col(['phase', 'theta', 'hue'])
    spins = find_col(['spin', 'vorticity'], default_val=0.5)

    # Convert units
    masses = _convert_masses(masses_raw, mass_unit)
    positions = _convert_positions(pos_x, pos_y, pos_z, pos_unit)
    velocities = np.column_stack([vel_x, vel_y, vel_z])

    state = _build_state_vector(
        masses, positions, velocities,
        np.array(phases), np.array(spins)
    )

    # CSV doesn't encode entanglement — default to nearest-neighbor chain
    adjacency = _build_adjacency_chain(n)

    metadata = {
        'name': Path(filepath).stem,
        'source': filepath,
        'format': 'csv',
        'mass_unit': mass_unit,
        'position_unit': pos_unit,
        'num_particles': n,
    }

    return state, adjacency, metadata


# ---------------------------------------------------------------------------
# TOML Parser
# ---------------------------------------------------------------------------
def _parse_toml(filepath: str) -> Tuple[torch.Tensor, torch.Tensor, dict]:
    """
    Parse a TOML configuration file with structured sections.

    Expected sections: [system], [particles], [coupling], [entanglement], [integration]
    """
    import tomllib

    with open(filepath, 'rb') as f:
        data = tomllib.load(f)

    # System
    system = data.get('system', {})
    n = system.get('num_particles', 4)
    name = system.get('name', Path(filepath).stem)

    # Particles
    particles = data.get('particles', {})
    mass_raw = particles.get('mass', [1.0] * n)
    mass_unit = particles.get('mass_unit', 'mev')
    pos_x = particles.get('position_x', [0.0] * n)
    pos_y = particles.get('position_y', [0.0] * n)
    pos_z = particles.get('position_z', [0.0] * n)
    pos_unit = particles.get('position_unit', 'sim')
    vel_x = particles.get('velocity_x', [0.0] * n)
    vel_y = particles.get('velocity_y', [0.0] * n)
    vel_z = particles.get('velocity_z', [0.0] * n)
    phases = particles.get('phase', [0.0] * n)
    spins = particles.get('spin', [0.5] * n)

    # Convert
    masses = _convert_masses(mass_raw, mass_unit)
    positions = _convert_positions(pos_x, pos_y, pos_z, pos_unit)
    velocities = np.column_stack([vel_x, vel_y, vel_z])

    state = _build_state_vector(
        masses, positions, velocities,
        np.array(phases), np.array(spins)
    )

    # Entanglement
    ent = data.get('entanglement', {})
    ent_type = ent.get('type', '')
    if ent_type == 'all_to_all':
        adjacency = torch.ones((n, n), dtype=torch.bool)
        adjacency.fill_diagonal_(False)
    else:
        pairs = ent.get('adjacency', [])
        adjacency = _build_adjacency(pairs, n)

    metadata = {
        'name': name,
        'source': filepath,
        'format': 'toml',
        'mass_unit': mass_unit,
        'position_unit': pos_unit,
        'num_particles': n,
        'raw_toml': data,
    }

    return state, adjacency, metadata


# ---------------------------------------------------------------------------
# Markdown Parser
# ---------------------------------------------------------------------------
def _parse_markdown(filepath: str) -> Tuple[torch.Tensor, torch.Tensor, dict]:
    """
    Parse a Markdown lab notebook with optional YAML frontmatter,
    pipe-delimited particle tables, and topological connection lists.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # --- YAML Frontmatter ---
    frontmatter = {}
    fm_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).strip().split('\n'):
            if ':' in line:
                key, val = line.split(':', 1)
                frontmatter[key.strip()] = val.strip()

    # --- Particle Table ---
    # Find markdown tables (pipe-delimited)
    table_pattern = re.compile(
        r'^\|(.+)\|\s*\n\|[-| :]+\|\s*\n((?:\|.+\|\s*\n?)+)',
        re.MULTILINE
    )
    tables = table_pattern.findall(content)

    particles = []
    table_headers = []
    for header_line, body in tables:
        headers = [h.strip().lower() for h in header_line.split('|') if h.strip()]
        # Check if this looks like a particle table
        if any(kw in ' '.join(headers) for kw in ['mass', 'node', 'pos', 'x ']):
            table_headers = headers
            for row_line in body.strip().split('\n'):
                cells = [c.strip() for c in row_line.split('|') if c.strip()]
                if cells and not cells[0].startswith('-'):
                    particles.append(cells)
            break

    if not particles:
        raise ValueError(
            f"No particle table found in {filepath}. "
            "Expected a markdown table with columns containing 'mass', 'x', 'phase'."
        )

    n = len(particles)

    # Map columns by header keywords
    def find_table_col(keywords: list, default: float = 0.0) -> List[float]:
        for kw in keywords:
            for i, h in enumerate(table_headers):
                if kw in h:
                    try:
                        return [float(particles[r][i]) for r in range(n)]
                    except (IndexError, ValueError):
                        pass
        return [default] * n

    # Detect units from headers
    mass_unit = 'mev'
    for h in table_headers:
        if 'amu' in h:
            mass_unit = 'amu'
        elif 'kg' in h:
            mass_unit = 'kg'

    pos_unit = 'sim'
    for h in table_headers:
        if 'nm' in h:
            pos_unit = 'nm'
        elif 'um' in h or 'µm' in h:
            pos_unit = 'um'

    masses_raw = find_table_col(['mass'], default=1.0)
    pos_x = find_table_col(['x ', 'pos_x', 'x(', 'x_'])
    pos_y = find_table_col(['y ', 'pos_y', 'y(', 'y_'])
    pos_z = find_table_col(['z ', 'pos_z', 'z(', 'z_'])
    phases = find_table_col(['phase', 'theta', 'hue'])
    spins = find_table_col(['spin', 'vorticity'], default=0.5)

    masses = _convert_masses(masses_raw, mass_unit)
    positions = _convert_positions(pos_x, pos_y, pos_z, pos_unit)
    velocities = np.zeros((n, 3))  # MD tables typically don't include velocity

    state = _build_state_vector(
        masses, positions, velocities,
        np.array(phases), np.array(spins)
    )

    # --- Topological Connections ---
    pairs = []
    conn_pattern = re.compile(r'Node\s*(\d+)\s*<->\s*Node\s*(\d+)', re.IGNORECASE)
    for m in conn_pattern.finditer(content):
        pairs.append([int(m.group(1)), int(m.group(2))])

    adjacency = _build_adjacency(pairs, n) if pairs else _build_adjacency_chain(n)

    metadata = {
        'name': frontmatter.get('Experiment', Path(filepath).stem),
        'source': filepath,
        'format': 'markdown',
        'mass_unit': mass_unit,
        'position_unit': pos_unit,
        'num_particles': n,
        'frontmatter': frontmatter,
    }

    return state, adjacency, metadata

# ---------------------------------------------------------------------------
# NPY Parser (Lattlib Grid Import)
# ---------------------------------------------------------------------------
def _parse_npy(filepath: str) -> Tuple[torch.Tensor, torch.Tensor, dict]:
    """
    Parse a Lattlib .npy complex grid matrix.
    Since this is a raw field and not a list of particles, we return
    a dummy state vector of 0 particles, but package the grid in the metadata
    so the engine can extract it during reset() if configured to do so.
    """
    import numpy as np
    
    grid_data = np.load(filepath)
    
    # We return a dummy 0-particle state vector.
    state = torch.zeros((0, 10), dtype=torch.float32)
    adjacency = torch.zeros((0, 0), dtype=torch.bool)
    
    metadata = {
        'name': Path(filepath).stem,
        'source': filepath,
        'format': 'npy',
        'num_particles': 0,
        'grid_data': grid_data,  # Pass the raw grid through
    }
    
    return state, adjacency, metadata



# ---------------------------------------------------------------------------
# State Vector Builder
# ---------------------------------------------------------------------------
def _build_state_vector(
    masses: np.ndarray,
    positions: np.ndarray,
    velocities: np.ndarray,
    phases: np.ndarray,
    spins: np.ndarray,
) -> torch.Tensor:
    """
    Build the 10-dimensional state vector from raw arrays.

    Layout: [t, x, y, z, px, py, pz, m0, theta_hue, gamma]

    - t = 0 for all particles at initialization
    - momentum p = m0 * gamma * v
    - gamma = 1 / sqrt(1 - v^2/c^2) with c = C_SIM
    """
    n = len(masses)
    masses = np.asarray(masses, dtype=np.float64)
    positions = np.asarray(positions, dtype=np.float64).reshape(n, 3)
    velocities = np.asarray(velocities, dtype=np.float64).reshape(n, 3)
    phases = np.asarray(phases, dtype=np.float64)

    # Compute gamma from velocity
    v_sq = np.sum(velocities**2, axis=1)
    beta_sq = v_sq / (C_SIM**2)
    beta_sq = np.clip(beta_sq, 0.0, 0.9999)  # prevent division by zero
    gamma = 1.0 / np.sqrt(1.0 - beta_sq)

    # Momentum: p = m0 * gamma * v
    momentum = masses[:, np.newaxis] * gamma[:, np.newaxis] * velocities

    # Assemble state vector
    state = np.zeros((n, 10), dtype=np.float64)
    state[:, 0] = 0.0           # t
    state[:, 1:4] = positions   # x, y, z
    state[:, 4:7] = momentum    # px, py, pz
    state[:, 7] = masses        # m0
    state[:, 8] = phases         # theta_hue
    state[:, 9] = gamma         # gamma

    return torch.tensor(state, dtype=torch.float32)


# ---------------------------------------------------------------------------
# Adjacency Matrix Builder
# ---------------------------------------------------------------------------
def _build_adjacency(pairs: List[list], n_particles: int) -> torch.Tensor:
    """
    Build a symmetric boolean adjacency matrix from an edge list.

    Parameters
    ----------
    pairs : list of [i, j] pairs defining entangled connections.
    n_particles : total number of particles.
    """
    W = torch.zeros(n_particles, n_particles, dtype=torch.bool)
    for pair in pairs:
        i, j = int(pair[0]), int(pair[1])
        if 0 <= i < n_particles and 0 <= j < n_particles:
            W[i, j] = True
            W[j, i] = True
    return W


def _build_adjacency_chain(n: int) -> torch.Tensor:
    """Build nearest-neighbor chain: 0-1, 1-2, ..., (n-2)-(n-1)."""
    pairs = [[i, i + 1] for i in range(n - 1)]
    return _build_adjacency(pairs, n)


# ---------------------------------------------------------------------------
# Unit Detection & Conversion Helpers
# ---------------------------------------------------------------------------
def _detect_unit(headers: List[str], col_keyword: str, default: str = 'sim') -> str:
    """Detect unit suffix from column headers (e.g., mass_amu → 'amu')."""
    for h in headers:
        if col_keyword in h:
            if 'amu' in h:
                return 'amu'
            elif 'mev' in h:
                return 'mev'
            elif 'kg' in h:
                return 'kg'
            elif 'nm' in h:
                return 'nm'
            elif 'um' in h or 'µm' in h:
                return 'um'
    return default


def _convert_masses(raw: list, unit: str) -> np.ndarray:
    """Convert mass values to simulation units (MeV/c^2)."""
    arr = np.array(raw, dtype=np.float64)
    if unit == 'amu':
        return arr * AMU_TO_MEV
    elif unit == 'kg':
        return np.array([kg_to_mev(m) for m in arr])
    else:  # mev or dimensionless
        return arr


def _convert_positions(
    x: list, y: list, z: list, unit: str
) -> np.ndarray:
    """Convert position values to simulation units."""
    pos = np.column_stack([x, y, z]).astype(np.float64)
    if unit == 'nm':
        # Scale: 680nm (lattice constant) → 1.0 sim unit
        # This makes the Bose-Hubbard lattice spacing = 1.0
        scale = 680.0
        pos /= scale
    elif unit == 'um':
        pos /= 680.0e-3  # micrometers
    return pos


# ---------------------------------------------------------------------------
# Self-Test
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import sys

    test_csv = Path(__file__).parent / 'examples' / 'state_initialization.csv'
    test_md = Path(__file__).parent / 'examples' / 'experiment_init.md'
    test_toml = Path(__file__).parent / 'presets' / 'bose_hubbard_islam2015.toml'

    for path in [test_csv, test_md, test_toml]:
        if path.exists():
            print(f"\n--- Testing: {path.name} ---")
            try:
                state, adj, meta = load_experiment(str(path))
                print(f"  Particles: {meta['num_particles']}")
                print(f"  State shape: {state.shape}")
                print(f"  Adjacency shape: {adj.shape}")
                print(f"  Adjacency:\n{adj.int()}")
                print(f"  State vector (first particle):")
                labels = ['t', 'x', 'y', 'z', 'px', 'py', 'pz', 'm0', 'hue', 'gam']
                for i, label in enumerate(labels):
                    print(f"    {label:>3} = {state[0, i].item():.4f}")
                print("  [OK] PASS")
            except Exception as e:
                print(f"  [FAIL]: {e}")
                sys.exit(1)
        else:
            print(f"  [SKIP] {path.name} not found")

    print("\nAll ingest tests passed.")
