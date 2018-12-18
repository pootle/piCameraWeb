#!/usr/bin/python3
"""
Module to generate a stream of mjpeg images(once) within a piCamHandler environment
"""
import io, threading

import papps
import piCamHtml as pchtml

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

############################################################################################
# group / table for live stream - mjpeg
############################################################################################

livestreamtable=(
    (pchtml.htmlStatus  , pchtml.HTMLSTATUSSTRING),
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
