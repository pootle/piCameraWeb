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

import time
from pootlestuff import watchables as wv

class gpiotrigger():
    def __init__(self, camapp, settings, loglevel=wv.loglvls.INFO):
        self.camapp=camapp
        self.loglevel=loglevel
        if not PIGPIO:
            stat='unavailable'
            self.log(wv,loglvls.WARN,'unable to import PIGPIO')
        else:
            try:
                pp=pigpio.pi()
                if pp.connected:
                    stat='off'
                else:
                    self.log(wv.loglvls.WARN, 'pigpio is not connecting')
                    stat='broken'
                pp.stop()
            except:
                stat='broken'
                self.log(wv.loglvls.WARN, 'exception starting pigpio')
        self.agentclass=self.camapp.agentclass
        self.status = wv.enumWatch(app=self, vlist=('off', 'watching', 'triggered', 'unavailable', 'broken'), value=stat)
        self.usertrigger= wv.enumWatch(app=self, vlist=('set trigger','release trigger'), value='set trigger')
        self.usertrigger.addNotify(self.usersetclear,  wv.myagents.user)
        self.settings=settings
        if stat=='off':
            self.autostart  = wv.enumWatch(app=self, vlist=('off', 'on'), value='off')
            self.pinno      = wv.intWatch(app=self, minv=0, maxv=27, value=17)
            self.pullud     = wv.enumWatch(app=self, vlist=('none','up','down'), value='none')
            self.triglvl    = wv.enumWatch(app=self, vlist=('none','up','down'), value='none')
            self.steadytime = wv.floatWatch(app=self, minv=0, maxv=.3, value=.1)
            self.holdtime   = wv.floatWatch(app=self, minv=0, maxv=1, value=.5)
            self.startstopbtn= wv.enumWatch(app=self, vlist=('start','stop'), value='start')
            self.trigcount  = wv.intWatch(app=self, value=0)
            self.lastactive = wv.floatWatch(app=self, value=float('nan'))
            self.lasttrigger= wv.floatWatch(app=self, value=float('nan'))
            for setw, setv in self.settings.items():
                if hasattr(self, setw):
                    try:
                        getattr(self, setw).setValue(setw, wv.myagents.app)
                        self.log(wv.loglvls.INFO, 'set %s to %s OK' % (setw, setv))
                    except:
                        self.log(wv.loglvls.WARN, 'set %s to %s failed' % (setw, setv))
            self.pigp=None
            self.startstopbtn.addNotify(self.startstop,  wv.myagents.user)
            self.log(wv.loglvls.INFO, 'trigger activity set up OK')
        else:
            self.pigp=None
            self.log(wv.loglvls.INFO, 'trigger activty set up failed - pigpio %s' % stat)

    def usersetclear(self, watched, agent, newValue, oldValue):
        if self.usertrigger.getIndex()==1: # user sets trigger manually
            if self.status.getIndex()!=2:  # 2 -> already triggered by gpio pin - do nothing
                self.status.setIndex(2, wv.myagents.app)
                self.lasttrigger.setValue(time.time(), wv.myagents.app)
                self.trigcount.increment(wv.myagents.app)
        else: # clear manual user trigger
            if self.pigp:       # first check if gpio pin is triggered and leave status if it is
                pinhigh=self.pigp.read(self.pinno.getValue())==1
                if self.triglvl.getValue()=='low':
                    pinhigh=not pinhigh
                if not pinhigh:
                    self.status.setIndex(1, wv.myagents.app)
                    self.lasttrigger.setValue(time.time(), wv.myagents.app)
            else:
                if PIGPIO:
                    if hasattr(self, 'startstopbtn'):
                        if self.startstopbtn.getIndex()==0:
                            newstatus='off'
                        else:
                            newstatus='watching'
                    else:
                        newstatus='broken'
                else:
                    newstatus = 'unavailable'
                self.status.setValue(newstatus, wv.myagents.app)
                self.lasttrigger.setValue(time.time(), wv.myagents.app)

    def startstop(self, watched, agent, newValue, oldValue):
        if self.startstopbtn.getIndex() == 1: # user clicked on Start
            assert self.pigp is None
            self.pigp=pigpio.pi()
            if self.pigp.connected:
                monpin=self.pinno.getValue()
                self.pigp.set_mode(monpin, pigpio.INPUT)
                self.pigp.set_pull_up_down(monpin, {'none': pigpio.PUD_OFF, 'up': pigpio.PUD_UP, 'down': pigpio.PUD_DOWN}[self.pullud.getValue()])
                steady = round(self.steadytime.getValue()*1000000)
                if steady > 0:
                    hold=round(self.holdtime.getValue()*1000000)
                    if hold > 0:
                        self.pigp.set_noise_filter(monpin, steady, hold)
                    else:
                        self.pigp.set_glitch_filter(monpin, steady)
                self.pigpcb=self.pigp.callback(monpin, pigpio.EITHER_EDGE, self.level_change_detected)
                pinhigh=self.pigp.read(monpin)==1
                if self.triglvl.getValue()=='low':
                    pinhigh=not pinhigh
                self.status.setIndex(2 if pinhigh else 1, wv.myagents.app)
                if pinhigh:
                    self.lasttrigger.setValue(time.time(), wv.myagents.app)
                    self.trigcount.increment(wv.myagents.app)
                self.lastactive.setValue(time.time(), wv.myagents.app)
            else:
                self.pigp.stop()
                self.pigp=None
                self.status.setIndex(0, wv.myagents.app)
        else:
            self.closegpio()
            self.status.setIndex(0, wv.myagents.app)

    def closegpio(self):
        if not self.pigp is None:
            self.pigpcb.cancel()
            self.pigp.set_pull_up_down(self.pinno.getValue(), pigpio.PUD_OFF)
            self.pigpcb=None
            self.pigp.stop()
            self.pigp=None
            self.lastactive.setValue(time.time(), wv.myagents.app)

    def closeact(self):
        self.closegpio()

    def level_change_detected(self, gpiopin, level, tick):
        pinhigh=level==1
        if self.triglvl.getValue()=='low':
            pinhigh=not pinhigh
        newv=1 if pinhigh else 0
        if newv==1:
            self.lastactive.setValue(time.time(), wv.myagents.app)
            self.trigcount.increment(wv.myagents.app)
            self.status.setIndex(2, wv.myagents.app)
        else:
            if self.usertrigger.getIndex()==0:
                self.lastactive.setValue(time.time(), wv.myagents.app)
                self.trigcount.increment(wv.myagents.app)
                self.status.setIndex(1, wv.myagents.app)

    def log(self, loglevel, *args, **kwargs):
        """
        request a logging operation. This does nothing if the given loglevel is < the loglevel set in the object
        """
        if self.loglevel.value <= loglevel.value:
            self.camapp.log(loglevel, *args, **kwargs)