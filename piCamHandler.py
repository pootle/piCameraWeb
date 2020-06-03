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

The program uses watcher derived variables to enable easy integration with front end software
"""

import picamera, logging, time
import threading, json, pathlib, fractions

from pootlestuff import watchables as wv

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
        if writeOK and not readOK:
            self.setCameraValue()

    def setCameraValue(self):
        """
        sets the actual attribute on the camera object if the camera is active and it is allowed
        """
        if self.writeOK and not self.app.picam is None:
            val=super().getValue()
            self.log(wv.loglvls.DEBUG, 'camera %s set to %s' % (self.camAttr, val))
            setattr(self.app.picam, self.camAttr, val)

    def setValue(self, value, agent):
        """
        This saves the value locally and updates the camera attribute if relevant /applicable.
        
        Calling super().setValue means any callbacks will be triggered if appropriate.
        """
        super().setValue(value, agent)          # call super().setValue first as this will 'clean' the value if needed
        self.setCameraValue()   # then update the camera with the clean value

    def getValue(self):
        """
        Fetches the current camera value if the camera is active and it is allowed else returns the last known value
        """
        if not self.readOK or self.app.picam is None:
            return super().getValue()
        else:
            curval=getattr(self.app.picam, self.camAttr)
            super().setValue(curval,self.app.agentclass.app)
            return curval

    def setupLogMsg(self):
        self.log(30, 'camera attribute ({}) {} set to {}.'.format(('not live' if self.app.picam is None else 'live'),
                    self.camAttr, self._lvvalue))

class camInt(picamAttrMixin, wv.intWatch):
    """
    a class for integer based camera attributes (e.g. brightness or contrast)
    """
    pass

class camGenericMode(picamAttrMixin, wv.enumWatch):
    """
    A class to handle settings that can take 1 value from a retrievable list, and can be set dynamically.
    """
    def __init__(self, app, camAttr, value, writeOK, camAttrList=None, **kwargs):
        """
        additional / used params:
     
        camAttr     : the PiCamera class attribute to read and write this setting.
        
        camAttrList : the Picamera class attribute that retrieves a list of valid values for this setting
                      if None, the values is uppercase of camAttr with 'S' on the end
        """
        assert hasattr(app.picam, camAttr), 'the object of type %s does not have an attribute %s' % (type(app.picam).__name__, camAttr) 
        vlist=list(getattr(app.picam, (camAttr.upper()+'S') if camAttrList is None else camAttrList).keys())
        if value is None:
            value=vlist[0]
        super().__init__(app=app,
                        camAttr=camAttr, 
                        vlist=vlist,
                        value=value if writeOK else getattr(app.picam,camAttr),
                        writeOK=writeOK,
                        **kwargs)
#        self.log(wv.loglvls.DEBUG,'camera %s set to %s from list %s' % (camAttr, getattr(app.picam,camAttr), vlist))

class camResolution(wv.enumWatch):
    """
    handles the resolution parameter of a picamera. The set of resolutions we preset have to match the camera type.
    
    The value is held as a string, widthxheight.
    
    This class does not use picamAttrMixin as the value is only set as we create a new PiCamera instance.
    """
    resolutions={
        'ov5647' : (('special', '3280x2464', '1640x1232', '1640x922', '1920x1080', '1280x720', '640x480'),
                    '1640x1232'),
                    
        'imx219' : (('special', '2592x1944','1296x972','640x480'),
                    '1296x972'),
        'testc'  : (('special', '4056x3040', '2028x1520', '1012x760', '1080p', '720p', '480p'),'2028x1520')
        }

    def __init__(self, app, value, **kwargs):
        """
        app is a cameraHandler object with camType already setup
        """
        assert app.camType in self.resolutions, 'unknown camera type %s' % app.camType
        camprops=self.resolutions[app.camType]
        useval=camprops[1] if value is 0 or not value in camprops[0] else value
        super().__init__(value=useval, app=app,
                vlist=camprops[0],
                **kwargs)

class camRotation(picamAttrMixin, wv.enumWatch):
    """
    handles camera rotation
    """
    rots=(0,90,180,270)
    def __init__(self, camAttr='rotation', **kwargs):
        super().__init__(
                vlist=self.rots,
                camAttr=camAttr,
                readOK=False,
                writeOK=True,
                **kwargs)

    def validValue(self, value, agent):
        ival = int(value)
        if not ival in self.vlist:
            raise ValueError('value (%s) not valid' % value)
        return ival

class camflip(picamAttrMixin, wv.enumWatch):
    """
    camera horizontal / vertical flip
    """
    def __init__(self, camAttr='hflip', **kwargs):
        super().__init__(
            vlist=(False, True),
            camAttr=camAttr,
            readOK=False,
            writeOK=True,
            **kwargs)

    def validValue(self, value, agent):
        return value==True

class camISO(picamAttrMixin, wv.enumWatch):
    """
    enables iso to be explicitly set
    """
    def __init__(self, camAttr='iso', **kwargs):
        super().__init__(
            vlist=(0, 100, 200, 320, 400, 500, 640, 800),
            camAttr=camAttr,
            readOK=False,
            writeOK=True,
            **kwargs)

    def validValue(self, value, agent):
        return super().validValue(int(value), agent)

class camFract(picamAttrMixin, wv.floatWatch):
    """
    reads camera attributes that return Fractions and converts them to a float
    """
    def validValue(self, value, agent):
        return super().validValue(value.numerator/value.denominator if isinstance(value, fractions.Fraction) else value, agent)



class cameraManager(wv.watchablesmart):
    """
    This class prepares all the settings that can be applied to a picamera.PiCamera and manages the running camera
    with its associated activities.
    
    It sets up for 4 potential video splitter ports, and initialises them to None to show they are unused.
    """
    def __init__(self, acts, **kwargs):
        """
        Runs the camera and everything it does as well as other camera related activities
        """
        self.picam=None
        self.cameraTimeout=None
        self.activityports=[None]*3
        self.running=True
        wables=[
            ('cam_framerate',   wv.floatWatch,      20,     True,   {'maxv': 100, 'minv': .001}),
            ('cam_resolution',  camResolution,      0,      True),
            ('cam_u_width',     wv.intWatch,        640,    True,   {'minv': 64, 'maxv': 5000}),
            ('cam_u_height',    wv.intWatch,        480,    True,   {'minv': 48, 'maxv': 5000}),
            ('cam_rotation',    camRotation,        0,      True),
            ('cam_hflip',       camflip,           False,   True),
            ('cam_vflip',       camflip,           False,   True,   {'camAttr': 'vflip'}),
            ('cam_awb_mode',    camGenericMode,     'auto', True,   {'camAttr': 'awb_mode', 'readOK': False, 'writeOK':  True}),
            ('cam_exposure_mode',camGenericMode,    'auto', True,   {'camAttr': 'exposure_mode', 'readOK': False, 'writeOK': True}),
            ('cam_meter_mode',  camGenericMode,     None,   True,   {'camAttr': 'meter_mode', 'readOK': False, 'writeOK': True}),
            ('cam_drc_strength',camGenericMode,     'off',  True,   {'camAttr': 'drc_strength', 'readOK': False, 'writeOK': True}),
            ('cam_contrast',    camInt,             0,      True,   {'camAttr': 'contrast', 'readOK': False, 'writeOK': True}),
            ('cam_brightness',  camInt,             50,     True,   {'camAttr': 'brightness', 'readOK': False, 'writeOK': True}),
            ('cam_exp_comp',    camInt,             0,      True,   {'camAttr': 'exposure_compensation', 'readOK': False, 'writeOK': True}),
            ('cam_iso',         camISO,             0,      True),
            ('cam_exp_speed',   camInt,             0,      False,  {'camAttr': 'exposure_speed', 'readOK': True, 'writeOK': False}),
            ('cam_shutter_speed',camInt,            0,      True,   {'camAttr': 'shutter_speed', 'readOK': False, 'writeOK': True}),
            ('cam_analog_gain', camFract,           0,      False,  {'camAttr': 'analog_gain', 'readOK': True, 'writeOK': False}),
            ('cam_digital_gain',camFract,           0,      False,  {'camAttr': 'digital_gain', 'readOK': True, 'writeOK': False}),
            ('zoomleft',        wv.floatWatch,      0,      True,   {'maxv': 1, 'minv': 0}),
            ('zoomright',       wv.floatWatch,      1,      True,   {'maxv': 1, 'minv': 0}),
            ('zoomtop',         wv.floatWatch,      0,      True,   {'maxv': 1, 'minv': 0}),
            ('zoombottom',      wv.floatWatch,      1,      True,   {'maxv': 1, 'minv': 0}),
            ('cam_state',       wv.enumWatch,       'closed',False, {'vlist': ('open', 'closed'), 'wrap': False, 'clamp': False}),
            ('cam_summary',     wv.textWatch,       'closed',False),
            ('cam_autoclose',   wv.enumWatch,       'auto close', True, {'vlist': ('keep open', 'auto close')}),
            ('cam_autoclose_time',wv.intWatch,       5,     True,   {'minv': 1, 'maxv': 600, 'clamp': True}),
            ('cam_close_btn',   wv.btnWatch,        'close camera', False),
            ('savedefaultbtn',  wv.btnWatch,        'Save', False),          
        ]
        with picamera.PiCamera() as tempcam:
            self.camType=tempcam.revision
            self.picam=tempcam
            super().__init__(wabledefs=wables, **kwargs)
            self.picam=None
        self.cam_framerate.addNotify(self.changeframerate, wv.myagents.user)
        self.cam_close_btn.addNotify(self.force_close, wv.myagents.user)
        self.savedefaultbtn.addNotify(self.savesettings, wv.myagents.user)
        self.zoomleft.addNotify(self.newzoom, wv.myagents.user)
        self.zoomright.addNotify(self.newzoom, wv.myagents.user)
        self.zoomtop.addNotify(self.newzoom, wv.myagents.user)
        self.zoombottom.addNotify(self.newzoom, wv.myagents.user)
        self.activities={}
        actsettings=self.startsettings.get('acts', {})
        if 'camstream' in acts:
            from piCamStreamWeb import webStream
            self.activities['camstream'] = webStream(app=self, value=actsettings.get('camstream',{}))
        if 'triggergpio' in acts:
            from triggergpioweb import webtriggergpio
            self.activities['triggergpio'] = webtriggergpio(app=self, value=actsettings.get('triggergpio', {}))
        if 'cpumove' in acts:
            from piCamMovecpuWeb import webcpumove
            self.activities['cpumove'] = webcpumove(app=self, value=actsettings.get('cpumove',{}))
        if 'focusser' in acts:
            from unipolarDirectWeb import webStepper
            self.activities['focusser'] = webStepper(app=self, value=actsettings.get('focusser', {}))
        if 'triggervid' in acts:
            from piCamRecordWeb import webVideoRec
            self.activities['triggervid'] = webVideoRec(app=self, value=actsettings.get('triggervid',{}))
        self.log(wv.loglvls.INFO,'closed camera after setup')
        threading.Thread(name='cammon', target=self.monitorloop).start()

    def camres(self):
        """
        fetches the current resolution the camera is using.
        
        returns (width, height) 
        """
        return [x for x in self.picam.resolution]

    def camrmode(self):
        """
        fetches the appropriate string for the resolution param on opening camera
        """
        if self.cam_resolution.getIndex()==0:
            return '%dx%d' % (self.cam_u_width.getValue(), self.cam_u_height.getValue())
        else:
            return self.cam_resolution.getValue()

    def fetchsettings(self):
        """
        override the standard fetchsettings to add in settings for the activities
        """
        acts={}
        for actname, act in self.activities.items():
            acts[actname]=act.fetchsettings() if hasattr(act, 'fetchsettings') else {}
        setts=super().fetchsettings()
        setts['acts']=acts
        return setts

    def startCamera(self):
        """
        starts the camera using the settings originally passed to the constructor. Does nothing if the camera is already running.
        """
        if self.picam is None:
            cres=self.camrmode()
            self.picam=picamera.PiCamera(
                    resolution=cres,
                    framerate=self.cam_framerate.getValue())
            for camval in ('cam_rotation', 'cam_awb_mode', 'cam_exposure_mode', 'cam_meter_mode', 'cam_shutter_speed', 'cam_drc_strength', 'cam_contrast',
                           'cam_brightness', 'cam_exp_comp',):
                getattr(self, camval).setCameraValue()
            self.setzoom()
            self.log(wv.loglvls.INFO, "pi camera (%s) starts with: frame rate %s screen size %s frame size %s." % (
                        self.camType, self.cam_framerate.getValue(), cres, self.picam.resolution))
            self.cam_state.setValue('open', wv.myagents.app)
            self.cam_summary.setValue('open: (%s) %4.2f fps' % (cres, self.cam_framerate.getValue()), wv.myagents.app)
            checkres=self.picam.resolution
            checkfr=self.picam.framerate
            checkmode=self.picam.sensor_mode
            print('-----> opened with res: %s, framerate: %4.2f, mode: %d' % (checkres, checkfr.numerator/checkfr.denominator, checkmode))
        else:
            self.log(wv.loglvls.INFO,"start ignored - camera already active")
        return self.picam

    def changeframerate(self, watched, agent, newValue, oldValue):
        if self.picam:
            self.log(wv.loglvls.INFO,"updating framrate on open camera to %5.3f" % newValue)
            camready=True
            for camuser in self.activityports:
                if not camuser is None:
                    if hasattr(camuser,'pausecamera'):
                        camuser.pausecamera()
                    else:
                        camready=False
            if camready:
                self.picam.framerate = newValue
            else:
                self.log(wv.loglvls.INFO, 'unable to change framerate - camera in use')
            for camuser in self.activityports:
                if not camuser is None:
                    if hasattr(camuser,'pausecamera'):
                        camuser.resumecamera()

    def newzoom(self, watched, agent, newValue, oldValue):
        self.setzoom()

    def setzoom(self):
        if self.picam:
            zx=self.zoomleft.getValue()
            zw=self.zoomright.getValue()-zx
            zy=self.zoomtop.getValue()
            zh=self.zoombottom.getValue()-zy
            self.picam.zoom=(zx,zy,zw,zh)

    def force_close(self, oldValue, newValue, agent, watched):
        self.stopCamera()

    def stopCamera(self):
        """
        stops the camera and releases the associated resources . Does nothing if the camera is not active
        """
        if self.picam is None:
            self.log(wv.loglvls.INFO,"stop ignored - camera not running")
        else:
            try:
                self.picam.close()
            except:
                pass
            self.log(wv.loglvls.INFO, "pi camera closed")
            self.picam=None
            self.cam_state.setValue('closed', wv.myagents.app)
            self.cam_summary.setValue('closed', wv.myagents.app)

    def monitorloop(self):
        self.log(wv.loglvls.INFO,"cameraManager runloop starts")
        camtimeout=None
        while self.running:
            time.sleep(2)
            if self.picam:
                self.cam_exp_speed.getValue()
                self.cam_analog_gain.getValue()
                self.cam_digital_gain.getValue()
                if self.cam_autoclose.getIndex() > 0:
                    for port in self.activityports:
                        if port:
                            break
                    else:
                        if camtimeout is None:
                            camtimeout=time.time()+20
                        elif time.time() > camtimeout: 
                            self.stopCamera()
                            camtimeout=None
        self.log(wv.loglvls.INFO,"cameraManager runloop closing down")
        self.stopCamera()
        self.log(wv.loglvls.INFO,"cameraManager runloop finished")

    def _getSplitterPort(self, activity):
        """
        finds the camera port and allocates it, returning the number, None if problem
        """
        try:
            freeport=self.activityports.index(None)
        except ValueError:
            self.log(wv.loglvls.ERROR,'unable to find free port for activity %s' % activity)
            return None
        self.activityports[freeport]=activity
        self.log(wv.loglvls.INFO,'port %d allocated to %s' % (freeport, activity))
        return freeport
       
    def _releaseSplitterPort(self, activity, s_port):
        assert self.activityports[s_port] is activity
        self.log(wv.loglvls.INFO,'port %d released from %s' % (s_port, activity))
        self.activityports[s_port] =None

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

    def close(self):
        self.safeStopCamera()

    def safeStopCamera(self):
        self.running=False
        self.activities['camstream'].closeact()
        return        
        
        
        for actname, actob in self.activities.items():
            try:
                actob.closeact()
                self.log(wv.loglvls.INFO,'activity %s closed' % actname)
            except:
                self.log(wv.loglvls.WARN,'activity %s failed to close' % actname, exc_info=True, stack_info=True)
