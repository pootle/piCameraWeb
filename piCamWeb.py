#!/usr/bin/python3
"""
Add on for piCamHandler that works with webserv.
"""
import logging
import pathlib
import piCamHandler as pch
import piCamFields as pcf
import piCamHtml as pchtml
import pforms
import threading
import json
import pypnm

from piCamActMoveCPU import cpumovetable
from piCamActMoveCPU import fetchmask
from piCamActMoveGPIO import extmovetable
from piCamActLiveStream import livestreamtable
from piCamActTriggerVid import tripvidtable
from piCamActListVid import vidlisttable
from piCamActWatcher import systemtable, watcherGroup
from piCamHtmlTables import htmlgentable, htmlgentabbedgroups

class piCamWeb(pch.cameraManager):
    def __init__(self, webserver, loglvl=logging.INFO, **kwargs):
        """
        this runs up the web specific stuff for the camera and all associated functionality.
        
        The views used are:
            'app'  : used by the pch.cameraManager to read and write vars
            'html' : used to generate the full html for a var to insert into the web page
            'webv' : used to fetch the value of a var when reading or  updating the web page - typically
                     after the app has changed a value
            'user' : used to write a var with input from the user via (in this case) the web browser / web server
            'pers' : (for persistent) used to fetch / set values that we want to save and restore.
        """
        self.webserver=webserver
        super().__init__(
            views=('app', 'html', 'webv', 'user', 'pers'),
            readers={'app':'_getValueDict', 'pers': '_getValueDict'},
            readersOn=('pers',),
            writers={'app':'_setValueDict', 'pers': '_setValueDict'},
            writersOn=('pers',),
            loglvl=loglvl,
            **kwargs)
        pagevars={n:v.getValue('html') for n,v in self.items()}

    def topPage(self):
        filepath=self.webserver.p_filepath(presetfolder='template', filepart='main.html')
        with filepath.open('r') as sfile:
            page=sfile.read()
        pagevars={n:v.getValue('html') for n,v in self.items()}
        pf=page.format(**pagevars)
        return pf, filepath.suffix

    def smallpage(self):
        filepath=self.webserver.p_filepath(presetfolder='template', filepart='small.html')
        with filepath.open('r') as sfile:
            page=sfile.read()
        pagevars={n:v.getValue('html') for n,v in self.items()}
        pf=page.format(**pagevars)
        return pf, filepath.suffix

    def settings(self,sname):
        headings= {
            'camsettings':  'Camera settings',
            'livevid':      'Live stream settings',
            'cpumove':      'cpu move detect settings',
            'extmove':      'gpio trigger settings',
            'tripvid':      'triggered video settings',
            'listvid':      'list recorded videos',
        }
        if sname[0] in self['settings']:
            filepath=self.webserver.p_filepath(presetfolder='template', filepart='singleset.html')
            with filepath.open('r') as sfile:
                page=sfile.read()
            pagevars={'settings' : self['settings/'+sname[0]].getValue('html'), 'heading': headings[sname[0]]}
            for set in ('camstatus','livevidstatus','cpumovestatus', 'extmovestatus','tripvidstatus'):
                pagevars[set]=self[set].getValue('html')
            pf=page.format(**pagevars)
            return pf, filepath.suffix
        else:
            return {'resp':500, 'rmsg': 'cannot find settings for'+sname[0]}

    def updateSetting(self, t, v):
        """
        Called via the webserver from the web browser to update a single app variable and return a response
        """
        splitn=t[0].split(sep=self.hiernamesep, maxsplit=1)
        if splitn[0]==self.name:
            return self.webUpdate(splitn[1],v)
        else:
            return {'resp':500, 'rmsg': 'app name mismatch '+t[0]}

    def dynamicUpdate(self, var, view, oldValue, newValue):
        """
        vars that can be updated by the app, and which we want to show to the user on the web page, use this callback
        at setup time to arrange for the front end to be updated.
        """
        self.webserver.addDynUpdate(var.fhtmlid, var.getValue('webv'))

    def setdetectmask(self, x):
        if 'mask' in x and 'name' in x:
            tfile=pathlib.Path(self['settings']['cpumove']['maskfolder'].getValue('app')).expanduser()/x['name']
            if tfile.parent.is_dir():
                img=pypnm.pbm(imgdata=x['mask'], comments=[b'picamera mask from user',])
                img.writeFile(str(tfile))
                print('mask >{}< is {} x {}, saved to file {}'.format(x['name'], len(x['mask'][0]), len(x['mask']),str(tfile)))
                return {'resp':200, 'rdata':x['name']+' saved'}
            else:
                return {'resp':403, 'rmsg': 'invalid save directory '+ str(tfile.parent)}
        else:
            return {'resp':501, 'rmsg':"incorrect data" }

    def fetchmask(self):
        print('yoohoo')
        print(self['settings']['cpumove'].keys())
        maskdata=fetchmask(self, self['settings']['cpumove'])
        if maskdata is None:
            rdata={'msg': 'no mask file known'}
        else:
            rdata={'msg':'I got the data', 'mdata': maskdata}
        return {'resp': 200, 'rdata': rdata}

