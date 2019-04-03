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
import pathlib
import picamera, logging, time
import pforms, papps
from inspect import signature
from threading import Lock as thrlock

from piCamActMoveCPU import mover as cpumover
from piCamActMoveGPIO import externalmover as externalmover
from piCamActLiveStream import liveVidStream
from piCamActTriggerVid import triggeredVideo
from piCamActWatcher import watcher as watcheract

actstartparams={
    'cpumove' : {'actclass': cpumover, 'withport': True},
    'extmove' : {'actclass': externalmover, 'withport': False},
    'tripvid' : {'actclass': triggeredVideo, 'withport': True},
}

class cameraManager(papps.appManager):
    """
    This class groups all the settings that can be applied to a picamera.PiCamera and manages the running camera
    with its assocoated activities.
    
    It sets up for 4 potential video splitter ports, and initialises them to None to show they are unused.
    
    This class uses the views 'pers' and 'app'.
    """
    def __init__(self, **kwargs):
        self.picam=None
        self.cameraTimeout=None
        self.camStreams=[None, None, None, None]
        self.camlock=thrlock()          # allocate a lock to use for multithreading data protection
        logging.info('opening camera for setup')
        with picamera.PiCamera() as tempcam:
            logging.info('camera opened OK')
            self.camType=tempcam.revision
            self.picam=tempcam
            super().__init__(name='camera', **kwargs)
        logging.info('closing camera after setup')
        self.picam=None
        self['settings']['tripvid']['run'].addNotify(self.videotrigger, 'user')
        self['settings']['cpumove']['run'].addNotify(self.cpumotiondetect, 'user')
        self['settings']['cpumove']['lasttrigger'].addNotify(self.movedetected, 'app')
        self['settings']['extmove']['run'].addNotify(self.extmotiondetect, 'user')
        self['settings']['extmove']['lasttrigger'].addNotify(self.movedetected, 'app')
        self['strmctrl']['camerastop'].addNotify(self.safeStopCamera,'user')
        for actname in ('cpumove', 'tripvid', 'extmove', 'livevid'):
            if actname in self['settings']:
                actsettings=self['settings'][actname]
                if 'autostart' in actsettings:
                    autovar = actsettings['autostart']
                    if autovar.getValue('app')=='ON':
                        self.addAlarm(func=self.flipActivity, runafter=3, actname=actname, start=True, **actstartparams[actname])
                if actname+'status' in self:
                    autovar=actsettings['status']
                    echovar=self[actname+'status']
                    echovar.echoFrom(fieldFrom=autovar, triggerkey='app', readkey='webv', writekey='app')
        self.addAlarm(func=self.startActivity, runafter=1.5, actname='watcher', actclass=watcheract)

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
            desiredres=self['settings']['camsettings']['resolution'].getValue('app')
            self.picam=picamera.PiCamera(resolution=desiredres, framerate=self['settings']['camsettings']['framerate'].getValue('app'))
            for v in self['settings']['camsettings'].values():
                if hasattr(v, 'liveUpdate'):
                    print("check setting {}, apply is {}".format(v.name, v.liveUpdate))
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
            if not self.cameraTimeout is None and time.time() > self.cameraTimeout:
                self.stopCamera()
                self.cameraTimeout=None
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

    def _releaseSplitterPort(self, activity, sPort):
        if self.camStreams[sPort]==activity:
            self.camStreams[sPort]=None
            alldone=True
            for act in self.camStreams:
                if not act is None:
                    alldone=False
            self.cameraTimeout=time.time()+self['settings']['camsettings']['camtimeout'].getValue('app') if alldone else None
            if self.loglvl <= logging.DEBUG:
                self.log.debug('releases port {} - previously used by {}'.format(sPort, activity.name))
        else:
            raise RuntimeError('release splitter port inconsistent info for activity {}'.format(activity.name))

    def startPortActivity(self, actname, actclass):
        """
        Attempts to start an activity that requires a camera port.
        
        First starts the camera if it is not running.
        
        Then (under semaphore) tries to allocate a splitter port - unallocated ports are set to None. 
        This sets the port table entry to zero
        """
        if self.picam is None:
            self.startCamera()
        self.camlock.acquire()
        try:
            sport=self.camStreams.index(None)
            self.camStreams[sport]=0
            self.camlock.release()
        except:
            self.camlock.release()
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

    def startLiveStream(self):
        if not 'livevid' in self.activities:
            act=self.startPortActivity('livevid', liveVidStream)
            if act is None:
                if self.loglvl <=logging.INFO:
                    self.log.warn('FAILED to start new livevidstream activity')
                return None
            else:
                act.usecount=1
                if self.loglvl <= logging.INFO:
                    self.log.info('starting livevidstream activity')
        else:
            act=self.activities['livevid']
            act.usecount+=1
            if self.loglvl <= logging.INFO:
                self.log.info('re-using livevidstream activity, count now %d' % act.usecount)
        return act.streambuff

    def stopLiveStream(self):
        if 'livevid' in self.activities:
            act=self.activities['livevid']
            act.usecount-=1
            if self.loglvl <=logging.INFO:
                self.log.info('stopping live stream - count now %d' % act.usecount)
            if act.usecount <= 0:
                act.requestFinish()

    def flipActivity(self, actname, actclass, withport, start=None):
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
                self.startPortActivity(actname=actname, actclass=actclass)
            else:
                self.startActivity(actname=actname, actclass=actclass)

    def videotrigger(self, var=None, view=None, oldValue=None, newValue=None):
        self.flipActivity('tripvid', triggeredVideo, True)

    def cpumotiondetect(self, var=None, view=None, oldValue=None, newValue=None):
        self.flipActivity('cpumove', cpumover, True)

    def extmotiondetect(self, var=None,  view=None, oldValue=None, newValue=None):
        self.flipActivity('extmove', externalmover, False)

    def movedetected(self, var=None, view=None, oldValue=None, newValue=None):
        if 'tripvid' in self.activities:
            act=self.activities['tripvid']
            act.trigger()

    def safeStopCamera(self, var=None, view=None, oldValue=None, newValue=None):
        actives=[]
        if not self.picam is None:
            for portact in self.camStreams:
                if not portact is None and not portact is 0:
                    actives.append(portact.name)
            if len(actives) == 0:
                self.stopCamera()
            elif self.loglvl <= logging.INFO:
                self.log.info('Cannot stop camera - active streams {}'.format(str(actives)))

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
