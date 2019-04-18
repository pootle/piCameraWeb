#!/usr/bin/python3
"""
module to run video to a circular buffer and, when triggered, writes 
previous few seconds to file and keeps writing till no trigger received
for several seconds
"""
import picamera, logging, time, datetime, shutil, pathlib
from subprocess import Popen, PIPE
import queue

import papps
import piCamHtml as pchtml
from piCamSplitter import camSplitterAct

class triggeredVideo(papps.appThreadAct):
    """
    This class records video when triggered. It can run a permanent video stream to a circular buffer. When triggered#
    it then writes a video file with the previous few seconds followed by the video of the following time the trigger is active.
    
    Alternatively it will only start recording when triggered. This saves power (and where ir leds are used, a lot of power
    can be saved by using and external triggr such as a pir.
    
    Trigger recording by calling the member function trigger from any thread. This adds an entry to a simple queue, which triggers 
    recordings.
    """
    def __init__(self, **kwargs):
        self.sport=None
        self.lasttrig=0
        self.trigQ = queue.Queue()
        super().__init__(**kwargs)
        self.vars['triggercount'].setValue('app',0)

    def startedlogmsg(self):
        if self.vars['backtime'].getValue('app')>0:
            return 'triggeredVideo wiith circular buffer using forward {} and back {}'.format(
                    str(self.vars['forwardtime'].getValue('app')),
                    str(self.vars['backtime'].getValue('app')))
        else:
            return 'triggeredVideo record on trigger using forward {}'.format(str(self.vars['forwardtime'].getValue('app')))

    def endedlogmsg(self):
        return 'triggeredVideo ends, {} video files recorded'.format(str(self.vars['triggercount'].getValue('app')))

    def trigger(self):
        """
        called to trigger a video - restricts trigger q entries to 1 to 1 per second
        """
        ttime=time.time()
        if ttime > self.lasttrig+1:
            try:
                self.trigQ.put(time.time())
            except queue.Full:
                pass
            self.lasttrig=ttime

    def ondemandrun(self):
        while self.requstate != 'stop' and self.vars['backtime'].getValue('app') == 0:
            try:
                trigtime=self.trigQ.get(block=True, timeout=5)
                record=True
            except queue.Empty:
                record=False
            if record:
                tnow=datetime.datetime.now()
                self.sPort=self.parent._getSplitterPort(self)
                if self.sPort is None:
                    if self.log is None:
                        print('ARgh no free splitter ports')
                    else:
                        self.log.critical('Failed to get splitter port')
                    self.requstate='stop'
                else:
                    picam=self.parent.startCamera()
                    self.updateState('recording')
                    tfile=(pathlib.Path(self.vars['basefolder'].getValue('app')).expanduser()/tnow.strftime(self.vars['file'].getValue('app'))).with_suffix('.mp4')
                    tfile.parent.mkdir(parents=True, exist_ok=True)
                    afile=(tfile.parent/(tfile.stem+'only')).with_suffix('.h264')
                    rs=self.vars['resize'].getValue('app')
                    picam.start_recording(str(afile), resize=rs, splitter_port=self.sPort, format='h264', sps_timing=True)
                    self.vars['triggercount'].setValue('app',self.vars['triggercount'].getValue('app')+1)
                    self.vars['lasttrigger'].setValue('app', time.time())
                    while self.requstate=='run' and trigtime+self.vars['forwardtime'].getValue('app') > time.time():
                        while not self.trigQ.empty():
                            try:
                                 trigtime=self.trigQ.get(block=False)
                            except queue.Empty:
                                 pass
                        try:
                            trigtime=self.trigQ.get(block=True, timeout=1)
                        except queue.Empty:
                            pass
                        picam.wait_recording(splitter_port=self.sPort)
                    if self.loglvl <= logging.DEBUG:
                        lstr='recording to {}'.format(str(tfile))
                        self.log.debug(lstr)
                    picam.stop_recording(splitter_port=self.sPort)
                    cmd=['MP4Box', '-quiet', '-add', str(afile), str(tfile)]
                    if self.loglvl <= logging.DEBUG:
                        self.log.debug('mp4 save using >{}<'.format(cmd))
                    subp=Popen(cmd, universal_newlines=True, stdout=PIPE, stderr=PIPE)
                    outs, errs = subp.communicate(timeout=15)
                    rcode=subp.returncode
                    if rcode==0:
                        shutil.copystat(str(afile), str(tfile))
                        if self.vars['saveX264'].getValue('app')=='OFF':
                            afile.unlink()
                    if rcode != 0 and not errs is None:
                        if self.loglvl<=logging.WARN:
                            self.log.warn('MP4Box stderr:'+str(errs))
                        else:
                            print('MP4Box stderr:')
                            print('   ', errs)
                    self.parent._releaseSplitterPort(self, self.sPort)
                    self.updateState('run')

    def circbuffrun(self):
        self.sPort=self.parent._getSplitterPort(self)
        if self.sPort is None:
            if self.log is None:
                print('ARgh no free splitter ports')
            else:
                self.log.critical('Failed to get splitter port')
            self.requstate='stop'
            print('abandoned circbuffrun')
            return
        picam=self.parent.startCamera()
        rs=self.vars['resize'].getValue('app')
        circstream=picamera.PiCameraCircularIO(picam, seconds=self.vars['backtime'].getValue('app')+1, splitter_port=self.sPort)
        picam.start_recording(circstream, resize=rs, splitter_port=self.sPort, format='h264', sps_timing=True)
        if self.loglvl <=logging.INFO:
            self.log.info("start_recording with size {}".format(str(rs)))            
        while self.requstate != 'stop' and self.vars['backtime'].getValue('app') > 0:
            try:
                trigtime=self.trigQ.get(block=True, timeout=5)
                record=True
            except queue.Empty:
                record=False
                picam.wait_recording(splitter_port=self.sPort)
            if record:
                self.updateState('recording')
                self.vars['triggercount'].setValue('app',self.vars['triggercount'].getValue('app')+1)
                self.vars['lasttrigger'].setValue('app', time.time())
                tnow=datetime.datetime.now()
                tfile=(pathlib.Path(self.vars['basefolder'].getValue('app')).expanduser()/tnow.strftime(self.vars['file'].getValue('app'))).with_suffix('.mp4')
                tfile.parent.mkdir(parents=True, exist_ok=True)
                afile=(tfile.parent/(tfile.stem+'after')).with_suffix('.h264')
                bfile=(tfile.parent/(tfile.stem+'before')).with_suffix('.h264')
                picam.split_recording(str(afile), splitter_port=self.sPort)
                circstream.copy_to(str(bfile), seconds=self.vars['backtime'].getValue('app'))
                circstream.clear()
                while self.requstate=='run' and trigtime+self.vars['forwardtime'].getValue('app') > time.time():
                    while not self.trigQ.empty():
                        try:
                             trigtime=self.trigQ.get(block=False)
                        except queue.Empty:
                             pass
                    try:
                        trigtime=self.trigQ.get(block=True, timeout=1)
                    except queue.Empty:
                        pass
                    picam.wait_recording(splitter_port=self.sPort)
                if self.loglvl <= logging.DEBUG:
                    lstr='recording to {}, pre-time: {}, post time {}. started at {}, prefile size {}'.format(str(tfile), 
                                        self.vars['backtime'].getValue('app'), self.vars['forwardtime'].getValue('app'),tnow.strftime('HH:MM:SS'), bfile.stat().st_size)
                    self.log.debug(lstr)
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
                if rcode==0:
                    shutil.copystat(str(bfile), str(tfile))
                    if self.vars['saveX264'].getValue('app')=='OFF':
                        afile.unlink()
                        bfile.unlink()                    
                if rcode != 0 and not errs is None:
                    if self.loglvl<=logging.WARN:
                        self.log.warn('MP4Box stderr:'+str(errs))
                    else:
                        print('MP4Box stderr:')
                        print('   ', errs)
                self.updateState('run')
        picam.stop_recording(splitter_port=self.sPort)
        time.sleep(.1)
        self.parent._releaseSplitterPort(self, self.sPort)

    def innerrun(self):
        self.startDeclare()
        while self.requstate != 'stop':
            if self.vars['backtime'].getValue('app')==0:
                self.ondemandrun()
            else:
                self.circbuffrun()
        self.endDeclare()

