#!/usr/bin/python3
"""
Module to run the camera in video mode with up to 4 differently purposed streams.

each stream can be independently started and stopped. The 4 streams are intended to be used for any combination of:

    streaming live video - simply using mjpeg
    watching for movement - continuously capture (fairly small) images and check for 'movement'
    triggered recording once movement is detected - records while 'movement' detected plus few seconds before and after
    timelapse photos

The camera is setup at a specific resolution and framerate - typically the resolution will use the whole sensor, binned to 
reduce the working size, and a framerate to suit the fastest use case.

The different streams then resize the image to an appropriate size for the particular task. As the GPU does the resizing it is
fast and low latency.

The camera handler overall is controlled by a hierarchic tree of variables with the following overall structure:

'camera': cameraManager
    'camsettings': pvars.groupVar   # holds the global camera settings such as framrate, resolution, exposure mode etc
        'framerate': pvars.floatVar
        'rotation': camRotation
        ...
    'activities': pvars.groupVar    # info about the various activities that can run
        'camstream': pvars.groupVar     # settings specific to streaming video. This activity only runs when needed and
                                        # serves all clients from the one activity. It automatically shuts down a few seconds
                                        # after the last stream closes
            'status':  pvars.enumVar    # 'on' or 'off' showing whether the activity is running. Anything that wants to know 
                                        # if the stream is active can trigger from changes to this var
            'width':   pvars.intVar     # the stream is resized to these values by the gpu before it gets passed to the handler
            'height'   pvars.intVar
            'lastactive' pvars.floatvar # last time the camera streaming started or stopped
"""
import papp
from pootlestuff import pvars
import picamera, logging, time
import threading

try:
    import pigpio
    PIGPIO=True
except:
    PIGPIO=False

from gpiotrigger import gpiotrigger
from camstreamer import Streamer
from videorecorder import VideoRecorder
from movedetectcpu import MoveDetectCPU
try:
    from brightpivar import brightpiVar
except:
    print('warning - btightpi module not found - brightpi LED controls not available')

class picamAttrMixin():
    """
    a mixin class for pforms classes that syncs the value with a PiCamera attribute when the camera is active.
    
    The app object should have an attribute 'picam' which is None or a PiCamera and an attribute
    'camType' which should be ‘ov5647’ (V1 module) or ‘imx219’ (V2 module).
    
    This class overrides getValue and setValue so they access the camera when appropriate.
    
    The saved value is always the actual value for the camera attribute.
    """
    def __init__(self, *, camAttr, writeOK, readOK, **kwargs):
        """
        Uses a locally held value and the actual camera attribute when the camera is active.
        
        camAttr     : the attribute in a PiCamera that handles this var
        
        writeOK     : this attribute can be set on PiCamera at any time
        
        readOK      : read this attribute from a PiCamera to find its value
        """
        self.camAttr=camAttr
        self.readOK=readOK==True
        self.writeOK=writeOK==True
        super().__init__(**kwargs)

    def setCameraValue(self, value):
        """
        sets the actual attribute on the camera object if the camera is active and it is allowed
        """
        if self.writeOK and not self.app.picam is None:
            setattr(self.app.picam, self.camAttr, value)

    def setValue(self, value, agent):
        """
        This updates the camera attribute if relevant /applicable and saves the value for when the camera is not running.
        
        Calling super().setValue means any callbacks will be triggered if appropriate.
        """
        super().setValue(value, agent)          # call super().setValue first as this will 'clean' the value if needed
        self.setCameraValue(super().getValue())   # then update the camera with the clean value

    def getValue(self):
        """
        Fetches the current camera value if the camera is active and it is allowed else returns the last known value
        """
        if not self.readOK or self.app.picam is  None:
            return super().getValue()
        else:
            curval=getattr(self.app.picam, self.camAttr)
            super().setValue(curval,'device')
            return curval

    def setupLogMsg(self):
        self.log(30, 'camera attribute ({}) {} set to {}.'.format(('not live' if self.app.picam is None else 'live'),
                    self.camAttr, self._lvvalue))

class camInt(picamAttrMixin, pvars.intVar):
    """
    a class for integer based camera attributes (e.g. brightness or contrast)
    """
    pass

