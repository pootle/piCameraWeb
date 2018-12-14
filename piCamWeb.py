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

from piCamCpuMove import cpumovetable

class piCamWeb(pch.cameraManager):
    def __init__(self, webserver, **kwargs):
        """
        this runs up the web specific stuff for the camera and all associated functionality.
        
        The views used are:
            'app'  : used by the pch.cameraManager to read and write vars
            'html' : used here to generate the full html for a var to insert into the web page
            'expo' : used to fetch values that can be used for stuff.
            'webv' : used to fetch the value of a var when we are dynamically updating the web page - typically
                     after the app has changed a value
            'pers' : used to fetch values that we want to save and restore.
        """
        self.webserver=webserver
        super().__init__(
            views=('app','html', 'expo', 'webv', 'pers'),
            readers={'app':'_getValueDict', 'pers': '_getValueDict'},
            writers={'app':'_setValueDict', 'pers': '_setValueDict'},
            loglvl=logging.DEBUG,
            **kwargs)

    def topPage(self):
        filepath=self.webserver.p_filepath(presetfolder='template', filepart='main.html')
        with filepath.open('r') as sfile:
            page=sfile.read()
#        camfields='\n'.join([c.getValue('html') for c in self.values()])
#        pf=page.format(ch_main=camfields)
        pagevars={n:v.getValue('html') for n,v in self.items()}
        print('=========================main page keys', pagevars.keys())
        print(pagevars['strmctrl'])
        pf=page.format(**pagevars)
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

class htmlgenbtns(htmlgentable):
    groupwrapper='{childfields}'
    childwrapper='<td class="value">{cont:}</td>\n'

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
        super().__init__(self, **kwargs)
        print('htmlCamResolution constructor ends')

class htmlCamRotation(pchtml.htmlgenOption, pcf.camRotation):
    def webUpdateValue(self, value):
        value[0]=int(value[0])
        return super().webUpdateValue(value)

class htmlCamFramerate(pchtml.htmlgenNumber, pcf.camFramerate):
    pass

class htmlCamBrightness(pchtml.htmlgenNumber, pcf.camBrightness):
    pass

class htmlCamContrast(pchtml.htmlgenNumber, pcf.camContrast):
    pass

class htmlCamAwb_mode(pchtml.htmlgenOption, pcf.camAwb_mode):
    pass

class htmlCamExpMode(pchtml.htmlgenOption, pcf.camExpoMode):
    pass

class htmlCamExpoComp(pchtml.htmlgenOption, pcf.camExpoComp):
    pass

