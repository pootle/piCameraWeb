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

try:
    import pigpio
    PIGPIO=True
except:
    PIGPIO=False


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
    def __init__(self, app, camAttr, camAttrList=None, **kwargs):
        """
        additional / used params:
     
        camAttr     : the PiCamera class attribute to read and write this setting.
        
        camAttrList : the Picamera class attribute that retrieves a list of valid values for this setting
                      if None, the values is uppercase of camAttr with 'S' on the end
        """
        assert hasattr(app.picam, camAttr), 'the object of type %s does not have an attribute %s' % (type(app.picam).__name__, camAttr) 
        vlist=list(getattr(app.picam, (camAttr.upper()+'S') if camAttrList is None else camAttrList).keys())
        super().__init__(app=app,
                        camAttr=camAttr, 
                        vlist=vlist,
                        value=getattr(app.picam,camAttr),
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

    def __init__(self, app, **kwargs):
        """
        app is a cameraHandler object with camType already setup
        """
        assert app.camType in self.resolutions, 'unknown camera type %s' % app.camType
        camprops=self.resolutions[app.camType]
        super().__init__(value=camprops[1], app=app,
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

class camHflip(picamAttrMixin, wv.enumWatch):
    """
    camera horizontal flip
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
        print('iso got value %s of type %s' % (value, type(value).__name__))
        return super().validValue(int(value), agent)

class camFract(picamAttrMixin, wv.floatWatch):
    """
    reads camera attributes that return Fractions and converts them to a float
    """
    def validValue(self, value, agent):
        return super().validValue(value.numerator/value.denominator if isinstance(value, fractions.Fraction) else value, agent)

class cameraManager(wv.watchableApp):
    """
    This class prepares all the settings that can be applied to a picamera.PiCamera and manages the running camera
    with its assocoated activities.
    
    It sets up for 4 potential video splitter ports, and initialises them to None to show they are unused.
    """
    def __init__(self, settingsfile= '~/camsettings.cfg', **kwargs):
        """
        Runs the camera and everything it does as well as other camera related activities
        """
        self.picam=None
        self.cameraTimeout=None
        self.activityports=[None]*3
        self.running=True
        super().__init__(**kwargs)
        with picamera.PiCamera() as tempcam:
            self.log(wv.loglvls.INFO, 'camera opened OK %s' % self)
            self.camType=tempcam.revision
            self.picam=tempcam
            self.cam_framerate=wv.floatWatch(maxv=100, minv=.001, app=self, value=30)
            self.cam_resolution=camResolution(app=self)
            self.cam_u_width=wv.intWatch(app=self, maxv=5000, minv=64, value=640)
            self.cam_u_height=wv.intWatch(app=self, maxv=5000, minv=48, value=480)
            self.cam_rotation=camRotation(app=self, value=0, )
            self.cam_hflip=camHflip(app=self, value=False, **kwargs)
            self.cam_awb_mode=camGenericMode(app=self, camAttr='awb_mode', readOK=False, writeOK= True)
            self.cam_exposure_mode=camGenericMode(app=self, camAttr='exposure_mode', readOK=False, writeOK=True)
            self.cam_meter_mode=camGenericMode(app=self, camAttr='meter_mode', readOK=False, writeOK=True)
            self.cam_drc_strength=camGenericMode(app=self, camAttr='drc_strength', readOK=False, writeOK=True)
            self.cam_contrast=camInt(app=self, camAttr='contrast', value=0, readOK=False, writeOK=True)
            self.cam_brightness=camInt(app=self, camAttr='brightness', value=50, readOK=False, writeOK=True)
            self.cam_exp_comp=camInt(app=self, camAttr='exposure_compensation', value=0, readOK=False, writeOK=True)
            self.cam_iso=camISO(app=self, value=0)
            self.cam_exp_speed=camInt(app=self, camAttr='exposure_speed', value=0, readOK=True, writeOK=False)
            self.cam_shutter_speed=camInt(app=self, camAttr='shutter_speed', value=0, readOK=False, writeOK=True)
            self.cam_analog_gain=camFract(app=self, camAttr='analog_gain', value=0, readOK=True, writeOK=False)
            self.cam_digital_gain=camFract(app=self, camAttr='digital_gain', value=0, readOK=True, writeOK=False)
            self.zoomleft=wv.floatWatch(maxv=1, minv=0, app=self, value=0)
            self.zoomright=wv.floatWatch(maxv=1, minv=0, app=self, value=1)
            self.zoomtop=wv.floatWatch(maxv=1, minv=0, app=self, value=0)
            self.zoombottom=wv.floatWatch(maxv=1, minv=0, app=self, value=1)
            self.picam=None
        self.cam_framerate.addNotify(self.changeframerate, wv.myagents.user)
        self.cam_state=wv.enumWatch(app=self, vlist=('open', 'closed'), value='closed', wrap=False, clamp=False)
        self.cam_summary=wv.textWatch(app=self, value='closed')
        self.cam_autoclose=wv.enumWatch(app=self, vlist=('keep open', 'auto close'), value='auto close')
        self.cam_autoclose_time=wv.intWatch(app=self, minv=1, maxv=600, clamp=True, value=5)
        self.cam_close_btn=wv.btnWatch(app=self, value='Close Camera')
        self.cam_close_btn.addNotify(self.force_close, wv.myagents.user)
        self.savedefaultbtn=wv.btnWatch(app=self, value='Save')
        self.savedefaultbtn.addNotify(self.savesettings, wv.myagents.user)
        self.zoomleft.addNotify(self.newzoom, wv.myagents.user)
        self.zoomright.addNotify(self.newzoom, wv.myagents.user)
        self.zoomtop.addNotify(self.newzoom, wv.myagents.user)
        self.zoombottom.addNotify(self.newzoom, wv.myagents.user)
        spath=pathlib.Path(settingsfile).expanduser()
        settings={}
        if spath.is_file():
                with spath.open('r') as cs:
                    try:
                        savedset=json.load(cs)
                        settings=savedset
                    except:
                        self.log(wv.loglvls.WARN,'FAILED loading settings from %s, defaults used' % (spath))
        if 'camsettings' in settings:
            for k,v in settings['camsettings'].items():
                try:
                    getattr(self,k).setValue(v, wv.myagents.app)
                except Exception as e:
                    self.log(wv.loglvls.WARN,'set %s to %s failed %s' % (k, v, type(e).__name__))
        self.activities={}
        if 'activities' in settings:
            actset=settings['activities']
        else:
            actset={'camstream': {'loglevel':wv.loglvls.DEBUG}, 'triggergpio': {}, 'triggervid': {}, 'cpumove': {}, 'focusser': {}}
        self.log(wv.loglvls.INFO, '=======using acts %s' % list(actset.keys()))
        if 'camstream'in actset:
            from piCamStreamWeb import webStream
            self.activities['camstream'] = webStream(app=self, settings=actset['camstream'])
        if 'triggergpio' in actset:
            from triggergpioweb import gpiotrigweb
            self.activities['triggergpio'] = gpiotrigweb(camapp=self, settings=actset['triggergpio'].get('settings', {}))
        if 'triggervid' in actset:
            from piCamRecordWeb import webVideoRec
            self.activities['triggervid'] = webVideoRec(app=self, settings=actset['triggervid'])
        if 'cpumove' in actset:
            from piCamMovecpuWeb import webcpumove
            self.activities['cpumove'] = webcpumove(camapp=self, settings=actset['cpumove'].get('settings', {}))
        if 'focusser' in actset:
            from unipolarDirectWeb import webStepper
            self.activities['focusser'] = webStepper(camapp=self, settings=actset['focusser'].get('settings', {}))
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
        acts={}
        for actname, act in self.activities.items():
            acts[actname]=act.fetchsettings() if hasattr(act, 'fetchsettings') else {}
        return {
            'camsettings': {sname: getattr(self,sname).getValue() for sname in (
                    'cam_framerate', 'cam_resolution', 'cam_rotation', 'cam_hflip', 'cam_awb_mode', 'cam_exposure_mode', 'cam_meter_mode', 'cam_shutter_speed',
                    'cam_iso', 'cam_drc_strength', 'cam_contrast', 'cam_brightness', 'cam_exp_comp', 'zoomleft', 'zoomright', 'zoomtop', 'zoombottom')},
            'activities' : acts,
        }

    def savesettings(self, oldValue, newValue, agent, watched):
        sp=pathlib.Path('~/camsettings.cfg').expanduser()
        with sp.open('w') as jd:
            json.dump(self.fetchsettings(), jd, indent=3)

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
            self.picam.close()
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
