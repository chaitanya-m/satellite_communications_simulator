import math
import random

import numpy as np


def sample_poisson(lam: float, rng: random.Random) -> int:
    """Sample Poisson(lam) using NumPy for stability across regimes.

    Deterministic given rng via a derived NumPy generator seed.
    """
    if lam <= 0.0:
        return 0
    seed = rng.getrandbits(64)
    generator = np.random.default_rng(seed)
    return int(generator.poisson(lam))
