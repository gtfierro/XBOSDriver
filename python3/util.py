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

def buildkv(fullname, obj, separator='/'):
    if isinstance(obj, dict):
        rv = []
        for newk, newv in obj.items():
            if len(fullname):
                rv += buildkv(fullname + separator + newk, newv, separator)
            else:
                rv += buildkv(newk, newv, separator)
        return rv
    else:
        return [(fullname, obj)]

# from smap.util
# make a nested object from a config file line
def build_recursive(d, suppress=['type', 'key', 'uuid']):
    rv = {}
    for k, v in d.items():
        if k in suppress: continue
        pieces = k.split('/')
        cur = rv
        for cmp in pieces[:-1]:
            if not cur.has_key(cmp):
                cur[cmp] = {}
            cur = cur[cmp]
        cur[pieces[-1]] = v
    return rv

# from smap.util
def dict_merge(o1, o2):
    """Recursively merge dict o1 into dict o2.
    """
    if not isinstance(o1, dict) or not isinstance(o2, dict):
        return o2
    o2 = dict(o2)
    for k, v in o1.items():
        if k in o2:
            o2[k] = dict_merge(v, o2[k])
        else:
            o2[k] = v
    return o2

