import scipy.io as sio
import numpy as np
import os

base_dir = os.path.dirname(os.path.abspath(__file__))

for graph in ['A', 'B', 'C']:
    mat_path = os.path.join(base_dir, f'Experimentdata{graph}.mat')
    data = sio.loadmat(mat_path)['Experimentdata']
    J_matrix = data[0, 0]
    N = J_matrix.shape[0]
    
    # Build entanglement pairs from J matrix (upper triangle, non-zero)
    pairs = []
    for i in range(N):
        for j in range(i+1, N):
            if J_matrix[i, j] != 0.0:
                pairs.append([i, j])
    
    # Spread 16 particles on a 4x4 grid
    pos_x = [(i % 4) * 10.0 for i in range(N)]
    pos_y = [(i // 4) * 10.0 for i in range(N)]
    pos_z = [0.0] * N
    
    # Random initial phases: 0 or pi (Ising binary spin mapping)
    np.random.seed(42 + ord(graph))
    phases = [round(float(p), 6) for p in np.random.choice([0.0, np.pi], size=N)]
    
    # Build the TOML string
    toml_lines = []
    toml_lines.append(f'# Ruan Graph {graph} - Max-Cut Spin Glass Benchmark')
    toml_lines.append(f'# {N} nodes, {len(pairs)} entangled pairs')
    toml_lines.append(f'# Source: Ruan, Zhichao et al. - Experimental data for Max-Cut problem')
    toml_lines.append('')
    toml_lines.append('[system]')
    toml_lines.append(f'name = "Ruan_SpinGlass_Graph_{graph}"')
    toml_lines.append(f'num_particles = {N}')
    toml_lines.append('')
    toml_lines.append('[particles]')
    toml_lines.append(f'mass = {[0.511] * N}')
    toml_lines.append(f'mass_unit = "mev"')
    toml_lines.append(f'position_x = {pos_x}')
    toml_lines.append(f'position_y = {pos_y}')
    toml_lines.append(f'position_z = {pos_z}')
    toml_lines.append(f'position_unit = "sim"')
    toml_lines.append(f'velocity_x = {[0.0] * N}')
    toml_lines.append(f'velocity_y = {[0.0] * N}')
    toml_lines.append(f'velocity_z = {[0.0] * N}')
    toml_lines.append(f'phase = {phases}')
    toml_lines.append(f'spin = {[0.5] * N}')
    toml_lines.append('')
    toml_lines.append('[entanglement]')
    toml_lines.append(f'adjacency = {pairs}')
    toml_lines.append('')

    output_path = os.path.join(base_dir, f'ruan_graph_{graph}.toml')
    with open(output_path, 'w') as f:
        f.write('\n'.join(toml_lines))
    
    print(f'Graph {graph}: {N} particles, {len(pairs)} entangled pairs -> {output_path}')
