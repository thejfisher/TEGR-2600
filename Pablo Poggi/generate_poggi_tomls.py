import os

def generate_toml(filename, name, coordinates):
    N = len(coordinates)
    x = [c[0] for c in coordinates]
    y = [c[1] for c in coordinates]
    z = [c[2] for c in coordinates]
    
    toml_str = f"""# {name}
[system]
name = "{name}"
num_particles = {N}

[particles]
mass = [{', '.join(['1.0']*N)}]
mass_unit = "mev"
position_x = [{', '.join(map(str, x))}]
position_y = [{', '.join(map(str, y))}]
position_z = [{', '.join(map(str, z))}]
position_unit = "sim"
phase = [{', '.join(['0.0']*N)}]
velocity_x = [{', '.join(['0.0']*N)}]
spin = [{', '.join(['0.5']*N)}]

[coupling]
pauli_strength = 10.0
torsion_coupling = 1.0
kuramoto_k = 0.0
vacuum_damping = 0.007

[integration]
dt = 0.001
total_ticks = 10000
grid_resolution = 64
wave_speed = 65.0
wave_decay = 0.9999

[output]
save_trajectories = true
save_plots = false
plot_format = "png"
"""
    with open(filename, 'w') as f:
        f.write(toml_str)
    print(f"Generated {filename}")

def main():
    spacing = 2.0  # TIGHT SPACING SO PARTICLES INTERACT!
    N = 16
    
    # 1. 1D Line (Nearest Neighbor)
    coords_1d = [(i * spacing, 0.0, 0.0) for i in range(N)]
    generate_toml('Z:\\TEGR 2600\\presets\\poggi_16_1D.toml', "Poggi 16-Atom 1D Chain", coords_1d)
    
    # 2. 2D Grid (4x4)
    coords_2d = []
    for i in range(4):
        for j in range(4):
            coords_2d.append((i * spacing, j * spacing, 0.0))
    generate_toml('Z:\\TEGR 2600\\presets\\poggi_16_2D.toml', "Poggi 16-Atom 2D Grid", coords_2d)

if __name__ == "__main__":
    main()
