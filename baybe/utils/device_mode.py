"""Device mode utilities."""

from contextlib import contextmanager
from typing import Generator

from gpytorch.settings import debug, fast_computations
from gpytorch.settings._feature_flag import _feature_flag

class single_device_mode(_feature_flag):
    """Context manager that forces all operations to happen on a single device."""
    _global_value = False

@contextmanager
def device_mode(state: bool = True) -> Generator[None, None, None]:
    """Context manager that forces all operations to happen on a single device.
    
    This combines multiple GPyTorch settings to ensure consistent device usage:
    - single_device_mode: Forces operations to stay on one device
    - debug: Enables additional device checks
    - fast_computations(solves=False): Prevents some caching that can lead to device mismatches
    
    Args:
        state: If True, enable single device mode. If False, disable it.
        
    Yields:
        None
    """
    with single_device_mode(state), debug(state), fast_computations(solves=False):
        yield