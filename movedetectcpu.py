#!/usr/bin/python3

import threading, queue, time
import picamera.array as picamarray, numpy, pathlib
import numpy.ma as nma
import png, io
from pootlestuff import pvars
import pvarfolderfiles as pvarf

cpumovevardefs=(
    {'name': 'status',      '_cclass': pvars.enumVar,       'fallbackValue': 'stopped','vlist': ('stopped', 'watching', 'detected')},
    {'name': 'startstop',   '_cclass': pvars.enumVar,       'fallbackValue': 'start', 'vlist': ('start', 'stop')},
    {'name': 'autostart',   '_cclass': pvars.enumVar,       'fallbackValue': 'off', 'vlist':('off', 'on'), 'filters': ['pers']},
    {'name': 'width',       '_cclass': pvars.intVar,        'fallbackValue': 128, 'minv': 4, 'maxv': 2000, 'filters': ['pers']},
    {'name': 'height',      '_cclass': pvars.intVar,        'fallbackValue': 96, 'minv': 3, 'maxv': 2000, 'filters': ['pers']},
    {'name': 'triggercount','_cclass': pvars.intVar,        'fallbackValue': 0},
    {'name': 'lastactive',  '_cclass': pvars.floatVar,      'fallbackValue': 0},
    {'name': 'lasttrigger', '_cclass': pvars.floatVar,      'fallbackValue': 0},
    {'name': 'imagemode',   '_cclass': pvars.enumVar,       'fallbackValue': 'rgb','vlist': ('rgb', 'yuv'), 'filters': ['pers']},
    {'name': 'imagechannel','_cclass': pvars.enumVar,       'fallbackValue': '0','vlist': ('0','1','2'), 'filters': ['pers']},
    {'name': 'cellthresh',  '_cclass': pvars.intVar,        'fallbackValue': 22, 'minv': 1, 'maxv': 255, 'filters': ['pers']},  
    {'name': 'celltrigcount','_cclass': pvars.intVar,       'fallbackValue': 100, 'minv': 1, 'filters': ['pers']},
    {'name': 'latchtime',   '_cclass': pvars.floatVar,      'fallbackValue': .5, 'filters': ['pers']},
    {'name': 'maskfold',    '_cclass': pvars.folderVar,     'fallbackValue': '~/camfiles/masks', 'filters': ['pers']},
    {'name': 'maskfile',    '_cclass': pvarf.selectFileVar, 'fvpath': 'maskfold', 'noneopt': '-off-', 'changeagent': 'driver', 'filters': ['pers']},
    {'name': 'skippedcount','_cclass': pvars.intVar,        'fallbackValue': 0},
    {'name': 'analysedcount','_cclass': pvars.intVar,       'fallbackValue': 0},
    {'name': 'overruns',    '_cclass': pvars.intVar,        'fallbackValue': 0},
    {'name': 'analbusy',    '_cclass': pvars.floatVar,        'fallbackValue': 0},
    {'name': 'analcpu',     '_cclass': pvars.floatVar,        'fallbackValue': 0},
)

