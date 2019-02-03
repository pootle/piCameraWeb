#!/usr/bin/python3
"""
module to run video to a circular buffer and, when triggered, writes 
previous few seconds to file and keeps writing till no trigger received
for several seconds
"""
import picamera, logging, time, datetime, shutil, pathlib
from subprocess import Popen, PIPE

import papps
import piCamHtml as pchtml
from piCamSplitter import camSplitterAct

class triggeredVideo(camSplitterAct, papps.appThreadAct):
    """
    This class runs a permanent video stream to a circular buffer. When triggered it then writes a video file with the previous
    few seconds followed by the video of the following time the trigger is active.
    
    Trigger recording by calling the member function trigger from any thread
    """
    def __init__(self, **kwargs):
        self.lasttrigger=0
        super().__init__(**kwargs)
        self.vars['triggercount'].setValue('app',0)

    def startedlogmsg(self):
        return 'triggeredVideo using forward {} and back {}'.format(str(self.vars['forwardtime'].getValue('app')),
                                                                    str(self.vars['backtime'].getValue('app')))

    def endedlogmsg(self):
        return 'triggeredVideo ends, {} video files recorded'.format(str(self.vars['triggercount'].getValue('app')))

    def trigger(self):
        self.lasttrigger=time.time()

    def innerrun(self):
        self.startDeclare()
        picam=self.parent.picam
        rs=self.vars['resize'].getValue('app')
        circstream=picamera.PiCameraCircularIO(picam, seconds=self.vars['backtime'].getValue('app')+1, splitter_port=self.sPort)
        picam.start_recording(circstream, resize=rs, splitter_port=self.sPort, format='h264', sps_timing=True)
        if self.loglvl <=logging.INFO:
            self.log.info("start_recording with size {}".format(str(rs)))            
        while self.requstate != 'stop':
            picam.wait_recording(.3, splitter_port=self.sPort)
            if self.lasttrigger+self.vars['forwardtime'].getValue('app')>time.time():
                self.updateState('recording')
#                self.summarystate='recording'
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
                if self.loglvl <= logging.DEBUG:
                    lstr='recording to {}, pre-time: {}, post time {}.'.format(str(tfile), 
                                                    self.vars['backtime'].getValue('app'), self.vars['forwardtime'].getValue('app'))
                    self.log.debug(lstr)
                while self.requstate=='run' and self.lasttrigger+self.vars['forwardtime'].getValue('app') > time.time():
                    picam.wait_recording(.5, splitter_port=self.sPort)
                if self.loglvl <= logging.DEBUG:
                    self.log.debug('done recording')
#                self.summaryState='waiting'
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
                if False:
#                if rcode ==0:
                    shutil.copystat(str(bfile), str(tfile))
                    afile.unlink()
                    bfile.unlink()                    
                if rcode != 0 and not errs is None:
                    print('MP4Box stderr:')
                    print('   ', errs)
                self.updateState('run')
        picam.stop_recording(splitter_port=self.sPort)
#        self.summaryState='closing'
        self.endDeclare()

############################################################################################
# group / table for tripped video recording
############################################################################################
EMPTYDICT={}
tripvidtable=(
    (pchtml.htmlStatus  , pchtml.HTMLSTATUSSTRING),

    (pchtml.htmlAutoStart, EMPTYDICT),

    (pchtml.htmlStreamSize, EMPTYDICT),

    (pchtml.htmlFloat, {
            'readersOn': ('app', 'pers', 'html'),
            'writersOn': ('app', 'pers', 'user'),
            'name': 'backtime',  'minv':0, 'maxv':15, 'clength':4, 'numstr':'{:2.2f}', 'fallbackValue':1,
            'label':'pre-trigger record time', 
            'shelp':'number of seconds before trigger to include in video',
    }),
    (pchtml.htmlFloat, {
            'readersOn': ('app', 'pers', 'html'),
            'writersOn': ('app', 'pers', 'user'),
            'name' : 'forwardtime',  'minv':0, 'maxv':15, 'clength':4, 'numstr':'{:2.2f}', 'fallbackValue':1,
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

    (pchtml.htmlCyclicButton, {'loglvl':logging.DEBUG,
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
