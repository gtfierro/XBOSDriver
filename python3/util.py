from datetime import datetime

from timeseriestypes import UNIT_TIMES
from timeseriestypes import UNIT_TIME_SECONDS, UNIT_TIME_MILLISECONDS, \
                  UNIT_TIME_MICROSECONDS, UNIT_TIME_NANOSECONDS

UNIT_TIME_LOOKUP = {
    UNIT_TIME_SECONDS: 1,
    UNIT_TIME_MILLISECONDS: 1e3,
    UNIT_TIME_MICROSECONDS: 1e6,
    UNIT_TIME_NANOSECONDS: 1e9
}

def get_current_time_as(time_unit):
    """
    Returns current time in the given units. Uses local timezone
    """
    if time_unit not in UNIT_TIME_LOOKUP:
        raise TimestampException("Unit of Time {0} not in {1}".format(time_unit, UNIT_TIME_LOOKUP))
    return int(datetime.now().timestamp() * UNIT_TIME_LOOKUP[time_unit])
    
