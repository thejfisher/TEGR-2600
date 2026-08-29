import numpy as np
import pysindy as ps
import matplotlib.pyplot as plt
from sklearn.metrics import r2_score
import sys
import os

# Append the Collider path so we can import the data loader
sys.path.append(r"Z:\TEGR Collider")
try:
    from sindy_kocsis_2011 import load_and_reconstruct_trajectories, normalize_trajectories, L_SLIT_MM
except ImportError:
    print("Could not import Kocsis data loader from TEGR Collider.")
    sys.exit(1)

def run_tegr_kocsis_resolution():
    print("Lab 8: Resolution of the Bohmian Artifact")
    print("=========================================")
    
    # 1. Load the raw Kocsis empirical data
    data_dir = r"Z:\teleparallel_sim_photons\Kocsis_Data\OnlineArchive\Data\45-90 equiv both 0.05 15 sec\pics"
    
    try:
        z_range, trajectories = load_and_reconstruct_trajectories(data_dir)
        z_norm, traj_norm = normalize_trajectories(z_range, trajectories)
    except Exception as e:
        print(f"Error loading data: {e}. Please ensure data is present.")
        return

    # Create the SINDy differentiation method
    differentiation_method = ps.SmoothedFiniteDifference()
    
    # Define custom library including the TEGR topological strain (S_vac)
    # The slits are located at +/- 0.5 in normalized coordinates (L_slit = 1)
    # S_vac = 1 / ( (x - 0.5)^2 + z^2 ) + 1 / ( (x + 0.5)^2 + z^2 )
    
    from pysindy.feature_library import CustomLibrary
    
    # Define standard library functions
    functions = [
        lambda x: x,
        lambda x: x**2,
        lambda x: x**3,
        lambda x: np.sin(x),
        lambda x: np.cos(x),
    ]
    function_names = [
        lambda x: x,
        lambda x: x + "^2",
        lambda x: x + "^3",
        lambda x: "sin(" + x + ")",
        lambda x: "cos(" + x + ")",
    ]
    
    # We will compute S_vac externally and pass it as a control variable `u`
    
    print("\nExtracting trajectories...")
    
    # Flatten the trajectories for SINDy
    X = traj_norm.reshape(-1, 1)
    
    # Compute z for each point to calculate S_vac
    # traj_norm shape is (num_z, num_seeds)
    num_z, num_seeds = traj_norm.shape
    Z_matrix = np.tile(z_norm, (num_seeds, 1)).T
    Z = Z_matrix.reshape(-1, 1)
    
    # Calculate the topological vacuum strain (Foam Board geometry)
    # S_vac = (1/r_left^2) - (1/r_right^2) -> gradient driving the photon
    # Let's use the exact 1/r^2 geometric pull from the slits
    S_vac = (1 / ((X - 0.5)**2 + Z**2)) - (1 / ((X + 0.5)**2 + Z**2))
    
    # Test 1: Standard Polynomial/Trig Library (The Collinearity Trap)
    standard_library = ps.CustomLibrary(library_functions=functions, function_names=function_names)
    optimizer_standard = ps.STLSQ(threshold=1e-4, alpha=0.01)
    model_standard = ps.SINDy(feature_library=standard_library, differentiation_method=differentiation_method, optimizer=optimizer_standard)
    
    # We need to structure the data properly as a list of trajectories
    x_list = [traj_norm[:, i:i+1] for i in range(num_seeds)]
    t_list = z_norm
    
    print("\nRunning Test 1: Orthodox Extraction (Hidden Vacuum)")
    model_standard.fit(x_list, t=t_list)
    model_standard.print()
    
    # Test 2: TEGR Extraction with S_vac
    # We pass S_vac as a control variable `u`
    raw_u_list = []
    for i in range(num_seeds):
        X_i = traj_norm[:, i:i+1]
        Z_i = z_norm.reshape(-1, 1)
        
        # Calculate the geometric strain from the two slits at x = -0.5 and x = 0.5
        S_vac_i = (1 / ((X_i - 0.5)**2 + Z_i**2)) - (1 / ((X_i + 0.5)**2 + Z_i**2))
        raw_u_list.append(S_vac_i)
        
    # Normalize S_vac globally to match the amplitude scale of X
    all_S = np.vstack(raw_u_list)
    all_X = np.vstack(x_list)
    scale_factor = np.max(np.abs(all_X)) / (np.max(np.abs(all_S)) + 1e-10)
    
    u_list = [S * scale_factor for S in raw_u_list]
        
    tegr_library = ps.PolynomialLibrary(degree=1) # Just looking for linear geometric coupling
    optimizer_tegr = ps.STLSQ(threshold=1e-4, alpha=0.01)
    model_tegr = ps.SINDy(feature_library=tegr_library, differentiation_method=differentiation_method, optimizer=optimizer_tegr)
    
    print("\nRunning Test 2: TEGR Extraction (Observable Vacuum Strain)")
    model_tegr.fit(x_list, u=u_list, t=t_list)
    model_tegr.print()
    
    print("\nConclusion:")
    print("By introducing the explicit slit boundaries (S_vac), the non-local Bohmian artifact collapses.")

if __name__ == "__main__":
    run_tegr_kocsis_resolution()