class camGenericMode(picamAttrMixin, pvars.enumVar):
    """
    A class to handle settings that can take 1 value from a retrievable list, and can be set dynamically.
    """
    def __init__(self, app, name, camAttr=None, camAttrList=None, **kwargs):
        """
        additional / used params:
        name        : name is used to derive the default value for camAttr
        
        camAttr     : the PiCamera class attribute to read and write this setting, if None then this is he same as the var's name
        
        camAttrList : the Picamera class attribute that retrieves a list of valid values for this setting
                      if None, the values is uppercase of camAttr with 'S' on the end
        """
        picam_attr=name if camAttr is None else camAttr
        vlist=list(getattr(app.picam, (picam_attr.upper()+'S') if camAttrList is None else camAttrList).keys())
        super().__init__(app=app,
                        name=name,
                        camAttr=picam_attr, 
                        vlist=vlist,
                        fallbackValue=vlist[0],
                        **kwargs)

#    def webset(self, valuelist):
#        try:
#            self.setValue(valuelist[0], 'user')
#        except:
#            return 'fail', 'unable to update %s to %s' % (self.getHierName(), valuelist[0]) 
#        return 'OK', ''#

class camResolution(pvars.enumVar):
    """
    handles the resolution parameter of a picamera. The set of resolutions we preset have to match the camera type.
    
    The value is held as a string, widthxheight.
    
    This class does not use picamAttrMixin as the value is only set as we create a new PiCamera instance.
    """
    resolutions={
        'ov5647' : (('3280x2464', '1640x1232', '1640x922', '1920x1080', '1280x720', '640x480'),
                    '1640x1232'),
                    
        'imx219' : (('2592x1944','1296x972','640x480'),
                    '1296x972')
        }

    def __init__(self, app, fallbackValue=None, **kwargs):
        """
        app is a cameraHandler object with camType already setup
        
        provides a fallbackValue based on the camera type
        """
        camprops=self.resolutions[app.camType]
        super().__init__(fallbackValue=camprops[1], app=app,
                vlist=camprops[0],
                **kwargs)

class camRotation(picamAttrMixin, pvars.enumVar):
    """
    handles camera rotation
    """
    rots=(0,90,180,270)
    def __init__(self, camAttr='rotation', fallbackValue=None, **kwargs):
        super().__init__(fallbackValue='0',
                vlist=self.rots,
                camAttr=camAttr,
                **kwargs)

    def setValue(self, value, agent):
        super().setValue(int(value), agent)

    def webset(self, valuelist):
        try:
            vv=int(valuelist[0])
        except:
            return 'fail', 'unable to convert %s , to int' % valuelist[0]
        try:
            self.setValue(vv, 'user')
        except:
            return 'fail', 'failed to update %s to value %f' % (self.getHierName(), vv)
        return 'OK', ''

        self.setValue(int(valuelist[0]), 'user')

camsettingsvardefs=(
    {'name': 'framerate',   '_cclass': pvars.floatVar,  'fallbackValue': 30, 'minv': 0.01, 'maxv': 60, 'loglvl': 10, 'filters': ['pers']},
    {'name': 'resolution',  '_cclass': camResolution, 'filters': ['pers']},
    {'name': 'rotation',    '_cclass': camRotation, 'fallbackValue': 180, 'readOK': False, 'writeOK': True, 'filters': ['pers']},
    {'name': 'awb_mode',    '_cclass': camGenericMode, 'readOK':False, 'writeOK': True, 'filters': ['pers']},
    {'name': 'exposure_mode', '_cclass': camGenericMode, 'readOK':False, 'writeOK': True, 'filters': ['pers']},
    {'name': 'meter_mode',  '_cclass': camGenericMode, 'readOK':False, 'writeOK': True, 'filters': ['pers']},
    {'name': 'drc_strength','_cclass': camGenericMode, 'readOK': False, 'writeOK': True, 'filters': ['pers']},
    {'name': 'contrast',    '_cclass': camInt, 'fallbackValue': 0, 'camAttr': 'contrast', 'readOK': False, 'writeOK': True, 'minv': -100, 'maxv': 100, 'clamp': True, 'filters': ['pers']},
    {'name': 'brightness',  '_cclass': camInt, 'fallbackValue': 50, 'camAttr': 'brightness', 'readOK': False, 'writeOK': True, 'minv': 0, 'maxv': 100, 'clamp': True, 'filters': ['pers']},
    {'name': 'exp_comp',    '_cclass': camInt, 'fallbackValue': 0, 'camAttr': 'exposure_compensation', 'readOK': False, 'writeOK': True, 'minv': -25, 'maxv': +25, 'clamp': True, 'filters': ['pers']},
)
camacts={'name': 'activities', '_cclass': pvars.groupVar}

