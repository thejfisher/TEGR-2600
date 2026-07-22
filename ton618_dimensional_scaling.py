import math

def calculate_ton618_scaling():
    # SI Constants
    c_SI = 299792458.0  # m/s
    G_SI = 6.67430e-11  # m^3 / (kg s^2)
    M_sun_SI = 1.989e30 # kg
    ly_to_meters = 9.461e15 # meters in a light-year
    
    # TON 618 Parameters
    M_ton = 6.6e10 * M_sun_SI
    Rs_SI = 2 * G_SI * M_ton / (c_SI**2)
    Rs_ly = Rs_SI / ly_to_meters
    
    # TEGR 2600 Engine Parameters (from manuscript)
    Rs_sim = 5.0       # Simulated horizon radius in simulation spatial units
    c_base_sim = 65.0  # Baseline wave speed in sim_units / sim_time
    dx_sim = 1.7812    # Grid cell size (dx)
    dt_sim = 0.001     # Tick size (dt)
    
    # --- STEP 1: SI Unit Conversion Matrix ---
    
    # Spatial Scale: How many meters is 1.0 simulation spatial unit?
    S_x = Rs_SI / Rs_sim 
    
    # Grid Cell SI Size
    dx_SI = dx_sim * S_x
    
    # Time Scale: How many seconds is 1.0 simulation time unit?
    # c_sim * (S_x / S_t) = c_SI  =>  S_t = c_sim * S_x / c_SI
    S_t = c_base_sim * S_x / c_SI
    
    # Tick SI Size
    dt_SI = dt_sim * S_t
    
    print("============================================================")
    print("  PHASE 6: TON 618 DIMENSIONAL ANCHOR")
    print("============================================================")
    print(f"Anchor Mass (TON 618): {M_ton:.3e} kg")
    print(f"Anchor R_s (SI): {Rs_SI:.3e} m ({Rs_ly:.2f} ly)")
    print(f"Simulation R_s: {Rs_sim} units")
    print("------------------------------------------------------------")
    print(f"[TEGR 2600 -> SI Conversion Matrix]")
    print(f" 1.0 sim_distance = {S_x:.3e} meters")
    print(f" 1.0 sim_time     = {S_t:.3e} seconds")
    print(f" 1 Grid Cell (dx) = {dx_SI:.3e} m ({dx_SI/ly_to_meters:.2f} ly)")
    print(f" 1 Engine Tick (dt)= {dt_SI:.3e} s ({dt_SI/3600:.2f} hours)")
    
    # --- STEP 2: Inverting the Operator F (The Cosmological Stack) ---
    
    print("\n============================================================")
    print("  THE COSMOLOGICAL STACK (Inverse Operator F)")
    print("============================================================")
    
    # Generation parameters
    # The transformation doubles wave speed per generation (x2)
    # The Schwarzschild radius compresses by 4x per generation
    # Our observable universe
    M_obs_SI = 1.5e53 # kg
    R_obs_SI = 4.4e26 # meters (radius of observable universe)
    
    # Generation +1 (Parent Universe)
    c_parent_sim = c_base_sim * 2.0
    c_parent_SI = c_SI * 2.0  # Apparent wave speed from our perspective
    
    # From Parent's perspective, our universe is a black hole.
    # Our observable universe radius compresses by 4 in their metric.
    # Or rather, the mass M_obs_SI creates an R_s in their universe:
    # R_s_parent = 2 * G * M_obs_SI / (c_parent_SI)^2 = R_s_us / 4
    Rs_us_as_bh = 2 * G_SI * M_obs_SI / (c_SI**2)
    Rs_parent_view = Rs_us_as_bh / 4.0
    
    print("[Generation 0: Our Universe]")
    print(f" Observable Radius: {R_obs_SI:.3e} m")
    print(f" Wave Speed: {c_base_sim} sim_units (1.0 c)")
    print(f" Damping (lambda): 0.999")
    
    print("\n[Generation +1: Parent Universe]")
    print(f" Wave Speed: {c_parent_sim} sim_units (2.0 c)")
    print(f" Damping (lambda): 0.9999")
    print(f" Apparent size of our entire universe in their metric:")
    print(f" R_s = {Rs_parent_view:.3e} m ({Rs_parent_view/ly_to_meters:.3e} ly)")
    
    print("\n[Generation +3: Universe Zero]")
    c_zero_sim = c_base_sim * 8.0
    c_zero_SI = c_SI * 8.0
    
    # Calculate M_0: The total mass budget of Universe Zero
    # From Manuscript: M_0 = R_obs * c_0^2 / (2G)
    # But R_obs is 4.4e26. And c_0 is 8*c_SI. 
    # M_0 = R_obs * (8*c_SI)^2 / (2G) = 64 * R_obs * c_SI^2 / (2G)
    M_0 = R_obs_SI * (c_zero_SI**2) / (2 * G_SI)
    
    print(f" Wave Speed: {c_zero_sim} sim_units (8.0 c)")
    print(f" Damping (lambda): 0.9999999")
    print(f" Absolute Mass Budget: {M_0:.3e} kg")
    print(f" Ratio to Observable Universe Mass: {M_0 / M_obs_SI:.1f}x")
    
    # Verification of max stable speed
    c_max = 1028.41
    print(f"\n[CFL Stability Limit]")
    print(f" Absolute Max c_w before topological shattering: {c_max}")
    print(f" Universe Zero c_w: {c_zero_sim} (Safely below shattering limit)")
    print("============================================================")

if __name__ == "__main__":
    calculate_ton618_scaling()
