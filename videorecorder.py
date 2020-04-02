#!/usr/bin/python3
"""
This module enables videos to be recorded in response to several triggers. It can save video from a few seconds before the trigger
to several seconds after the trigger.
"""
from pootlestuff import pvars

import threading, queue, time, logging, picamera, shutil
from subprocess import Popen, PIPE

videovardefs=( # these are all the var's used by the videorecorder
    {'name': 'status',      '_cclass': pvars.enumVar,       'fallbackValue': 'stopped','vlist': ('stopped', 'waiting', 'recording')},
    {'name': 'startstop',   '_cclass': pvars.enumVar,       'fallbackValue': 'start', 'vlist': ('start', 'stop')},
    {'name': 'autostart',   '_cclass': pvars.enumVar,       'fallbackValue': 'off', 'vlist':('off', 'on'), 'filters': ['pers']},
    {'name': 'width',       '_cclass': pvars.intVar,        'fallbackValue': 640, 'minv': 240, 'maxv': 2000},
    {'name': 'height',      '_cclass': pvars.intVar,        'fallbackValue': 480, 'minv': 180, 'maxv': 2000},
    {'name': 'recordcount', '_cclass': pvars.intVar,        'fallbackValue': 0},
    {'name': 'lastactive',  '_cclass': pvars.floatVar,      'fallbackValue': 0},
    {'name': 'lasttrigger', '_cclass': pvars.floatVar,      'fallbackValue': 0},
    {'name': 'recordnow',   '_cclass': pvars.enumVar,       'fallbackValue': 'start', 'vlist': ('start', 'stop')},
    {'name': 'cpudetect',   '_cclass': pvars.enumVar,       'fallbackValue': 'off', 'vlist': ('off', 'on'), 'filters': ['pers']},
    {'name': 'gpiodetect',  '_cclass': pvars.enumVar,       'fallbackValue': 'off', 'vlist': ('off', 'on'), 'filters': ['pers']},
    {'name': 'saveX264',    '_cclass': pvars.enumVar,       'fallbackValue': 'on', 'vlist': ('off', 'on'), 'filters': ['pers']},
    {'name': 'recordback',  '_cclass': pvars.floatVar,      'fallbackValue': 0, 'minv':0, 'maxv':4, 'filters': ['pers']},
    {'name': 'recordfwd',   '_cclass': pvars.floatVar,      'fallbackValue': 0, 'minv':0, 'maxv':30, 'filters': ['pers']},
    {'name': 'vidfold',     '_cclass': pvars.folderVar,     'fallbackValue': '~/camfiles/videos', 'filters': ['pers']},
    {'name': 'vidfile',     '_cclass': pvars.textVar,       'fallbackValue': '%y/%m/%d/%H_%M_%S', 'filters': ['pers']},
)