class htmlgenbtns(htmlgentable):
    groupwrapper='{childfields}'
    childwrapper='<td class="value">{cont:}</td>\n'

    def __init__(self, readers=None, readersOn=('app', 'html'), writers=None,writersOn=('app', ), **kwargs):
        super().__init__(
                readers=pforms.extendViews(readers, {'app':'_getValueDict', 'html': '_getHtmlValue', 'pers':'_getValueDict'}),
                readersOn=readersOn,
                writers=pforms.extendViews(writers, {'app':'_setValueDict', 'pers': '_setValueDict'}),
                writersOn=writersOn,
                **kwargs)

class htmlgencat(pforms.groupVar):
    """
    group that just concatenates the html for all its children
    """
    def _getHtmlValue(self, view):
        return '\n'.join([ch.getValue(view) for ch in self.values()])

class htmlgendictgroup():
    """
    this group type returns a dict of childname: childshtml to facilitate building a page where
    the html hierarchy does not follow the var hierarchy. The returned dict can be easily used as **kwargs
    to ''.format()
    """
    def _getHtmlValue(self, view):
        return {f.name: f.getValue(view) for f in self.values()}

############################################################################################
#   classes for all the camera's settings for a web site                                   #
############################################################################################
class htmlCamResolution(pchtml.htmlgenOption, pcf.camResolution):
    def __init__(self, **kwargs):
        print('htmlCamResolution constructor starts using', str(kwargs.keys()))
        super().__init__(readersOn=('app', 'html','pers', 'webv'), writersOn=('app', 'user', 'pers'), **kwargs)
        print('htmlCamResolution constructor ends')

class htmlCamRotation(pchtml.htmlgenOption, pcf.camRotation):
    def __init__(self, **kwargs):
        super().__init__(readersOn=('app', 'html','pers'), writersOn=('app', 'user', 'pers'), **kwargs)
        
    def webUpdateValue(self, value):
        value[0]=int(value[0])
        return super().webUpdateValue(value)

class htmlCamFramerate(pchtml.htmlgenNumber, pcf.camFramerate):
    def __init__(self, **kwargs):
        super().__init__(readersOn=('app', 'html','pers'), writersOn=('app', 'user', 'pers'), **kwargs)

class htmlCamBrightness(pchtml.htmlgenNumber, pcf.camBrightness):
    def __init__(self, **kwargs):
        super().__init__(readersOn=('app', 'html','pers'), writersOn=('app', 'user', 'pers'), **kwargs)

class htmlCamContrast(pchtml.htmlgenNumber, pcf.camContrast):
    def __init__(self, **kwargs):
        super().__init__(readersOn=('app', 'html','pers'), writersOn=('app', 'user', 'pers'), **kwargs)

class htmlCamAwb_mode(pchtml.htmlgenOption, pcf.camAwb_mode):
    def __init__(self, **kwargs):
        super().__init__(readersOn=('app', 'html','pers'), writersOn=('app', 'user', 'pers'), **kwargs)

class htmlCamExpMode(pchtml.htmlgenOption, pcf.camExpoMode):
    def __init__(self, **kwargs):
        super().__init__(readersOn=('app', 'html','pers'), writersOn=('app', 'user', 'pers'), **kwargs)

class htmlCamExpoComp(pchtml.htmlgenOption, pcf.camExpoComp):
    def __init__(self, **kwargs):
        super().__init__(readersOn=('app', 'html','pers'), writersOn=('app', 'user', 'pers'), **kwargs)

