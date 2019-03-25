#!/usr/bin/python3
"""
module to pick up gpio input for movement detection (e.g. PIR sensor)
"""
import time, pigpio
import logging
from subprocess import check_output

import papps, pforms
import piCamHtml as pchtml
from piCamHtmlTables import htmlgentabbedgroups

class watcher(papps.appThreadAct):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def startedlogmsg(self):
        return 'started system watcher'

    def endedlogmsg(self):
        return 'finished system watcher'

    def movewatcher(self):
        b=self.parent.activities
        try:
            mact=b['cpumove']
        except:
            return
        if hasattr(self,'mwcount'):
            if time.time() > self.mwtime+60:
                if self.mwcount == mact.procCount:
                    self.mwfails+=1
                    if self.mwfails>4:
                        if self.log:
                            self.log.critical('cpu move problem? rebooting')
                        time.sleep(1)
                        print('restart')
                        check_output(['sudo','shutdown', '-r', 'now'])
                    else:
                        print('warn')
                        if self.loglvl > logging.WARN:
                            self.log.warn('cpumove stuck? count is %d' % self.mwfails)
                else:
                    self.mwfails=0
        else:
            if self.loglvl > logging.INFO:
                self.log.info('cpumove watcher started')
            print('cpumove watcher started')
            self.mwtime=time.time()
            self.mwcount=mact.procCount
            self.mwfails=0

    def tick(self):
        changed, changeset = self.vars.throtcheck.checkThrottles()
        if changed:
            for fname in changset:
                self.vars['fname'].setValue('app',  self.vars.throtcheck.getThrottleState(fname))
        self.movewatcher()

    def run(self):
        self.startDeclare()
        period=self.vars['ticktime'].getValue('app')
        nextcheck=time.time()+period
        while self.requstate != 'stop':
            waittime=nextcheck-time.time()
            if waittime < 0:
                self.tick()
                nextcheck=time.time()+period
            else:
                time.sleep(waittime if waittime < 2 else 2)                   
        self.endDeclare()

def getvgensetting(pvals, checkval):
    out = check_output(['vcgencmd', ]+pvals, universal_newlines=True).split()
    outs=[v.split('=') for v in out]
    for o in outs:
        if o[0]==checkval:
            return True if int(o[1])==1 else False
    else:
        raise ValueEror('unable to retrieve %s  setting with vgencmd' % str(checkval))

throttleInfo={
    'undervolts':       (2**0,  'Under-voltage detected'),
    'capped':           (2**1,  'Arm frequency capped'),
    'throttled':        (2**2,  'Currently throttled'),
    'temp warn':        (2**3,  'Soft temperature limit active'),
    'was undervolts':   (2**16, 'Under-voltage has occurred'),
    'was capped':       (2**17, 'Arm frequency capped has occurred'),
    'was throttled':    (2**18, 'Throttling has occurred'),
    'was temp warn':    (2**19, 'Soft temperature limit has occurred'),
}

class watcherGroup(htmlgentabbedgroups):
    def __init__(self, **kwargs):
        self.throtcheck=throttles()
        super().__init__(**kwargs)

class throttles():
    """
    A little class to provide an easy interface to check on the various bits in vcgencmd get_throttled
    """
    def __init__(self):
        self.flaghistory={}
        self.throttleState=0

    def _getThrottles(self):
        return int(check_output(['vcgencmd', 'get_throttled'], universal_newlines=True).strip().split('=')[1],0)

    def checkThrottles(self):
        """
        reads the throttle flags and sets list of those changed, then saves the current state
        """
        newstate=self._getThrottles()
        if newstate==self.throttleState:
            return False, None
        else:
            changed=[]
            for k,v in throttleInfo.items():
                if newstate & v[0] != self.throttleInfo & v[0]:
                    flagchange = 1 if newstate & v[0] else 0
                    if not k in self.flaghistory:
                        fh=[]
                        self.flaghistory[k]=fh
                    else:
                        fh=self.flaghistory[k]
                    fh.append((flagchange,time.time()))
                    if len(fh) > 20:
                        fh.pop(0)
                    changed.append(k)
            return True, changed

    def getThrottleState(self,th):
        return self.throttleState & throttleInfo[th][0]==1

