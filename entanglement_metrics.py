"""
entanglement_metrics.py — Quantum-equivalent metrics from TEGR phase data.

Key insight: in the TEGR framework, quantum purity maps to phase coherence.
If two copies of a system have perfectly correlated phases, they are pure.
If phases are random, they are mixed.

For a subsystem A of particles, the TEGR purity is computed from the
time-averaged phase coherence:

    Purity(A) = <prod_k cos(theta_k - theta_k_mean)>_time

More precisely, for each subsystem partition we compute:
    1. Phase coherence matrix: C_ij = <cos(theta_i - theta_j)>_t
       (time-averaged over the last 50% of simulation)
    2. Subsystem purity: Tr(rho^2) approximated by the mean of the
       coherence sub-matrix entries
    3. 2nd Rényi entropy: S2(A) = -log(Tr(rho_A^2))
    4. Mutual information: I_AB = S2(A) + S2(B) - S2(AB)
"""

import numpy as np
from typing import List, Tuple, Dict
from itertools import combinations


# ---------------------------------------------------------------------------
# Core metric functions
# ---------------------------------------------------------------------------

def compute_phase_coherence_matrix(
    trajectory: np.ndarray,
    hue_col: int = 8,
) -> np.ndarray:
    """
    Compute time-averaged phase coherence between all particle pairs.

    Detrends the common Compton frequency (rotating frame) so that we
    measure only the differential phase evolution caused by local forces.
    Without detrending, equal-mass particles show trivial coherence = 1.00
    because the dominant m0/gamma base clock is identical for all.

    Args:
        trajectory: (T, N, 10) array of state vectors over time.
        hue_col: column index for theta_hue (default 8).

    Returns:
        (N, N) coherence matrix where C_ij = <cos(delta_i - delta_j)>_t.
    """
    # Use last 50% of trajectory for steady-state averaging
    T: int = trajectory.shape[0]
    start: int = T // 2
    hues: np.ndarray = trajectory[start:, :, hue_col]  # (T_half, N)

    # Detrend: subtract mean phase at each timestep (rotating frame)
    # This removes the common Compton oscillation m0/gamma * t
    mean_phase: np.ndarray = np.mean(hues, axis=1, keepdims=True)  # (T_half, 1)
    detrended: np.ndarray = hues - mean_phase  # (T_half, N)

    # Phase differences: broadcast to (T_half, N, N)
    dtheta: np.ndarray = detrended[:, :, np.newaxis] - detrended[:, np.newaxis, :]
    coherence: np.ndarray = np.mean(np.cos(dtheta), axis=0)  # (N, N)
    return coherence


def compute_subsystem_purity(
    coherence_matrix: np.ndarray,
    subsystem_indices: List[int],
) -> float:
    """
    Compute purity Tr(rho^2) for a subsystem from its coherence sub-matrix.

    The purity is approximated as the mean of the coherence values within
    the subsystem, which maps to the product of pairwise overlaps.

    Args:
        coherence_matrix: (N, N) full coherence matrix.
        subsystem_indices: indices of particles in the subsystem.

    Returns:
        Purity value clamped to [0, 1].
    """
    sub: np.ndarray = coherence_matrix[
        np.ix_(subsystem_indices, subsystem_indices)
    ]
    # Purity Tr(rho^2) maps to the mean of the *squared* coherence elements
    purity: float = float(np.mean(sub**2))
    return float(np.clip(purity, 0.0, 1.0))


def compute_renyi_entropy(purity: float) -> float:
    """
    Compute the 2nd Rényi entropy.

    S2 = -log(Tr(rho^2)).  Purity is clamped away from zero to avoid log(0).

    Args:
        purity: Tr(rho^2) value.

    Returns:
        S2 entropy (non-negative float).
    """
    return -np.log(max(purity, 1e-10))


def compute_mutual_information(
    coherence: np.ndarray,
    partition_a: List[int],
    partition_b: List[int],
) -> float:
    """
    Compute mutual information between two subsystems.

    I_AB = S2(A) + S2(B) - S2(AB)

    Args:
        coherence: (N, N) coherence matrix.
        partition_a: indices of subsystem A.
        partition_b: indices of subsystem B.

    Returns:
        Mutual information I_AB.
    """
    # For classical phase coherence (covariance) matrices, standard discrete
    # subadditivity (S_A + S_B >= S_AB) is violated by the Tr(rho^2) mean mapping,
    # causing uncorrelated states to return negative Mutual Information.
    # The mathematically correct, strictly non-negative Mutual Information
    # for a continuous correlation matrix is given by the Gaussian formula:
    # I(A; B) = 0.5 * ln( det(C_A) * det(C_B) / det(C_AB) )
    
    sub_a = coherence[np.ix_(partition_a, partition_a)]
    sub_b = coherence[np.ix_(partition_b, partition_b)]
    sub_ab = coherence[np.ix_(full, full)]
    
    # Add a tiny epsilon to the diagonal for numerical stability
    eps = 1e-12
    det_a = max(np.linalg.det(sub_a + np.eye(len(partition_a))*eps), eps)
    det_b = max(np.linalg.det(sub_b + np.eye(len(partition_b))*eps), eps)
    det_ab = max(np.linalg.det(sub_ab + np.eye(len(full))*eps), eps)
    
    mi = 0.5 * np.log((det_a * det_b) / det_ab)
    return float(max(mi, 0.0))


