
import numpy as np
import matplotlib.pyplot as plt 

def L_color(val):
    LogLmax=25
    inds=np.linspace(0,1,LogLmax+1)*0.7+0.2
    color=plt.cm.viridis(inds[val])
    return color

def graph_color(val):
    LogLmax=30
    inds=np.linspace(0,1,LogLmax+1)*0.7+0.2
    color = plt.cm.inferno(inds[val])
    return color

FIG=4
datdir='../PUREdata/Fig_{0}/'.format(FIG)

Number_of_spins_list = [8,16,32]
coupling = "hypercube"
state_type="plus"
Random_vals=[1,8,16]
########## Main Figure (4b) #################
for n in range(len(Number_of_spins_list)):
    color = L_color(int(Random_vals[n]))
    Number_of_spins = Number_of_spins_list[n]
    if Number_of_spins==32:
        Bd = 256
        Fname = datdir+"Strob_evolution_max_time_transition_first_order_MPS_{0} _{1} _{2} _17.68.txt".format(Number_of_spins,coupling,Bd)
    else:
        Fname = datdir+"Strob_evolution_max_time_transition_first_order_{0}_{1}_{2}.txt".format(Number_of_spins, coupling, state_type)
    QFI_iter, Error, iteration_first_order = np.loadtxt(Fname)
    QFI_iter = np.array(QFI_iter)
    QFI_iter = QFI_iter / (Number_of_spins ** 2)
    plt.plot(iteration_first_order, QFI_iter, label=f"N = {Number_of_spins}", color=color)
plt.ylabel(r'$\frac{F_Q}{N^2}$')
plt.xlabel(r'$M$')
plt.legend()
plt.show()
###### Inset #########
Number_of_spins_list = [16]
for n in range(len(Number_of_spins_list)):
    color = graph_color(int(16))
    Number_of_spins = Number_of_spins_list[n]
    Fname = datdir+"Strob_evolution_max_time_transition_first_order_Jexp_{0}_{1}_{2}.txt".format(Number_of_spins, coupling, state_type)
    Jsq_iter, DT, iteration_first_order = np.loadtxt(Fname)
    Jsq_iter = np.array(Jsq_iter) / ((Number_of_spins / 2) * ((Number_of_spins / 2) + 1))
    plt.plot(iteration_first_order, Jsq_iter, linestyle="-", marker="v", label=f"N = {Number_of_spins}", color=color, linewidth=2, markersize=8)
    plt.xlabel(r'$M$')
    plt.ylabel(r'$\frac{\langle \mathbf{J}^2 \rangle}{j(j+1)}$',color=color)
plt.show()
for n in range(len(Number_of_spins_list)):
    Number_of_spins = Number_of_spins_list[n]
    Fname = datdir+"Strob_evolution_max_time_transition_first_order_TMI_{0}_{1}_{2}.txt".format(Number_of_spins, coupling, state_type)
    TMI, DT, iteration_first_order = np.loadtxt(Fname)
    plt.plot(iteration_first_order, TMI, linestyle="-", marker="s", label=f"N = {Number_of_spins}", color=color, linewidth=2, markersize=8)
    plt.ylabel(r'$\mathcal{I}_3$',color=color)
    plt.xlabel(r'$M$')
plt.xlim(0,101) # otherwise the right y-label is slightly clipped
plt.show()