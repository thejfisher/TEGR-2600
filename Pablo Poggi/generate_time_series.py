import numpy as np
import os
import csv

def compute_s2_over_time(trajectory_file, output_txt, half_cut_indices=None):
    if not os.path.exists(trajectory_file):
        print(f"File not found: {trajectory_file}")
        return

    # trajectory shape: (T, N, 10)
    # Col 8 is hue (phase)
    traj = np.load(trajectory_file)
    T, N, _ = traj.shape
    hues = traj[:, :, 8]
    
    if half_cut_indices is None:
        # Default to splitting the system in half (e.g. left and right)
        half_cut_indices = list(range(N // 2))

    print(f"Processing {T} timesteps for N={N}...")
    
    times = []
    s2_values = []
    
    for t in range(T):
        # Detrend mean phase at this timestep to remove common Compton clock
        mean_phase = np.mean(hues[t])
        detrended = hues[t] - mean_phase
        
        # Coherence matrix for this single timestep
        # C_ij = cos(theta_i - theta_j)
        dtheta = detrended[:, np.newaxis] - detrended[np.newaxis, :]
        coherence = np.cos(dtheta)
        
        # Purity of the subsystem A
        sub = coherence[np.ix_(half_cut_indices, half_cut_indices)]
        purity = float(np.clip(np.mean(sub), 0.0, 1.0))
        
        # S2 = -log(Tr(rho^2))
        s2 = -np.log(max(purity, 1e-10))
        
        times.append(t * 0.001)  # Assuming dt=0.001
        s2_values.append(s2)
        
    with open(output_txt, 'w') as f:
        # Match Poggi format: row of times, row of values? 
        # Wait, Poggi's format: "Coloumn 1 contains the value of time, Coloumn 2 contains the value of Quantum Fisher information"
        # Wait, the txt file we looked at had a row of times, and a row of QFI! 
        # Ah, it was 2 lines. Line 1 = time, Line 2 = QFI. Let's output it exactly like that.
        f.write(" ".join([f"{t:e}" for t in times]) + "\n")
        f.write(" ".join([f"{s:e}" for s in s2_values]) + "\n")
        
    print(f"Saved time-series S2 to {output_txt}")

if __name__ == "__main__":
    compute_s2_over_time("Z:\\TEGR 2600\\output\\trajectory.npy", "Z:\\TEGR 2600\\Pablo Poggi\\TEGR_S2_TimeSeries.txt")