# ---------------------------------------------------------------------------
# Partition enumeration
# ---------------------------------------------------------------------------

def compute_all_partitions(
    n_particles: int,
    max_exhaustive: int = 12
) -> List[Tuple[List[int], List[int]]]:
    """
    Generate bipartitions of *n_particles*.
    
    For N <= max_exhaustive, generates ALL possible bipartitions.
    For large N (e.g., 45), generating 2^N partitions causes an immediate 
    Out-Of-Memory (OOM) OS crash. In this case, we only generate a subset
    of representative partitions (singletons, bisection, even/odd) to keep
    analysis tractable.
    """
    indices: List[int] = list(range(n_particles))
    partitions: List[Tuple[List[int], List[int]]] = []
    
    if n_particles <= max_exhaustive:
        for size in range(1, n_particles):
            for combo in combinations(indices, size):
                a: List[int] = list(combo)
                b: List[int] = [i for i in indices if i not in a]
                partitions.append((a, b))
    else:
        # 1. Single particles vs rest
        for i in indices:
            a = [i]
            b = [j for j in indices if j != i]
            partitions.append((a, b))
            
        # 2. Main bisection (first half vs second half)
        mid = n_particles // 2
        a = indices[:mid]
        b = indices[mid:]
        partitions.append((a, b))
        
        # 3. Even/Odd bisection
        a = indices[0::2]
        b = indices[1::2]
        partitions.append((a, b))
        
    return partitions


# ---------------------------------------------------------------------------
# Full entanglement report
# ---------------------------------------------------------------------------

def full_entanglement_report(
    trajectory: np.ndarray,
    n_particles: int,
) -> Dict:
    """
    Compute a complete entanglement analysis for a trajectory.

    Args:
        trajectory: (T, N, 10) array of state vectors over time.
        n_particles: number of particles (N).

    Returns:
        Dict with keys:
            - ``coherence_matrix``: (N, N) ndarray
            - ``partitions``: list of (A, B) index lists
            - ``purities``: dict mapping str(A) -> purity
            - ``entropies``: dict mapping str(A) -> S2
            - ``mutual_info``: dict mapping str((A,B)) -> I_AB
    """
    coherence: np.ndarray = compute_phase_coherence_matrix(trajectory)
    partitions: List[Tuple[List[int], List[int]]] = compute_all_partitions(
        n_particles
    )

    purities: Dict[str, float] = {}
    entropies: Dict[str, float] = {}
    mutual_info: Dict[str, float] = {}

    for a, b in partitions:
        key_a: str = str(a)
        key_b: str = str(b)
        key_ab: str = str((a, b))

        # Subsystem A
        if key_a not in purities:
            p_a: float = compute_subsystem_purity(coherence, a)
            purities[key_a] = p_a
            entropies[key_a] = compute_renyi_entropy(p_a)

        # Subsystem B
        if key_b not in purities:
            p_b: float = compute_subsystem_purity(coherence, b)
            purities[key_b] = p_b
            entropies[key_b] = compute_renyi_entropy(p_b)

        # Mutual information for (A, B)
        mutual_info[key_ab] = compute_mutual_information(coherence, a, b)

    return {
        "coherence_matrix": coherence,
        "partitions": partitions,
        "purities": purities,
        "entropies": entropies,
        "mutual_info": mutual_info,
    }


# ---------------------------------------------------------------------------
# Coupling sweep (Islam et al. Fig. 4 comparison)
# ---------------------------------------------------------------------------

def generate_entropy_vs_coupling_sweep(
    sweep_data: List[Tuple[float, np.ndarray]],
    subsystem_indices: List[int],
    hue_col: int = 8,
) -> Dict[str, np.ndarray]:
    """
    Produce S2(A) vs U/J data for comparison with Islam et al. 2015, Fig. 4.

    For each coupling ratio in the sweep, computes the coherence matrix from
    the trajectory and extracts the 2nd Rényi entropy of the specified
    subsystem.

    Args:
        sweep_data: list of (coupling_ratio, trajectory) pairs where
            *coupling_ratio* is U/J and *trajectory* has shape (T, N, 10).
        subsystem_indices: particle indices defining subsystem A.
        hue_col: column index for theta_hue (default 8).

    Returns:
        Dict with:
            - ``coupling_ratios``: 1-D ndarray of U/J values.
            - ``purities``: 1-D ndarray of Tr(rho_A^2) at each U/J.
            - ``entropies``: 1-D ndarray of S2(A) at each U/J.
    """
    coupling_ratios: List[float] = []
    purities: List[float] = []
    entropies: List[float] = []

    for ratio, trajectory in sweep_data:
        coherence: np.ndarray = compute_phase_coherence_matrix(
            trajectory, hue_col=hue_col
        )
        purity: float = compute_subsystem_purity(coherence, subsystem_indices)
        entropy: float = compute_renyi_entropy(purity)

        coupling_ratios.append(ratio)
        purities.append(purity)
        entropies.append(entropy)

    return {
        "coupling_ratios": np.array(coupling_ratios),
        "purities": np.array(purities),
        "entropies": np.array(entropies),
    }