camactoptions={
    'gpio_trigger'  : {'name': 'gpio_trigger','_cclass': gpiotrigger},
    'trig_record'   : {'name': 'trig_record','_cclass': VideoRecorder}, #, 'loglvl':10
    'cpumove'       : {'name': 'cpumove','_cclass': MoveDetectCPU},
    'camstream'     : {'name': 'camstream','_cclass': Streamer, 'loglvl':10},
}
camManSetup=(
    {'name': 'camstate', '_cclass': pvars.groupVar, 'childdefs': (
        {'name': 'camactive', '_cclass': pvars.textVar, 'fallbackValue': 'off'},
        {'name':'ports', '_cclass': pvars.groupVar, 'loglvl':10, 'childdefs':(
            {'_cclass': pvars.textVar, 'name':'0', 'fallbackValue': ''},
            {'_cclass': pvars.textVar, 'name':'1', 'fallbackValue': ''},
            {'_cclass': pvars.textVar, 'name':'2', 'fallbackValue': ''},
            {'_cclass': pvars.textVar, 'name':'3', 'fallbackValue': ''},
            )},
        )},
    {'name': 'camsettings', '_cclass': pvars.groupVar, 'childdefs': camsettingsvardefs},
    camacts,
    {'name': 'saveset', '_cclass': pvars.enumVar, 'fallbackValue': 'save', 'vlist': ('save', 'svae ')},
)

