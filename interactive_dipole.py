import numpy as np
import plotly.graph_objects as go
from skimage import measure

def create_interactive_visual():
    # 1. Create a 3D grid
    grid_size = 60
    x = np.linspace(-1, 1, grid_size)
    y = np.linspace(-1, 1, grid_size)
    z = np.linspace(-1, 1, grid_size)
    X, Y, Z = np.meshgrid(x, y, z, indexing='ij')

    # 2. Define the topological well (rounded cube due to grid anisotropy)
    phi = X**4 + Y**4 + Z**4
    threshold = 0.4

    # 3. Extract the isosurface using marching cubes
    verts, faces, normals, values = measure.marching_cubes(phi, threshold, spacing=(x[1]-x[0], y[1]-y[0], z[1]-z[0]))
    verts = verts - np.array([grid_size/2, grid_size/2, grid_size/2]) * (x[1]-x[0])

    # 4. Create the Plotly Figure
    fig = go.Figure()

    # Add the Isosurface (Event Horizon)
    fig.add_trace(go.Mesh3d(
        x=verts[:, 0],
        y=verts[:, 1],
        z=verts[:, 2],
        i=faces[:, 0],
        j=faces[:, 1],
        k=faces[:, 2],
        opacity=0.2,
        color='cyan',
        name='Topological Event Horizon'
    ))

    # Add the Core (Origin)
    fig.add_trace(go.Scatter3d(
        x=[0], y=[0], z=[0],
        mode='markers',
        marker=dict(size=8, color='yellow', symbol='circle'),
        name='Core of Topological Well (Origin)'
    ))

    # Add Earth (Off-center)
    earth_pos = np.array([0.4, 0.3, 0.2])
    fig.add_trace(go.Scatter3d(
        x=[earth_pos[0]], y=[earth_pos[1]], z=[earth_pos[2]],
        mode='markers',
        marker=dict(size=6, color='lime', symbol='circle'),
        name='Earth / Local Web'
    ))

    # Add the Observable Universe (Sphere around Earth) with CMB Mapping
    obs_radius = 0.25
    u, v = np.mgrid[0:2*np.pi:60j, 0:np.pi:40j]
    
    # Unit normal vectors on the sphere
    nx = np.cos(u) * np.sin(v)
    ny = np.sin(u) * np.sin(v)
    nz = np.cos(v)
    
    obs_x = earth_pos[0] + obs_radius * nx
    obs_y = earth_pos[1] + obs_radius * ny
    obs_z = earth_pos[2] + obs_radius * nz
    
    # Calculate CMB Temperature Mapping
    # 1. Dipole: projection of the normal vector onto the direction towards the core
    dipole_dir = -earth_pos / np.linalg.norm(earth_pos)
    T_dipole = nx * dipole_dir[0] + ny * dipole_dir[1] + nz * dipole_dir[2]
    
    # 2. Quadrupole (Grid Anisotropy): Oh symmetry invariant (x^4 + y^4 + z^4)
    # The grid structure modulates the temperature, creating the "Axis of Evil" alignments
    base_grid = nx**4 + ny**4 + nz**4
    
    # 3. Primordial Acoustic Oscillations (High-frequency "splotchy" texture)
    # This simulates the small-scale acoustic peaks seen in WMAP/Planck maps
    splotchy_noise = (np.sin(20*nx) * np.cos(25*ny) + np.sin(22*ny) * np.cos(18*nz) + np.sin(24*nz) * np.cos(21*nx))
    splotchy_noise += 0.5 * (np.sin(45*nx) * np.cos(40*ny) + np.sin(42*ny) * np.cos(38*nz) + np.sin(48*nz) * np.cos(41*nx))
    
    T_grid = base_grid + 0.2 * splotchy_noise
    
    # Combine into a CMB map (Dipole is the massive gradient, grid is the underlying texture)
    cmb_combined = 1.0 * T_dipole + 0.3 * T_grid
    cmb_clear = np.zeros_like(T_dipole)
    
    # Custom Colorscale for CMB (Dark Blue -> Transparent -> Dark Red)
    cmb_colorscale = [
        [0.0, 'rgba(0, 0, 139, 1.0)'],   # Dark Blue
        [0.2, 'rgba(0, 0, 139, 0.8)'],   
        [0.45, 'rgba(0, 0, 0, 0.0)'],    # Clear
        [0.55, 'rgba(0, 0, 0, 0.0)'],    # Clear
        [0.8, 'rgba(139, 0, 0, 0.8)'],   
        [1.0, 'rgba(139, 0, 0, 1.0)']    # Dark Red
    ]
    
    # --- The Predictive Out-of-Bounds Sphere (Topological Triangulation) ---
    pred_radius = 0.55  # Extends past the observable sphere
    pred_x = earth_pos[0] + pred_radius * nx
    pred_y = earth_pos[1] + pred_radius * ny
    pred_z = earth_pos[2] + pred_radius * nz
    
    # Map the gradient equation to the outer sphere
    pred_T_dipole = nx * dipole_dir[0] + ny * dipole_dir[1] + nz * dipole_dir[2]
    pred_T_grid = nx**4 + ny**4 + nz**4 + 0.2 * splotchy_noise
    pred_cmb_combined = 1.0 * pred_T_dipole + 0.3 * pred_T_grid
    
    # Clamp the predictive sphere so it doesn't extend outside the Event Horizon
    # The event horizon is defined by x^4 + y^4 + z^4 = 0.4
    # Anything outside this is in the Parent Universe, where our internal CMB plasma does not exist.
    outside_horizon = (pred_x**4 + pred_y**4 + pred_z**4) > 0.4
    
    # We set the surfacecolor to NaN for points outside the horizon to clip the sphere
    pred_cmb_combined[outside_horizon] = np.nan
    pred_T_dipole[outside_horizon] = np.nan
    pred_T_grid[outside_horizon] = np.nan
    
    # Create an opacity gradient (dark/opaque near the inner sphere, fading to transparent on the outside)
    # Plotly doesn't natively support per-vertex opacity on Surface without tricks, 
    # but we can simulate the "fade to light/transparent" by altering the colorscale 
    # and dropping the overall opacity.
    
    fig.add_trace(go.Surface(
        x=pred_x, y=pred_y, z=pred_z,
        surfacecolor=pred_cmb_combined,
        opacity=0.35,  # Increased slightly to make the dark colors visible
        colorscale=cmb_colorscale, 
        showscale=False,
        name='Predicted Extrapolation (Unobservable)'
    ))
    # -----------------------------------------------------------------------

    fig.add_trace(go.Surface(
        x=obs_x, y=obs_y, z=obs_z,
        surfacecolor=cmb_combined,
        opacity=0.9,
        colorscale=cmb_colorscale,
        showscale=True,
        colorbar=dict(title=dict(text='CMB Anisotropy', font=dict(color='white')), x=0.85, tickfont=dict(color='white')),
        name='Observable Universe (CMB Map)'
    ))

    # Add the Dipole Vector (Arrow from Earth to Core)
    dipole_vector = -earth_pos
    
    # We draw the arrow as a line segment
    fig.add_trace(go.Scatter3d(
        x=[earth_pos[0], earth_pos[0] + dipole_vector[0]*0.9],
        y=[earth_pos[1], earth_pos[1] + dipole_vector[1]*0.9],
        z=[earth_pos[2], earth_pos[2] + dipole_vector[2]*0.9],
        mode='lines',
        line=dict(color='magenta', width=5),
        name='CMB Dipole Vector'
    ))
    
    # Add a cone to simulate the arrowhead
    fig.add_trace(go.Cone(
        x=[earth_pos[0] + dipole_vector[0]*0.9],
        y=[earth_pos[1] + dipole_vector[1]*0.9],
        z=[earth_pos[2] + dipole_vector[2]*0.9],
        u=[dipole_vector[0]],
        v=[dipole_vector[1]],
        w=[dipole_vector[2]],
        sizemode='absolute',
        sizeref=0.1,
        anchor='tip',
        colorscale=[[0, 'magenta'], [1, 'magenta']],
        showscale=False,
        name='Vector Head'
    ))

    # Layout and Formatting
    fig.update_layout(
        title='Topological Event Horizon & The Cosmic Dipole',
        scene=dict(
            xaxis=dict(visible=False, range=[-1, 1]),
            yaxis=dict(visible=False, range=[-1, 1]),
            zaxis=dict(visible=False, range=[-1, 1]),
            bgcolor='black'
        ),
        paper_bgcolor='black',
        font=dict(color='white'),
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01
        ),
        updatemenus=[
            dict(
                type="buttons",
                direction="down",
                x=0.01,
                y=0.90,
                xanchor="left",
                yanchor="top",
                font=dict(color="black"),
                bgcolor="white",
                buttons=list([
                    dict(
                        label="Inner: Combined CMB",
                        method="restyle",
                        args=[{"surfacecolor": [cmb_combined]}, [4]]
                    ),
                    dict(
                        label="Inner: Dipole Only",
                        method="restyle",
                        args=[{"surfacecolor": [T_dipole]}, [4]]
                    ),
                    dict(
                        label="Inner: Thermal Grid",
                        method="restyle",
                        args=[{"surfacecolor": [T_grid]}, [4]]
                    ),
                    dict(
                        label="Inner: Clear",
                        method="restyle",
                        args=[{"surfacecolor": [cmb_clear]}, [4]]
                    )
                ])
            ),
            dict(
                type="buttons",
                direction="down",
                x=0.01,
                y=0.65,
                xanchor="left",
                yanchor="top",
                font=dict(color="black"),
                bgcolor="white",
                buttons=list([
                    dict(
                        label="Outer: Extrapolated Combined",
                        method="restyle",
                        args=[{"surfacecolor": [pred_cmb_combined], "visible": [True]}, [3]]
                    ),
                    dict(
                        label="Outer: Extrapolated Dipole",
                        method="restyle",
                        args=[{"surfacecolor": [pred_T_dipole], "visible": [True]}, [3]]
                    ),
                    dict(
                        label="Outer: Extrapolated Grid",
                        method="restyle",
                        args=[{"surfacecolor": [pred_T_grid], "visible": [True]}, [3]]
                    ),
                    dict(
                        label="Outer: Hidden",
                        method="restyle",
                        args=[{"visible": [False]}, [3]]
                    )
                ])
            )
        ]
    )

    # Save to HTML so it's fully interactive
    fig.write_html("interactive_cosmic_dipole.html")
    print("Saved 'interactive_cosmic_dipole.html'")

if __name__ == "__main__":
    create_interactive_visual()
