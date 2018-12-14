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

import picamera, logging, time, datetime, threading, io, shutil
from subprocess import Popen, PIPE
import numpy, queue
import pforms, papps
from inspect import signature

from piCamCpuMove import mover as cpumover
import pigpio

class cameraManager(papps.appManager):
    """
    This class groups all the settings that can be applied to a picamera.PiCamera and manages the running camera
    with its assocoated activities.
    
    It sets up for 4 potential video splitter ports, and initialises them to None to show they are unused.
    """
    def __init__(self, **kwargs):
        self.picam=None
        self.camStreams=[None, None, None, None]
        with picamera.PiCamera() as tempcam:
            self.camType=tempcam.revision
            self.picam=tempcam
            super().__init__(name='camera', **kwargs)
        self.picam=None
        self['settings']['tripvid']['trigger'].addNotify(self.videotrigger, 'html')
        self['settings']['cpumove']['run'].addNotify(self.cpumotiondetect, 'html')
        self['settings']['cpumove']['lasttrigger'].addNotify(self.movedetected, 'app')
        self['settings']['extmove']['run'].addNotify(self.extmotiondetect, 'html')
        self['settings']['extmove']['lasttrigger'].addNotify(self.movedetected, 'app')
        self['strmctrl']['camerastop'].addNotify(self.safeStopCamera,'html')
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
            print('Starting camera with resolution',desiredres)
            self.picam=picamera.PiCamera(resolution=desiredres, framerate=self['settings']['camsettings']['framerate'].getValue('app'))
            for v in self['settings']['camsettings'].values():
                if v.liveUpdate:
                    v._applyVar()
            if self.loglvl <= logging.INFO:
                self.log.info("pi camera (%s) starts with: frame rate %s screen size %s." % (
                        self.camType, self['settings']['camsettings']['framerate'].getValue('expo'), self['settings']['camsettings']['resolution'].getValue('expo')))
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
        return useport

    def setSplitterPort(self, port, activity):
        if self.camStreams[port] is 0:
            self.camStreams[port]=activity
        else:
            raise RuntimeError('splitter port setup error')

    def releaseSplitterPort(self, activity):
        if self.camStreams[activity.sPort]==activity:
            self.camStreams[activity.sPort]=None
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

    def startTriggerVid(self):
        if 'tripvid' in self.activities:
            if self.loglvl <= logging.WARN:
                self.log.warn('tripvid activity already running?')
        else:
            act=self.startPortActivity(actname='tripvid', actclass=triggeredVideo)

    def stopTriggeredVid(self):
        if 'tripvid' in self.activities:
            act=self.activities['tripvid']
            act.requestFinish()

    def videotrigger(self, var=None, view=None, oldValue=None, newValue=None):
        if not 'tripvid' in self.activities:
            self.startTriggerVid()
        else:
            act=self.activities['tripvid']
            act.trigger()

    def startCpuMotionDetect(self):
        if 'cpumove' in self.activities:
            if self.loglvl <= logging.WARN:
                self.log.warn('cpumove activity already running?')
        else:
            act=self.startPortActivity(actname='cpumove', actclass=cpumover)

    def stopCpuMotionDetect(self):
        if 'cpumove' in self.activities:
            act=self.activities['cpumove']
            act.requestFinish()

    def cpumotiondetect(self, var=None, view=None, oldValue=None, newValue=None):
        if 'cpumove' in self.activities:
            self.stopCpuMotionDetect()
        else:
            self.startCpuMotionDetect()

    def startextmoveDetect(self):
        if 'extmove' in self.activities:
            if self.loglvl <= logging.WARN:
                self.log.warn('extmove activity already running?')
        else:
            act=self.startActivity(actname='extmove', actclass=externalmover)

    def stopextmoveDetect(self):
        if 'extmove' in self.activities:
            act=self.activities['extmove']
            act.requestFinish()

    def extmotiondetect(self, var=None,  view=None, oldValue=None, newValue=None):
        print('start external motion detect now')
        if 'extmove' in self.activities:
            self.stopextmoveDetect()
        else:
            self.startextmoveDetect()

    def movedetected(self, var=None, view=None, oldValue=None, newValue=None):
        if 'tripvid' in self.activities:
            act=self.activities['tripvid']
            act.trigger()

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

