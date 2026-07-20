import csv
import random
import math

def generate_blind_dataset(num_particles=45, spacing_nm=680.0):
    filename = "blind_45_particle_target.csv"
    
    headers = [
        "node_id", "mass_mev", "pos_x", "pos_y", "pos_z", 
        "vel_x", "vel_y", "vel_z", "phase_rad", "spin_vorticity"
    ]
    
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        
        for i in range(num_particles):
            # Enforcing the dimensionless mass and drift fixes
            node_id = i
            mass_mev = 1.0  
            pos_x = i * spacing_nm
            pos_y = 0.0
            pos_z = 0.0
            vel_x = 0.1
            vel_y = 0.0
            vel_z = 0.0
            
            # Randomized phase to emulate the Mott Insulator baseline
            phase_rad = random.uniform(0, 2 * math.pi)
            spin_vorticity = 0.5
            
            writer.writerow([
                node_id, mass_mev, pos_x, pos_y, pos_z,
                vel_x, vel_y, vel_z, phase_rad, spin_vorticity
            ])
            
    print(f"Blind dataset generated: {filename}")
    print(f"Total Particles: {num_particles}")
    print("Supercomputer Equivalent RAM Required (State Vector): > 0.5 Petabytes")

if __name__ == "__main__":
    generate_blind_dataset()
