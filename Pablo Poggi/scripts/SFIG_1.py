import numpy as np
import matplotlib.pyplot as plt 


def graph_color(val):
    LogLmax=30
    inds=np.linspace(0,1,LogLmax+1)*0.7+0.2
    color = plt.cm.inferno(inds[val])
    return color

SFIG=1
datdir='../PUREdata/SFIG_{0}/'.format(SFIG)

####### Fig S1(a) ###################
coupling_list = ["all_to_all", "PWR2", "hypercube"]
coupling_labels_list = ["A2A", "PWR2", "Hypercube"]
Random_vals=[1,8,16,20]
for c in range (len(coupling_list)):
    coupling = coupling_list[c]
    coupling_label = coupling_labels_list[c]
    color=graph_color(int(Random_vals[c]))
    Fname =datdir+"Compass_States_{0}.txt".format(coupling)
    QFI_CS, Time_CS, Number_of_spins_list = np.loadtxt(Fname)
    plt.plot(Number_of_spins_list, QFI_CS, label=f"{coupling_label}", color=color,linewidth=3, markersize=10)
plt.legend()
plt.xlabel("N")
plt.xscale("log")
plt.yscale("log")
plt.ylabel("QFI")
plt.show()
###### Fig S1(b) #################
coupling_list = ["all_to_all", "PWR2", "hypercube","NN"]
coupling_labels_list = ["A2A", "PWR2", "Hypercube","NN"]
Random_vals=[1,8,16,20]
for c in range (len(coupling_list)):
    coupling = coupling_list[c]
    coupling_label = coupling_labels_list[c]
    color=graph_color(int(Random_vals[c]))
    Fname =datdir+"Overlap_{0}.txt".format(coupling)
    Number_of_spins_list, Overlap = np.loadtxt(Fname)
    plt.plot(Number_of_spins_list, Overlap, label=f"{coupling_label}", color=color,linewidth=3, markersize=10)
plt.legend()
plt.xlabel("N")
plt.ylabel("Overlap with GHZ")
plt.show()
########### Fig S1 (c) ##########
coupling_list = ["all_to_all", "PWR2", "hypercube","NN"]
coupling_labels_list = ["A2A", "PWR2", "Hypercube","NN"]
Random_vals=[1,8,16,20]
Number_of_spins = 16
Tf = 1/np.sqrt(Number_of_spins)
Random_vals=[1,8,16,20]
for c in range (len(coupling_list)):
    coupling = coupling_list[c]
    coupling_label = coupling_labels_list[c]
    color=graph_color(int(Random_vals[c]))
    Fname1=datdir + "Wineland_squeezing_parameter_XY_{0}_{1}_{2}.txt".format(Number_of_spins,coupling,Tf)
    [Squeezing_parameter, tfinal] = np.loadtxt(Fname1)
    plt.plot(tfinal,Squeezing_parameter, label=f"{coupling_label}", color=color,linewidth=3, markersize=5)
plt.ylabel("Wineland Parameter")
plt.xlabel("t")
plt.show()