---
Experiment: 4-Site Bose-Hubbard Array
Date: 2026-07-20
Target Paper: Islam et al. 2015 (Nature)
Notes: Rb-87 atoms on 1D optical lattice, 680nm spacing
---

# Particle Inventory

| Node_ID | Mass (amu) | X (nm) | Y (nm) | Z (nm) | Phase (rad) | Spin |
|---------|------------|--------|--------|--------|-------------|------|
| 0       | 86.909     | 0.0    | 0.0    | 0.0    | 0.0         | 0.5  |
| 1       | 86.909     | 680.0  | 0.0    | 0.0    | 0.0         | 0.5  |
| 2       | 86.909     | 1360.0 | 0.0    | 0.0    | 0.0         | 0.5  |
| 3       | 86.909     | 2040.0 | 0.0    | 0.0    | 0.0         | 0.5  |

# Topological Connections

* Node 0 <-> Node 1
* Node 1 <-> Node 2
* Node 2 <-> Node 3

# Coupling Parameters

- Pauli Strength (U): 10.0
- Torsion Coupling (J): 1.0
- U/J Ratio: 10.0

# Integration

- dt: 0.001
- Total Ticks: 10000
- Grid Resolution: 64
