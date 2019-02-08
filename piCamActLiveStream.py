#!/usr/bin/python3
"""
Module to generate a stream of mjpeg images(once) within a piCamHandler environment
"""
import io, threading, logging

import papps
import piCamHtml as pchtml
from piCamSplitter import camSplitterAct

class liveVidStream(camSplitterAct, papps.appThreadAct):

    def __init__(self, **kwargs):
        self.streambuff=StreamingOutput()
        self.streambuff.actback=self
        super().__init__(**kwargs)

    def innerrun(self):
        self.startDeclare()
        self.parent.picam.start_recording(self.streambuff,
                    format='mjpeg',
                    splitter_port=self.sPort, 
                    resize=self.vars['resize'].getValue('app'))
        while self.requstate != 'stop':
            self.parent.picam.wait_recording(.7, splitter_port=self.sPort)
        if self.loglvl <= logging.INFO:
            self.log.info('calling stop recording')
        self.parent.picam.stop_recording(splitter_port=self.sPort)
        if self.loglvl <= logging.INFO:
            self.log.info('returned from stop recording')
        self.endDeclare()

    def endedlogmsg(self):
        return super().endedlogmsg() + '\n        onepartbuffercount: {:d}, multipartbuffercount: {:d}'.format(
                self.streambuff.oneshotbuffs, self.streambuff.multishotbuffs)
        

class xliveVidStream(camSplitterAct, papps.appActivity):
    def start(self):
        self.startDeclare()
        self.streambuff=StreamingOutput()
        self.streambuff.actback=self
        self.parent.picam.start_recording(self.streambuff,
                    format='mjpeg',
                    splitter_port=self.sPort, 
                    resize=self.vars['resize'].getValue('app'))

    def requestFinish(self):
        self.requstate='stop'
        if self.loglvl <= logging.INFO:
            self.log.info('calling stop recording')
        self.parent.picam.stop_recording(splitter_port=self.sPort)
        if self.loglvl <= logging.INFO:
            self.log.info('returned from stop recording')
        self.endDeclare()

    def endedlogmsg(self):
        return super().endedlogmsg() + '\n        onepartbuffercount: {:d}, multipartbuffercount: {:d}'.format(
                self.streambuff.oneshotbuffs, self.streambuff.multishotbuffs)
        

class StreamingOutput():
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = threading.Condition()
        self.bufbits=0
        self.oneshotbuffs=0
        self.multishotbuffs=0

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            # New frame, copy the existing buffer's content and notify all
            # clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
            if self.bufbits==1:
                self.oneshotbuffs+=1
            else:
                self.multishotbuffs+=1
            self.bufbits=1
        else:
            self.bufbits+=1
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
