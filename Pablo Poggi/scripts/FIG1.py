
import numpy as np
import matplotlib.pyplot as plt 

def L_color(val):
    LogLmax=25
    inds=np.linspace(0,1,LogLmax+1)*0.7+0.2
    color=plt.cm.viridis(inds[val])
    return color


FIG=1
datdir='../PUREdata/Fig_{0}/'.format(FIG)
Random_vals=[1,8,16,24]
Number_of_spins_list = [8, 16, 32, 64]
Tf = 2*np.pi
s = 0
### Fig 1(a) ###
coupling = "all_to_all"
for n in range (len(Number_of_spins_list)):
    color = L_color(int(Random_vals[n]))
    Number_of_spins = Number_of_spins_list[n]
    Bd = 512 if Number_of_spins == 64 else 256
    steps = 500 if Number_of_spins == 64 else 1000
    Fname = datdir + "QFI_OAT_XY_MPS_{0} _{1} _{2} _{3} _{4}.txt".format(Number_of_spins, s, Tf, coupling, Bd)
    [tvec,Opt_QFI] = np.loadtxt(Fname)
    plt.plot(tvec, Opt_QFI, "*-", label=f"N = {Number_of_spins}",color=color,linewidth=3, markersize=10)
ax=plt.gca()
plt.xlabel("t")
plt.ylabel("QFI")
plt.legend()
plt.ylim(0,66)
plt.show()
######## Fig 1(b) ##########
coupling = "PWR2"
for n in range (len(Number_of_spins_list)):
    color = L_color(int(Random_vals[n]))
    Number_of_spins = Number_of_spins_list[n]
    Bd = 512 if Number_of_spins == 64 else 256
    steps = 500 if Number_of_spins == 64 else 1000
    Fname = datdir + "QFI_OAT_XY_MPS_normalized_{0} _{1} _{2} _{3} _{4} _{5} _{6}.txt".format(Number_of_spins, s, Tf, coupling, Bd, steps, Tf)
    [tvec,Opt_QFI] = np.loadtxt(Fname)
    plt.plot(tvec, Opt_QFI, "*-", label=f"N = {Number_of_spins}",color=color,linewidth=3, markersize=10)
ax=plt.gca()
plt.ylim(0,66)
plt.xlabel("t")
plt.ylabel("QFI")
plt.legend()
plt.show()
######### Fig 1(c) #######
coupling = "hypercube"
for n in range (len(Number_of_spins_list)):
    color = L_color(int(Random_vals[n]))
    Number_of_spins = Number_of_spins_list[n]
    Bd = 512 if Number_of_spins == 64 else 256
    steps = 500 if Number_of_spins == 64 else 1000
    Fname = datdir + "QFI_OAT_XY_MPS_normalized_{0} _{1} _{2} _{3} _{4} _{5} _{6}.txt".format(Number_of_spins, s, Tf, coupling, Bd, steps, Tf)
    [tvec,Opt_QFI] = np.loadtxt(Fname)
    plt.plot(tvec, Opt_QFI, "*-", label=f"N = {Number_of_spins}",color=color,linewidth=3, markersize=10)
ax=plt.gca()
plt.ylim(0,66)
plt.xlabel("t")
plt.ylabel("QFI") 
plt.legend()
plt.show()
### Fig 1(d) #####
coupling = "NN"
for n in range (len(Number_of_spins_list)):
    color = L_color(int(Random_vals[n]))
    Number_of_spins = Number_of_spins_list[n]
    Bd = 512 if Number_of_spins == 64 else 256
    steps = 500 if Number_of_spins == 64 else 1000
    Fname = datdir +"QFI_OAT_XY_MPS_normalized_{0} _{1} _{2} _{3} _{4} _{5} _{6}.txt".format(Number_of_spins, s, Tf, coupling, Bd, steps, Tf)
    [tvec,Opt_QFI] = np.loadtxt(Fname)
    plt.plot(tvec, Opt_QFI, "*-", label=f"N = {Number_of_spins}",color=color,linewidth=3, markersize=10)
ax=plt.gca()
plt.ylim(0,66)
plt.xlabel("t")
plt.ylabel("QFI")
plt.legend()
plt.show()

