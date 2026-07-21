import numpy as np
import matplotlib.pyplot as plt
import os

# 1. Load TEGR data
tegr_file = "Z:\\TEGR 2600\\Pablo Poggi\\TEGR_OAT_XY_16_NN.txt"
with open(tegr_file, "r") as f:
    lines = f.readlines()
tegr_times = np.array([float(x) for x in lines[0].split()])
tegr_s2 = np.array([float(x) for x in lines[1].split()])

# 2. Load Poggi's QFI data
# File: QFI_OAT_XY_MPS_normalized_16 _0 _6.283185307179586 _NN _256 _1000 _6.283185307179586.txt
poggi_file = "Z:\\TEGR 2600\\Pablo Poggi\\PUREdata\\FIG_1\\QFI_OAT_XY_MPS_normalized_16 _0 _6.283185307179586 _NN _256 _1000 _6.283185307179586.txt"
poggi_data = np.loadtxt(poggi_file)
poggi_times = poggi_data[0]
poggi_qfi = poggi_data[1]

# 3. Create the comparison plot
fig, ax1 = plt.subplots(figsize=(10, 6))

color1 = 'tab:blue'
ax1.set_xlabel('Time')
ax1.set_ylabel('TEGR 2600: S2 Entropy', color=color1)
ax1.plot(tegr_times, tegr_s2, color=color1, linewidth=3, label="TEGR S2 Entropy (1D Nearest Neighbor)")
ax1.tick_params(axis='y', labelcolor=color1)

ax2 = ax1.twinx()  
color2 = 'tab:red'
ax2.set_ylabel('Pablo Poggi: Quantum Fisher Information (QFI)', color=color2)  
ax2.plot(poggi_times, poggi_qfi, '--', color=color2, linewidth=3, label="Poggi QFI (N=16, NN)")
ax2.tick_params(axis='y', labelcolor=color2)

fig.suptitle('Verification: TEGR 2600 (Classical CPU) vs Poggi Metrology (Quantum MPS)')
fig.tight_layout()

# Save the plot
output_path = "Z:\\TEGR 2600\\output\\TEGR_vs_Poggi_Comparison.png"
plt.savefig(output_path, dpi=150)
print(f"Saved comparison plot to {output_path}")