class boolVar(pforms.listVar):
    """
    a derivative of listvar that just uses 2 states showing the state of an external thing
    """
    def __init__(self, vlists=('Yes', 'No'), **kwargs):
        super().__init__(vlists=vlists, **kwargs)

class htmlBool(pchtml.htmlgenOption, boolVar):
    """
    simple base for class that displays the current value of some external thing
    """
    def __init__(self, valueView, value, app, parent, displaylist=('Yes', 'No'), vlists=None, readonly=True, **kwargs):
        readersOn = ('app', 'webv', 'html')
        writersOn = ('app',) if readonly else ('app', 'user')
        self.app=app
        self.parent=parent
        if vlists is None:
            vlists={v:(1,0) if v=='app' else displaylist for v in self.getAllViews()}
        super().__init__(
            vlists=vlists,
            app=app,
            parent=parent,
            value=1 if self.getBool() else 0,
            valueView='app',
            readersOn=readersOn,
            writersOn=writersOn,
            **kwargs)

    def getBool(self):
        """
        redefine this to get the current value, should return True or False 
        """
        raise NotImplementedError()

############################################################################################
# user interface setup for watcher - web page version 
############################################################################################
class htmlCameraLED(pchtml.htmlgenOption, pforms.listVar):
    defaultName='camled'
    def __init__(self, name='camled', vlists=('ON', 'OFF'), fallbackValue='ON',    
            readersOn = ('app', 'pers', 'webv', 'html'),
            writersOn = ('app', 'pers'),  #'user' TODO
            label     = 'camera LED on',
            shelp     = 'sets camera LED to turn on when camera active ', **kwargs):
        val='OFF' if getvgensetting(['get_config','disable_camera_led'], 'disable_camera_led') else 'ON'
        super().__init__(
            name=name, vlists=vlists, fallbackValue=val, readersOn=readersOn, writersOn=writersOn, label=label, shelp=shelp, **kwargs)

class htmlCameraEnabled(pchtml.htmlgenOption, pforms.listVar):
    defaultName='camenabled'
    def __init__(self, name='camenabled', vlists=('ON', 'OFF'), fallbackValue='ON',    
            readersOn = ('app', 'webv', 'html'),
            writersOn = ('app', ),
            label     = 'camera enabled',
            shelp     = 'Camera is enabled (change with raspi-config)', **kwargs):
        super().__init__(
            name=name, vlists=vlists, fallbackValue=fallbackValue, readersOn=readersOn, writersOn=writersOn, label=label, shelp=shelp, **kwargs)

    def setInitialValue(self, view, value, fallbackValue):
        self._setVar(0 if getvgensetting(['get_camera'],'supported') else 1) # field value doesn't change so fetch the system value 

class htmlCameraPresent(pchtml.htmlgenOption, pforms.listVar):
    defaultName='campresent'
    def __init__(self, name='campresent', vlists=('ON', 'OFF'), fallbackValue='ON',    
            readersOn = ('app', 'webv', 'html'),
            writersOn = ('app',),
            label     = 'camera present',
            shelp     = 'Shows if camera found (only when camera support is on)', **kwargs):
        super().__init__(
            name=name, vlists=vlists, fallbackValue=fallbackValue, readersOn=readersOn, writersOn=writersOn, label=label, shelp=shelp, **kwargs)

    def setInitialValue(self, view, value, fallbackValue):
        self._setVar(0 if getvgensetting(['get_camera'],'detected') else 1) # field value doesn't change so fetch the system value 

class htmlFreeSpace(pchtml.htmlInt):
    defaultName='freespace'

    def __init__(self, **kwargs):
        dfs=check_output(['df', '.'], universal_newlines=True).split('\n')[1].split()
        for f in dfs:
            if f.endswith('%'):
                val=100-int(f[0:-1])
                break
        else:
            raise ValueError('unable to find free space')
        super().__init__(name='freespace', fallbackValue=val, formatString='{value:d}%',
            readersOn = ('app', 'webv', 'html'),
            writersOn = ('app', ),
            label='filestore free',
            shelp='The percentage of space available in filesystem', **kwargs)

    def setInitialValue(self, view, value, fallbackValue):
        self._setVar(fallbackValue) # field value doesn't change so fetch the system value

class htmlUnderVoltsNow(htmlBool):
    defaultName='undervolts'
    def __init__(self, name='undervolts',
                label='undervoltage NOW',
                shelp='&#34;Yes&#34; if system undervoltage is currently set', **kwargs):
        super().__init__(name=name, label=label, shelp=shelp, **kwargs)

    def getBool(self):
        return self.parent.throtcheck.getThrottleState('undervolts')

