#!/usr/bin/python3

import threading, queue, time
import picamera.array as picamarray, numpy, pathlib
import numpy.ma as nma
import png, io
from pootlestuff import watchables as wv

class piCamCPU(wv.watchablesmart):
    """
    a base class for things that want to analyse images in detail for movement detection, exposure adjustment or anything else.
    
    It uses picamera to resize frames (to reduce processing load and reduce noise, pulls out each frame and passes it to 
    an analyser.
    """
    def __init__(self, statusvals, wabledefs, startbtnvals, loglevel=wv.loglvls.INFO, **kwargs):
        assert hasattr(self, 'monitor')
        super().__init__(wabledefs=[
            ('status',      wv.enumWatch,       statusvals[0],          False,      {'vlist': statusvals}),
            ('startstopbtn',wv.enumWatch,       startbtnvals[0],        False,      {'vlist': startbtnvals}),
            ('autostart',   wv.enumWatch,       'off',                  True,       {'vlist': ('off', 'on')}),
            ('width',       wv.intWatch,        128,                    True,       {'minv': 8, 'maxv': 800}),
            ('height',      wv.intWatch,        96,                     True,       {'minv': 6, 'maxv': 600}),
            ('lastactive',  wv.floatWatch,      float('nan'),           False),
            ('imagemode',   wv.enumWatch,       'rgb',                  True,       {'vlist': ('rgb', 'yuv')}),
            ('imagechannel',wv.enumWatch,       '0',                    True,       {'vlist': ('0','1','2', '*')}),
            ('skippedcount',wv.intWatch,        0,                      False),
            ('analysedcount',wv.intWatch,       0,                      False),           
        ]+wabledefs,
        **kwargs)
        self.agentclass=self.app.agentclass
        self.monthread=None
        self.procthread=None
        self.loglevel=loglevel
        if self.autostart.getIndex()==1:
            self.startstopbtn.setIndex(1,wv.myagents.app)
            self.running=True
            self.monthread=threading.Thread(name=type(self).__name__, target=self.monitor, kwargs={'startdelay':2.5})
            self.monthread.start()
        self.startstopbtn.addNotify(self.do_startstop, wv.myagents.user)

    def do_startstop(self, watched, agent, newValue, oldValue):
        """
        called when the users clicks the start / stop button
        
        to start running detection, run up a thread on the 'monitor' function of this object
        """
        btnstate=watched.getIndex()
        if self.monthread==None and btnstate==1:
            self.running=True
            self.monthread=threading.Thread(name=type(self).__name__, target=self.monitor)
            self.monthread.start()
        elif not self.monthread==None and btnstate==0:
            self.running=False
        else:
            self.log(wv.loglvls.WARN,' inconsistent move detection states running is %s and button was %s' % (self.running, oldValue))

    def preparearray(self):
        """
        prepares / updates a numpy array or masked array dependent on various variables
        """
        nshape=[self.height.getValue(),self.width.getValue()]
        if self.imagechannel.getIndex() == 3:
            nspage.append(3)
        return numpy.empty(shape=nshape, dtype=numpy.int16)

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
        self.status.setIndex(1, self.agentclass.app)
        self.lastactive.setValue(time.time(), self.agentclass.app)
        picam=self.app.startCamera()
        resize=((self.width.getValue()+31) // 32 * 32, (self.height.getValue()+15) // 16 * 16)
        self.freebuffs=queue.Queue()
        arraytype=picamarray.PiRGBArray if self.imagemode.getValue()=='rgb' else picamarray.PiYUVArray
        for i in range(3):
            self.freebuffs.put(arraytype(picam, size=resize))
        self.camerabuff=None        # the buffer currently being filled
        self.pendingbuffs=queue.Queue(maxsize=1) # and a queue of buffers we want to analyse  - restricted to 1 - just using threadsafeness
        splitter_port=self.app._getSplitterPort(type(self).__name__)
        self.log(wv.loglvls.INFO, 'cpu move detect using port %d and image size %s' % (splitter_port, resize))
        time.sleep(.1)
        self.condition=None # used to trigger detection overlay streaming
        self.analthread=threading.Thread(name='cpuanalyse', target=self.analysethread)
        self.analthread.start()
        picam.capture_sequence(self.buffercycle(), 
                format='rgb' if self.imagemode.getValue()=='rgb' else 'yuv',
                resize=resize, splitter_port=splitter_port, use_video_port=True)
        self.camerabuff=None
        self.pendingbuffs=None
        self.freebuffs=None
        self.app._releaseSplitterPort(type(self).__name__, splitter_port)
        self.lastactive.setValue(time.time(), self.agentclass.app)
        self.monthread=None
        self.analthread.join()
        self.analthread=None
        self.status.setIndex(0, self.agentclass.app)

    def buffercycle(self):
        """
        This generator function is used by picamera.capture_sequence to yield buffers to capture_sequence.
        A small pool of buffers is used, and each time it runs round the loop it records the last filled buffer so
        the analyse thread can pick up the latest frame whenever it is ready.
        """
        try:
            while self.running:
                try:
                    nextbuff=self.freebuffs.get_nowait()
                except queue.Empty:
                    nextbuff=None
                if nextbuff is None:
                    self.overruns.increment(agent=self.agentclass.app)
                    time.sleep(.2)
                    try:
                        nextbuff=self.freebuffs.get_nowait()
                    except queue.Empty:
                        raise StopIteration()
                        self.log(wv.loglvls.ERROR,'irrecoverable buffer overflow')
                prevbuff=self.camerabuff
                self.camerabuff=nextbuff
                if not prevbuff is None:
                    try:
                        expiredbuff=self.pendingbuffs.get_nowait()
                        expiredbuff.truncate(0)
                        self.freebuffs.put(expiredbuff)
                        self.skippedcount.increment(agent=self.agentclass.app)
                    except queue.Empty:
                        pass
                    self.pendingbuffs.put_nowait(prevbuff)
                yield nextbuff
        except:
            self.log(wv.loglvls.DEBUG,'move detect thread problem!', exc_info=True)


    def analysethread(self):
        prevbuff=None
        clocktimestart=time.time()
        cputimestart=time.clock()
        busytime=0
        busystart=time.time()
        tick5=busystart+5
        logpal=None
        logpng=None
        detstreamcount=0
        channel=self.imagechannel.getIndex()
        workarray=None
        while self.running:
            try:
                busytime+=time.time()-busystart
                thisbuff=self.pendingbuffs.get(block=True, timeout=2)
                busystart=time.time()
            except queue.Empty:
                thisbuff=None
            if not thisbuff is None:
                thisbuff, prevbuff, workarray = self.analysebuff(thisbuff, prevbuff, workarray, channel)
                prevbuff=thisbuff             
            if time.time() > tick5:
                elapsed=time.time()-clocktimestart
                self.analcpu.setValue(100*(time.clock()-cputimestart)/elapsed,self.agentclass.app)
                self.analbusy.setValue(100*busytime/elapsed, self.agentclass.app)
                tick5+=5
        if self.condition:
            try:
                self.condition.notify_all() # release clients one last time
            except:
                pass
            self.condition=None

class MoveDetectCPU(piCamCPU):
    """
    This class analyses successive frames and looks for significant change, setting its 'triggered' watchable True when movement is detected.
    
    This remains True until all frames for 'latchtime' have not detected movement. Anything wanting to be triggered can poll or set a notification 
    on this watchable.
    
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
    def __init__(self, statusvals=('off', 'watching', 'triggered'), startbtnvals=('start watching', 'stop watching'), **kwargs):
        """
        initialisation just sets up the vars used.
        """
        super().__init__(statusvals=statusvals, startbtnvals=startbtnvals, wabledefs=[
                ('triggercount',    wv.intWatch,    0,                  False),
                ('lasttrigger',     wv.floatWatch,  float('nan'),       False),
                ('cellthresh',      wv.intWatch,    22,                 True,       {'minv': 1, 'maxv': 255}),
                ('celltrigcount',   wv.intWatch,    100,                True,       {'minv': 1}),
                ('latchtime',       wv.floatWatch,  4,                  True),
                ('maskfold',        wv.folderWatch, '~/camfiles/masks', True),
                ('maskfile',        wv.textWatch,   '-off-',            True),
                ('overruns',        wv.intWatch,    0,                  False),
                ('analbusy',        wv.floatWatch,  0,                  False),
                ('analcpu',         wv.floatWatch,  0,                  False),
            ], **kwargs)

        self.running=False

    def fetchmasksize(self):
        """
        called from web server to retrieve info about mask in preparation for editing
        """
        rr={'width'     : self.width.getValue(),
            'height'    : self.height.getValue(),
            }
        return rr

    def savemask(self, pathinf, name, mask):
        """
        called from webserver when user saves a mask after editing
        """
        mfile=(self.maskfold.getFolder()/name).with_suffix('.png')
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
        if True:
            return super().preparearray()
        if self.maskfile.getValue()=='-off-':
            return dataarray
        else:
            mfile=(self.maskfold.getValue()/self.maskfile.getValue()).with_suffix('.png')
            if mfile.is_file():
                with mfile.open('rb') as mfo:
                    mwidth, mheight, mrows, minfo = png.Reader(file=mfo).read()
                    rowdat=[m for m in mrows]
                if mwidth==self.width.getValue() and mheight==self.height.getValue():
                    if minfo['planes']==1 and minfo['bitdepth']==1:
                        mask=numpy.array(rowdat,dtype=numpy.bool_)
                        self.log(wv.loglvls.INFO,'mask updated from %s %d of %d masked' % (str(mfile), len(numpy.nonzero(mask)[0]), mask.shape[0]*mask.shape[1]))
                        return nma.masked_array(data=dataarray, mask=mask)
                    else:
                        self.log(wv.loglvls.INFO, 'mask file has %d planes and bitdepth %d: should be 1 and 1' % (minfo.planes, minfo.bit_depth))
                else:
                    self.log(wv.loglvls.INFO,'mask image is wrong size - expected (%3d/%3d), file has (%3d/%3d)' % (self['width'].getValue(), self['height'].getValue(), mwidth, mheight))
            else:
                self.log(wv.loglvls.INFO, 'unable to get maskfile %s' % str(maskfile))
            return dataarray

    def analysebuff(self, thisbuff, prevbuff, workarray, channel):
        if prevbuff is None:
            workarray=self.preparearray()
        else:
            logthresh=self. cellthresh.getValue()
            if channel == 3:
                numpy.copyto(workarray, thisbuff.array)
                workarray -= prevbuff.array
            else:
                numpy.copyto(workarray, thisbuff.array[:,:,channel])
                workarray -= prevbuff.array[:,:,channel]
            numpy.absolute(workarray, workarray)
            cthresh=self.cellthresh.getValue()
            if logthresh != cthresh:
                logthresh = cthresh
                logpal=None
            hits=(workarray >= logthresh).nonzero()
            trig=len(hits[0]) >=self.celltrigcount.getValue()
            if trig:
                if self.status.getIndex() < 2:
                    self.triggercount.increment(agent=self.agentclass.app)
                    self.status.setIndex(2, agent=self.agentclass.app)
                self.lasttrigger.setValue(time.time(), agent=self.agentclass.app)
            else:
                if self.status.getIndex() > 1 and time.time() > (self.lasttrigger.getValue() + self.latchtime.getValue()):
                    self.status.setIndex(1, agent=self.agentclass.app)
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
                        if abs(xb) < self.width.getValue() and abs(yb) < self.height.getValue():
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
        return thisbuff, prevbuff, workarray

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
