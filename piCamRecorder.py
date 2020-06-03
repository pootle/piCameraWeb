#!/usr/bin/python3
"""
This module enables videos to be recorded in response to several triggers. It can save video from a few seconds before the trigger
to several seconds after the trigger.
"""
from pootlestuff import watchables as wv

import threading, queue, time, picamera, shutil
from subprocess import Popen, PIPE

class VideoRecorder(wv.watchableAct):
    def __init__(self, app, **kwargs):
        """
        initialisation just sets up the vars used.
        """
        self.monthread=None
        self.procthread=None
        self.actionq=queue.Queue()
        self.withsps=True
        self.activetriggers={}
        self.activetriglock=threading.Lock()
        super().__init__(app=app, wabledefs=(
            ('status',      wv.enumWatch,       'off',              False,      {'vlist': ('off', 'waiting', 'recording')}),
            ('rec_width',   wv.intWatch,       640,                 True,       {'minv': 120, 'maxv': 2400}),
            ('rec_height',  wv.intWatch,       480,                 True,       {'minv': 90, 'maxv': 1600}),
            ('lastactive',  wv.floatWatch,     float('nan'),        False,      {}),
            ('autostart',   wv.enumWatch,      'off',               True,       {'vlist': ('off', 'on')}),
            ('startstopbtn',wv.enumWatch,      'start waiting',     False,      {'vlist':('start waiting', 'stop waiting')}),
            ('format',      wv.enumWatch,      'h264',              True,       {'vlist': ('h264', 'mjpeg', 'yuv', 'rgb')}),
            ('recordcount', wv.intWatch,        0,                  False,      {},),
            ('lasttrigger', wv.floatWatch,      float('nan'),       False,      {}),
            ('recordnow',   wv.enumWatch,       'start recording',  False,      {'vlist': ('start recording', 'stop recording')}),
            ('cpudetect',   wv.enumWatch,       'off',              True,       {'vlist': ('off', 'on'), 'flags': wv.wflags.NONE if 'cpumove' in app.activities else wv.wflags.DISABLED}),
            ('gpiodetect',  wv.enumWatch,       'off',              True,       {'vlist': ('off', 'on'), 'flags': wv.wflags.NONE if 'triggergpio' in app.activities else wv.wflags.DISABLED}),
            ('saveh264',    wv.enumWatch,       'off',              True,       {'vlist': ('off', 'on')}),
            ('splitrecord', wv.floatWatch,      0,                  True,       {'minv': 0, 'maxv': 30}),
            ('maxvidlength',wv.intWatch,        1,                  True,       {'minv': 1}),
            ('recordback',  wv.floatWatch,      0,                  True,       {'minv': 0, 'maxv': 8}),
            ('recordfwd',   wv.floatWatch,      0,                  True,       {'minv': 0, 'maxv': 30}),
            ('vidfold',     wv.folderWatch,     '~/camfiles/videos',True,       {}),
            ('vidfile',     wv.textWatch,       '%y/%m/%d/%H_%M_%S',True,       {}),
            ),
            **kwargs)
        if self.autostart.getIndex()==1:
            self.startstopbtn.setIndex(1,wv.myagents.app)
            self.running=True
            self.monthread=threading.Thread(name=type(self).__name__, target=self.monitor, kwargs={'startdelay':2.5})
            self.monthread.start()
        self.startstopbtn.addNotify(self.do_startstop, wv.myagents.user)
        self.cpudetect.addNotify(self.trigsetchange, wv.myagents.user)
        self.gpiodetect.addNotify(self.trigsetchange, wv.myagents.user)
        self.log(wv.loglvls.INFO, 'video record activity set up')

    def do_startstop(self, watched, agent, newValue, oldValue):
        startrequ=watched.getIndex()==1
        if self.monthread==None and startrequ:
            self.running=True
            self.monthread=threading.Thread(name='video_record', target=self.monitor)
            self.monthread.start()
        elif not self.monthread == None and not startrequ:
            self.running=False

    def stopme(self):
        self.running=False

    def makefilename(self):
        """
        picks up the folder and file info and returns filepath
        """
        fp= (self.vidfold.getFolder()/(time.strftime(self.vidfile.getValue()))).with_suffix('')
        fp.parent.mkdir(parents=True, exist_ok=True)
        return fp

    def trigsetchange(self, watched, agent, newValue, oldValue):
        """
        called if the user changes a 'use xxx detection' setting
        """
        if self.status.getIndex() != 1:
            if watched == self.cpudetect:
                target=self.app.activities['cpumove'].status
                if watched.getIndex()==1:
                    self.settrigger(target, lambda wable : wable.getIndex() == 2)
                else:
                    self.cleartrigger(target)
            elif watched==self.gpiodetect:
                target=self.app.activities['triggergpio'].status
                if watched.getIndex()==1:
                    self.settrigger(target, lambda wable : wable.getIndex() == 2)
                else:
                    self.cleartrigger(target)

    def settrigger(self, wable, onexp):
        """
        adds a variable to watch to the set of triggers.
        
        wable :   the watchable to watch
        
        onexp   :   function that returns True if triggered
        """
        with self.activetriglock:
            if not wable in self.activetriggers:
                self.activetriggers[wable] = (wable, onexp)
                for agent in wv.myagents:
                    wable.addNotify(self.triggerevent, agent)

    def cleartrigger(self, wable):
        if wable=='*':
            for trigid in list(self.activetriggers.keys()):
                self.cleartrigger(trigid)
        else:
            with self.activetriglock:
                if wable in self.activetriggers:
                    awab, _ = self.activetriggers.pop(wable)
                    for agent in wv.myagents:
                        awab.dropNotify(self.triggerevent, agent)
                else:
                    self.log(wv.loglvls.WARN, 'attempt to remove absent video record trigger {}'.format(tvfull)) 

    def triggerevent(self, watched, agent, newValue, oldValue):
        varx, func = self.activetriggers.get(watched, (None, None))
        if not func is None and func(varx):
            self.actionq.put(0)

    def monitor(self, startdelay=0):
        if startdelay > 0:
            time.sleep(startdelay)
        self.status.setIndex(1, wv.myagents.app)  # waiting
        self.lastactive.setValue(time.time(), wv.myagents.app)
        picam=self.app.startCamera()
        splitter_port=self.app._getSplitterPort(self)
        
        resize=[self.rec_width.getValue(), self.rec_height.getValue()]
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
        self.log(wv.loglvls.INFO, 'triggered video using port %d and resize to %d / %d' % (splitter_port, dsize[0], dsize[1]))
        pretime=self.recordback.getValue()
        if pretime > 0:
            circstream=picamera.PiCameraCircularIO(picam, seconds=pretime+1, splitter_port=splitter_port)
            picam.start_recording(circstream, format='h264', sps_timing=self.withsps, resize=resize, splitter_port=splitter_port)
            recorder='circ'
        else:
            recorder='none'
            circstream=None
        self.settrigger(self.recordnow, lambda wable : wable.getIndex() == 1 )
        if self.cpudetect.getIndex()==1:
            self.settrigger(self.app.activities['cpumove'].status, lambda wable : wable.getIndex() == 2)
        if self.gpiodetect.getIndex()==1:
            self.settrigger(self.app.activities['triggergpio'].status, lambda wable : wable.getIndex() == 2)
        time.sleep(.1)
        aftertimeout=None
        while self.running:
            try:
                x = self.actionq.get(True,2)
            except queue.Empty:
                pass
            for trigid, bits in self.activetriggers.items():
                if bits[1](bits[0]):
                    trig=True # set trig if any active trigger set
                    break
            else:
                trig=False
            if trig:
                aftertimeout=None  # reset aftertimeout so it restarts when trigger stops
                if recorder=='circ':
                    #switch to file
                    fpath=self.makefilename()
                    recordingstart=time.time()
                    recordingsequ=1
                    vformat='.'+self.format.getValue()
                    postpath=fpath.with_name(fpath.name+'%03d' % recordingsequ).with_suffix(vformat)
                    self.log(wv.loglvls.DEBUG, '>>>>>>>>>>>>>>>>>    trig split recording to %s' % postpath)
                    picam.split_recording(str(postpath), splitter_port=splitter_port)
                    prepath=fpath.with_name(fpath.name+'%03d' % 0).with_suffix(vformat)
                    circstream.copy_to(str(prepath), seconds=self['recordback'].getValue())
                    self.processfiles((True, prepath))
                    circstream.clear()
                    recorder='afile'
                    self.recordcount.increment(agent = wv.myagents.app)
                    self.lasttrigger.setValue(time.time(), wv.myagents.app)
                    self.status.setIndex(2, wv.myagents.app) # recording
                elif recorder=='none':
                    # start recording to file
                    fpath=self.makefilename()
                    prepath=None
                    postpath=fpath.with_name(fpath.name+'%03d' % 0).with_suffix('.'+self.format.getValue())
                    self.log(wv.loglvls.DEBUG, '>>>>>>>>>>>>>>>>>trig start recording to file %s' % postpath)
                    picam.start_recording(str(postpath), resize=resize, sps_timing=self.withsps,splitter_port=splitter_port)
                    recordingstart=time.time()
                    recordingsequ=0
                    recorder='afile'
                    self.recordcount.increment(agent = wv.myagents.app)
                    self.lasttrigger.setValue(time.time(), wv.myagents.app)
                    self.status.setIndex(2, wv.myagents.app) # recording
                else:
                    # already recording to file - carry on
                    picam.wait_recording(splitter_port=splitter_port) # carry on recording - check for split recording file
                    if self.splitrecord.getValue() > 0.01:
                        splitsecs= round(self.splitrecord.getValue()*60)
                        if time.time() > recordingstart + splitsecs:
                            vformat='.'+self.format.getValue()
                            postpath=fpath.with_name(fpath.name+'%03d' % (recordingsequ+1)).with_suffix(vformat)
                            picam.split_recording(str(postpath), splitter_port=splitter_port)
                            if vformat =='.h264':
                                self.processfiles((True, fpath.with_name(fpath.name+'%03d' % recordingsequ).with_suffix(vformat)))
                            recordingsequ += 1
                            recordingstart=time.time()
                            self.log(wv.loglvls.DEBUG, '>>>>>>>>>>>>>>>>>trig split recording and continue')
                    else:
                        self.log(wv.loglvls.DEBUG, '>>>>>>>>>>>>>>>>>trig check and continue')
            else: # no triggers present (now) - what were we doing?
                if recorder=='circ':
                    if self.recordback.getValue()==0: # no re-trigger time now so close that down
                        self.log(wv.loglvls.DEBUG, '>>>>>>>>>>>>>>>>>not trig stop circ recorder')
                        picam.stop_recording(splitter_port=splitter_port)
                        circstream=None
                        recorder=None
                    else:
                        self.log(wv.loglvls.DEBUG, '>>>>>>>>>>>>>>>>>not trig circ check and continue')
                        picam.wait_recording(splitter_port=splitter_port) # carry on recording to circ buff
                elif recorder=='none':
                    if self.recordback.getValue()> 0: # turn on circ buffer record
                        self.log(wv.loglvls.DEBUG, '>>>>>>>>>>>>>>>>>not trig start circ recording')
                        circstream=picamera.PiCameraCircularIO(picam, seconds=pretime+1, splitter_port=splitter_port)
                        picam.start_recording(circstream, resize=resize, format='.'+self.format.getValue(), sps_timing=self.withsps, splitter_port=splitter_port)
                        recorder='circ'
                    else:
                        self.log(wv.loglvls.DEBUG, '>>>>>>>>>>>>>>>>>not trig carry on not recording')
                        pass # nothing to do here
                else: # we're recording to file
                    if aftertimeout is None:
                        self.log(wv.loglvls.DEBUG, '>>>>>>>>>>>>>>>>>not trig start post record timeout')
                        aftertimeout = time.time() + self.recordfwd.getValue()
                    elif time.time() < aftertimeout: # waiting for post trigger timeout
                        self.log(wv.loglvls.DEBUG, '>>>>>>>>>>>>>>>>>not trig and waiting for timeout - carry on')
                    else: # were done now - go back to waiting state
                        pretime=self.recordback.getValue()
                        if pretime > 0:
                            if circstream is None:
                                self.log(wv.loglvls.DEBUG, '>>>>>>>>>>>>>>>>>not trig split recording to circ buffer - making circ buffer')
                                circstream=picamera.PiCameraCircularIO(picam, seconds=pretime+1, splitter_port=splitter_port)
                            else:
                                self.log(wv.loglvls.DEBUG, '>>>>>>>>>>>>>>>>>not trig split recording to circ buffer - re-use circ buffer')
                            picam.split_recording(circstream, splitter_port=splitter_port)
                            recorder='circ'
                        else:
                            picam.stop_recording(splitter_port=splitter_port)
                            circstream = None
                            self.log(wv.loglvls.DEBUG, '>>>>>>>>>>>>>>>>>not trig stop recording')
                            recorder='none'
                        self.status.setIndex(1, wv.myagents.app)
                        if self.format.getValue() == 'h264':
                            self.processfiles((False, fpath.with_name(fpath.name+'%03d' % recordingsequ).with_suffix('.h264')))
        if recorder=='circ':
            picam.stop_recording(splitter_port=splitter_port)
            circstream=None
            recorder='none'
        elif recorder=='afile': # we're recording to file
            picam.stop_recording(splitter_port=splitter_port)
            circstream = None
            recorder='none'
            self.log(wv.loglvls.DEBUG, '>>>>>>>>>>>>>>>>>final stop recording')
            if self.format.getValue() == 'h264':
                self.processfiles((False, fpath.with_name(fpath.name+'%03d' % recordingsequ).with_suffix('.h264')))
        if not self.procthread is None:
            self.procqueue.put('stop')
        self.app._releaseSplitterPort(self, splitter_port)
        self.status.setIndex(0, wv.myagents.app)
        self.lastactive.setValue(time.time(), wv.myagents.app)
        self.cleartrigger('*')
        self.monthread=None

    def processfiles(self, data):
        print('processfiles requests', data)
        if self.procthread is None:
            self.procqueue=queue.Queue()
            self.procthread=threading.Thread(name='video_record', target=self.fileprocessor, kwargs={'q': self.procqueue})
            self.procthread.start()
        self.procqueue.put(data)

    def fileprocessor(self, q):
        nextact=q.get()
        while nextact != 'stop':
            print('==================', nextact)
            flist=[]
            more, fpath=nextact
            while more:
                if fpath.exists:
                    if  fpath.stat().st_size > 0:
                        flist.append(fpath)
                        if self.maxvidlength.getValue() > 0 and len(flist) >=self.maxvidlength.getValue():
                            self.processvid(flist)
                            flist=[]
                    else:
                        fpath.unlink()
                else:
                    print('file processor oops A', fpath)
                more, fpath = q.get()
            if fpath.exists():
                if  fpath.stat().st_size > 0:
                    flist.append(fpath)
                else:
                    fpath.unlink()
            else:
                print('file processor oops B', fpath)
            self.processvid(flist)
            nextact=q.get()
        print('===============fileprocessor exits')

    def processvid(self, flist):
        if len(flist) > 0:
            cmd=['MP4Box', '-quiet', '-add', str(flist[0] )]
            for fpath in flist[1:]:
                cmd.append('-cat')
                cmd.append(str(fpath))
            outfile=flist[0].with_suffix('.mp4')
            cmd.append(str(outfile))
            print(cmd)
            subp=Popen(cmd, universal_newlines=True, stdout=PIPE, stderr=PIPE)
            outs, errs = subp.communicate()
            rcode=subp.returncode
            if rcode==0:
                self.log(wv.loglvls.INFO, 'recording postprocessing done for %s'% str(outfile))
                shutil.copystat(str(flist[0]), str(outfile))
                if self.saveh264.getIndex()==0:
                    for f in flist:
                        f.unlink()
            else:
                if errs is None:
                    self.log(wv.loglvls.WARN, 'MP4Box error - code %s' % rcode)
                    print('MP4Box error - code %s' % rcode)
                else:
                    self.log(wv.loglvls.WARN, 'MP4Box stderr:'+str(errs))
                    print('MP4Box stderr:'+str(errs))            
