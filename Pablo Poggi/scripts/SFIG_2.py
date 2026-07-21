
import numpy as np
import matplotlib.pyplot as plt 


def L_color(val):
    LogLmax=25
    inds=np.linspace(0,1,LogLmax+1)*0.7+0.2
    color=plt.cm.viridis(inds[val])
    return color


SFIG=2
datdir='../PUREdata/SFIG_{0}/'.format(SFIG)


Number_of_spins_list = [8, 16, 32]
coupling = "hypercube"
state_type="plus"
Random_vals=[1,8,16]
for n in range (len(Number_of_spins_list)):
    Number_of_spins = Number_of_spins_list[n]
    color = L_color(int(Random_vals[n]))
    Norm = 0.2*(Number_of_spins**2) + 0.43*Number_of_spins ### The normalisation 
    Fname = datdir+"QFI_sqrt_time_vals_{0}.txt".format(coupling)
    QFI_vals, _ = np.loadtxt(Fname)
    ## Strobosocopic ###
    Bd = 256
    Fname_strob =datdir+"Strob_evolution_sqrt_time_transition_first_order_MPS_{0} _{1} _{2}.txt".format(Number_of_spins, coupling, Bd)
    QFI_X, QFI_Y, iteration_first_order= np.loadtxt(Fname_strob)
    QFI_X=np.array(QFI_X)
    QFI_Y=np.array(QFI_Y)
    Opt_QFI = []
    for i in range(min(len(QFI_X), len(QFI_Y))):
        Opt_QFI.append(max(QFI_X[i], QFI_Y[i]))
    Opt_QFI= np.array(Opt_QFI)
    Opt_QFI = Opt_QFI/Norm
    plt.plot(iteration_first_order, Opt_QFI,linestyle="-", label=f"N = {Number_of_spins}", color=color, linewidth=3, markersize=10 )
    plt.axhline(QFI_vals[n], linestyle=":", color=color, linewidth=3)
    plt.xlim(0,105)
plt.legend()
plt.ylabel("FQ/Norm")
plt.xlabel("M")
plt.show()