class htmlUnderVoltsPrev(htmlBool):
    defaultName='was undervolts'
    def __init__(self, name='was undervolts',
                label='undervoltage since boot',
                shelp='&#34;Yes&#34; if system undervoltage occurred since boot', **kwargs):
        super().__init__(name=name, label=label, shelp=shelp, **kwargs)

    def getBool(self):
        return self.parent.throtcheck.getThrottleState('was undervolts')

class htmlTempWarnNow(htmlBool):
    defaultName='temp warn'
    def __init__(self, name='tempwarn',
                label='temperature warning',
                shelp='&#34;Yes&#34; if system temperature warning is currently set', **kwargs):
        super().__init__(name=name, label=label, shelp=shelp, **kwargs)

    def getBool(self):
        return self.parent.throtcheck.getThrottleState('temp warn')

class htmlTempWarnPrev(htmlBool):
    defaultName='was temp warn'
    def __init__(self, name='was temp warn',
                label='temperature warn since boot',
                shelp='&#34;Yes&#34; if system temperature warning occurred since boot', **kwargs):
        super().__init__(name=name, label=label, shelp=shelp, **kwargs)

    def getBool(self):
        return self.parent.throtcheck.getThrottleState('was temp warn')

class htmlThrottleNow(htmlBool):
    defaultName='throttled'
    def __init__(self, name='throttled',
                label='processor throttled',
                shelp='&#34;Yes&#34; if system throttling is currently set', **kwargs):
        super().__init__(name=name, label=label, shelp=shelp, **kwargs)

    def getBool(self):
        return self.parent.throtcheck.getThrottleState('throttled')

class htmlThrottlePrev(htmlBool):
    defaultName='was throttledv'
    def __init__(self, name='was throttled',
                label='processor throttled since boot',
                shelp='&#34;Yes&#34; if system throttling has occorred since boot', **kwargs):
        super().__init__(name=name, label=label, shelp=shelp, **kwargs)

    def getBool(self):
        return self.parent.throtcheck.getThrottleState('was throttled')

class htmlCappedNow(htmlBool):
    defaultName='capped'
    def __init__(self, name='capped',
                label='processor capped',
                shelp='&#34;Yes&#34; if system capped is currently set', **kwargs):
        super().__init__(name=name, label=label, shelp=shelp, **kwargs)

    def getBool(self):
        return self.parent.throtcheck.getThrottleState('capped')

class htmlCappedPrev(htmlBool):
    defaultName='was capped'
    def __init__(self, name='was capped',
                label='processor capped',
                shelp='&#34;Yes&#34; if system has been capped since boot', **kwargs):
        super().__init__(name=name, label=label, shelp=shelp, **kwargs)

    def getBool(self):
        return self.parent.throtcheck.getThrottleState('was capped')

EMPTYDICT={}
systemtable=(
    (pchtml.htmlStatus  , pchtml.HTMLSTATUSSTRING),
    (pchtml.htmlInt,        {
            'name'      : 'ticktime', 'minv':1, 'maxv':60, 'clength':2, 'fallbackValue': 3,
            'readersOn' : ('html', 'app', 'pers'),
            'writersOn' : ('app', 'pers', 'user'),            
            'label'     : 'tick time',
            'shelp'     : 'seconds between checking *everything*'}),
    (htmlUnderVoltsNow, EMPTYDICT),
    (htmlUnderVoltsPrev, EMPTYDICT),
    (htmlTempWarnNow, EMPTYDICT),
    (htmlTempWarnPrev, EMPTYDICT),
    (htmlThrottleNow, EMPTYDICT),
    (htmlThrottlePrev, EMPTYDICT),
    (htmlCappedNow, EMPTYDICT),
    (htmlCappedPrev, EMPTYDICT),
    (htmlCameraLED, EMPTYDICT),
    (htmlCameraEnabled, EMPTYDICT),
    (htmlCameraPresent, EMPTYDICT),
    (htmlFreeSpace, EMPTYDICT),
    (pchtml.htmlStartedTimeStamp, EMPTYDICT),
    (pchtml.htmlStoppedTimeStamp, EMPTYDICT),
)
