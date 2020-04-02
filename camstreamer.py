#!/usr/bin/python3
"""
streams images to (multiple) clients from the picamera by calling start_recording and passing over successive frames.

It shuts the camera when there are no active clients
"""
from pootlestuff import pvars

import time, threading, io, logging

camstreamvardefs=(
    {'name': 'status',      '_cclass': pvars.enumVar,      'fallbackValue': 'off', 'vlist': ('off', 'streaming')},
    {'name': 'width',       '_cclass': pvars.intVar,        'fallbackValue': 640, 'minv': 64, 'maxv': 2000, 'filters': ['pers']},
    {'name': 'height',      '_cclass': pvars.intVar,        'fallbackValue': 480, 'minv': 48, 'maxv': 2000, 'filters': ['pers']},
    {'name': 'lastactive',  '_cclass': pvars.floatVar,      'fallbackValue': 0},
)

class Streamer(pvars.groupVar):
    """
    An activity that provides the live streaming service as a sequence of frames.
    
    It starts streaming on demand, and stops after a few seconds of no activity
    """
    def __init__(self, **kwargs):
        """
        initialisation just sets up the vars used.
        """
        super().__init__(childdefs=camstreamvardefs, **kwargs)
        self.log(logging.INFO, 'camstream activity set up')
        self.condition=None

    def getStream(self):
        """
        When we get a stream request, check if already running and if not start everything up and return self.
        
        This is called by an http handler request thread.
        
        THE HTTP thread (there can be several) then loops calling nextframe
        
        Note that start_recording internally runs a thread that will call write as each frame arrives.
        
        This also starts a thread to monitor activity. Once all running streams have stopped, we call stop_recording and release resoources
        
        The thread will also exit at this point
        """
        if self.condition==None:
            self.condition = threading.Condition()
            self.buffer = io.BytesIO()
            self.lastactive=time.time()
            self.splitter_port=self.app._getSplitterPort(self.name)
            resize=(self['width'].getValue(), self['height'].getValue())
            self.log(logging.INFO, 'camera streaming using port %d and resize to %d / %d' % (self.splitter_port, resize[0], resize[1]))
            self.picam=self.app.startCamera()
            self.monthread=threading.Thread(name=self.name, target=self.monitor)
            self.picam.start_recording(self, format='mjpeg', splitter_port=self.splitter_port, resize=resize)
            self.monthread.start()
            self.log(10,'live streaming starts')
        return self

    def write(self, buf):
        """
        called by the camera software from its own thread.
        
        record the next frame and notify all those waiting
        """
        if self['status'].getIndex() == 0:
            self.log(10,'streamer raising StopIteration')
            raise StopIteration()
        if buf.startswith(b'\xff\xd8'):
            # New frame, copy the existing buffer's content and notify all clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)

    def nextframe(self):
        """
        The http handler thread(s) calls this to get each successive frame.
        
        It waits for a new frame to arrive, then updates the lastactive timestamp and returns the frame
        """
        with self.condition:
            self.condition.wait()
            self.lastactive=time.time()
        return self.frame, 'image/jpeg', len(self.frame)

    def monitor(self):
        self['status'].setIndex(1, 'driver')
        self['lastactive'].setValue(time.time(), 'driver')
        while self.lastactive+5 > time.time():
            self.picam.wait_recording(1.7, splitter_port=self.splitter_port)
            self.log(10, 'last active %4.1f seconds ago' % (time.time()-self.lastactive))
        self.monthread=None
        self.picam.stop_recording(splitter_port=self.splitter_port)
        self.log(10, 'camstream recording stopped')
        self.app._releaseSplitterPort(self.name, self.splitter_port)
        self.log(10, 'splitter port released')
        self['status'].setIndex(0, 'driver')
        self['lastactive'].setValue(time.time(), 'driver')
        self.condition = None
        self.buffer = None