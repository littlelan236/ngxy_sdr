import numpy as np
sig = np.fromfile("2.iq", dtype=np.complex64)
print(sig[-30:])