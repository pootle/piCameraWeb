#!/usr/bin/python3
"""
Module to generate a stream of mjpeg images(once) within a piCamHandler environment
"""
import io, threading

import papps
import piCamHtml as pchtml
from piCamSplitter import camSplitterAct

class liveVidStream(camSplitterAct, papps.appActivity):
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
    (pchtml.htmlStartedTimeStamp, {'shelp': 'last time this view was started'}),
    (pchtml.htmlStoppedTimeStamp, {'shelp': 'last time this view stopped'}),
)
