#!/usr/bin/env python3
"""
basic module for driving unipolar stepper via simple darlington drivers.

For example the el cheapo box of 10 28BYJ-48 steppers with ULN2003A based driver boards
"""

import pigpio
import threading, math
import time
from pootlestuff import watchables as wv

# the pins that control the 4 outputs in the proper order!
defaultpins=(17, 23, 22,27)

# steptables is a dict with keys that identify the various ways we can step the motor.
# each key references a 2 part dict:
#       'factor' is the number of microteps this table moves the motor each step. Allows consistent position to be maintanined if the table is changed
#       'table' is list of lists. The lower levels list defines the pwm factor to apply to each pin that drives a motor coil (so all lists are the same 
#                   length and match the number of drive pins)
#           the top level list defines the sequence in which the lower list is applied.
# Note that these power levels are scaled by a power factor before being applied to the motor

StepTables={
    'single'    : {'factor':4, 'table':
                ((255, 0, 0, 0), (0, 255, 0, 0), (0, 0, 255, 0), (0, 0, 0, 255))},          # energise each coil in turn
    'double'    : {'factor':4, 'table':
                ((255, 255, 0, 0), (0, 255, 255, 0), (0, 0, 255, 255), (255, 0, 0, 255))},  # energise pairs of coils in turn
    'two'       : {'factor':2, 'table': 
                ((255, 0, 0, 0), (128,128, 0, 0), (0,255, 0, 0), (0, 128, 128, 0),          # 
                  (0, 0, 255, 0), (0, 0, 128, 128), (0, 0, 0, 255), (128, 0, 0, 128))},
    'four'      : {'factor':1, 'table': ((255, 0, 0, 0),
                                         (192, 64, 0, 0),
                                         (128, 128, 0, 0),
                                         (64, 192,0,0),
                                         (0,255,0,0),
                                         (0,192, 64, 0),
                                         (0, 128, 128, 0),
                                         (0, 64, 192, 0),
                                         (0, 0, 255,0),
                                         (0,0,192,64),
                                         (0,0,128,128),
                                         (0,0,64,192),
                                         (0,0,0,255),
                                         (64, 0, 0, 192),
                                         (128,0,0,128),
                                         (192, 0, 0, 64),
                   )},
}

