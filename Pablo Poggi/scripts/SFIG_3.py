

import numpy as np
import matplotlib.pyplot as plt 



def graph_color(val):
    LogLmax=30
    inds=np.linspace(0,1,LogLmax+1)*0.7+0.2
    color = plt.cm.inferno(inds[val])
    return color

SFIG=3
datdir='../PUREdata/SFIG_{0}/'.format(SFIG)


###### Fig S3 (a) ########
Number_of_spins = 32
Tf = 2*np.pi
s=0
coupling_list = ["all_to_all","PWR2", "hypercube", "NN"]
coupling_labels_list = ["A2A","PWR2", "Hypercube", "NN"]
steps_list = [500,1000]
Bd_list=[256,512]
cutoff_list = [1.0e-10] ## basically -9
Random_vals = [1, 8, 16, 20]
for n in range (len(coupling_list)):
    coupling = coupling_list[n]
    coupling_label = coupling_labels_list[n]
    color = graph_color(int(Random_vals[n]))
    steps=steps_list[1]
    Bd=Bd_list[0]
    if coupling =="all_to_all":
        Fname =  datdir+"QFI_OAT_XY_MPS_{0} _{1} _{2} _{3} _{4}.txt".format(Number_of_spins, s, Tf, coupling, Bd)
        [tvec,Opt_QFI] = np.loadtxt(Fname)
        plt.plot(tvec, Opt_QFI, label=f"{coupling_label}",color=color)
        min_QFI = Opt_QFI.copy()
        max_QFI = Opt_QFI.copy()
        steps=500
        for b in range (len(Bd_list)):
            Bd = Bd_list[b]
            Fname = datdir+"QFI_OAT_XY_MPS_normalized_{0} _{1} _{2} _{3} _{4} _{5} _{6}.txt".format(Number_of_spins, s, Tf, coupling, Bd, steps, Tf)
            tvec_other, Opt_QFI_other = np.loadtxt(Fname)
            if steps != steps_list[1] or Bd != Bd_list[0]:
                Opt_QFI_interp = np.interp(tvec, tvec_other, Opt_QFI_other)
                min_QFI = np.minimum(min_QFI, Opt_QFI_interp)
                max_QFI = np.maximum(max_QFI, Opt_QFI_interp)
        plt.fill_between(tvec, min_QFI, max_QFI, alpha=0.5, color="blue")
        Bd = 256
        steps = 500
        for c in range (len(cutoff_list)):
            cutoff=cutoff_list[c]
            cutoff = "{:.1e}".format(cutoff).replace("e-0", "e-")
            Fname =  datdir+"QFI_OAT_XY_MPS_normalized_{0} _{1} _{2} _{3} _{4} _{5} _{6} _{7}.txt".format(Number_of_spins, s, Tf, coupling, Bd, steps, cutoff,Tf)
            tvec_other, Opt_QFI_other = np.loadtxt(Fname)
            if steps != steps_list[1] or Bd != Bd_list[0]:
                Opt_QFI_interp = np.interp(tvec, tvec_other, Opt_QFI_other)
                min_QFI = np.minimum(min_QFI, Opt_QFI_interp)
                max_QFI = np.maximum(max_QFI, Opt_QFI_interp)
        plt.fill_between(tvec, min_QFI, max_QFI, alpha=0.5, color="blue")
    else:
        Fname = datdir+"QFI_OAT_XY_MPS_normalized_{0} _{1} _{2} _{3} _{4} _{5} _{6}.txt".format(Number_of_spins, s, Tf, coupling, Bd, steps, Tf)
        [tvec,Opt_QFI] = np.loadtxt(Fname)
        plt.plot(tvec, Opt_QFI, label=f"{coupling_label}",color=color)
        min_QFI = Opt_QFI.copy()
        max_QFI = Opt_QFI.copy()
        for st in range (len(steps_list)):
            steps= steps_list[st]
            for b in range (len(Bd_list)):
                Bd = Bd_list[b]
                Fname = datdir+"QFI_OAT_XY_MPS_normalized_{0} _{1} _{2} _{3} _{4} _{5} _{6}.txt".format(Number_of_spins, s, Tf, coupling, Bd, steps, Tf)
                tvec_other, Opt_QFI_other = np.loadtxt(Fname)
                if steps != steps_list[1] or Bd != Bd_list[0]:
                    Opt_QFI_interp = np.interp(tvec, tvec_other, Opt_QFI_other)
                    min_QFI = np.minimum(min_QFI, Opt_QFI_interp)
                    max_QFI = np.maximum(max_QFI, Opt_QFI_interp)
        plt.fill_between(tvec, min_QFI, max_QFI, alpha=0.5, color="blue")
        Bd = 256
        steps = 500
        for c in range (len(cutoff_list)):
            cutoff=cutoff_list[c]
            cutoff = "{:.1e}".format(cutoff).replace("e-0", "e-")
            Fname =  datdir+"QFI_OAT_XY_MPS_normalized_{0} _{1} _{2} _{3} _{4} _{5} _{6} _{7}.txt".format(Number_of_spins, s, Tf, coupling, Bd, steps, cutoff,Tf)
            tvec_other, Opt_QFI_other = np.loadtxt(Fname)
            if steps != steps_list[1] or Bd != Bd_list[0]:
                Opt_QFI_interp = np.interp(tvec, tvec_other, Opt_QFI_other)
                min_QFI = np.minimum(min_QFI, Opt_QFI_interp)
                max_QFI = np.maximum(max_QFI, Opt_QFI_interp)
        plt.fill_between(tvec, min_QFI, max_QFI, alpha=0.5, color="blue")
