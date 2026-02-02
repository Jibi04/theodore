import functools

def theodore_task(name: str | None = None):
    """
    Docstring for theodore_task
    
    :param name: Description
    :type name: str | None

    Decorates functions as Theodore tasks
    """

    def decorator(func):
        # Wrap function to keep function Identity 

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        wrapper._is_theodore_task = True
        wrapper._task_name = name or func.__name__
        return wrapper
    return decorator
