**These datasets include code as well as experimental data for analyzing the solution of the Max-cut problem.**

## Datasets included:

A) **Experimentally collected data**

1. The three '.mat' files correspond to the experimental data for three graphs. For example, 'ExperimentdataA.mat' corresponds to the experimental data for graph A.
2. In each '.mat' file, for the first row: the first column represents the element values of the interaction **J**, as a 16\*16 matrix; the second column represents the values of the temperature during each annealing process as an array; and the third column is the number of iterations at each temperature; the fourth column represents the plotting index, i.e., the index of run taken from the total 100 experimental runs.
3. In each '.mat' file, the third row shows the experimental results obtained from a complete experiment run. For the third row: the first column is the detected intensity during annealing process as an array; the second column is the Hamiltonian during annealing process as an array; the third column is the variation of 16 spin states during annealing process as an array.
4. In each '.mat' file, the third to 102nd rows, respectively, represent 100 experimental runs.

B) **Matlab Scripts**

1. Run 'PlotGraphA.m' file to plot the histograms of the obtained solutions in 100 runs and the evolution of the Hamiltonian for the eight of 100 runs at corresponding temperature for graph A.
2. Run 'PlotGraphB.m' file to plot the histograms of the obtained solutions in 100 runs and the evolution of the Hamiltonian for the eight of 100 runs at corresponding temperature for graph B.
3. Run 'PlotGraphC.m' file to plot the histograms of the obtained solutions in 100 runs and the evolution of the Hamiltonian for the eight of 100 runs at corresponding temperature for graph C.