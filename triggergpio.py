#!/usr/bin/python3
"""
gpio pin monitor activity

sets status watchablevar whe triggered. Provides simple debounce using pipgio facilities
"""
import pigpio

import time
from pootlestuff import watchables as wv

class gpiotrigger(wv.watchablepigpio):
    """
    an activity that watches a gpio pin and sets a status when the pin level changes.
    
    Can deglitch the pin using pigpio facilities and also allows the trigger to be set by the
    user for testing (or any other reason.
    
    The pin is always watched, but the trigger state is only set if the activity is 'on' 
    """
    def __init__(self, app=None, **kwargs):
        wables=[
            ('status',          wv.enumWatch,       'off',          False,  {'vlist': ('off', 'watching', 'triggered')}),
            ('usertrigger',     wv.enumWatch,       'set trigger',  False,  {'vlist': ('set trigger','release trigger')}),
            ('pintrigger',      wv.enumWatch,       'off',          False,  {'vlist': ('off', 'on')}),
            ('startstopbtn',    wv.enumWatch,       'start',        False,  {'vlist': ('start','stop')}),     
            ('autostart',       wv.enumWatch,       'off',          True,   {'vlist': ('off', 'on')}),
            ('pinno',           wv.intWatch,        17,             True,   {'minv': 0, 'maxv': 27}),
            ('pullud',          wv.enumWatch,       'none',         True,   {'vlist': ('none','up','down')}),
            ('triglvl',         wv.enumWatch,       'high',         True,   {'vlist': ('high', 'low')}),
            ('steadytime',      wv.floatWatch,      .1,             True,   {'minv': 0, 'maxv': 30}),
            ('holdtime',        wv.floatWatch,      .5,             True,   {'minv': 0, 'maxv': 30}),
            ('trigcount',       wv.intWatch,        0,              False),
            ('lastactive',      wv.floatWatch,      float('nan'),   False),
            ('lasttrigger',     wv.floatWatch,      float('nan'),   False),
        ]
        if app is None:
            wables.append(('save_settingsbtn', wv.btnWatch,        'Save settings',False))
        super().__init__(app=app, wabledefs=wables, **kwargs)
        if self.autostart.getIndex()==1:                # if autostart is on, flip the start/stop button
            self.startstopbtn.setIndex(1, wv.myagents.app)
        monpin=self.pinno.getValue()
        self.pio.set_mode(monpin, pigpio.INPUT)
        self.pio.set_pull_up_down(monpin, {'none': pigpio.PUD_OFF, 'up': pigpio.PUD_UP, 'down': pigpio.PUD_DOWN}[self.pullud.getValue()])
        steady = round(self.steadytime.getValue()*1000000)
        if steady > 0:
            hold=round(self.holdtime.getValue()*1000000)
            if hold > 0:
                self.pio.set_noise_filter(monpin, steady, hold)
            else:
                self.pio.set_glitch_filter(monpin, steady)
        self.pigpcb=self.pio.callback(monpin, pigpio.EITHER_EDGE, self.level_change_detected)
        self.usertrigger.addNotify(self.usersetclear,  wv.myagents.user)
        self.startstopbtn.addNotify(self.startstop,  wv.myagents.user)
        if app is None:
            self.save_settingsbtn.addNotify(self.savesettings, wv.myagents.user)  # this function is in the ancestor class, but we add the ability to use it here
        self.log(wv.loglvls.INFO, 'trigger activity set up OK')
           
    def usersetclear(self, watched, agent, newValue, oldValue):
        if self.usertrigger.getIndex()==1:      # user sets trigger manually
            if self.status.setIndex(2, wv.myagents.app):
                self.lasttrigger.setValue(time.time(), wv.myagents.app)     # only do this if the value changed
                self.trigcount.increment(wv.myagents.app)
        else: # clear manual user trigger
            if self.pintrigger.getIndex()==0:                               # check if pin is triggered
                                                                            # and set status off or watching as appropriate
                self.status.setIndex(1 if self.startstopbtn.getIndex()==1 else 0, wv.myagents.app)                    
                self.lasttrigger.setValue(time.time(), wv.myagents.app)

    def startstop(self, watched, agent, newValue, oldValue):                # user started or stopped the activity
        if self.startstopbtn.getIndex() == 1: # user clicked on Start
            if self.pintrigger.getIndex()==1:
                if self.status.setIndex(2, wv.myagents.app): # set status if pin already triggered, but only update other things if it changed
                    self.lasttrigger.setValue(time.time(), wv.myagents.app)
                    self.trigcount.increment(wv.myagents.app)
            self.lastactive.setValue(time.time(), wv.myagents.app)
        else:
            if self.usertrigger.getIndex()==0: # user trigger is off, so clear status
                if self.status.setIndex(0, wv.myagents.app):
                    self.lasttrigger.setValue(time.time(), wv.myagents.app)

    def level_change_detected(self, gpiopin, level, tick):
        pinhigh=level==1
        if self.triglvl.getValue()=='low':
            pinhigh=not pinhigh
        if pinhigh:
            self.pintrigger.setIndex(1, wv.myagents.app)
            if self.startstopbtn.getIndex() == 1: # and we are watching
                if self.status.setIndex(2, wv.myagents.app):    # set the status and if it changed.....
                    self.lastactive.setValue(time.time(), wv.myagents.app)
                    self.trigcount.increment(wv.myagents.app)
        else:
            if self.usertrigger.getIndex()==0:                  # user trigger isn't set - so clear 
                self.lastactive.setValue(time.time(), wv.myagents.app)
                self.status.setIndex(1 if self.startstopbtn.getIndex()==1 else 0, wv.myagents.app)
