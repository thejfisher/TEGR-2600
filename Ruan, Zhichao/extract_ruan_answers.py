import scipy.io as sio
import numpy as np
import os

base_dir = os.path.dirname(os.path.abspath(__file__))

def extract_answers(graph_name):
    mat_path = os.path.join(base_dir, f'Experimentdata{graph_name}.mat')
    if not os.path.exists(mat_path):
        return

    data = sio.loadmat(mat_path)['Experimentdata']
    
    # Rows 2 to 101 (indices 2 to 101) contain the 100 experimental runs.
    # Column 0: detected intensity array
    # Column 1: Hamiltonian array
    # Column 2: Spin states variation array (shape: n_steps x 16)
    
    final_states = []
    final_energies = []

    # Iterate over the 100 experimental runs
    for run_idx in range(2, 102):
        if run_idx >= data.shape[0]:
            break
            
        run_data = data[run_idx]
        if len(run_data) < 3:
            continue
            
        energies = run_data[1]
        spins_evolution = run_data[2]
        
        # The final spin state at the end of the annealing process
        if spins_evolution.shape[1] > 0:
            final_spin = spins_evolution[:, -1]
            # Convert binary {0, 1} to {-1, 1} for Ising if needed, or keep as is.
            # Ruan data uses 0 and 1 or -1 and 1. We just grab it raw.
            # Ensure it's a 1D array of integers
            final_spin = np.round(final_spin).astype(int).flatten()
            final_states.append(tuple(final_spin))
            
            if len(energies) > 0:
                final_energies.append(energies[-1][0] if isinstance(energies[-1], np.ndarray) else energies[-1])

    # Find the most frequent ground states discovered by Ruan's experiment
    from collections import Counter
    state_counts = Counter(final_states)
    
    print(f"=== Ruan Graph {graph_name} Experimental Answers ===")
    print(f"Total runs analyzed: {len(final_states)}")
    print("Most frequent final spin configurations (Top 5):")
    for state, count in state_counts.most_common(5):
        # Find corresponding energy for this state
        idx = final_states.index(state)
        energy = final_energies[idx] if idx < len(final_energies) else "Unknown"
        
        state_str = "".join(map(str, state))
        # Replace -1 with - for compactness if it uses -1
        state_str = state_str.replace('-1', '-')
        print(f"  [{state_str}] - Count: {count}/100, Final Energy: {energy}")
    print("\n")

if __name__ == "__main__":
    for g in ['A', 'B', 'C']:
        extract_answers(g)