camsettingstable=(
    (htmlCamResolution, {}),
    (htmlCamFramerate, {}),
    (htmlCamRotation, {}),
    (htmlCamBrightness, {}),
    (htmlCamContrast, {}),
    (htmlCamAwb_mode, {}),
    (htmlCamExpMode, {}),
    (htmlCamExpoComp, {}),
    (pchtml.htmlInt,        {
            'name'      : 'camtimeout', 'fallbackValue': 10,
            'readersOn' : ('html', 'app', 'pers'),
            'writersOn' : ('app', 'user', 'pers'),
            'onChange'  : ('dynamicUpdate','app'),
            'label'     : 'camera timeout',
            'shelp'     : 'time (seconds) delay to close camera after last activity finishes'}),
 )

############################################################################################
# stream and camera start / stop buttons
############################################################################################

streambuttons=(
    (pchtml.htmlCyclicButton, {
            'name' : 'camerastop',  'fallbackValue': 'stop', 'alist': ('stop', ' stop '),
            'shelp': 'stop the camera - can only be stopped with no active streams',
    }),
)

def testcam2(**kwargs):
    """
    This function creates a camera controller, runs its runloop in a new thread and returns the class instance
    """
    allsettingsgroups=(
        (htmlgentabbedgroups, {'varlist': camsettingstable, 'name': 'camsettings', 'label': 'camera',}),
        (htmlgentabbedgroups, {'varlist': livestreamtable, 'name': 'livevid', 'label': 'live stream',}),
        (htmlgentabbedgroups, {'varlist': cpumovetable, 'name': 'cpumove', 'label': 'cpu&nbsp;move detect',}),
        (htmlgentabbedgroups, {'varlist': extmovetable, 'name': 'extmove', 'label': 'gpio&nbsp;move detect',}),
        (htmlgentabbedgroups, {'varlist': tripvidtable, 'name': 'tripvid', 'label': 'tripped video',}),
        (htmlgentabbedgroups, {'varlist': vidlisttable, 'name': 'listvid', 'label': 'list videos',}),
        (watcherGroup,        {'varlist': systemtable, 'name': 'watcher', 'label': 'system info',}),
    )
    allsettings=(
        (htmlgencat, {'varlist': allsettingsgroups, 'name': 'settings',
                'readers'  : {'app':'_getValueDict', 'html': '_getHtmlValue', 'pers': '_getValueDict'},
                'readersOn': ('app', 'html', 'pers'),
                'writers'  : {'app':'_setValueDict', 'pers': '_setValueDict'},
                'writersOn': ('app', 'pers'),
        }),
        (htmlgenbtns, {'varlist': streambuttons, 'name': 'strmctrl',
                'readers':{'app':'_getValueDict', 'html': '_getHtmlValue'},
                'writers':{'app':'_setValueDict'},
        }),
        (pchtml.htmlPlainString, {'name': 'camstatus', 'fallbackValue': 'off',
                'onChange' : ('dynamicUpdate', 'app'),
                'readersOn': ('app', 'html', 'webv'),
                'writersOn': ('app', 'pers'),
        }),
        (pchtml.htmlStatus, {'name': 'cpumovestatus', 'fallbackValue': 'off',
                'onChange' : ('dynamicUpdate', 'app'),
                'readersOn': ('app', 'html', 'webv'),
                'writersOn': ('app', 'pers'),
        }),
        (pchtml.htmlStatus, {'name': 'extmovestatus', 'fallbackValue': 'off',
                'onChange' : ('dynamicUpdate', 'app'),
                'readersOn': ('app', 'html', 'webv'),
                'writersOn': ('app', 'pers'),
        }),
        (pchtml.htmlStatus, {'name': 'tripvidstatus', 'fallbackValue': 'off',
                'onChange' : ('dynamicUpdate', 'app'),
                'readersOn': ('app', 'html', 'webv'),
                'writersOn': ('app', 'pers'),
        }),
        (pchtml.htmlStatus, {'name': 'livevidstatus', 'fallbackValue': 'off',
                'onChange' : ('dynamicUpdate', 'app'),
                'readersOn': ('app', 'html', 'webv'),
                'writersOn': ('app', 'pers'),
        }),
    )
    settingsfile=pathlib.Path('~/.picamsettings.txt').expanduser()
    settings={}
    if settingsfile.is_file():
        with settingsfile.open() as sf:
            settings=json.load(sf)
    cm=piCamWeb(
           varlist=allsettings, value=settings, valueView='pers',
           **kwargs
    )
    cmthread=threading.Thread(target=cm.runloop, name='camMan')
    cmthread.start()
    print("camera web handler thread started")
    return cm 