class cameraManager(papp.appManager):
    """
    This class groups all the settings that can be applied to a picamera.PiCamera and manages the running camera
    with its assocoated activities.
    
    It sets up for 4 potential video splitter ports, and initialises them to None to show they are unused.
    """
    def __init__(self, features, **kwargs):
        """
        Runs the camera and everything it does as well as other camera related activities
        """
        self.picam=None
        self.cameraTimeout=None
        camacts['childdefs']=[]
        for featname in features:
            if featname in camactoptions:
                opts=camactoptions[featname]
                camacts['childdefs'].append(camactoptions[featname])
        self.activityports={'camstream':2, 'trig_record': 1, 'cpumove': 0}
        self.running=True
        with picamera.PiCamera() as tempcam:
            logging.info('camera opened OK')
            self.camType=tempcam.revision
            self.picam=tempcam
            super().__init__(name='camera', settingsfile='~/camfiles/settings.cfg', childdefs=camManSetup, **kwargs)
            self['saveset'].addNotify(self.savebtn, '*')
            if 'brightpi' in features:
                try:
                    self['camsettings'].makeChild(_cclass = brightpiVar, name='lights')
                except ValueError:
                    self.log(50, 'failed trying to setup brightpi control')
        self.log(20,'closed camera after setup')
        self.picam=None
        threading.Thread(name='cammon', target=self.monitorloop).start()
        return

    def savebtn(self, oldValue, newValue, var, agent):
        """
        just uses saveValues in papp to grab all settings marked as 'pers'
        """
        self.saveValues('~/camfiles/settings.cfg')   

    def saveDefaultSettings(self):
        settingsfile=pathlib.Path('~/.picamsettings.txt').expanduser()
        with settingsfile.open('w') as sf:
            sf.write(self.getSettings('pers'))
            return {'resp':200, 'rdata':{'msg':'defaults set'}}
        return {'resp':502, 'rmsg':'eeek'}

    def fetchSettings(self):
        return self.getSettings('pers')

    def putSettings(self, valuestring):
        self.setSettings('pers', valuestring)

    def startCamera(self):
        """
        starts the camera using the settings originally passed to the constructor. Does nothing if the camera is already running.
        """
        if self.picam is None:
            self.picam=picamera.PiCamera(
                    resolution=self['camsettings/resolution'].getValue(),
                    framerate=self['camsettings/framerate'].getValue())
            settings=self['camsettings']
            for setname in ('rotation',):
                aset=settings[setname]
                v=aset.getValue()
                print('set camera %s to %s' % (setname, v))
                aset.setCameraValue(aset.getValue())
            self.log(20, "pi camera (%s) starts with: frame rate %s screen size %s." % (
                        self.camType, self['camsettings/framerate'].getValue(), self['camsettings/resolution'].getValue()))
            self['camstate/camactive'].setValue('running', 'driver')
        else:
            self.log(10,"start ignored - camera already active")
        return self.picam

    def stopCamera(self):
        """
        stops the camera and releases the associated resources . Does nothing if the camera is not active
        """
        if self.picam is None:
            self.log(10,"stop ignored - camera not running")
        else:
            self.picam.close()
            self.log(20, "pi camera closed")
            self.picam=None
            self['camstate/camactive'].setValue('off', 'driver')

    def monitorloop(self):
        self.log(20,"cameraManager runloop starts")
        stateinf=self['camstate']
        portinf=stateinf['ports']
        while self.running:
            time.sleep(2)
            if stateinf['camactive'].getValue() != 'off':
                keepon=False
                for port in portinf.values():
                    if port.getValue() != '':
                        keepon=True
                        break;
                if not keepon:
                    self.stopCamera()
        self.log(20,"cameraManager runloop closing down")
        self.stopCamera()
        self.log(20,"cameraManager runloop finished")

    def _getSplitterPort(self, activity):
        """
        finds the camera port and allocates it, returning the number, None if problem
        """
        portno=self.activityports[activity]
        pvar=self['camstate/ports/%d' % portno]
        print('==================================', self['camstate/ports'].getValue())
        if pvar.getValue()=='':
            pvar.setValue(activity,'driver')
            self.log(30, '---------->Allocated port for %s, port %d now in use' %(activity, portno))
            return portno
        else:
            self.log(30, '----------->cannot allocate port for %s, port %d already in use (%s)' %(activity, portno, pvar.getValue()))
            return None

    def _releaseSplitterPort(self, activity, s_port):
        portno=self.activityports[activity]
        if portno!=s_port:
            self.log(50, '----------->invalid port release, activity %s trying to release port %d, but in use by %s' %(activity, portno, pvar.getValue()))
        else:
            pvar=self['camstate/ports/%d' % portno]
            if pvar.getValue()==activity:
                pvar.setValue('', 'driver')
                self.log(30, '----------->released port for %s' % activity)
            else:
                self.log(30, '----------->cannont release port for %s, port %d state is (%s)' %(activity, portno, pvar.getValue()))

    def xxstartPortActivity(self, actname, actclass):
        """
        Attempts to start an activity that requires a camera port full time.
        
        First starts the camera if it is not running.
        
        Then (under semaphore) tries to allocate a splitter port - unallocated ports are set to None. 
        This sets the port table entry to zero
        """
        if self.picam is None:
            self.startCamera()
        sport=self._getSplitterPort(0)
        if sport is None:
            if self.loglvl <= logging.WARN:
                self.log.warn("unable to start {} - no free splitter ports".format(actname))
            return None
        if self.loglvl <= logging.DEBUG:
            self.log.debug('allocated port {} for activity {}'.format(sport, actname))
        try:
            newact = self.startActivity(actname=actname, actclass=actclass, splitterport=sport, loglvl=logging.DEBUG)
        except:
            self.camStreams[sport]=None
            raise
        self.camStreams[sport]=newact
        if self.loglvl <= logging.DEBUG:
            self.log.debug('sets port {} used by {}'.format(sport,actname))
        return newact

    def startDetectStream(self):
        return None

    def flipActivity(self, actname, withport, start=None, **kwargs):
        """
        starts and stops activities on demand
        
        actname:   name of the activity
        
        actclass:  class to use to create the activity
        
        withport:  if true, a splitter port is allocated and passed to the activity
        
        start   :  if True then the activity is started if not present, otherwise no action
                   if False then the activity is stopped if present, otherwise no action is taken
                   if None then the activity is stopped if present else it is started
        """
        if actname in self.activities and not start is True:
            self.activities[actname].requestFinish()
        elif not actname in self.activities and not start is False:
            if withport:
                self.startPortActivity(actname=actname, **kwargs)
            else:
                self.startActivity(actname=actname, **kwargs)

    def safeStopCamera(self):
        self.running=False
        for act in self['activities'].values():
            if hasattr(act, 'stopme'):
                act.stopme()

    def setupLogMsg(self):
        print("its'a", self.camType)
        super().setupLogMsg()