# FIG1
Files with data points that are required for recreating Fig. 1 (a-d).
## Fig. 1 (a-d)
   * `QFI_OAT_XY_MPS_N _s _Tf _coupling _Bd.txt`
    with `N` replaced with the values `L=8, 16, 32, 64`
    `s=0`, `Tf=2pi` and `Bd = 512` if `N=64` else `Bd = 256`
   * Coloumn 1 contains the value of time
   * Coloumn 2 contains the value of Quantum Fisher information
   * Here `coupling=all_to_all`
   * `QFI_OAT_XY_MPS_normalized_N _s _Tf _coupling _Bd _steps _Tf.txt`
   with `N` replaced with the values `L=8, 16, 32, 64`
    `s=0`, `Tf=2pi`,  `Bd = 512` if `N=64` else `Bd = 256`, `steps = 500` if `N=64` else `steps=1000`.
   * Coloumn 1 contains the value of time
   * Coloumn 2 contains the value of Quantum Fisher information
   * Here `coupling=PWR2, NN, Hypercube`