camsettingstable=(
    (htmlCamResolution, {}),
    (htmlCamFramerate, {}),
    (htmlCamRotation, {}),
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
# classes for various stream settings                                                      #
############################################################################################

class htmlFolder(pchtml.htmlgenBase, pforms.folderVar):
    tophtml='<h3>{topname}</h3><ul>{dlist}{flist}</ul>\n'
    folderitemhtml="<li><span>{0[path].name:14s} ({0[count]:3})</span></li>\n"
    fileitemhtml="<li><span>{0[path].name:14s} ({0[size]:3.2f}MB)</span></li>\n"

    def __init__(self,
            readers={'html': '_getHtmlValue', 'app': '_getAppValue', 'expo': '_getStrValue'},
            writers={'html': '_validValue', 'app': '_validValue'},
            **kwargs):
        super().__init__(readers=readers, writers=writers, **kwargs)
        
    def _getHtmlInputValue(self):
#        print('trees')
        dets=self._getDictValue(None)
#        print(dets)
        topname=list(dets.keys())[0]
        entries=sorted([v for v in dets[topname]['inner'].values() if v['type'] is None], key=lambda x: x['path'].name)
        dlist='\n'.join([self.folderitemhtml.format(e) for e in entries])
        entries=sorted([v for v in dets[topname]['inner'].values() if not v['type'] is None], key=lambda x: x['path'].name)
        flist='\n'.join([self.fileitemhtml.format(e) for e in entries])
        return self.tophtml.format(topname=topname, dlist=dlist, flist=flist)
        
    def _setVar(self, val):
        if val is None:
            x=17/0
        else:
            print('setting value', val)
            super()._setVar(val)
############################################################################################
# group / table for live stream - mjpeg
############################################################################################

livestreamtable=(
    (pchtml.htmlStringnp, {'name': 'status', 'fallbackValue': 'off',
            'onChange': ('dynamicUpdate','app'),
            'label'   : 'state',
            'shelp'   : 'current status of this activity',
            'readers' : {'html': '_getHtmlValue', 'expo':'_getSValue', 'webv': '_getSValue'}}),
    (pchtml.htmlStreamSize,{}),
    (pchtml.htmlTimestamp, {'name': 'started', 'fallbackValue':0,
            'strft': '%H:%M:%S' , 'unset':'never',
            'onChange': ('dynamicUpdate','app'),
            'label': 'started at',
            'shelp': 'last time this view was started'}),
    (pchtml.htmlTimestamp, {'name': 'stopped', 'fallbackValue':0,
            'strft': '%H:%M:%S' , 'unset':'never',
            'onChange': ('dynamicUpdate','app'),
            'label': 'stopped at',
            'shelp': 'last time this view stopped'}),
)

############################################################################################
# group / table for tripped video recording
############################################################################################

tripvidtable=(
    (pchtml.htmlStringnp, {'name': 'status', 'fallbackValue': 'off',
            'onChange': ('dynamicUpdate','app'),
            'label'   : 'state',
            'shelp'   : 'current status of this activity',
            'readers' : {'html': '_getHtmlValue', 'expo':'_getSValue', 'webv': '_getSValue'}}),
    (pchtml.htmlStreamSize, {}),
    (pchtml.htmlFloat, {
            'name': 'backtime',  'minv':0, 'maxv':15, 'clength':4, 'numstr':'{:2.2f}', 'fallbackValue':1,
            'label':'pre-trigger record time', 
            'shelp':'number of seconds before trigger to include in video',
    }),
    (pchtml.htmlFloat, {
            'name' : 'forwardtime',  'minv':0, 'maxv':15, 'clength':4, 'numstr':'{:2.2f}', 'fallbackValue':1,
            'label':'post-trigger record time', 
            'shelp':'number of seconds after trigger ends to include in video',
    }),
    (htmlFolder, {#'loglvl':logging.DEBUG,
            'name' : 'basefolder', 'fallbackValue': '~/movevids',
            'label': 'video folder',
            'shelp': 'base folder for saved video files'}),
    (pchtml.htmlString, {
            'name' : 'file', 'fallbackValue': '%y/%m/%d/%H_%M_%S', 'clength':15,
            'label': 'filename',
            'shelp': 'filename with date-time compenents', 'shelp': 'extends the basefolder to define the filename for recorded videos.'}),

    (pchtml.htmlCyclicButton, {'loglvl':logging.DEBUG,
            'name': 'trigger',  'fallbackValue': 'trigger now', 'alist': ('trigger now', 'trigger now '),
                        # use single value twice so change is triggered
            'label':'trigger recording', 
            'shelp':'triggers recording immediately',
    }),
    (pchtml.htmlInt,        {
            'name' : 'triggercount', 'fallbackValue': 0,
            'readers' : {'html': '_getHtmlValue', 'app': '_getCValue', 'expo':'_getSValue', 'webv': '_getSValue'},
            'writers' : {'app': '_validNum'},
            'onChange': ('dynamicUpdate','app'),
            'label': 'recordings',
            'shelp': 'number of recorded videos this session'}),
    (pchtml.htmlTimestamp, {'name': 'lasttrigger', 'fallbackValue':0,
            'strft': '%H:%M:%S' , 'unset':'never',
            'onChange': ('dynamicUpdate','app'),
            'label': 'time of last recording',
            'shelp': 'time last video recording triggered'}),
    (pchtml.htmlTimestamp, {'name': 'started', 'fallbackValue':0,
            'strft': '%H:%M:%S' , 'unset':'never',
            'onChange': ('dynamicUpdate','app'),
            'label': 'started at',
            'shelp': 'last time this view was started'}),
    (pchtml.htmlTimestamp, {'name': 'stopped', 'fallbackValue':0,
            'strft': '%H:%M:%S' , 'unset':'never',
            'onChange': ('dynamicUpdate','app'),
            'label': 'stopped at',
            'shelp': 'last time this view stopped'}),

)


############################################################################################
# group / table for gpio external trigger
############################################################################################

extmovetable=(
    (pchtml.htmlStringnp, {'name': 'status', 'fallbackValue': 'off',
            'onChange': ('dynamicUpdate','app'),
            'label'   : 'state',
            'shelp'   : 'current status of this activity',
            'readers' : {'html': '_getHtmlValue', 'expo':'_getSValue', 'webv': '_getSValue'}}),
    (pchtml.htmlInt,        {
            'name' : 'triggerpin', 'minv':1, 'maxv':63, 'clength':2, 'fallbackValue': 1,'loglvl': logging.DEBUG,
            'readers' : {'html': '_getHtmlValue', 'app': '_getCValue', 'expo':'_getSValue', 'webv': '_getSValue'},
            'writers' : {'app': '_validNum', 'html': '_validNum'},            
            'label': 'gpio pin',
            'shelp': 'broadcom pin number for external sensor'}),
    (pchtml.htmlCyclicButton, {
            'name' : 'run',  'fallbackValue': 'start now', 'alist': ('start now', 'stop now '),
            'label': 'enable detection', 
            'shelp': 'enables / disables this motion detection method',
    }),
    (pchtml.htmlIntnp,        {
            'name' : 'triggercount', 'fallbackValue': 0,
            'readers' : {'html': '_getHtmlValue', 'app': '_getCValue', 'expo':'_getSValue', 'webv': '_getSValue'},
            'writers' : {'app': '_validNum'},
            'onChange': ('dynamicUpdate','app'),
            'label': 'triggers',
            'shelp': 'number of triggers this session'}),
    (pchtml.htmlTimestamp, {'name': 'lasttrigger', 'fallbackValue':0,
            'strft': '%H:%M:%S' , 'unset':'never',
            'onChange': ('dynamicUpdate','app'),
            'label': 'time of last trigger',
            'shelp': 'time last triggered (rising edge) detected'}),
    (pchtml.htmlTimestamp, {'name': 'started', 'fallbackValue':0,
            'strft': '%H:%M:%S' , 'unset':'never',
            'onChange': ('dynamicUpdate','app'),
            'label': 'started at',
            'shelp': 'last time this activity was started'}),
    (pchtml.htmlTimestamp, {'name': 'stopped', 'fallbackValue':0,
            'strft': '%H:%M:%S' , 'unset':'never',
            'onChange': ('dynamicUpdate','app'),
            'label': 'stopped at',
            'shelp': 'last time this view stopped'}),
)

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
    }),
    (pchtml.htmlCyclicButton, {
            'name' : 'test2',  'fallbackValue': 'click', 'alist': ('click', ' click '),
            'shelp': 'do test 2',
    }),
)

