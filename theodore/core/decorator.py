"""
Docstring for theodore.core.decorator

This wrapper sets the theodore task flag on tasks decorated with it, tagging them as 
executable by theodore dispatch. 

tasks without the theodore tag are not allowed to run
it creates a whitelist perse of functions that are allowed to be perfomed by dispatch 
to prevent detrimental function calls.

"""

import functools

def theodore_task(name: str | None = None):
    def decorator(func):
        # wrap function to keep function Identity
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        wrapper._is_theodore_task = True
        wrapper._name = name or func.__name__
        return wrapper
    return decorator