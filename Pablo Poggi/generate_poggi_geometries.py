import csv
import math

def generate_csv(filename, coordinates, mass=1.0, vel=(0.0, 0.0, 0.0), phase=0.0, spin=0.5):
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['node_id', 'mass_mev', 'pos_x', 'pos_y', 'pos_z', 'vel_x', 'vel_y', 'vel_z', 'phase_rad', 'spin_vorticity'])
        for i, (x, y, z) in enumerate(coordinates):
            writer.writerow([i, mass, x, y, z, vel[0], vel[1], vel[2], phase, spin])
    print(f"Generated {filename} with {len(coordinates)} particles.")

def main():
    spacing = 500.0
    N = 64
    
    # 1. 1D Line (Nearest Neighbor mapping)
    coords_1d = [(i * spacing, 0.0, 0.0) for i in range(N)]
    generate_csv('poggi_N64_1D_line.csv', coords_1d)
    
    # 2. 2D Grid (8x8)
    coords_2d = []
    for i in range(8):
        for j in range(8):
            coords_2d.append((i * spacing, j * spacing, 0.0))
    generate_csv('poggi_N64_2D_grid.csv', coords_2d)
    
    # 3. 3D Grid (4x4x4)
    coords_3d = []
    for i in range(4):
        for j in range(4):
            for k in range(4):
                coords_3d.append((i * spacing, j * spacing, k * spacing))
    generate_csv('poggi_N64_3D_grid.csv', coords_3d)

if __name__ == "__main__":
    main()