###############################################################################
# Class to setup triggering from a gpio input
###############################################################################

class externalmover(papps.appThreadAct):
    def __init__(self, **kwargs):
        self.gph=pigpio.pi()
        if not self.gph.connected:
            raise RuntimeError('pigpio not running - external sensing not available')
        super().__init__(**kwargs)
        self.vars['lasttrigger'].setValue('app', 0)

    def startedlogmsg(self):
        return 'external gpio trigger on gpio {} starts'.format(self.vars['triggerpin'].getValue('expo'))

    def endedlogmsg(self):
        return 'external gpio trigger on gpio {} ends, {} triggers'.format(self.vars['triggerpin'].getValue('expo'), 
                                                                           self.vars['triggercount'].getValue('app'))

    def reportstatetime(self, level):
        tnow=time.time()
        if self.lastedgetime==0:
            print('first transition is to {}'.format('high' if level == 1 else 'low'))
        else:
            elapsed=tnow-self.lastedgetime
            print('{} level lasted {:1.2f} seconds'.format('high' if level==0 else 'low', elapsed))
        self.lastedgetime=tnow

    def trigger(self, pin, level, tick):
        print('kicked on pin', pin, 'level', level)
        if self.triggered:
            if level==0:
                self.triggered=False
                self.reportstatetime(level)
            else:
                print('unexpected trigger to high when triggered')
        else:
            if level==1:
                self.triggered=True
                self.vars['triggercount'].setValue('app', self.vars['triggercount'].getValue('app')+1)
                tnow=time.time()
                self.vars['lasttrigger'].setValue('app', tnow)    
                self.reportstatetime(level)         
            else:
                print('unexpected trigger to low when not triggered')

    def run(self):
        self.startDeclare()
        tpin=self.vars['triggerpin'].getValue('app')
        tnow=time.time()
        self.gph.set_mode(tpin,pigpio.INPUT)
        self.lastedgetime=0
        self.triggered = self.gph.read(tpin)==1
        self.callbackref=self.gph.callback(tpin, edge=pigpio.EITHER_EDGE, func=self.trigger)
        self.vars['triggercount'].setValue('app',1 if self.triggered else 0)
        self.vars['lasttrigger'].setValue('app', tnow if self.triggered else 0)
        print('trigger running in gpio', tpin) 
        while self.requstate != 'stop':
            time.sleep(1)
            if self.triggered:
                tnow=time.time()
                if self.vars['lasttrigger'].getValue('app')+1 < tnow:
                    self.vars['lasttrigger'].setValue('app', tnow)
        self.callbackref.cancel()
        self.summaryState='closing'
        self.endDeclare()

