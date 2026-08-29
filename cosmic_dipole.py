import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from skimage import measure

def create_visual():
    # 1. Create a 3D grid
    grid_size = 60
    x = np.linspace(-1, 1, grid_size)
    y = np.linspace(-1, 1, grid_size)
    z = np.linspace(-1, 1, grid_size)
    X, Y, Z = np.meshgrid(x, y, z, indexing='ij')

    # 2. Define the topological well (rounded cube due to grid anisotropy)
    # Using L4 norm for a rounded cube shape
    phi = X**4 + Y**4 + Z**4
    
    # Isosurface threshold (event horizon)
    threshold = 0.4

    # 3. Extract the isosurface using marching cubes
    verts, faces, normals, values = measure.marching_cubes(phi, threshold, spacing=(x[1]-x[0], y[1]-y[0], z[1]-z[0]))
    
    # Shift vertices to be centered at (0,0,0)
    verts = verts - np.array([grid_size/2, grid_size/2, grid_size/2]) * (x[1]-x[0])

    # 4. Set up the plot
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')
    ax.set_facecolor('black')
    fig.patch.set_facecolor('black')

    # 5. Plot the rounded cube event horizon
    mesh = Poly3DCollection(verts[faces], alpha=0.15, edgecolor='cyan', linewidth=0.2)
    mesh.set_facecolor((0.0, 1.0, 1.0, 0.1))
    ax.add_collection3d(mesh)

    # 6. Plot the Core (Center of Collapse)
    ax.scatter([0], [0], [0], color='yellow', s=100, label='Core of Topological Well (Origin)', zorder=5)

    # 7. Plot Earth / Observable Universe (Off-center)
    earth_pos = np.array([0.4, 0.3, 0.2])
    ax.scatter([earth_pos[0]], [earth_pos[1]], [earth_pos[2]], color='lime', s=60, label='Earth / Local Web', zorder=5)

    # 8. Draw the Dipole Vector (Arrow from Earth to Core)
    # The dipole points up the gradient (or down the gradient)
    dipole_vector = -earth_pos # Pointing towards center
    ax.quiver(earth_pos[0], earth_pos[1], earth_pos[2], 
              dipole_vector[0], dipole_vector[1], dipole_vector[2], 
              color='magenta', length=1.0, arrow_length_ratio=0.15, linewidth=3, label='CMB Dipole Vector')

    # Format the plot
    ax.set_xlim([-1, 1])
    ax.set_ylim([-1, 1])
    ax.set_zlim([-1, 1])
    ax.set_axis_off()
    
    # Legend
    legend = ax.legend(loc='upper right', facecolor='black', edgecolor='white', fontsize=10)
    for text in legend.get_texts():
        text.set_color("white")

    plt.title('Topological Event Horizon & The Cosmic Dipole', color='white', fontsize=14, pad=20)
    
    plt.tight_layout()
    plt.savefig('cosmic_dipole_visual.png', dpi=300, facecolor='black')
    print("Saved 'cosmic_dipole_visual.png'")

if __name__ == "__main__":
    create_visual()
