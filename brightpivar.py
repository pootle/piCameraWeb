#!/usr/bin/python3
"""
This module drives brightpi LEDs very simply by providing an enumVar which can be used to turn on and off the visible
and IR leds on a brightpi
"""

from pootlestuff.pvars import enumVar

import brightpi # do it here to fail early, remove this line to fail on setup

class brightpiVar(enumVar):
    def __init__(self,
            vlist=('ALL_OFF', 'IR_ON', 'VIS_ON', 'ALL_ON'),
            fallbackValue='ALL_OFF',
            enabled=True, 
            **kwargs):
        try:
            import brightpi
            bpOK=True
        except ModuleNotFoundError:
            bpOK=False
            errmsg='brightpi module not installed'
            enabled=False
            self.bpcontrol=None
        if bpOK:
            try:
                self.bpcontrol=brightpi.BrightPi()
            except OSError:
                self.bpcontrol=None
                bpOK=False
                errmsg='brightpi board does not seem to be connected'
                enabled=False
        if not self.bpcontrol is None:
            self.setparams={
                0:{'leds': brightpi.LED_ALL, 'state': 0},
                1:{'leds': brightpi.LED_IR, 'state': 1},
                2:{'leds': brightpi.LED_WHITE, 'state': 1},
                3:{'leds': brightpi.LED_ALL, 'state': 1},
            }
        super().__init__(vlist=vlist, fallbackValue=fallbackValue, enabled=enabled, **kwargs)

    def setValue(self, value, agent):
        if self.enabled:
            changed=super().setValue(value, agent)
            if changed:
                if self.bpcontrol is None:
                    raise RuntimeError('brightpi device unavailable')
                else:
                    self.bpcontrol.set_led_on_off(**self.setparams[self.getIndex()])
            return changed
        return False
#        raise ValueError('brightpi interface is disabled')