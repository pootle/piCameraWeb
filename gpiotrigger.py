#!/usr/bin/python3
"""
gpio pin monitor activity

Simple version - no debounce
"""
try:
    import pigpio
    PIGPIO=True
except:
    PIGPIO=False

import logging, time
from pootlestuff import pvars

gpiovardefs=(
    {'name': 'status',      '_cclass': pvars.enumVar,       'fallbackValue': 'stopped', 'vlist': ('stopped', 'failed', 'watching', 'triggered')},
    {'name': 'pinno',       '_cclass': pvars.intVar,        'fallbackValue': 17, 'minv': 0, 'maxv': 27, 'filters': ['pers']},
    {'name': 'pullud',      '_cclass': pvars.enumVar,       'fallbackValue':'none', 'vlist': ('none','up','down'), 'filters': ['pers']},
    {'name': 'triglvl',     '_cclass': pvars.enumVar,       'fallbackValue': 'high', 'vlist': ('high', 'low'), 'filters': ['pers']},
    {'name': 'steadytime',  '_cclass': pvars.intVar,        'fallbackValue': 0, 'minv': 0, 'maxv': 300000},
    {'name': 'holdtime',    '_cclass': pvars.intVar,        'fallbackValue': 0, 'minv': 0, 'maxv': 1000000},
    {'name': 'startstop',   '_cclass': pvars.enumVar,       'fallbackValue': 'start', 'vlist': ('start', 'stop')}, # the gui shows this as a cyclic button
    {'name': 'trigcount',   '_cclass': pvars.intVar,        'fallbackValue': 0},
    {'name': 'lastactive',  '_cclass': pvars.floatVar,      'fallbackValue': 0},
    {'name': 'lasttrigger', '_cclass': pvars.floatVar,      'fallbackValue': 0}
)

class gpiotrigger(pvars.groupVar):
    def __init__(self, **kwargs):
        super().__init__(childdefs=gpiovardefs, **kwargs)
        self.pigp=None
        if PIGPIO:
            self['startstop'].addNotify(self.startstop, 'driver')
            self.log(logging.INFO, 'trigger activity set up OK')
        else:
            self['status'].setIndex(1, 'driver')
            self.log(logging.INFO, 'trigger activty set up failed - pigpio unavailable')
        
    def startstop(self, var, agent, newValue, oldValue):
        if oldValue=='start':
            assert self.pigp is None
            self.pigp=pigpio.pi()
            if self.pigp.connected:
                monpin=self['pinno'].getValue()
                self.pigp.set_mode(monpin, pigpio.INPUT)
                self.pigp.set_pull_up_down(monpin, {'none': pigpio.PUD_OFF, 'up': pigpio.PUD_UP, 'down': pigpio.PUD_DOWN}[self['pullud'].getValue()])
                steady = self['steadytime'].getValue()
                if steady > 0:
                    hold=self['holdtime'].getValue()
                    if hold > 0:
                        self.pigp.set_noise_filter(monpin, steady, hold)
                    else:
                        self.pigp.set_glitch_filter(monpin, steady)
                self.pigpcb=self.pigp.callback(monpin, pigpio.EITHER_EDGE, self.level_change_detected)
                pinhigh=self.pigp.read(monpin)==1
                if self['triglvl'].getValue()=='low':
                    pinhigh=not pinhigh
                self['status'].setIndex(3 if pinhigh else 2, 'driver')
                if pinhigh:
                    self['lasttrigger'].setValue(time.time(), 'driver')
                    self['trigcount'].increment('driver')
                self['lastactive'].setValue(time.time(), 'driver')
            else:
                self.pigp.stop()
                self.pigp=None
                self['status'].setIndex(1, 'driver')
        else:
            if not self.pigp is None:
                self.pigpcb.cancel()
                self.pigp.set_pull_up_down(self['pinno'].getValue(), pigpio.PUD_OFF)
                self.pigpcb=None
                self.pigp.stop()
                self.pigp=None
                self['lastactive'].setValue(time.time(), 'driver')
            self['status'].setIndex(0, 'driver')

    def level_change_detected(self, gpiopin, level, tick):
        pinhigh=level==1
        if self['triglvl'].getValue()=='low':
            pinhigh=not pinhigh
        newv=1 if pinhigh else 0
        if newv==1:
            self['lastactive'].setValue(time.time(), 'driver')
            self['trigcount'].increment('driver')
        self['status'].setIndex(3 if pinhigh else 2, 'driver')