def testcam2(**kwargs):
    """
    This function creates a camera controller, runs its runloop in a new thread and returns the class instance
    """
    allsettingsgroups=(
        (htmlgentabbedgroups, {'varlist': camsettingstable, 'name': 'camsettings', 'label': 'camera',
                'readers':{'app':'_getValueDict', 'html': '_getHtmlValue', 'pers':'_getValueDict'},
                'writers':{'app':'_setValueDict', 'pers':'_setValueDict'},
        }),
        (htmlgentabbedgroups, {'varlist': livestreamtable, 'name': 'livevid', 'label': 'live stream',
                'readers':{'app':'_getValueDict', 'html': '_getHtmlValue', 'pers':'_getValueDict'},
                'writers':{'app':'_setValueDict', 'pers':'_setValueDict'},
        }),
        (htmlgentabbedgroups, {'varlist': cpumovetable, 'name': 'cpumove', 'label': 'cpu&nbsp;move test',
                'readers':{'app':'_getValueDict', 'html': '_getHtmlValue', 'pers':'_getValueDict'},
                'writers':{'app':'_setValueDict', 'pers':'_setValueDict'},
        }),
        (htmlgentabbedgroups, {'varlist': extmovetable, 'name': 'extmove', 'label': 'gpio&nbsp;move test',
                'readers':{'app':'_getValueDict', 'html': '_getHtmlValue', 'pers':'_getValueDict'},
                'writers':{'app':'_setValueDict', 'pers': '_setValueDict'},
        }),
        (htmlgentabbedgroups, {'varlist': tripvidtable, 'name': 'tripvid', 'label': 'tripped video',
                'readers':{'app':'_getValueDict', 'html': '_getHtmlValue', 'pers':'_getValueDict'},
                'writers':{'app':'_setValueDict', 'pers':'_setValueDict'},
        }),
    )
    allsettings=(
        (htmlgencat, {'varlist': allsettingsgroups, 'name': 'settings',
                'readers':{'app':'_getValueDict', 'html': '_getHtmlValue', 'pers': '_getValueDict'},
                'writers':{'app':'_setValueDict', 'pers': '_setValueDict'},
        }),
        (htmlgenbtns, {'varlist': streambuttons, 'name': 'strmctrl',
                'readers':{'app':'_getValueDict', 'html': '_getHtmlValue'},
                'writers':{'app':'_setValueDict'},
        }),
    )
    cm=piCamWeb(
           varlist=allsettings, value={}, valueView='app', 
           **kwargs
    )
    cmthread=threading.Thread(target=cm.runloop, name='camMan')
    cmthread.start()
    return cm#, cmthread