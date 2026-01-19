from datetime import datetime, timedelta
from typing import Dict, Any
from tzlocal import get_localzone


def cal_runtime(*, target: Dict[str, Any], dow: int | None = None) -> float | None | datetime | tuple:
    now = datetime.now(get_localzone())

    if dow:
        days_until = (dow - now.day + 7) % 7
        print(days_until)
        runtime = now + timedelta(days=days_until, **target)
        return now.ctime(), runtime.ctime()

    runtime = now + timedelta(**target)

def calculate_runtime_as_timestamp(
        *,
        target: Dict[str, Any], 
        dow: int | None = None
        ) -> float | None:
    now = datetime.now(get_localzone())
    try:
        _target = now.replace(**target)
    except ValueError:
        return None

    if dow:
        _target_day = (dow - now.day + 7) % 7
        if _target_day == 1 and _target <= now:
            # run in next schedule
            runtime = _target + timedelta(days=_target_day)
            return get_timestamp(runtime)

    if _target <= now and dow is None:
        # time passed go to next shift 
        runtime =_target + timedelta(days=1)
        return get_timestamp(runtime)
    
    return get_timestamp(_target)

def get_timestamp(t: datetime) -> float:
    return datetime.timestamp(t)

def is_ready_to_run(t: float) -> bool:
    return t >= datetime.now(tz=get_localzone()).timestamp()

def get_time_difference(t: float) -> float:
    return t - datetime.now(tz=get_localzone()).timestamp()


print(cal_runtime(target={"minutes": 30, "hours": 4}, dow=5))