class SimpleUniStepper(wv.watchableApp):
    """
    simple controller for a direct from pi (well via driver transistors) unipolar stepper.
    
    The class automatically runs a new thread to control the motor when instantiated.
    
    Most of the control and state variables are watchable based which allows easy integration into a local or
    web server based gui.

    The class drives the (4) gpio pins directly, and provides no capabilities for ramp-up ramp-down of motor speed
    so the top speed achievable is limited to that achievable from a standing start. The pins are driven using PWM
    so there is good control of power.
    
    The class maintains a variable drive_uStepPos with the current motor position in the smallest microsteps available.
    (This means that positions do not change in moving from full (single) stepping to 1/4 stepping for example.)

    The motor is prepared by setting (at least) the table entry to use (see below under internals) and the step interval.
    Then the 'drive mode' is set to define how the motor is controlled:
        'stop'   : all drive is switched off
        'off'    : the motor is stationary but with a holding current defined by drive_hold_power
        'run'    : the motor runs continuously at the speed defined by drive_target_intvl (-ve for reverse)
                   drive_target_intvl can be changed at any time to change the speed
        'goto'   : The motor continuously monitors the variable drive_target_pos and compares it with drive_uStepPos
                   It then drives the motor in the appropriate direction to reach drive_target_pos.
                   drive_target_pos can be changed at any time.
    
    Internals
    =========
    The driver uses a control table with named entries (the sample table here has 4, but there can be any number).
    Each entry in the table is made up of a list of 4-tuples. Each 4-tuple defines the power required for each od the 4 pins.
    (power is in the range 0 (off) to 255 (full power). These values are simply scaled further by a power factor which allows
    power to be reduced (or switched off) when stationary, and a lower power level to be used for slow step speeds.
    
    The full list is typically a power of 2 long - 4, 8, 16 etc.
    
    In the sample table:
        'single' switches each pin in turn to full power
        'double' switches pairs of pins in turn to full power (more current and more torque)
        'two'    switches 1 pin to full power then that pin and an adjacent pin to 1/2 power, then the adjacent pin to full power....
        
    """
    def __init__(self, camapp, settings, pins=defaultpins, pio=None, stepdefs=StepTables, **kwargs):
        """
        pins:   list (like) of the 4 pins to drive the 4 outputs
        
        pio     : an existing instance of pigpio to use, or None, in which case
                  a new pigpio instance is setup and will be closed on exit

        stepdefs: dict that defines the various step modes to be used and details the power levels for each pin.
        
        settings: dict of previously saved values for appropriate variables that override the built-in defaults. 

        agentclass & loglevel: passed to super()
        
        The motor can be set to various drive modes which provide different functionality.
        """
        self.camapp=camapp
        self.loglevel=wv.loglvls.INFO
        assert len(pins) == 4
        for i in pins:
            assert isinstance(i, int) and 0<i<32
        if not pio is None:
            ptest=pigpio.pi()
            if not ptest.connected:
                raise ValueError('no pigpio connection available')
            ptest.stop()
        self.pins=pins
        self.pio=pio
        self.running=True
        self.stepdefs=stepdefs
        super().__init__(agentclass=wv.myagents, loglevel=wv.loglvls.INFO)
        self.status=wv.textWatch(app=self, value='starting')
                                                        # a simple status string describing what the motor is doing
        self.drive_mode=wv.enumWatch(app=self, vlist=('stop', 'off', 'run', 'goto'), value='off')
        mlist=list(self.stepdefs.keys())
        self.drive_stepmode=wv.enumWatch(app=self, vlist=mlist, value=settings.get('drive_stepmode', mlist[0]))
        self.drive_uStepPos=wv.intWatch(app=self, value=settings.get('drive_uStepPos', 0))                  
                                                        # maintains the absolute (micro)step position since we started
        self.drive_reverse=wv.enumWatch(app=self, vlist=('normal','reverse'), value=settings.get('drive_reverse', 'normal')) 
                                                        # flips motor direction when set
        self.drive_PWM_frequency=wv.intWatch(app=self, value=settings.get('drive_PWM_frequency',10000))
                                                        # requested PWM frequency
        self.drive_actual_frequency=wv.intWatch(app=self, value=0)          
                                                        # actual PWM frequency
        self.drive_hold_power=wv.floatWatch(app=self, minv=0, maxv=1, value=settings.get('drive_hold_power', .3)) 
                                                        # power factor used when stationary
        self.drive_slow_power=wv.floatWatch(app=self, minv=.5, maxv=1, value=settings.get('drive_slow_power', .7))
                                                        # power factor when slow stepping
        self.drive_slow_limit=wv.floatWatch(app=self, value=settings.get('drive_slow_limit', .01))
                                                        # step interval above which slow power factor used
        self.drive_fast_power=wv.floatWatch(app=self, value=settings.get('drive_fast_power', 1))
                                                        # power factor for faster steps
        self.drive_step_intvl=wv.floatWatch(app=self, value=float('nan'))   # initialise step interval to unknown (=> stopped) -ve reverse, +ve fwds
        self.drive_target_intvl=wv.floatWatch(app=self, value=settings.get('drive_target_intvl', .1))
                                                        # once moving, this is the interval between full steps
        self.drive_target_pos=wv.intWatch(app=self, value=0)
                                                        # for goto mode this is where we want to be
        self.drive_backlash=wv.intWatch(app=self, value=settings.get('drive_backlash', 80))
        self.monthread=threading.Thread(name='cammon', target=self.run)
        self.monthread.start()

    def _dosteppins(self, lastentry, thisentry):
        for i in range(len(thisentry)):
            if lastentry is None or thisentry[i]!=lastentry[i]:
                self.pio.set_PWM_dutycycle(self.pins[i],thisentry[i])
        return thisentry

    def run(self):
        if self.pio is None:
            self.mypio=True
            self.pio=pigpio.pi()
        else:
            self.mypio=False
        if not self.pio.connected:
            raise ValueError('no pigpio connection available')
            return
        for p in self.pins:
            self.pio.set_PWM_frequency(p, self.drive_PWM_frequency.getValue())
        self.drive_actual_frequency.setValue(self.pio.get_PWM_frequency(self.pins[0]), agent=wv.myagents.app)
        currentStepMode=self.drive_stepmode.getValue()
        usetable, stepfactor =self._maketable(currentStepMode)
        stepintvl=self.drive_step_intvl.getValue()*stepfactor
        nextsteptime=time.time() + 1 if math.isnan(stepintvl) else abs(stepintvl)
        thisentry=None
        lastentry=None
        stepindex=0  # index into the array of pin pwm values  - used to set new pwm values on each step
        gotoisfwd=True;
        while self.running:
            delay=nextsteptime-time.time()
            if delay > .25:
                time.sleep(.25)
            else:
                if delay > .0001:
                    time.sleep(delay)
                if math.isnan(stepintvl):
                    pf=self.drive_hold_power.getValue()
                    tabe=[round(x*pf) for x in usetable[stepindex]]