############################################################################################
# group / table for tripped video recording
############################################################################################
EMPTYDICT={}
tripvidtable=(
    (pchtml.htmlStatus  , pchtml.HTMLSTATUSSTRING),

    (pchtml.htmlAutoStart, EMPTYDICT),

    (pchtml.htmlCyclicButton, {
            'name': 'triggernow',  'fallbackValue': 'trigger', 'alist': ('trigger', 'trigger '),
            'onChange'  : ('dynamicUpdate','user'),
            'label':'trigger now', 
            'shelp':'trigger a recording now',
    }),

    (pchtml.htmlStreamSize, EMPTYDICT),

    (pchtml.htmlFloat, {
            'readersOn': ('app', 'pers', 'html'),
            'writersOn': ('app', 'pers', 'user'),
            'name': 'backtime',  'minv':0, 'maxv':15, 'clength':4, 'formatString':'{value:2.2f}', 'fallbackValue':1,
            'label':'pre-trigger record time', 
            'shelp':'number of seconds before trigger to include in video',
    }),
    (pchtml.htmlFloat, {
            'readersOn': ('app', 'pers', 'html'),
            'writersOn': ('app', 'pers', 'user'),
            'name' : 'forwardtime',  'minv':0, 'maxv':15, 'clength':4, 'formatString':'{value:2.2f}', 'fallbackValue':1,
            'label':'post-trigger record time', 
            'shelp':'number of seconds after trigger ends to include in video',
    }),
    (pchtml.htmlString, {
            'name': 'basefolder',
            'readersOn' : ('app', 'pers', 'html', 'webv'),
            'writersOn' : ('app', 'pers'),
            'fallbackValue': '~/movevids', 'clength':15,
            'label'     : 'video folder',
            'shelp'     : 'base folder for recorded videos'            
    }),
#    (pchtml.htmlFolder, {#'loglvl':logging.DEBUG,
#            'readersOn': ('app', 'pers', 'html'),
#            'writersOn': ('app', 'pers', 'user'),    
#            'name' : 'basefolder', 'fallbackValue': '~/movevids',
#            'label': 'video folder',
#            'shelp': 'base folder for saved video files'}),
    (pchtml.htmlString, {
            'readersOn': ('app', 'pers', 'html'),
            'writersOn': ('app', 'pers', 'user'),    
            'name' : 'file', 'fallbackValue': '%y/%m/%d/%H_%M_%S', 'clength':15,
            'label': 'filename',
            'shelp': 'filename with date-time compenents', 'shelp': 'extends the basefolder to define the filename for recorded videos.'}),

    (pchtml.htmlChoice, {
            'name': 'saveX264', 'vlists': ('OFF', 'ON'), 'fallbackValue': 'OFF',    
            'readersOn' : ('app', 'pers', 'html'),
            'writersOn' : ('app', 'pers', 'user'),
            'label'     : 'save raw video',
            'shelp'     : 'When on the raw video (X264) files are not deleted after final mp4 file created'}),

    (pchtml.htmlCyclicButton, {
            'name': 'run',  'fallbackValue': 'start now', 'alist': ('start now', 'stop now '),
            'onChange'  : ('dynamicUpdate','user'),
            'label':'start recording', 
            'shelp':'starts recording to circular buffer, ready for trigger',
    }),
    (pchtml.htmlInt,        {
            'name' : 'triggercount', 'fallbackValue': 0,
            'readersOn' : ('html', 'app', 'webv'),
            'writersOn' : ('app', 'pers'),
            'onChange': ('dynamicUpdate','app'),
            'label': 'recordings',
            'shelp': 'number of recorded videos this session'}),
    (pchtml.htmlTimestamp, {'name': 'lasttrigger', 'fallbackValue':0,
            'strft': '%H:%M:%S' , 'unset':'never',
            'onChange': ('dynamicUpdate','app'),
            'label': 'last trigger time',
            'shelp': 'time last triggered occurred'}),

    (pchtml.htmlStartedTimeStamp, EMPTYDICT),
    (pchtml.htmlStoppedTimeStamp, EMPTYDICT),

)
