import numpy as np
import matplotlib.pyplot as plt 


FIG=3
datdir='../PUREdata/Fig_{0}/'.format(FIG)
Random_vals=[1,8,16,20]

coupling_labels = ["A2A", "pwr2", "hyp","NN","PL3","PL2","PL1"]
for c in range (len(coupling_labels)):
  coupling = coupling_labels[c]
  Fname = datdir+"Analytical_Gap_{0}.txt".format(coupling)
  Number_of_spins, analytical_val = np.loadtxt(Fname)
  plt.plot(Number_of_spins, analytical_val,label=f"{coupling}")
plt.legend()
plt.xlabel("N")
plt.ylabel("Spectral Gap")
plt.xscale("log")
plt.yscale("log")
plt.show()