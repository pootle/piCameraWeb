#!/usr/bin/python3
"""
experimental module to run the camera in video mode with up to 3 differently purposed streams.

each stream can be independently started and stopped. The 3 streams are intended to be used for any combination of:

    streaming live video - simply using mjpeg
    watching for movement - continuously capture (fairly small) images and check for 'movement'
    triggered recording once movement is detected - records while 'movement' detected plus few seconds before and after
    timelapse photos

The camera is setup at a specific resolution and framerate - typically the resolution will use the whole sensor, binned to 
reduce the working size, and a framerate to suit.

The different feeds then resize the image to an appropriate size for the particular task. As the GPU does the resizing it is
very fast and low latency.
"""

import picamera, logging, time
import pforms, papps
from inspect import signature

from piCamActMoveCPU import mover as cpumover
from piCamActMoveGPIO import externalmover as externalmover
from piCamActLiveStream import liveVidStream
from piCamActTriggerVid import triggeredVideo

class cameraManager(papps.appManager):
    """
    This class groups all the settings that can be applied to a picamera.PiCamera and manages the running camera
    with its assocoated activities.
    
    It sets up for 4 potential video splitter ports, and initialises them to None to show they are unused.
    
    This class uses the views 'pers' and 'app'.
    """
    def __init__(self, **kwargs):
        self.picam=None
        self.camStreams=[None, None, None, None]
        with picamera.PiCamera() as tempcam:
            self.camType=tempcam.revision
            self.picam=tempcam
            super().__init__(name='camera', **kwargs)
        self.picam=None
        self['settings']['tripvid']['run'].addNotify(self.videotrigger, 'user')
        self['settings']['cpumove']['run'].addNotify(self.cpumotiondetect, 'user')
        self['settings']['cpumove']['lasttrigger'].addNotify(self.movedetected, 'app')
        self['settings']['extmove']['run'].addNotify(self.extmotiondetect, 'user')
        self['settings']['extmove']['lasttrigger'].addNotify(self.movedetected, 'app')
        self['strmctrl']['camerastop'].addNotify(self.safeStopCamera,'user')
