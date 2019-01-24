#!/usr/bin/python3
"""
module to pick up gpio input for movement detection (e.g. PIR sensor)
"""
import time, pigpio
import logging

import papps
import piCamHtml as pchtml

class externalmover(papps.appThreadAct):
    def __init__(self, **kwargs):
        self.gph=pigpio.pi()
        if not self.gph.connected:
            raise RuntimeError('pigpio not running - external sensing not available')
        super().__init__(**kwargs)
        self.vars['lasttrigger'].setValue('app', 0)

    def startedlogmsg(self):
        return 'external gpio trigger on gpio {} starts'.format(self.vars['triggerpin'].getValue('pers'))

    def endedlogmsg(self):
        return 'external gpio trigger on gpio {} ends, {} triggers'.format(self.vars['triggerpin'].getValue('pers'), 
                                                                           self.vars['triggercount'].getValue('app'))

    def reportstatetime(self, level):
        tnow=time.time()
        if self.lastedgetime==0:
            if self.loglvl <= logging.DEBUG:
                self.log.debug('first transition is to {}'.format('high' if level == 1 else 'low'))
        else:
            elapsed=tnow-self.lastedgetime
            if self.loglvl <= logging.DEBUG:
                self.log.debug('{} level lasted {:1.2f} seconds'.format('high' if level==0 else 'low', elapsed))
        self.lastedgetime=tnow

    def trigger(self, pin, level, tick):
        if self.triggered:
            if level==0:
                self.triggered=False
                self.reportstatetime(level)
            else:
                if self.loglvl <= logging.DEBUG:
                    self.log.debug('unexpected trigger to high when triggered')
        else:
            if level==1:
                self.triggered=True
                self.vars['triggercount'].setValue('app', self.vars['triggercount'].getValue('app')+1)
                tnow=time.time()
                self.vars['lasttrigger'].setValue('app', tnow)    
                self.reportstatetime(level)         
            else:
                if self.loglvl <= logging.DEBUG:
                    self.log.debug('unexpected trigger to low when not triggered')

    def run(self):
        self.startDeclare()
        tpin=self.vars['triggerpin'].getValue('app')
        tnow=time.time()
        self.gph.set_mode(tpin,pigpio.INPUT)
        self.lastedgetime=0
        self.triggered = self.gph.read(tpin)==1
        self.callbackref=self.gph.callback(tpin, edge=pigpio.EITHER_EDGE, func=self.trigger)
        self.vars['triggercount'].setValue('app',1 if self.triggered else 0)
        self.vars['lasttrigger'].setValue('app', tnow if self.triggered else 0)
        while self.requstate != 'stop':
            time.sleep(1)
            if self.triggered:
                tnow=time.time()
                if self.vars['lasttrigger'].getValue('app')+1 < tnow:
                    self.vars['lasttrigger'].setValue('app', tnow)
        self.callbackref.cancel()
#        self.summaryState='closing'
        self.endDeclare()

############################################################################################
# user interface setup for gpio move detection - web page version 
############################################################################################

extmovetable=(
    (pchtml.htmlStatus  , pchtml.HTMLSTATUSSTRING),
    (pchtml.htmlInt,        {
            'name'      : 'triggerpin', 'minv':1, 'maxv':63, 'clength':2, 'fallbackValue': 17,'loglvl': logging.DEBUG,
            'readersOn' : ('html', 'app', 'pers'),
            'writersOn' : ('app', 'pers', 'user'),            
            'label'     : 'gpio pin',
            'shelp'     : 'broadcom pin number for external sensor'}),
    (pchtml.htmlCyclicButton, {
            'name' : 'run',  'fallbackValue': 'start now', 'alist': ('start now', 'stop now '),
            'onChange'  : ('dynamicUpdate','user'),
            'label': 'enable detection', 
            'shelp': 'enables / disables this motion detection method',
    }),
    (pchtml.htmlInt,        {
            'name'      : 'triggercount', 'fallbackValue': 0,
            'readersOn' : ('html', 'app', 'webv'),
            'writersOn' : ('app',),
            'onChange'  : ('dynamicUpdate','app'),
            'label'     : 'triggers',
            'shelp'     : 'number of triggers this session'}),
    (pchtml.htmlTimestamp, {'name': 'lasttrigger', 'fallbackValue':0,
            'strft': '%H:%M:%S' , 'unset':'never',
            'onChange': ('dynamicUpdate','app'),
            'label': 'last trigger time',
            'shelp': 'time last triggered (rising edge) detected'}),
    (pchtml.htmlTimestamp, {'name': 'started', 'fallbackValue':0,
            'strft': '%H:%M:%S' , 'unset':'never',
            'onChange': ('dynamicUpdate','app'),
            'label': 'started at',
            'shelp': 'time this activity last started'}),
    (pchtml.htmlTimestamp, {'name': 'stopped', 'fallbackValue':0,
            'strft': '%H:%M:%S' , 'unset':'never',
            'onChange': ('dynamicUpdate','app'),
            'label': 'stopped at',
            'shelp': 'time this activity last stopped'}),
)
