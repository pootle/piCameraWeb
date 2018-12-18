#!/usr/bin/python3
"""
Add on for piCamHandler that works with webserv.
"""
import logging
import piCamHandler as pch
import piCamFields as pcf
import piCamHtml as pchtml
import pforms
import threading

from piCamActMoveCPU import cpumovetable
from piCamActMoveGPIO import extmovetable
from piCamActLiveStream import livestreamtable
from piCamActTriggerVid import tripvidtable

class piCamWeb(pch.cameraManager):
    def __init__(self, webserver, loglvl=logging.INFO, **kwargs):
        """
        this runs up the web specific stuff for the camera and all associated functionality.
        
        The views used are:
            'app'  : used by the pch.cameraManager to read and write vars
            'html' : used to generate the full html for a var to insert into the web page
            'webv' : used to fetch the value of a var when we are dynamically updating the web page - typically
                     after the app has changed a value
            'user' : used to write a var with input from the user via the web browser / web server
            'pers' : used to fetch / set values that we want to save and restore.
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

    def topPage(self):
        filepath=self.webserver.p_filepath(presetfolder='template', filepart='main.html')
        with filepath.open('r') as sfile:
            page=sfile.read()
        pagevars={n:v.getValue('html') for n,v in self.items()}
        print('=========================main page keys', pagevars.keys())
        print('camstatus: ',pagevars['camstatus'].keys())
        pf=page.format(**pagevars) #camstat=pagevars['camstatus']['cont'], 
        return pf, filepath.suffix

    def updateSetting(self, t, v):
        """
        Called via the webserver from the web browser to update a single app variable and return a response
        """
        print ('update request for {} to {}'.format(t[0],v))
        splitn=t[0].split(sep=self.hiernamesep, maxsplit=1)
        if splitn[0]==self.name:
            return self.webUpdate(splitn[1],v)
        else:
            return {'resp':500, 'rmsg': 'app name mismatch'}

    def dynamicUpdate(self, var, view, oldValue, newValue):
        """
        vars that can be updated by the app, and which we want to show to the user on the web page, use this callback to arrange
        for the front end to be updated.
        """
        self.webserver.addDynUpdate(var.fhtmlid, var.getValue('webv'))

class htmlgentable(pforms.groupVar):
    """
    mixin for pforms field groups that create an html table for all the fields
    """
    groupwrapper='<table>{childfields}</table>'
    childwrapper='<tr><th scope="row">{label:}</th><td class="value">{cont:}</td><td class="helpbtn" title="{shelp:}">?</td></tr>\n'
    def _getHtmlValue(self, view):
        rows='\n'.join([self.childwrapper.format(**ch.getValue('html')) for ch in self.values()])
        return self.groupwrapper.format(childfields=rows,f=self)

class htmlgentabbedgroups(htmlgentable):
    groupwrapper=('<input name="tabgroup1" id="{f.name}" type="radio" >'
                        '<section>\n'
                        '    <h1><label for="{f.name}">{f.label}</label></h1>\n'
                        '    <div><table>\n{childfields}</table></div>'
                        '</section>\n')
    def __init__(self, readers=None, readersOn=('app', 'html', 'pers'), writers=None,writersOn=('app', 'pers'), **kwargs):
        super().__init__(
                readers=pforms.extendViews(readers, {'app':'_getValueDict', 'html': '_getHtmlValue', 'pers':'_getValueDict'}),
                readersOn=readersOn,
                writers=pforms.extendViews(writers, {'app':'_setValueDict', 'pers': '_setValueDict'}),
                writersOn=writersOn,
                **kwargs)

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
    (htmlCamRotation, {'loglvl':logging.DEBUG-1}),
    (htmlCamBrightness, {}),
    (htmlCamContrast, {}),
    (htmlCamAwb_mode, {}),
    (htmlCamExpMode, {}),
    (htmlCamExpoComp, {}),
 )

camsettingvalues={ # default values picked up from camera attribute classes
#    'resolution': '640x480',
#    'rotation'  :0,
#    'framerate' : 30,
#    'brightness': 50,
#    'contrast'  : 0,
#    'awbMode'   : 'auto',
#    'expMode'   : 'auto',
#    'expComp'   : 0,
}

############################################################################################
# stream and camera start / stop buttons
############################################################################################

streambuttons=(
    (pchtml.htmlCyclicButton, {
            'name' : 'camerastop',  'fallbackValue': 'stop', 'alist': ('stop', ' stop '),
            'shelp': 'stop the camera - can only be stopped with no active streams',
    }),
    (pchtml.htmlCyclicButton, {
            'name' : 'test1',  'fallbackValue': 'fetch settings', 'alist': ('fetch settings', ' fetch settings '),
            'shelp': 'do test 1',
            'onChange'  : ('dynamicUpdate','user'),
    }),
    (pchtml.htmlCyclicButton, {
            'name' : 'test2',  'fallbackValue': 'click', 'alist': ('click', ' click '),
            'shelp': 'do test 2',
            'onChange'  : ('dynamicUpdate','user'),
    }),
)

def testcam2(**kwargs):
    """
    This function creates a camera controller, runs its runloop in a new thread and returns the class instance
    """
    allsettingsgroups=(
        (htmlgentabbedgroups, {'varlist': camsettingstable, 'name': 'camsettings', 'label': 'camera',}),
        (htmlgentabbedgroups, {'varlist': livestreamtable, 'name': 'livevid', 'label': 'live stream',}),
        (htmlgentabbedgroups, {'varlist': cpumovetable, 'name': 'cpumove', 'label': 'cpu&nbsp;move test',}),
        (htmlgentabbedgroups, {'varlist': extmovetable, 'name': 'extmove', 'label': 'gpio&nbsp;move test',}),
        (htmlgentabbedgroups, {'varlist': tripvidtable, 'name': 'tripvid', 'label': 'tripped video',}),
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
                'onChange' : ('dynamicUpdate','app'),
                'readersOn': ('app', 'html','webv'),
                'writersOn': ('app',),
        }),
    )
    cm=piCamWeb(
           varlist=allsettings, value={}, valueView='app', 
           **kwargs
    )
    cmthread=threading.Thread(target=cm.runloop, name='camMan')
    cmthread.start()
    return cm#, cmthread