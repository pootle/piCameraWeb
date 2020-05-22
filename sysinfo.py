#!/usr/bin/python3
"""
This module provides a simple link to enable various psutils data to be retrieved and returned in a dict

"""
import psutil

def getsystemstats(qp, pp):
    xx=[f for f in qp['fields']]
    calls={}
    for x in xx:
        if x in rmap:
            rx=rmap[x]
            if rx[0] in calls:
                calls[rx[0]].append(rx[1])
            else:
                calls[rx[0]] = [rmap[x][1]]
        else:
            print('oops in getsystemstats', x)
    result={}
    for acall, adata in calls.items():
        ares=acall()
        for item in adata:
            result[item[0]]=item[1](data=ares, field=item[0], **item[2])
    return result

def extract_cpu(data, field, scfield=None):
    if field=='cpu_busy':
        return 100-getattr(data, 'idle')
    else:
        return getattr(data, scfield)

def extract_sensor(data, field, dkey, dent, dattr):
    return getattr(data[dkey][dent], 'current')

rmap={
    'cpu_busy' : (psutil.cpu_times_percent,     ('cpu_busy', extract_cpu, {})),
    'cpu_temp' : (psutil.sensors_temperatures,  ('cpu_temp', extract_sensor, {'dkey': 'cpu-thermal', 'dent': 0, 'dattr': 'current'})),
}

