import numpy as np
import matplotlib.pyplot as plt 

def graph_color(val):
    LogLmax=30
    inds=np.linspace(0,1,LogLmax+1)*0.7+0.2
    color = plt.cm.inferno(inds[val])
    return color



FIG=2
datdir='../PUREdata/Fig_{0}/'.format(FIG)
Random_vals=[1,8,16,20]

### Main Figure ###
coupling_list = ["all_to_all", "PWR2", "hypercube", "NN"]
coupling_labels_list = ["A2A", "PWR2", "Hypercube","NN"]
for c in range (len(coupling_list)):
    coupling = coupling_list[c]
    coupling_label = coupling_labels_list[c]
    color = graph_color(int(Random_vals[c]))
    Fname =datdir+"Max_QFI_vs_N_{0}.txt".format(coupling)
    Number_of_spins_list, Maximum_val_QFI = np.loadtxt(Fname)
    plt.plot(Number_of_spins_list, Maximum_val_QFI, label=f"{coupling_label}", color=color)
plt.xlabel("N")
plt.ylabel("QFI Max")
plt.xscale('log')
plt.yscale('log')
plt.legend()
plt.show()

### Inset #####
for c in range(len(coupling_list)):
    coupling = coupling_list[c]
    coupling_label = coupling_labels_list[c]
    color = graph_color(int(Random_vals[c]))
    Fname =datdir+"Max_time_N_XY_{0}.txt".format(coupling)
    Number_of_spins_list, Time = np.loadtxt(Fname)
    plt.plot(Number_of_spins_list, Time, label=f"{coupling_label}", color=color)
coupling_list = ["PWR2", "hypercube"]
coupling_labels_list = ["PWR2", "Hypercube"]
for c in range(len(coupling_list)):
    coupling = coupling_list[c]
    coupling_label = coupling_labels_list[c]
    color = graph_color(int(Random_vals[c]))
    Fname =datdir+"Analytical_vals_{0}.txt".format(coupling)
    Number_of_spins_list, analytical_val = np.loadtxt(Fname)
    plt.plot(Number_of_spins_list, analytical_val, "--", label=f"{coupling_label}", color=color)
plt.xlabel("N")
plt.ylabel("time")
plt.legend()
plt.show()