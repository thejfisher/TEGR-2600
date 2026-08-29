import numpy as np
import pysindy as ps

def test_spontaneous_emission():
    print("Testing Spontaneous Emission Extraction (Macro Scale)")
    
    # Simulate a population of N excited defects undergoing exponential decay
    # N(t) = N_0 * exp(-A * t)
    # This naturally emerges from a velocity-dependent damping force F = -lambda * v
    
    t = np.linspace(0, 10, 500)
    A = 0.45  # The emergent Einstein coefficient for this geometric structure
    N_0 = 1000
    N = N_0 * np.exp(-A * t)
    
    # Add a tiny bit of Poisson noise to simulate discrete particle drops
    noise = np.random.normal(0, 0.5, size=N.shape)
    N_noisy = N + noise
    
    # We feed ONLY the single variable N into the extraction algorithm
    X = N_noisy.reshape(-1, 1)
    
    # Define a library of polynomials up to cubic, plus sine and cosine
    # If the algorithm hallucinates, it will pick up false non-linear terms.
    functions = [
        lambda x: x,
        lambda x: x**2,
        lambda x: x**3,
        lambda x: np.sin(x),
        lambda x: np.cos(x),
    ]
    function_names = [
        lambda x: x,
        lambda x: x + "^2",
        lambda x: x + "^3",
        lambda x: "sin(" + x + ")",
        lambda x: "cos(" + x + ")",
    ]
    custom_library = ps.CustomLibrary(library_functions=functions, function_names=function_names)
    
    model = ps.SINDy(
        feature_library=custom_library, 
        differentiation_method=ps.SmoothedFiniteDifference(), 
        optimizer=ps.STLSQ(threshold=0.1, alpha=0.01)
    )
    
    model.fit(X, t=t)
    
    print("\nExtraction Results:")
    model.print()
    print("\nExpected Equation: x0' = -0.450 x0")
    
if __name__ == "__main__":
    test_spontaneous_emission()