plt.tight_layout() 
plt.legend()
plt.show()
##### Fig S3 (b) #####
Number_of_spins = 64
Tf = 2*np.pi
coupling_list = ["all_to_all","PWR2", "hypercube", "NN"]
coupling_labels_list = ["A2A","PWR2", "Hypercube", "NN"]
Bd=512
s=0
Random_vals = [1, 8, 16, 20]
for n in range (len(coupling_list)):
    steps = 500
    cutoff_list = [1.0e-9]
    coupling = coupling_list[n]
    coupling_label = coupling_labels_list[n]
    color = graph_color(int(Random_vals[n]))
    if coupling =="all_to_all":
        Fname =  datdir+"QFI_OAT_XY_MPS_{0} _{1} _{2} _{3} _{4}.txt".format(Number_of_spins, s, Tf, coupling, Bd)
        [tvec,Opt_QFI] = np.loadtxt(Fname)
        plt.plot(tvec, Opt_QFI, label=f"{coupling_label}",color=color)
        ax=plt.gca()
        min_QFI = Opt_QFI.copy()
        max_QFI = Opt_QFI.copy()
        for c in range (len(cutoff_list)):
            cutoff=cutoff_list[c]
            cutoff = "{:.1e}".format(cutoff).replace("e-0", "e-")
            Fname =  datdir+"QFI_OAT_XY_MPS_{0} _{1} _{2} _{3} _{4} _{5}.txt".format(Number_of_spins, s, Tf, coupling, Bd, cutoff)
            [tvec_other,Opt_QFI_other] = np.loadtxt(Fname)
            Opt_QFI_interp = np.interp(tvec, tvec_other, Opt_QFI_other)
            min_QFI = np.minimum(min_QFI, Opt_QFI_interp)
            max_QFI = np.maximum(max_QFI, Opt_QFI_interp)
        plt.fill_between(tvec, min_QFI, max_QFI, alpha=0.5, color="blue")
        Bd_list = [256, 512]
        for b in range (len(Bd_list)):
            Bd = Bd_list[b]
            Opt_QFI = []
            steps = 500
            Fname = datdir+"QFI_OAT_XY_MPS_{0} _{1} _{2} _{3} _{4}.txt".format(Number_of_spins, s, Tf, coupling,Bd)
            tvec_other,Opt_QFI_other = np.loadtxt(Fname)
            if Bd != Bd_list[1]:
                Opt_QFI_interp = np.interp(tvec, tvec_other, Opt_QFI_other)
                min_QFI = np.minimum(min_QFI, Opt_QFI_interp)
                max_QFI = np.maximum(max_QFI, Opt_QFI_interp)
        plt.fill_between(tvec, min_QFI, max_QFI, alpha=0.5, color="blue")
    elif coupling =="PWR2":
        steps= 500
        Fname = datdir+"QFI_OAT_XY_MPS_normalized_{0} _{1} _{2} _{3} _{4} _{5} _{6}.txt".format(Number_of_spins, s, Tf, coupling, Bd, steps, Tf)
        [tvec,Opt_QFI] = np.loadtxt(Fname)
        plt.plot(tvec, Opt_QFI,label=f"{coupling_label}",color=color)
        ax=plt.gca()
        min_QFI = Opt_QFI.copy()
        max_QFI = Opt_QFI.copy()
        for c in range (len(cutoff_list)):
            cutoff=cutoff_list[c]
            cutoff = "{:.1e}".format(cutoff).replace("e-0", "e-")
            Fname = datdir+"QFI_OAT_XY_MPS_normalized_{0} _{1} _{2} _{3} _{4} _{5} _{6} _{7}.txt".format(Number_of_spins, s, Tf, coupling, Bd, steps, cutoff, Tf)
            [tvec_other,Opt_QFI_other] = np.loadtxt(Fname)
            Opt_QFI_interp = np.interp(tvec, tvec_other, Opt_QFI_other)
            min_QFI = np.minimum(min_QFI, Opt_QFI_interp)
            max_QFI = np.maximum(max_QFI, Opt_QFI_interp)
        plt.fill_between(tvec, min_QFI, max_QFI, alpha=0.5, color="blue")
        Bd_list = [256, 512]
        for b in range (len(Bd_list)):
            Bd = Bd_list[b]
            Fname = datdir+"QFI_OAT_XY_MPS_normalized_{0} _{1} _{2} _{3} _{4} _{5} _{6}.txt".format(Number_of_spins, s, Tf, coupling, Bd, steps, Tf)
            tvec_other, Opt_QFI_other = np.loadtxt(Fname)
            if Bd != Bd_list[1]:
                Opt_QFI_interp = np.interp(tvec, tvec_other, Opt_QFI_other)
                min_QFI = np.minimum(min_QFI, Opt_QFI_interp)
                max_QFI = np.maximum(max_QFI, Opt_QFI_interp)
        plt.fill_between(tvec, min_QFI, max_QFI, alpha=0.5, color="blue")
    elif coupling =="NN":
        steps= 500
        Fname = datdir+"QFI_OAT_XY_MPS_normalized_{0} _{1} _{2} _{3} _{4} _{5} _{6}.txt".format(Number_of_spins, s, Tf, coupling, Bd, steps, Tf)
        [tvec,Opt_QFI] = np.loadtxt(Fname)
        plt.plot(tvec, Opt_QFI, label=f"{coupling_label}",color=color)
        ax=plt.gca()
        min_QFI = Opt_QFI.copy()
        max_QFI = Opt_QFI.copy()
        for c in range (len(cutoff_list)):
            cutoff=cutoff_list[c]
            cutoff = "{:.1e}".format(cutoff).replace("e-0", "e-")
            Fname = datdir+"QFI_OAT_XY_MPS_normalized_{0} _{1} _{2} _{3} _{4} _{5} _{6} _{7}.txt".format(Number_of_spins, s, Tf, coupling, Bd, steps, cutoff, Tf)
            [tvec_other,Opt_QFI_other] = np.loadtxt(Fname)
            Opt_QFI_interp = np.interp(tvec, tvec_other, Opt_QFI_other)
            min_QFI = np.minimum(min_QFI, Opt_QFI_interp)
            max_QFI = np.maximum(max_QFI, Opt_QFI_interp)
        plt.fill_between(tvec, min_QFI, max_QFI, alpha=0.5, color="blue")
        Bd_list = [256, 512]
        steps=2000
        for b in range (len(Bd_list)):
            Bd = Bd_list[b]
            cutoff=cutoff_list[c]
            cutoff = "{:.1e}".format(cutoff).replace("e-0", "e-")
            Fname = datdir+"QFI_OAT_XY_MPS_normalized_{0} _{1} _{2} _{3} _{4} _{5} _{6} _{7}.txt".format(Number_of_spins, s, Tf, coupling, Bd, steps, cutoff, Tf)
            tvec_other, Opt_QFI_other = np.loadtxt(Fname)
            if Bd != Bd_list[1]:
                Opt_QFI_interp = np.interp(tvec, tvec_other, Opt_QFI_other)
                min_QFI = np.minimum(min_QFI, Opt_QFI_interp)
                max_QFI = np.maximum(max_QFI, Opt_QFI_interp)
        plt.fill_between(tvec, min_QFI, max_QFI, alpha=0.5, color="blue")
    else:
        steps= 500
        Fname = datdir+"QFI_OAT_XY_MPS_normalized_{0} _{1} _{2} _{3} _{4} _{5} _{6}.txt".format(Number_of_spins, s, Tf, coupling, Bd, steps, Tf)
        [tvec,Opt_QFI] = np.loadtxt(Fname)
        plt.plot(tvec, Opt_QFI, label=f"{coupling_label}",color=color)
        min_QFI = Opt_QFI.copy()
        max_QFI = Opt_QFI.copy()
        for c in range (len(cutoff_list)):
            cutoff=cutoff_list[c]
            cutoff = "{:.1e}".format(cutoff).replace("e-0", "e-")
            Fname = datdir+"QFI_OAT_XY_MPS_normalized_{0} _{1} _{2} _{3} _{4} _{5} _{6} _{7}.txt".format(Number_of_spins, s, Tf, coupling, Bd, steps, cutoff, Tf)
            [tvec_other,Opt_QFI_other] = np.loadtxt(Fname)
            Opt_QFI_interp = np.interp(tvec, tvec_other, Opt_QFI_other)
            min_QFI = np.minimum(min_QFI, Opt_QFI_interp)
            max_QFI = np.maximum(max_QFI, Opt_QFI_interp)
        plt.fill_between(tvec, min_QFI, max_QFI, alpha=0.5, color="blue")
        Bd_list = [400, 512]
        for b in range (len(Bd_list)):
            Bd = Bd_list[b]
            if Bd != Bd_list[1]:
                cutoff=cutoff_list[0]
                cutoff = "{:.1e}".format(cutoff).replace("e-0", "e-")
                Fname = datdir+"QFI_OAT_XY_MPS_normalized_{0} _{1} _{2} _{3} _{4} _{5} _{6} _{7}.txt".format(Number_of_spins, s, Tf, coupling, Bd, steps, cutoff,Tf )
                tvec_other, Opt_QFI_other = np.loadtxt(Fname)
                Opt_QFI_interp = np.interp(tvec, tvec_other, Opt_QFI_other)
                min_QFI = np.minimum(min_QFI, Opt_QFI_interp)
                max_QFI = np.maximum(max_QFI, Opt_QFI_interp)
        plt.fill_between(tvec, min_QFI, max_QFI, alpha=0.5, color="blue")
plt.tight_layout() 
plt.legend()
plt.show()