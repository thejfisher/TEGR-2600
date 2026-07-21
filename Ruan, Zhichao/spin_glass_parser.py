import numpy as np
import torch
import psutil
import platform
import time


def print_system_diagnostics(label="SYSTEM DIAGNOSTICS"):
    """
    Prints a full hardware resource report:
      - CPU model, core count, and current utilization %
      - DRAM: total, used, available (GB)
      - GPU name, driver version
      - VRAM: total, used, free (GB)
    """
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")

    # ---- CPU ----
    cpu_name = platform.processor() or "Unknown CPU"
    cpu_cores_physical = psutil.cpu_count(logical=False)
    cpu_cores_logical = psutil.cpu_count(logical=True)
    cpu_percent = psutil.cpu_percent(interval=0.5)
    print(f"  CPU: {cpu_name}")
    print(f"  Cores: {cpu_cores_physical} physical / {cpu_cores_logical} logical")
    print(f"  CPU Utilization: {cpu_percent:.1f}%")

    # ---- DRAM ----
    mem = psutil.virtual_memory()
    print(f"\n  DRAM Total:     {mem.total / (1024**3):.2f} GB")
    print(f"  DRAM Used:      {mem.used / (1024**3):.2f} GB ({mem.percent:.1f}%)")
    print(f"  DRAM Available: {mem.available / (1024**3):.2f} GB")

    # ---- GPU / VRAM ----
    if torch.cuda.is_available():
        gpu_id = torch.cuda.current_device()
        gpu_name = torch.cuda.get_device_name(gpu_id)
        vram_total = torch.cuda.get_device_properties(gpu_id).total_mem / (1024**3)
        vram_allocated = torch.cuda.memory_allocated(gpu_id) / (1024**3)
        vram_reserved = torch.cuda.memory_reserved(gpu_id) / (1024**3)
        vram_free = vram_total - vram_reserved

        print(f"\n  GPU: {gpu_name} (Device {gpu_id})")
        try:
            # Try to get driver version (CUDA runtime)
            print(f"  CUDA Version: {torch.version.cuda}")
        except Exception:
            pass
        print(f"  VRAM Total:     {vram_total:.2f} GB")
        print(f"  VRAM Allocated: {vram_allocated:.4f} GB")
        print(f"  VRAM Reserved:  {vram_reserved:.4f} GB")
        print(f"  VRAM Free:      {vram_free:.2f} GB")
    elif hasattr(torch, 'hip') or torch.cuda.is_available():
        # ROCm reports through the same torch.cuda interface
        print(f"\n  GPU: ROCm device detected (use torch.cuda calls)")
    else:
        print(f"\n  GPU: No CUDA/ROCm device detected (running on CPU)")

    print(f"{'='*60}\n")


class SpinGlassToTEGR:
    """
    Parses a standard Ising spin glass edge list and maps it into 
    the Entanglement Adjacency Tensor (W_ij) and Kuramoto coupling matrix.
    """
    def __init__(self, filepath, num_nodes=None, device='cuda'):
        self.filepath = filepath
        self.num_nodes = num_nodes
        self.device = device
        self.edge_list = []

    def load_data(self):
        """Loads the edge list. Assumes format: node_i, node_j, J_ij"""
        # Load the data, ignoring any header lines
        data = np.loadtxt(self.filepath, comments="#")
        
        # If node count isn't explicitly provided, infer it from the max index
        if self.num_nodes is None:
            self.num_nodes = int(np.max(data[:, 0:2])) + 1
            
        self.edge_list = data
        print(f"Loaded {len(self.edge_list)} topological connections across {self.num_nodes} defects.")
        return self.edge_list

    def generate_entanglement_tensors(self, kappa_scale=1.0):
        """
        Translates the Ising graph into the TEGR Super-Matrix layer.
        Returns:
            W_ij (Tensor): Binary adjacency matrix (1 = entangled, 0 = isolated)
            K_ij (Tensor): The continuous phase-coupling weights (scaled J_ij)
        """
        W_ij = torch.zeros((self.num_nodes, self.num_nodes), device=self.device)
        K_ij = torch.zeros((self.num_nodes, self.num_nodes), device=self.device)

        for row in self.edge_list:
            i, j, j_weight = int(row[0]), int(row[1]), row[2]

            # Populate the symmetric binary entanglement bridge
            W_ij[i, j] = 1.0
            W_ij[j, i] = 1.0

            # Map the Ising coupling to the Kuramoto phase spring (kappa)
            # A negative J_ij (ferromagnetic) encourages phase alignment.
            # A positive J_ij (antiferromagnetic) encourages pi phase separation.
            scaled_weight = j_weight * kappa_scale
            K_ij[i, j] = scaled_weight
            K_ij[j, i] = scaled_weight

        return W_ij, K_ij

    def initialize_phase_clocks(self):
        """
        Maps standard binary Ising spins (+1, -1) into the continuous 
        internal de Broglie phase clocks (0, pi) of the wave defects.
        """
        # Generate random initial binary states (0 or 1)
        binary_states = torch.randint(0, 2, (self.num_nodes,), device=self.device).float()
        
        # Convert to geometric phase angles: 0 rad or 3.14 rad
        theta_hue = binary_states * torch.pi
        return theta_hue

# ==========================================
# Example Execution Pipeline
# ==========================================
if __name__ == "__main__":
    # Print hardware diagnostics before anything runs
    print_system_diagnostics("PRE-RUN HARDWARE REPORT")

    # 1. Initialize the parser (pointing to a downloaded dataset)
    # parser = SpinGlassToTEGR("path_to_dryad_lattice.txt", device='cuda')
    
    # 2. Load the raw topological data
    # parser.load_data()
    
    # 3. Extract the TEGR-ready matrices
    # W_ij, K_ij = parser.generate_entanglement_tensors(kappa_scale=500.0)
    
    # 4. Initialize the internal phase clocks for the simulation start
    # initial_theta_hue = parser.initialize_phase_clocks()

    # Print hardware diagnostics after run completes
    # print_system_diagnostics("POST-RUN HARDWARE REPORT")
    
    print("Matrix extraction pipeline ready.")
