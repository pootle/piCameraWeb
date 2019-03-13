#!/usr/bin/python3

import logging
from subprocess import Popen, PIPE, check_output

import pforms

import piCamHtml as pcmh

class htmlCameraLED(pcmh.htmlgenOption, pforms.listVar):
    defaultName='camled'
    def __init__(self, name='camled', vlists=('ON', 'OFF'), fallbackValue='ON',    
            readersOn = ('app', 'pers', 'webv', 'html'),
            writersOn = ('app', 'pers'),  #'user' TODO
            label     = 'camera LED on',
            shelp     = 'sets camera LED to turn on when camera active ', **kwargs):
        val='OFF' if getvgensetting(['get_config','disable_camera_led'], 'disable_camera_led') else 'ON'
        super().__init__(
            name=name, vlists=vlists, fallbackValue=val, readersOn=readersOn, writersOn=writersOn, label=label, shelp=shelp, **kwargs)

def getvgensetting(pvals, checkval):
    out = check_output(['vcgencmd', ]+pvals, universal_newlines=True).split()
    outs=[v.split('=') for v in out]
    for o in outs:
        if o[0]==checkval:
            return True if int(o[1])==1 else False
    else:
        raise ValueEror('unable to retrieve %s  setting with vgencmd' % str(checkval))

class htmlFreeSpace(pcmh.htmlInt):
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

class htmlCameraEnabled(pcmh.htmlgenOption, pforms.listVar):
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

class htmlCameraPresent(pcmh.htmlgenOption, pforms.listVar):
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
 
class htmlGenButton(pcmh.htmlgenBase, pforms.textVar):
    txtinputhtml = ('<input id="{f.fhtmlid:}" type="text" value="{sval:}" '
                   '''style="width: {f.clength:}em" onchange="appNotify(this, 'abcd')" />''')
    def __init__(self, readers=None , writers=None , clength=6, **kwargs):
        self.clength=clength
        super().__init__(
                readers=pforms.extendViews(readers, {'app': '_getSValue', 'html': '_getHtmlValue', 'webv': '_getSValue', 'pers':'_getSValue'}),
                readersOn = ('app', 'webv', 'html'),
                writers=pforms.extendViews(writers, {'app': '_validStr', 'pers': '_validStr', 'user': '_validStr'}),
                writersOn = ('app', 'user'),
                **kwargs)

    def setInitialValue(self, view, value, fallbackValue):
        self._setVar(fallbackValue) # field value doesn't change so use the fallbackvalue 
 
    def _getSValue(self, view):
        return self._getVar()

    def webUpdateValue(self, value):
        return {'resp':200, 'rdata': self.buttonAction()}

    def buttonAction(self):
        return 'nothing happened'

#        sudo_password = '99bonk'
#        command = 'shutdown -r now'.split()
#        p = Popen(['sudo', '-S'] + command, stdin=PIPE, stderr=PIPE, universal_newlines=True)
#        sudo_prompt = p.communicate(sudo_password + '\n')[1]
#        print('XXXXXXXXXXXXXXXXXXXXXXX', sudo_prompt)
#        return 'something happened'

    def _getHtmlInputValue(self):
        mv = '''<span id="{f.fhtmlid:}" title="{f.shelp}" class="clicker clicker0" onclick="appNotify(this, 'abcd')" >{sval:}</span>'''.format(
                sval=self.getValue('webv'), f=self)       
        if self.loglvl <= logging.DEBUG:
            self.log.debug('_getHtmlInputValue returns %s' % mv)
        return mv

class resetButton(htmlGenButton):
    def buttonaction(self):
        command = 'shutdown -r now'.split()
        p = Popen(['sudo',] + command, stdin=PIPE, stderr=PIPE, universal_newlines=True)
        return 'restarting'

class stopButton(htmlGenButton):
    def buttonaction(self):
        command = 'shutdown -h now'.split()
        p = Popen(['sudo',] + command, stdin=PIPE, stderr=PIPE, universal_newlines=True)
        return 'restarting'


EMPTYDICT={}
systemtable=(
    (htmlCameraLED, EMPTYDICT),
    (htmlCameraEnabled, EMPTYDICT),
    (htmlCameraPresent, EMPTYDICT),
    (htmlFreeSpace, {'loglvl': logging.DEBUG}),
    (resetButton, {
            'name' : 'restart',  'fallbackValue': 'Restart',
            'onChange'  : ('dynamicUpdate','user'),
            'label': 'Restart system', 
            'shelp': 'Shutdown Raspbian and restart NOW',
    }),
    (stopButton, {
            'name' : 'halt',  'fallbackValue': 'halt',
            'onChange'  : ('dynamicUpdate','user'),
            'label': 'Halt system',
            'shelp': 'Shutdown Raspbian and halt NOW',
    }),)