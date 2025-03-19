import numpy as np

# Add backward compatibility for numpy.float_
if not hasattr(np, 'float_'):
    np.float_ = np.float64