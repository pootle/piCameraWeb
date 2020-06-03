#!/usr/bin/env python3
"""
basic module for driving unipolar stepper via simple darlington drivers.

For example the el cheapo box of 10 28BYJ-48 steppers with ULN2003A based driver boards
"""

import pigpio
import threading, math, logging, pathlib, time, json

from pootlestuff import watchables as wv

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


class SimpleUniStepper(wv.watchablepigpio):
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
    def __init__(self, app=None, pio=None, stepdefs=StepTables, **kwargs):
        """
        pins:   list (like) of the 4 pins to drive the 4 outputs
        
        pio     : an existing instance of pigpio to use, or None, in which case
                  a new pigpio instance is setup and will be closed on exit

        stepdefs: dict that defines the various step modes to be used and details the power levels for each pin.

        agentclass & loglevel: passed to super()
        
        The motor can be set to various drive modes which provide different functionality.
        """
        self.running=True
        self.stepdefs=stepdefs
        mlist=list(self.stepdefs.keys())
        wables=[
               ('status',           wv.textWatch,       'starting',     False),     # a simple status string describing what the motor is doing
               ('drive_mode',       wv.enumWatch,       'off',          True,   {'vlist': ('stop', 'off', 'run', 'goto')}), # see class help
               ('drive_pins',       wv.textWatch,       '17 23 22 27',  True),    # list of the pins in use
               ('drive_stepmode',   wv.enumWatch,       mlist[0],       True,   {'vlist': mlist}),
               ('drive_uStepPos',   wv.intWatch,        0,              False),     # absolute pos in microsteps
               ('drive_reverse',    wv.enumWatch,       'normal',       True, {'vlist': ('normal', 'reverse')}),
               ('drive_PWM_frequency', wv.intWatch,     10000,          True),      # requested PWM frequency - see pigpio docs
               ('drive_actual_frequency',wv.intWatch,   0,              False),     # frequency actually used
               ('drive_hold_power', wv.floatWatch,      .3,             True, {'minv':.1, 'maxv':1}),   # power factor used when stationary
               ('drive_slow_power', wv.floatWatch,      .7,             True, {'minv':.1, 'maxv':1}),   # power factor when slow stepping
               ('drive_slow_limit', wv.floatWatch,      .01,            True),                          # step interval above which slow power factor used
               ('drive_fast_power', wv.floatWatch,      1,              True, {'minv':.1, 'maxv':1}),   # power factor when faster stepping
               ('drive_step_intvl', wv.floatWatch,      float('nan'),   False),     # step interval currently in use ('nan' when stopped)
               ('drive_target_intvl',wv.floatWatch,     .05,            True),      # once moving this will be the interval
               ('drive_target_pos', wv.intWatch,        0,              False),     # for goto mode - where we want to be
               ('drive_backlash',   wv.intWatch,        40,             True),      # primitive backlash adjustment
        ]
        if app is None:
            wables.append(('save_settingsbtn', wv.btnWatch,        'Save settings',False))
        super().__init__(app=app, wabledefs=wables, **kwargs)
        self.pins=[int(p) for p in self.drive_pins.getValue().split()]
        assert len(self.pins) == 4
        for i in self.pins:
            assert isinstance(i, int) and 0<i<32
        if app is None:
            self.save_settingsbtn.addNotify(self.savesettings, wv.myagents.user)  # this function is in the ancestor class, but we add the ability to use it here
        self.monthread=threading.Thread(name='cammon', target=self.run)
        self.monthread.start()

    def _dosteppins(self, lastentry, thisentry):
        for i in range(len(thisentry)):
            if lastentry is None or thisentry[i]!=lastentry[i]:
                self.pio.set_PWM_dutycycle(self.pins[i],thisentry[i])
        return thisentry

    def run(self):
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
        self.log(wv.loglvls.INFO,'stepper driver ready')
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

        for p in self.pins:
            self.pio.set_PWM_dutycycle(p,0)
        super().close()
        self.log(wv.loglvls.INFO,'stepper driver thread exits')

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