#        self['strmctrl']['test1'].addNotify(self.dlsettings,'html')
#        self['strmctrl']['test2'].addNotify(self.dotest,'html')

    def dotest(self, var, view=None, oldValue=None, newValue=None):
        print('you pressed', var.name)
        if var.name in self.activities:
            self.activities[var.name].requestFinish()
        else:
            self.startActivity(actname=var.name,
                actclass=papps.appActivity if var.name=='test1' else papps.appThreadAct)

    def fetchSettings(self):
        return self.getSettings('pers')

    def putSettings(self, valuestring):
        self.setSettings('pers', valuestring)

    def startCamera(self):
        """
        starts the camera using the settings originally passed to the constructor. Does nothing if the camera is already running.
        """
        if self.picam is None:
            desiredres=self['settings']['camsettings']['resolution'].getValue('app')
            self.picam=picamera.PiCamera(resolution=desiredres, framerate=self['settings']['camsettings']['framerate'].getValue('app'))
            for v in self['settings']['camsettings'].values():
                if v.liveUpdate:
                    v._applyVar()
            self['camstatus'].setValue('app',self['settings']['camsettings']['resolution'].getValue('webv'))
            if self.loglvl <= logging.INFO:
                self.log.info("pi camera (%s) starts with: frame rate %s screen size %s." % (
                        self.camType, self['settings']['camsettings']['framerate'].getValue('pers'), self['settings']['camsettings']['resolution'].getValue('pers')))
        elif self.loglvl <= logging.INFO:
            self.log.info("start ignored - camera already active")

    def stopCamera(self):
        """
        stops the camera and releases the associated resources . Does nothing if the camera is not active
        """
        if self.picam is None:
            if self.loglvl <= logging.INFO:
                self.log.info("stop ignored - camera not running")
        else:
            self.picam.close()
            if self.loglvl <= logging.INFO:
                self.log.info("pi camera closed")
            self.picam=None
            self['camstatus'].setValue('app', 'off')

    def runloop(self):
        while self.running:
            time.sleep(2)
            self.checkActivities()
        if self.loglvl <= logging.INFO:
            self.log.info("cameraManager runloop closing down")
        pending=0
        for act in self.activities.values():
            act.requestFinish()
            pending+=1
        while pending > 0:
            self.checkActivities()
            if len(self.activities) > 0:
                time.sleep(.3)
            pending=len(self.activities)
        self.stopCamera()
        if self.loglvl <= logging.INFO:
            self.log.info("cameraManager runloop all streams closed, time to exit.")

    def getSplitterPort(self):
        try:
            useport=self.camStreams.index(None)
            self.camStreams[useport]=0
        except:
            return None
        if self.picam is None:
            self.startCamera()
        if self.loglvl <= logging.DEBUG:
            self.log.debug('allocated port {}'.format(useport))
        return useport

    def setSplitterPort(self, port, activity):
        if self.camStreams[port] is 0:
            self.camStreams[port]=activity
            if self.loglvl <= logging.DEBUG:
                self.log.debug('sets port {} used by {}'.format(port,activity.name))
        else:
            raise RuntimeError('splitter port setup error')

    def releaseSplitterPort(self, activity):
        if self.camStreams[activity.sPort]==activity:
            self.camStreams[activity.sPort]=None
            if self.loglvl <= logging.DEBUG:
                self.log.debug('releases port {} - previously used by {}'.format(activity.sPort, activity.name))
        else:
            raise RuntimeError('release splitter port inconsistent info for activity {}'.format(activity.name))

    def startPortActivity(self, actname, actclass):
        sport=self.getSplitterPort()
        if sport is None:
            if self.loglvl <= logging.WARN:
                self.log.warn("unable to start {} - no free splitter ports".format(actname))
            return None
        self.startActivity(actname=actname, actclass=actclass, splitterport=sport, loglvl=logging.DEBUG)
        act=self.activities[actname]
        self.setSplitterPort(sport, act)
        return act

    def startDetectStream(self):
        return None

    def startLiveStream(self):
        if not 'livevid' in self.activities:
            act=self.startPortActivity('livevid', liveVidStream)
            if act is None:
                return None
            else:
                act.usecount=1
        else:
            act=self.activities['livevid']
            act.usecount+=1
        return act.streambuff

    def stopLiveStream(self):
        if 'livevid' in self.activities:
            act=self.activities['livevid']
            act.usecount-=1
            if act.usecount <= 0:
                act.requestFinish()

    def startCameraActivity(self, actname, actclass, withport):
        if actname in self.activities:
            if self.loglvl <= logging.WARN:
                self.log.warn('{} activity already running, start request ignored'.format(actname))
        else:
            if withport:
                self.startPortActivity(actname=actname, actclass=actclass)
            else:
                self.startActivity(actname=actname, actclass=actclass)

    def stopCameraActivity(self, actname):
        if actname in self.activities:
            act=self.activities[actname]
            act.requestFinish()
        else:
            if self.loglvl <= logging.WARN:
                self.log.warn('{} activity not running, stop request ignored'.format(actname))

    def videotrigger(self, var=None, view=None, oldValue=None, newValue=None):
        if 'tripvid' in self.activities:
            self.stopCameraActivity('tripvid')
#?            act.trigger()
        else:
            self.startCameraActivity('tripvid', triggeredVideo, True)

    def cpumotiondetect(self, var=None, view=None, oldValue=None, newValue=None):
        if 'cpumove' in self.activities:
            self.stopCameraActivity('cpumove')
        else:
            self.startCameraActivity('cpumove', cpumover, True)

    def extmotiondetect(self, var=None,  view=None, oldValue=None, newValue=None):
        if 'extmove' in self.activities:
            self.stopCameraActivity('extmove')
        else:
            self.startCameraActivity('extmove', externalmover, False)

    def movedetected(self, var=None, view=None, oldValue=None, newValue=None):
        if 'tripvid' in self.activities:
            print('piCamHandler: movedetected -vid triggered')
            act=self.activities['tripvid']
            act.trigger()
        else:
            print('piCamHandler: movedetected -vid not active')

    def safeStopCamera(self, var=None, view=None, oldValue=None, newValue=None):
        if len(self.activities) == 0:
            self.stopCamera()
            if self.loglvl <= logging.INFO:
                self.log.info('Camera stopped')
        elif self.loglvl <= logging.INFO:
            self.log.info('Cannot stop camera - active streams')

    def setupLogMsg(self):
        print("its'a", self.camType)
        super().setupLogMsg()

    def streamstates(self):
        """
        called to generate a sequence of updates reporting the status of the camera handler.
        TODO: prolly replacing this with dynamic update vars
        """
        while True:
            ys= {sname: self.activities[sname]._localstate if sname in self.activities else 'off' for sname in ('livevid','tripvid')}
            ys['camactive']='running' if self.picam else 'stopped'
            yield ys