#                    print('using table', tabe)
                else:
                    tabe=usetable[stepindex]
                lastentry = self._dosteppins(lastentry, tabe)  
                stepintvl=self.drive_step_intvl.getValue()
                stepchange = 0 if math.isnan(stepintvl) else 1 if stepintvl > 0 else -1
                nextsteptime += .25 if math.isnan(stepintvl) else abs(stepintvl) 
                stepindex += stepchange
                if stepindex >= len(usetable):
                    stepindex=0
                elif stepindex < 0:
                    stepindex=len(usetable)-1
                self.drive_uStepPos.increment(wv.myagents.app, stepchange*stepfactor)
            mode=self.drive_mode.getValue()
            if mode=='stop' or mode=='off':
                self.drive_step_intvl.setValue(float('nan'), self.agentclass.app)
                self.status.setValue('stopped', self.agentclass.app)
            elif mode=='run':
                t_intvl=self.drive_target_intvl.getValue()
                self.drive_step_intvl.setValue(t_intvl, self.agentclass.app)
                self.status.setValue('run continuous with tick %5.4f' % t_intvl, self.agentclass.app)
            elif mode=='goto':
                change=self.drive_target_pos.getValue()-self.drive_uStepPos.getValue()
                current=self.drive_step_intvl.getValue()
                if abs(change) < stepfactor:
                    intset = float('nan')
                    self.status.setValue('goto at target', self.agentclass.app)
                elif change > 0:
                    intset = abs(self.drive_target_intvl.getValue())
                    self.status.setValue('goto moving %7d' % intset, self.agentclass.app)
                    if not gotoisfwd:
                        gotoisfwd=True
                        self.drive_uStepPos.increment(self.agentclass.app, -self.drive_backlash.getValue())
                else:
                    intset = -abs(self.drive_target_intvl.getValue())
                    self.status.setValue('goto moving %7d' % intset, self.agentclass.app)
                    if gotoisfwd:
                        gotoisfwd=False
                        self.drive_uStepPos.increment(self.agentclass.app, self.drive_backlash.getValue())
                if not (math.isnan(intset) and math.isnan(current)) and intset != current:
                    print('change speed to %s from %s' % ('stopped' if math.isnan(intset) else '%4.3f' % intset, current))
                    self.drive_step_intvl.setValue(intset, self.agentclass.app)
            if currentStepMode != self.drive_stepmode.getValue():
                currentStepMode = self.drive_stepmode.getValue()
                usetable, stepfactor =self._maketable(currentStepMode)

#        print('motor thread shutting down')
        for p in self.pins:
            self.pio.set_PWM_dutycycle(p,0)
        if self.mypio:
            self.pio.stop()
            self.mypio=False
        self.pio=None

    def _maketable(self, stepmode):
        newSpeed= self.drive_target_intvl.getValue()
        if self.drive_mode.getIndex() == 0:
            pfact=0
        elif abs(newSpeed) < .0001:
            pfact=self.drive_hold_power.getValue()
        elif abs(newSpeed) > self.drive_slow_limit.getValue():
            pfact=self.drive_slow_power.getValue()
        else:
            pfact= self.drive_fast_power.getValue()
        onetable=self.stepdefs[stepmode]
        newtable=[[int(oneval*pfact) for oneval in coilvals] for coilvals in onetable['table']]
        flipdir=self.drive_reverse.getIndex() == 1
        if flipdir != (newSpeed < 0):
            newtable=list(reversed(newtable))
#        print('new power table for %s:\n  ' % stepmode, '\n   '.join(['%3d, %3d, %3d, %3d' % tuple(cvals) for cvals in newtable]))
        return newtable, onetable['factor']

    def moveby(self, change, intvl=None):
        if not intvl is None:
            self.drive_target_intvl.setValue(intvl, self.agentclass.app)
        self.drive_target_pos.setValue(self.drive_uStepPos.getValue()+change, self.agentclass.app)
        if self.drive_mode.getValue() != 'goto':
            self.drive_mode.setValue('goto', self.agentclass.app)

    def setmode(self, mode):
        oldv=self.drive_stepmode.getValue()
        print('mode change from %s to %s' % (oldv, mode))
        self.drive_stepmode.setValue(mode, self.agentclass.app)

    def close(self):
        self.running=False

    def log(self, loglevel, *args, **kwargs):
        """
        request a logging operation. This does nothing if the given loglevel is < the loglevel set in the object
        """
        if self.loglevel.value <= loglevel.value:
            self.camapp.log(loglevel, *args, **kwargs)