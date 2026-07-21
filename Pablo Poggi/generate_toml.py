def main():
    spacing = 500.0
    x, y, z = [], [], []
    for i in range(4):
        for j in range(4):
            for k in range(4):
                x.append(i * spacing)
                y.append(j * spacing)
                z.append(k * spacing)
                
    N = 64
    
    toml_str = f"""# Poggi 2025 - 64-Atom 3D Optical Tweezer Grid
[system]
name = "Poggi 2025 - 64-Atom 3D Optical Tweezer Grid"
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
save_plots = true
plot_format = "png"
"""
    
    with open('Z:\\TEGR 2600\\presets\\poggi_metrology_3D_grid.toml', 'w') as f:
        f.write(toml_str)
        
    print("Generated Z:\\TEGR 2600\\presets\\poggi_metrology_3D_grid.toml")

if __name__ == "__main__":
    main()
