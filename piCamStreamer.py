#!/usr/bin/python3
"""
streams images to (multiple) clients from the picamera by calling start_recording and passing over successive frames.

It shuts the camera when there are no active clients
"""
from pootlestuff import watchables as wv

import time, threading, io, logging

from enum import Flag, auto

from picamera.exc import PiCameraNotRecording

class Streamer(wv.watchablesmart):
    """
    An activity that provides the live streaming service as a sequence of frames.
    
    It starts streaming on demand, and stops after a few seconds of no activity
    
    This class has the following watchables:
        status      : a simple string shows if streaming is active
        str_width   : the width of images in the generated stream
        str_height  : the height of images in the generated stream
        lastactive  : timestamp of the last time a stream requested an image - used as a backstop to detect when all streaming clients have gone
        realframerate: the actual framerate being achieved - goes wonky at rates below 1 fps
        timeout     : The time in seconds after which (if not images are requested by streaming clients) the streaming stops using the camera
        clientcount : number of active clients - camera splitter port is released >timeout< seconds after the the client count reaches 0.
    """
    def __init__(self, **kwargs):
        """
        initialisation just sets up the vars used.
        """
        self.usebuffer=False
        super().__init__(wabledefs=(
            ('status',      wv.enumWatch,       'off',              False,      {'vlist': ('off', 'streaming')}),
            ('str_width',   wv.intWatch,        640,                True,       {'minv': 120, 'maxv': 1920}),
            ('str_height',  wv.intWatch,        480,                True,       {'minv': 90, 'maxv': 1080}),
            ('lastactive',  wv.floatWatch,      float('nan'),       False,      {}),
            ('realframerate',wv.floatWatch,     float('nan'),       False,      {}),
            ('timeout',     wv.intWatch,        25,                 True,       {}),
            ('clientcount', wv.intWatch,        0,                  False,      {}),
            ),
            **kwargs)
        self.log(wv.loglvls.INFO, 'camstream activity set up')
        self.protect=threading.Lock()
        self.condition=None
        self.running=True
        self.monthread=None

    def getStream(self):
        """
        When we get a stream request, check if already running and if not start everything up and return self.
        
        This is called by an http handler request thread.
        
        THE HTTP thread (there can be several) then loops calling nextframe
        
        Note that start_recording internally runs a thread that will call write as each frame arrives.
        
        This also starts a thread to monitor activity. Once all running streams have stopped, we call stop_recording and release resoources
        
        The monitor thread will also exit at this point
        """
        if self.running:
            with self.protect:
                if self.condition==None:
                    self.framerateclock=time.time()
                    self.realframerate.setValue(0, wv.myagents.app)
                    self.buffcountgood=0
                    self.buffcountbad=0
                    self.sentframecount=0
                    self.condition = threading.Condition()
                    if self.usebuffer:
                        self.buffer = io.BytesIO()
                    self.lastactive.setValue(time.time(),wv.myagents.app)
                    self.splitter_port=self.app._getSplitterPort(self)
                    self.picam=self.app.startCamera()
                    resize=[self.str_width.getValue(), self.str_height.getValue()]
                    camsize=self.app.camres()
                    if resize==camsize:
                        dsize=resize
                        resize=None
                    else:
                        if camsize[0] < resize[0]:
                            resize[0]=camsize[0]
                        if camsize[1] < resize[1]:
                            resize[1]=camsize[1]
                        dsize=resize
                    camfr = self.app.cam_framerate.getValue()
                    if camfr <= 30:
                        self.skipframes=0
                    else:
                        self.skipframes=round(camfr/20)
                    print('----------------------------->using skipframes', self.skipframes)
                    self.skipctr=self.skipframes
                    self.monthread=threading.Thread(name='livestream', target=self.monitor)
                    self.picam.start_recording(self, format='mjpeg', splitter_port=self.splitter_port, resize=resize)
                    self.clientcount.setValue(1, wv.myagents.app)
                    self.monthread.start()
                    self.log(wv.loglvls.INFO, 'camera live streaming using port %d and resize to %d / %d' % (self.splitter_port, dsize[0], dsize[1]))
                else:
                    self.clientcount.increment(wv.myagents.app)
            return self
        else:
            return None

    def write(self, buf):
        """
        called by the camera software from its own thread.
        
        record the next frame and notify all those waiting
        """
        if buf.startswith(b'\xff\xd8'):
            # New frame, copy the existing buffer's content and notify all clients it's available -OR- just remember the passed data
            if self.usebuffer:
                self.buffer.truncate()
            if self.skipctr==0 :
                with self.condition:
                    self.frame=buf
                    if self.usebuffer:
                        self.frame = self.buffer.getvalue()
                    self.condition.notify_all()
                self.skipctr = self.skipframes
            else:
                self.skipctr -= 1
            if self.usebuffer:
                self.buffer.seek(0)
            self.buffcountgood+=1
        else:
            self.buffcountbad+=1
            prints('boops')
        if self.usebuffer:
            return self.buffer.write(buf)
        else:
            return len(buf)

    def streamends(self):
        """
        called from the web server's handler when it stops serving a stream
        """
        with self.protect:
            clientsleft=self.clientcount.increment(wv.myagents.app,-1)
        self.log(wv.loglvls.INFO, 'camera live stream clients left: %d' % clientsleft)

    def nextframe(self):
        """
        The http handler thread(s) calls this to get each successive frame.
        
        It waits for a new frame to arrive, then updates the lastactive timestamp and returns the frame
        """
        with self.condition:
            self.condition.wait()
            self.lastactive.setValue(time.time(), wv.myagents.app)
        self.sentframecount+=1
        return self.frame, 'image/jpeg', len(self.frame)

    def monitor(self):
        self.status.setIndex(1, wv.myagents.app)
        montick=time.time()
        self.lastactive.setValue(montick, wv.myagents.app)
        montick+=2
        delay=0
        cameraclosed=False
        while self.clientcount.getValue() > 0 and self.lastactive.getValue()+125 > time.time() and self.running:
            if delay > 1:
                goodcount=self.buffcountgood
                self.buffcountgood = 0
                self.realframerate.setValue(goodcount/delay, wv.myagents.app)
                self.buffcountgood=0
                if self.buffcountbad > 0:
                    self.log(wv.loglvls.WARN,'in last %4.2f seconds %d goodframes, %d badframes' % (delay, goodcount, self.buffcountbad))
                    self.buffcountbad=0
            delay=montick-time.time()
            self.log(wv.loglvls.DEBUG, 'last active %4.1f seconds ago' % (time.time()-self.lastactive.getValue()))
            try:
                self.picam.wait_recording(delay if delay > 0 else 0, splitter_port=self.splitter_port)
            except PiCameraNotRecording:
                cameraclosed=True
                self.clientcount.setValue(0, wv.myagents.app)
                self.log(wv.loglvls.INFO,'wait recording camera was closed')
            except:
                self.log(wv.loglvls.ERROR,'wait recording failed', exc_info=True, stack_info=True)
            montick += 2
        with self.protect:
            if not cameraclosed:
                self.picam.stop_recording(splitter_port=self.splitter_port)
                self.log(wv.loglvls.INFO, 'streamer recording stopped')
                self.app._releaseSplitterPort(self, self.splitter_port)
            else:
                self.log(wv.loglvls.INFO, 'streamer stopped - camera removed')
            self.splitter_port=None
            self.status.setIndex(0, wv.myagents.app)
            self.lastactive.setValue(time.time(),  wv.myagents.app)
            self.clientcount.setValue(0, wv.myagents.app)
            self.condition = None
            if self.usebuffer:
                self.buffer = None

    def closeact(self):
        monthread=self.monthread
        self.running=False
        if not monthread is None:
            self.log(wv.loglvls.INFO, 'livestream waiting for thread to terminate')
            monthread.join()
        self.log(wv.loglvls.INFO, 'livestream shutdown')