class triggeredVideo(papps.appThreadAct):
    """
    This class runs a permanent video stream to a circular buffer. When triggered it then writes a video file with the previous
    few seconds followed by the video of the following time the trigger is active.
    
    Trigger recording by calling the member function trigger from any thread
    """
    def __init__(self, splitterport, **kwargs):
        self.sPort=splitterport
        self.lasttrigger=0
        self.summaryState='waiting'
        super().__init__(**kwargs)
        self.vars['triggercount'].setValue('app',0)
        self.vars['lasttrigger']

    def startedlogmsg(self):
        return 'triggeredVideo using forward {} and back {}'.format(self.vars['forwardtime'].getValue('expo'),
                                                                    self.vars['backtime'].getValue('expo'))

    def endedlogmsg(self):
        return 'triggeredVideo ends, {} video files recorded'.format(self.vars['triggercount'].getValue('app'))

    def trigger(self):
        self.lasttrigger=time.time()

    def run(self):
        self.startDeclare()
        picam=self.parent.picam
        rs=self.vars['resize'].getValue('app')
        circstream=picamera.PiCameraCircularIO(picam, seconds=self.vars['backtime'].getValue('app')+1, splitter_port=self.sPort)
        picam.start_recording(circstream, resize=rs, splitter_port=self.sPort, format='h264')#, sps_timing=True)
        if self.loglvl <=logging.INFO:
            self.log.info("start_recording with size {}".format(str(rs)))            
        while self.requstate != 'stop':
            picam.wait_recording(.3, splitter_port=self.sPort)
            if self.lasttrigger+self.vars['forwardtime'].getValue('app')>time.time():
                self.updateState('recording')
                self.summarystate='recording'
                self.vars['triggercount'].setValue('app',self.vars['triggercount'].getValue('app')+1)
                self.vars['lasttrigger'].setValue('app', time.time())
                tnow=datetime.datetime.now()
                tfile=(self.vars['basefolder'].getValue('app')/tnow.strftime(self.vars['file'].getValue('app'))).with_suffix('.mp4')
                tfile.parent.mkdir(parents=True, exist_ok=True)
                afile=(tfile.parent/(tfile.stem+'after')).with_suffix('.h264')
                bfile=(tfile.parent/(tfile.stem+'before')).with_suffix('.h264')
                picam.split_recording(str(afile), splitter_port=self.sPort)
                circstream.copy_to(str(bfile), seconds=self.vars['backtime'].getValue('app'))
                circstream.clear()
                if self.loglvl <= logging.DEBUG:
                    lstr='recording to {}, pre-time: {}, post time {}.'.format(str(tfile), 
                                                    self.vars['backtime'].getValue('app'), self.vars['forwardtime'].getValue('app'))
                    self.log.debug(lstr)
                while self.requstate=='run' and self.lasttrigger+self.vars['forwardtime'].getValue('app') > time.time():
                    picam.wait_recording(.5, splitter_port=self.sPort)
                if self.loglvl <= logging.DEBUG:
                    self.log.debug('done recording')
                self.summaryState='waiting'
                picam.split_recording(circstream, splitter_port=self.sPort)
                if bfile.stat().st_size == 0:
                    cmd=['MP4Box', '-quiet', '-add', str(afile), str(tfile)]
                else:
                    cmd=['MP4Box', '-quiet', '-add', str(bfile), '-cat', str(afile), str(tfile)]
                if self.loglvl <= logging.DEBUG:
                    self.log.debug('mp4 save using >{}<'.format(cmd))
                subp=Popen(cmd, universal_newlines=True, stdout=PIPE, stderr=PIPE)
                outs, errs = subp.communicate(timeout=15)
                rcode=subp.returncode
                if rcode ==0:
                    shutil.copystat(str(bfile), str(tfile))
                    afile.unlink()
                    bfile.unlink()                    
                if rcode != 0 and not errs is None:
                    print('MP4Box stderr:')
                    print('   ', errs)
                self.updateState('run')
        picam.stop_recording(splitter_port=sPort)
        self.summaryState='closing'
        self.endDeclare()

###############################################################################
# Classes to generate a stream of mjpeg images (once) and notify all 
# consumers through Notify
###############################################################################

class liveVidStream(papps.appActivity):
    def __init__(self, splitterport, **kwargs):
        self.sPort=splitterport
        super().__init__(**kwargs)

    def start(self):
        self.startDeclare()
        self.streambuff=StreamingOutput()
        self.parent.picam.start_recording(self.streambuff,
                    format='mjpeg',
                    splitter_port=self.sPort, 
                    resize=self.vars['resize'].getValue('app'))

    def requestFinish(self):
        self.requstate='stop'
        self.parent.picam.stop_recording(splitter_port=self.sPort)
        self.parent.releaseSplitterPort(self)
        self.endDeclare()

class StreamingOutput():
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = threading.Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            # New frame, copy the existing buffer's content and notify all
            # clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)

###############################################################################
# class to run video to a circular buffer and, when triggered, writes 
# previous few seconds to file and keeps writing till no trigger received
# for several seconds
###############################################################################