class MoveDetectCPU(pvars.groupVar):
    """
    This class analyses successive frames and looks for significant change, setting its 'triggered' variable True when movement is detected.
    
    The variable remains True until all frames for 'latchtime' have not detected movement. Anything wanting to be triggered can poll this variable
    or set a notifcation on the variable.
    
    The code uses picamera to resize the frames (which happens in the GPU) to a (typically) much smaller size for analysis in this thread.
    
    Initially this class just sets up a bunch of variables that control and monitor this functionality. When detection is active, it runs a monitor thread
    to drive the camera and grab frames, and a further thread to actually analyse the frames.
    
    
    The mpnitor thread creates a small number of buffers and uses picamera.capture_sequence to run the camera, the capture_sequence call does not return
    until an external event causes capture sequence to stop.
    
    The buffers are allocated and managed by the member function buffercycle which is called from within picamera.capture_sequence. 'buffercycle' uses 'yield'
    to give a free buffer back to the camera, and passes places the buffer just filled to be ready for the analysis thread to use. If there was already a buffer
    waiting for analysis this expired buffer is returned to the free list and replaced by the more recent buffer, if the analysis thread has grabbed the previous
    buffer, the analysis thread returns it to the queue when it has dealt with it.
    
    Starting with the second buffer, the analysis thread picks 1 channel from the buffer and compares it with previous frame to check for differences.
    """
    def __init__(self, **kwargs):
        super().__init__(childdefs=cpumovevardefs, **kwargs)
        self.monthread=None
        self.procthread=None
        self.running=False
        if self['autostart'].getIndex()==1:
            self['startstop'].setIndex(1,'driver')
            self.running=True
            self.monthread=threading.Thread(name=self.name, target=self.monitor, kwargs={'startdelay':2})
            self.monthread.start()
        self['startstop'].addNotify(self.startstop, 'driver')    
        self['maskfile'].addNotify(self.checkmask, '*')

    def startstop(self, var, agent, newValue, oldValue):
        """
        called when the users clicks the start / stop button
        
        to start running detection, run up a thread on the 'monitor' function of this object
        """
        btnstate=var.getIndex()
        if self.monthread==None and btnstate==1:
            self.running=True
            self.monthread=threading.Thread(name=self.name, target=self.monitor)
            self.monthread.start()
        elif not self.monthread==None and btnstate==0:
            self.running=False
        else:
            self.log(40,' inconsistent move detection states running is %s and button was %s' % (self.running, oldValue))

    def fetchmaskinfo(self, parsedpath, requinfo, t):
        """
        called from web server to retrieve info about mask in preparation for editing
        """
        rr={'width'     : self['width'].getValue(),
            'height'    : self['height'].getValue(),
            }
        return True, rr

    def savemask(self, pathinf, name, mask):
        """
        called from webserver when user saves a mask after editing
        """
        mfile=(self['maskfold'].getValue()/name).with_suffix('.png')
        print('savemask (%3d/%3d) to %s  (%s): ' % (len(mask[0]), len(mask), name, mfile))
        pw = png.Writer(len(mask[0]), len(mask), greyscale=True, bitdepth=1)
        with mfile.open('wb') as fff:
            pw.write(fff,mask)
        return {'resp': 200, 'rdata':{'message': 'saved to %s' % mfile}} 

    def checkmask(self, var, agent, newValue, oldValue):
        pass

    def preparearray(self):
        """
        prepares / updates a numpy array or masked array dependent on various variables
        """
        dataarray=numpy.empty(shape=(self['height'].getValue(),self['width'].getValue()), dtype=numpy.int16)
        if self['maskfile'].getIndex()==0:
            return dataarray
        else:
            mfile=(self['maskfold'].getValue()/self['maskfile'].getValue()).with_suffix('.png')
            if mfile.is_file():
                with mfile.open('rb') as mfo:
                    mwidth, mheight, mrows, minfo = png.Reader(file=mfo).read()
                    rowdat=[m for m in mrows]
                if mwidth==self['width'].getValue() and mheight==self['height'].getValue():
                    if minfo['planes']==1 and minfo['bitdepth']==1:
                        mask=numpy.array(rowdat,dtype=numpy.bool_)
                        self.log(30,'mask updated from %s %d of %d masked' % (str(mfile), len(numpy.nonzero(mask)[0]), mask.shape[0]*mask.shape[1]))
                        return nma.masked_array(data=dataarray, mask=mask)
                    else:
                        self.log(30, 'mask file has %d planes and bitdepth %d: should be 1 and 1' % (minfo.planes, minfo.bit_depth))
                else:
                    self.log(40,'mask image is wrong size - expected (%3d/%3d), file has (%3d/%3d)' % (self['width'].getValue(), self['height'].getValue(), mwidth, mheight))
            else:
                self.log(40, 'unable to get maskfile %s' % str(maskfile))
            return dataarray

    def monitor(self, startdelay=0):
        """
        This function coordinates cpu based movement detection, it runs in its own thread within the loop of a picamera.capture_sequence call
        until self.running is set False.
        
        buffercycle (a generator) runs in a loop to process each frame.
        
        This also starts another thread to analyse successive frames from the camera, this thread uses a threadsafe queue (which only ever has 1 entry)
        to trigger analysis (if analysis still running when next frame arrives, it is discarded)
        """
        if startdelay > 0:
            time.sleep(startdelay)
        self['status'].setIndex(1, 'driver')
        self['lastactive'].setValue(time.time(), 'driver')
        picam=self.app.startCamera()
        resize=((self['width'].getValue()+31) // 32 * 32, (self['height'].getValue()+15) // 16 * 16)
        self.freebuffs=queue.Queue()
        arraytype=picamarray.PiRGBArray if self['imagemode'].getValue()=='rgb' else picamarray.PiYUVArray
        for i in range(3):
            self.freebuffs.put(arraytype(picam, size=resize))
        self.camerabuff=None        # the buffer currently being filled
        self.pendingbuffs=queue.Queue(maxsize=1) # and a queue of buffers we want to analyse  - restricted to 1 - just using threadsafeness
        splitter_port=self.app._getSplitterPort(self.name)
        self.log(30, 'cpu move detect using port %d' % splitter_port)
        time.sleep(.1)
        self.condition=None # used to trigger detection overlay streaming
        self.analthread=threading.Thread(name='cpuanalyse', target=self.analysethread)
        self.analthread.start()
        picam.capture_sequence(self.buffercycle(), 
                format='rgb' if self['imagemode'].getValue()=='rgb' else 'yuv',
                resize=resize, splitter_port=splitter_port, use_video_port=True)
        self.camerabuff=None
        self.pendingbuffs=None
        self.freebuffs=None
        self.app._releaseSplitterPort(self.name, splitter_port)
        self['lastactive'].setValue(time.time(), 'driver')
        self.monthread=None
        self.analthread.join()
        self.analthread=None
        self['status'].setIndex(0, 'driver')

    def buffercycle(self):
        """
        This generator function is used by picamera.capture_sequence to yield buffers to capture_sequence.
        A small pool of buffers is used, and each time it runs round the loop it records the last filled buffer so
        the analyse thread can pick it the latest frame whenever it is ready.
        """
        try:
            while self.running:
                try:
                    nextbuff=self.freebuffs.get_nowait()
                except queue.Empty:
                    nextbuff=None
                if nextbuff is None:
                    self['overruns'].increment(agent='driver')
                    time.sleep(.2)
                    try:
                        nextbuff=self.freebuffs.get_nowait()
                    except queue.Empty:
                        raise StopIteration()
                        self.log(50,'irrecoverable buffer overflow')
                prevbuff=self.camerabuff
                self.camerabuff=nextbuff
                if not prevbuff is None:
                    try:
                        expiredbuff=self.pendingbuffs.get_nowait()
                        expiredbuff.truncate(0)
                        self.freebuffs.put(expiredbuff)
                        self['skippedcount'].increment(agent='driver')
                    except queue.Empty:
                        pass
                    self.pendingbuffs.put_nowait(prevbuff)
                yield nextbuff
        except:
            self.log(10,'move detect thread problem!', exc_info=True)

    def analysethread(self):
        prevbuff=None
        clocktimestart=time.time()
        cputimestart=time.clock()
        busytime=0
        busystart=time.time()
        tick5=busystart+5
        logthresh=self['cellthresh'].getValue()
        logpal=None
        logpng=None
        detstreamcount=0
        while self.running:
            try:
                busytime+=time.time()-busystart
                thisbuff=self.pendingbuffs.get(block=True, timeout=2)
                busystart=time.time()
            except queue.Empty:
                thisbuff=None
            if not thisbuff is None:
                if prevbuff is None:
                    workarray=self.preparearray()
                else:
                    channel=self['imagechannel'].getIndex()
                    numpy.copyto(workarray, thisbuff.array[:,:,channel])
                    workarray -= prevbuff.array[:,:,channel]
                    numpy.absolute(workarray, workarray)
                    cthresh=self['cellthresh'].getValue()
                    if logthresh != cthresh:
                        logthresh = cthresh
                        logpal=None
                    hits=(workarray >= logthresh).nonzero()
                    trig=len(hits[0]) >=self['celltrigcount'].getValue()
                    if trig:
                        if self['status'].getIndex() < 2:
                            self['triggercount'].increment(agent='driver')
                            self['status'].setIndex(2, agent='driver')
                        self['lasttrigger'].setValue(time.time(), agent='driver')
                    else:
                        if self['status'].getIndex() > 1 and time.time() > (self['lasttrigger'].getValue() + self['latchtime'].getValue()):
                            self['status'].setIndex(1, agent='driver')
                    if not self.condition is None: # check if we're streaming the detection overlay
                        if self.laststreamactive+5 < time.time():
                            # client(s) all gone - stop the stream
                            print('clients gone - shut detect stream')
                            self.condition=None
                            logpal=None
                            streaming=None
                            logpng=None
                        else:
                            if logpal is None:
                                logpal=makepalette(logthresh)
                            streamimg = io.BytesIO()
                            arshape=workarray.shape
                            if logpng is None:
                                logpng = png.Writer(arshape[1], arshape[0], palette=logpal)
                            detimg=workarray.filled(fill_value=0) if hasattr(workarray, 'filled') else workarray
                            if trig and not detoverlay['xbase'] is None: # check if we want a blob
                                xb=detoverlay['xbase']
                                yb=detoverlay['ybase']
                                if abs(xb) < self['width'].getValue() and abs(yb) < self['height'].getValue():
                                    if xb < 0:
                                        xe=min((-1, xb+detoverlay['xsize']))
                                    else:
                                        xe=min((255, xb+detoverlay['xsize']))
                                    if yb < 0:
                                        ye=min((-1, yb+detoverlay['ysize']))
                                    else:
                                        ye=min((255, yb+detoverlay['ysize']))
                                    detimg[yb:ye,xb:xe]=255
                            logpng.write(streamimg, detimg.tolist())
                            with self.condition:
                                self.frame = streamimg.getvalue()
                                self.condition.notify_all()
                            if False:
                                sfp=pathlib.Path('~/Pictures').expanduser()/('b%04d.png' % self['triggercount'].getValue())
                                with sfp.open('wb') as sfpf:
                                    sfpf.write(self.frame)
                    prevbuff.truncate(0)
                    self.freebuffs.put(prevbuff)
                prevbuff=thisbuff             
            if time.time() > tick5:
                elapsed=time.time()-clocktimestart
                self['analcpu'].setValue(100*(time.clock()-cputimestart)/elapsed,'driver')
                self['analbusy'].setValue(100*busytime/elapsed, 'driver')
                tick5+=5
        if self.condition:
            try:
                self.condition.notify_all() # release clients one last time
            except:
                pass
            self.condition=None

    def getStream(self):
        """
        When we get a stream request from the web server, check if already running.
        
        This is called by an http handler request thread.
        
        THE HTTP thread (there can be several) then loops calling nextframe
        """
        if self.running:
            if self.condition==None:
                print('make detect stream')
                self.condition = threading.Condition()
                self.laststreamactive=time.time()
            else:
                print('returning existing detect stream')
            return self
        else:
            print('aborting detect stream')
            raise StopIteration()

    def nextframe(self):
        """
        The http handler thread calls this to get each successive frame.
        
        It waits for a new frame to arrive, then updates the lastactive timestamp and returns the frame
        """
        if self.running and self.condition:
            with self.condition:
                self.condition.wait()
                self.laststreamactive=time.time()
            return self.frame, 'image/png', len(self.frame)
        else:
            raise StopIteration()

detpalette=(
    (0.5, (  0,   0,   0,   0)),        # totally transparent black below 1/2 threshold
    (0.75,( 60,  60, 140, 160)),        # medium blue for 1/2 to 3/4 below
    (1,   ( 75,  75, 255, 200)),        # brighter and more opaque blue to threshold
    (1.5, ( 75, 255,  75, 200)),        # green just above threshold
    (2,   ( 60, 150,  69, 160)),        # then paler green
    (400, (255,   0,   0, 139)),        # then red wash
)
detoverlay={                            # overlay a blob when triggered
    'xbase': -4,                        # set 'xbase' to None to stop the blob, pos for inset from left, neg for inset from right
    'xsize': 4,                         # size must be +ve
    'ybase': 4,
    'ysize': 4,
    'palette': (255,100,100,255)
}

def makepalette(thresh):
    """
    prepares a pallette to use with the difference data to make a png image.
    The diff values are all in range 0..255 so we'll use a simple palette to highlight things as follows:
            values below cellthreshold * .5 are black
            values then below cellthreshold *.75 are medium blue
            values then below cellthreshold are bright blue
            values then below cellthreshold * 1.25 are dark green
            values then below cellthreshold * 2 are light green
            values beyond that go from dark blue to bright blue as the value increases
    
    The actual colours and transparency are set in a table, so can be easily changed
    """
    colourno=0
    palette=[]
    for tfact, pal in detpalette:
        nextmax=tfact*thresh
        while colourno < nextmax:
            palette.append(pal)
            colourno += 1
            if colourno > 254:
                palette.append(detoverlay['palette'])
                return palette

    while colourno < 255:
        palette.append(pal)
        colourno += 1
    palette.append(detoverlay['palette'])
    return palette