class VideoRecorder(pvars.groupVar):
    def __init__(self, **kwargs):
        super().__init__(childdefs=videovardefs, **kwargs)
        self.monthread=None
        self.procthread=None
        self.actionq=queue.Queue()
        self.withsps=True
        self.activetriggers={}
        self.activetriglock=threading.Lock()
        if self['autostart'].getIndex()==1:
            self['startstop'].setIndex(1,'driver')
            self.running=True
            self.monthread=threading.Thread(name=self.name, target=self.monitor, kwargs={'startdelay':2.5})
            self.monthread.start()
        self['startstop'].addNotify(self.startstop, 'driver')

    def startstop(self, var, agent, newValue, oldValue):
        startrequ=var.getIndex()==1
        if self.monthread==None and startrequ:
            self.running=True
            self.monthread=threading.Thread(name=self.name, target=self.monitor)
            self.monthread.start()
        elif not self.monthread == None and not startrequ:
            self.running=False

    def stopme(self):
        self.running=False

    def makefilename(self):
        """
        picks up the folder and file info and returns filepath
        """
        fp= (self['vidfold'].getValue()/(time.strftime(self['vidfile'].getValue()))).with_suffix('')
        fp.parent.mkdir(parents=True, exist_ok=True)
        return fp

    def trigsetchange(self, var, agent, newValue, oldValue):
        """
        called if the user changes a 'use xxx detection' setting
        """
        pass
        
    def settrigger(self, varname, onexp):
        """
        adds a variable to watch to the set of triggers.
        
        varname :   name of the variable to watch
        
        onexp   :   function that returns True if triggered
        """
        trigvar=self[varname]
        tvfull=trigvar.getHierName()
        with self.activetriglock:
            if not tvfull in self.activetriggers:
                self.activetriggers[tvfull] = (trigvar, onexp)
                trigvar.addNotify(self.triggerevent, '*')

    def cleartrigger(self, varname):
        if varname=='*':
            for trigid in list(self.activetriggers.keys()):
                self.cleartrigger(trigid)
        else:
            trigvar=self[varname]
            tvfull=trigvar.getHierName()
            with self.activetriglock:
                if tvfull in self.activetriggers:
                    trigvar, _ = self.activetriggers.pop(tvfull)
                    trigvar.removeNotify(self.triggerevent, '*')
                else:
                    self.log(logging.WARN, 'attempt to remove absent video record trigger {}'.format(tvfull)) 

    def triggerevent(self, var, agent, newValue, oldValue):
        varid = var.getHierName()
        varx, func = self.activetriggers.get(var.getHierName(), (None, None))
        if not func is None and func(varx):
            self.actionq.put(0)

    def monitor(self, startdelay=0):
        if startdelay > 0:
            time.sleep(startdelay)
        self['status'].setIndex(1, 'driver')  # waiting
        self['lastactive'].setValue(time.time(), 'driver')
        print('=====================', self.app['camstate/ports'].getValue())
        picam=self.app.startCamera()
        splitter_port=self.app._getSplitterPort(self.name)
        resize=(self['width'].getValue(), self['height'].getValue())
        self.log(logging.INFO, 'triggered video using port %d and resize to %d / %d' % (splitter_port, resize[0], resize[1]))
        pretime=self['recordback'].getValue()
        if pretime > 0:
            circstream=picamera.PiCameraCircularIO(picam, seconds=pretime+1, splitter_port=splitter_port)
            picam.start_recording(circstream, format='h264', sps_timing=self.withsps, splitter_port=splitter_port)
            recorder='circ'
        else:
            recorder='none'
            circstream=None
        self.settrigger('recordnow', lambda var : var.getValue() != 'start' )
        if self['cpudetect'].getValue():
            self.settrigger('/activities/cpumove/status', lambda var : var.getIndex() > 1)
        if self['gpiodetect'].getValue():
            self.settrigger('/activities/gpio_trigger/status', lambda var : var.getIndex() > 2)
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
                    postpath=fpath.with_name(fpath.name+'post').with_suffix('.h264')
                    self.log(10, '>>>>>>>>>>>>>>>>>    trig split recording to %s' % postpath)
                    picam.split_recording(str(postpath), splitter_port=splitter_port)
                    prepath=fpath.with_name(fpath.name+'pre').with_suffix('.h264')
                    circstream.copy_to(str(prepath), seconds=self['recordback'].getValue())
                    circstream.clear()
                    recorder='afile'
                    self['recordcount'].increment(agent = 'driver')
                    self['lasttrigger'].setValue(time.time(), 'driver')
                    self['status'].setIndex(2, 'driver') # recording
                elif recorder=='none':
                    # start recording to file
                    fpath=self.makefilename()
                    prepath=None
                    postpath=fpath.with_name(fpath.name+'post').with_suffix('.h264')
                    self.log(10, '>>>>>>>>>>>>>>>>>trig start recording to file %s' % postpath)
                    picam.start_recording(str(postpath), resize=resize, sps_timing=self.withsps,splitter_port=splitter_port)
                    recorder='afile'
                    self['recordcount'].increment(agent = 'driver')
                    self['lasttrigger'].setValue(time.time(), 'driver')
                    self['status'].setIndex(2, 'driver') # recording
                else:
                    # already recodrding to file - carry on
                    self.log(10, '>>>>>>>>>>>>>>>>>trig check and continue')
                    picam.wait_recording(splitter_port=splitter_port) # carry on recording - (check for split recording file?
            else: # no triggers present (now) - what were we doing?
                if recorder=='circ':
                    if self['recordback'].getValue()==0: # no re-trigger time now so close that down
                        self.log(10, '>>>>>>>>>>>>>>>>>not trig stop circ recorder')
                        picam.stop_recording(splitter_port=splitter_port)
                        circstream=None
                        recorder=None
                    else:
                        self.log(10, '>>>>>>>>>>>>>>>>>not trig circ check and continue')
                        picam.wait_recording(splitter_port=splitter_port) # carry on recording to circ buff
                elif recorder=='none':
                    if self['recordback'].getValue()> 0: # turn on circ buffer record
                        self.log(10, '>>>>>>>>>>>>>>>>>not trig start circ recording')
                        circstream=picamera.PiCameraCircularIO(picam, seconds=pretime+1, splitter_port=splitter_port)
                        picam.start_recording(circstream, resize=resize, format='h264', sps_timing=self.withsps, splitter_port=splitter_port)
                        recorder='circ'
                    else:
                        self.log(10, '>>>>>>>>>>>>>>>>>not trig carry on not recording')
                        pass # nothing to do here
                else: # we're recording to file
                    if aftertimeout is None:
                        self.log(10, '>>>>>>>>>>>>>>>>>not trig start post record timeout')
                        aftertimeout = time.time() + self['recordfwd'].getValue()
                    elif time.time() < aftertimeout: # waiting for post trigger timeout
                        self.log(10, '>>>>>>>>>>>>>>>>>not trig and waiting for timeout - carry on')
                    else: # were done now - go back to waiting state
                        pretime=self['recordback'].getValue()
                        if pretime > 0:
                            if circstream is None:
                                self.log(10, '>>>>>>>>>>>>>>>>>not trig split recording to circ buffer - making circ buffer')
                                circstream=picamera.PiCameraCircularIO(picam, seconds=pretime+1, splitter_port=splitter_port)
                            else:
                                self.log(10, '>>>>>>>>>>>>>>>>>not trig split recording to circ buffer - re-use circ buffer')
                            picam.split_recording(circstream, splitter_port=splitter_port)
                            recorder='circ'
                        else:
                            picam.stop_recording(splitter_port=splitter_port)
                            circstream = None
                            self.log(10, '>>>>>>>>>>>>>>>>>not trig stop recording')
                            recorder='none'
                        self['status'].setIndex(1, 'driver')
                        self.processfiles([fpath, postpath] if prepath is None else [fpath, prepath, postpath])
        if recorder=='circ':
            picam.stop_recording(splitter_port=splitter_port)
            circstream=None
            recorder='none'
        elif recorder=='afile': # we're recording to file
            picam.stop_recording(splitter_port=splitter_port)
            circstream = None
            recorder='none'
            self.log(10, '>>>>>>>>>>>>>>>>>final stop recording')
            self.processfiles([fpath, postpath] if prepath is None else [fpath, prepath, postpath])
        if not self.procthread is None:
            self.procqueue.put('stop')
        self.app._releaseSplitterPort(self.name, splitter_port)
        self['status'].setIndex(0, 'driver')
        self['lastactive'].setValue(time.time(), 'driver')
        self.cleartrigger('*')
        self.monthread=None
        
    def processfiles(self, filelist):
        if self.procthread is None:
            self.procqueue=queue.Queue()
            self.procthread=threading.Thread(name=self.name, target=self.fileprocessor, kwargs={'q': self.procqueue})
            self.procthread.start()
        self.procqueue.put(filelist)

    def fileprocessor(self, q):
        nextact=q.get()
        while nextact != 'stop':
            cmd=['MP4Box', '-quiet']
            output=nextact.pop(0).with_suffix('.mp4')
            inp1=nextact.pop(0)
            while not inp1 is None and inp1.is_file() and inp1.stat().st_size == 0:
                if len(nextact) > 0:
                    inp1=nextact.pop(0)
                else:
                    inp1=None
            if inp1 is None:
                self.log(30, 'recording postprocess found nothing to do for output %s' % output)
            else:
                cmd.append('-add')
                cmd.append(str(inp1))
                filepaths=[inp1]
                while len(nextact) > 0:
                    nextin = nextact.pop(0)
                    if nextin.is_file():
                        if nextin.stat().st_size > 0:
                            cmd.append('-cat')
                            cmd.append(str(nextin))
                            filepaths.append(nextin)
                    else:
                        self.log(30, 'mp4boxing input file %s not found' % str(nextin))
                cmd.append(str(output))
                self.log(40, 'record postprocessing with %s' % str(cmd))
                subp=Popen(cmd, universal_newlines=True, stdout=PIPE, stderr=PIPE)
                outs, errs = subp.communicate()
                rcode=subp.returncode
                if rcode==0:
                    self.log(40, 'recording postprocessing done')
                    shutil.copystat(str(filepaths[0]), str(output))
                    if self['saveX264'].getIndex()==0:
                        for f in filepaths:
                            if f.is_file():
                                f.unlink()
                else:
                    if errs is None:
                        self.log(30, 'MP4Box error - code %s' % rcode)
                    else:
                        self.log(30, 'MP4Box stderr:'+str(errs))
            nextact=q.get()
        