class triggeredVideo(papps.appThreadAct):
    """
    This class runs a permanent video stream to a circular buffer. When triggered it then writes a video file with the previous
    few seconds followed by the video of the following time the trigger is active.
    
    Trigger recording by calling the member function trigger from any thread
    """
    def __init__(self, splitterport, **kwargs):
        self.sPort=splitterport
        self.lasttrigger=0
        self.summaryState='waiting'
        super().__init__(**kwargs)
        self.vars['triggercount'].setValue('app',0)

    def startedlogmsg(self):
        return 'triggeredVideo using forward {} and back {}'.format(self.vars['forwardtime'].getValue('expo'),
                                                                    self.vars['backtime'].getValue('expo'))

    def endedlogmsg(self):
        return 'triggeredVideo ends, {} video files recorded'.format(self.vars['triggercount'].getValue('app'))

    def trigger(self):
        self.lasttrigger=time.time()

    def run(self):
        self.startDeclare()
        picam=self.parent.picam
        rs=self.vars['resize'].getValue('app')
        circstream=picamera.PiCameraCircularIO(picam, seconds=self.vars['backtime'].getValue('app')+1, splitter_port=self.sPort)
        picam.start_recording(circstream, resize=rs, splitter_port=self.sPort, format='h264')#, sps_timing=True)
        if self.loglvl <=logging.INFO:
            self.log.info("start_recording with size {}".format(str(rs)))            
        while self.requstate != 'stop':
            picam.wait_recording(.3, splitter_port=self.sPort)
            if self.lasttrigger+self.vars['forwardtime'].getValue('app')>time.time():
                self.updateState('recording')
                self.summarystate='recording'
                self.vars['triggercount'].setValue('app',self.vars['triggercount'].getValue('app')+1)
                self.vars['lasttrigger'].setValue('app', time.time())
                tnow=datetime.datetime.now()
                tfile=(self.vars['basefolder'].getValue('app')/tnow.strftime(self.vars['file'].getValue('app'))).with_suffix('.mp4')
                tfile.parent.mkdir(parents=True, exist_ok=True)
                afile=(tfile.parent/(tfile.stem+'after')).with_suffix('.h264')
                bfile=(tfile.parent/(tfile.stem+'before')).with_suffix('.h264')
                picam.split_recording(str(afile), splitter_port=self.sPort)
                circstream.copy_to(str(bfile), seconds=self.vars['backtime'].getValue('app'))
                circstream.clear()
                if self.loglvl <= logging.DEBUG:
                    lstr='recording to {}, pre-time: {}, post time {}.'.format(str(tfile), 
                                                    self.vars['backtime'].getValue('app'), self.vars['forwardtime'].getValue('app'))
                    self.log.debug(lstr)
                while self.requstate=='run' and self.lasttrigger+self.vars['forwardtime'].getValue('app') > time.time():
                    picam.wait_recording(.5, splitter_port=self.sPort)
                if self.loglvl <= logging.DEBUG:
                    self.log.debug('done recording')
                self.summaryState='waiting'
                picam.split_recording(circstream, splitter_port=self.sPort)
                if bfile.stat().st_size == 0:
                    cmd=['MP4Box', '-quiet', '-add', str(afile), str(tfile)]
                else:
                    cmd=['MP4Box', '-quiet', '-add', str(bfile), '-cat', str(afile), str(tfile)]
                if self.loglvl <= logging.DEBUG:
                    self.log.debug('mp4 save using >{}<'.format(cmd))
                subp=Popen(cmd, universal_newlines=True, stdout=PIPE, stderr=PIPE)
                outs, errs = subp.communicate(timeout=15)
                rcode=subp.returncode
                if rcode ==0:
                    shutil.copystat(str(bfile), str(tfile))
                    afile.unlink()
                    bfile.unlink()                    
                if rcode != 0 and not errs is None:
                    print('MP4Box stderr:')
                    print('   ', errs)
                self.updateState('run')
        picam.stop_recording(splitter_port=sPort)
        self.summaryState='closing'
        self.endDeclare()
