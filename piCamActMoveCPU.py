#!/usr/bin/python3
"""
Module to provide cpu based movement detection, within a piCamHandler environment
"""

import logging
import numpy, queue, time
import numpy.ma as nam
import png, pathlib

import papps
import piCamHtml as pchtml
import piCamFields as pcf
from piCamSplitter import camSplitterAct
import pypnm
import threading

def makepalette(thresh):
    threshctr=thresh/2
    palette=[]
    for i in range(int(threshctr)):
        palette.append((0,0,0))
    threshctr=thresh *.75
    while len(palette) < threshctr:
        palette.append((40,40,100))
    threshctr=thresh
    while len(palette) < threshctr:
        palette.append((90,90,200))
    threshctr=thresh*1.25
    while len(palette) < threshctr:
        palette.append((40,100,40))
    nextrange=thresh*2 - len(palette)  # say 7 if threshold is 10 - number of entries we'll write
    gvalues=[int(100+155/nextrange*i) for i in range(nextrange)]
    for g in gvalues:
        palette.append((40,g,40))
    rleft=255-len(palette)
    bvalues=[int(100+155/rleft*b) for b in range(rleft)]
    for b in bvalues:
        palette.append((40,40,b))
    return palette

class changedImage():
    """
    A class to compare 2 images, by using a separate class it is easy to 
    implement very different comparison techniques.
    
    This class compares a new image against the previous image by counting all cells where the difference
    between images is greater than a threshold value, then checking how many such cells there are.
    """
    def __init__(self, vars, imagesize, buffers, loglvl=logging.DEBUG):
        """
        sets up a change test. Only Y value is used
        
        vars     : pforms var group with useful parameters
        
        imagesize: tuple of the size of the image we expect (any passed image is cropped to this size)
        
        buffers  : array of buffers in use - only the index is passed
        """
        self.log=None if loglvl is None else logging.getLogger(__loader__.name+'.'+type(self).__name__)
        self.loglvl=1000 if loglvl is None else loglvl
        self.vars=vars
        self.imagesize=imagesize
        self.workarray=numpy.empty((self.imagesize[1], self.imagesize[0]), dtype=numpy.int16)
        self.prevImage=False
        self.hitcount=0
        self.setMask()
        self.setDifflog()
        self.buffers=buffers

    def setMask(self):
        imgdata=fetchmask(self, self.vars)
        if imgdata is None:
            self.mask=None
            return
        else:
            m=numpy.array(imgdata,dtype=numpy.bool_)
            if self.loglvl <= logging.INFO:
                maskfile=self.vars['mask'].getFile()
                self.log.info('using mask from file {}, data type is {}, size is {}, {} cells are ignored'.format(
                        str(maskfile), str(m.dtype), m.shape, numpy.count_nonzero(m)))
            self.mask=m

    def check(self, newix):
        """
        checks the given image for change against the previous image
        
        newix: index to a numpy image of shape 3, >=width, >= height
        
        returns   a boolean, True if change detected
        """
        newimage = self.buffers[newix]
        if self.mask is None:
            imin=newimage[0, :self.imagesize[1], :self.imagesize[0]]
        else:
            imin=nam.masked_array(data=newimage[self.vars['channel'].getValue('app'), :self.imagesize[1], :self.imagesize[0]],
                    mask=self.mask, fill_value=0)
        if self.prevImage:
            self.workarray -= imin
            numpy.absolute(self.workarray, self.workarray)
            self.hits=(self.workarray >= self.vars['cellthreshold'].getValue('app')).nonzero()
            self.hitcount=len(self.hits[0])
            found=self.hitcount >= self.vars['cellcount'].getValue('app')
        else:
            found=False
        if found and not self.logdiffpalette is None:
            self.diffToPng(self.workarray)
        numpy.copyto(self.workarray, imin)
        self.prevImage=True
        return found

    def setDifflog(self):
        if self.vars['logdetect'].getValue('app')=='OFF':
            self.logdiffpalette=None
            print('diff logging is OFF')
            return
        self.logdiffpalette=makepalette(self.vars['cellthreshold'].getValue('app'))
        self.diffdir=pathlib.Path(self.vars['maskfolder'].getValue('app')).expanduser()/'detects'
        self.diffdir.mkdir(parents=True, exist_ok=True)
        print('diff logging is on with pal length', len( self.logdiffpalette))

    def diffToPng(self, diffarray):
        """
        a simple routine to write the numpy difference array out as png file.
        The values are all in range 0..255 so we'll use a simple palette to highlight things as follows:
            values below cellthreshold * .5 are black
            values then below cellthreshold *.75 are medium blue
            values then below cellthreshold are bright blue
            values then below cellthreshold * 1.25 are dark green
            values then below cellthreshold * 2 are increasingly light green
            values beyond that go from dark blue to bright blue as the value increases
        """
        pfile=self.diffdir/'d{:04d}.png'.format(self.vars['triggercount'].getValue('app'))
        print('diff to file', str(pfile))
        with pfile.open('wb') as pff:
            arshape=diffarray.shape
            pw = png.Writer(arshape[1], arshape[0], palette=self.logdiffpalette, bitdepth=8)
            pw.write(pff, diffarray)    

def fetchmask(actm, vars):
    maskfile=vars['mask'].getFile()
    if maskfile is None:
        if actm.loglvl <= logging.INFO:
            actm.log.info('no mask set')
        return None
    try:
        img=pypnm.open(maskfile)
    except ValueError as ve:
        if actm.loglvl <= logging.CRITICAL:
            actm.log.critical('no mask set, error opening file {}: {}'.format(str(maskfile), 'WHAT?'))
        return None
    if img.imgtype() != 'PBM':
        if actm.loglvl <= logging.CRITICAL:
            actm.log.critical('mask file {} is wrong type'.format(str(maskfile)))
        return None
    img.loadImage()
    return img.imgdata


class ciActivity(papps.appThreadAct):
    def __init__(self, inQ, outQ, analyser, analyserparams, **kwargs):
        self.inQ = inQ
        self.outQ= outQ
        super().__init__(**kwargs)
        self.engine=analyser(**analyserparams)

    def run(self):
        self.startDeclare()
        self.vars['triggercount'].setValue('app',0)
        while self.requstate != 'stop':
            try:
                imx=self.inQ.get(block=True, timeout=.7)
            except queue.Empty:
                imx=None
            if not imx is None:
                detect=self.engine.check(imx)
                if detect:
                    self.vars['triggercount'].setValue('app',self.vars['triggercount'].getValue('app')+1)
                    self.vars['lasttrigger'].setValue('app',time.time())
                    if self.loglvl <= logging.DEBUG:
                        logging.debug('it moved, hitcount {} from {}'.format(self.engine.hitcount, type(self.engine.hits).__name__))
                self.outQ.put(imx)
        self.endDeclare()

def calcbuff(width, height):
    """
    when using numpy capture we need to round up the array size
    pass"""
    return (3, int((height+15)/16)*16, int((width+31)/32)*32)

class mover(camSplitterAct,papps.appThreadAct):
    """
    When movement detected, variables 'triggercount' and 'lasttrigger' are updated.
    
    The actual analysis is run in a separate thread. Since most of the work is in numpy, the thread does not block
    other python threads from running.
    """
    def innerrun(self):
        imgsize=self.vars['resize'].getValue('app')
        self.checkQueue=queue.Queue()
        self.returnQueue=queue.Queue()
        narsize=calcbuff(*imgsize)
        self.numpyBuffs=[numpy.empty(narsize, dtype=numpy.uint8) for _ in range(6)]
        self.parent.startActivity(actname='movedetect', actclass=ciActivity, vars=self.vars,
                    inQ=self.checkQueue, outQ=self.returnQueue,
                    analyser=changedImage,
                    analyserparams={
                        'imagesize': imgsize,
                        'vars':self.vars,
                        'buffers': self.numpyBuffs})
        self.freebuffs=[x for x in range(len(self.numpyBuffs))]
        self.bufflog=[None]*100
        self.buffli=0
        self.bufflock=threading.Lock()
        picam=self.parent.picam
        self.currentBuff=None
        self.procCount=0
        self.startDeclare()
        format= self.vars['imgmode'].getValue('app')
        self.parent.picam.capture_sequence(self, resize=imgsize, format=format, use_video_port=True, splitter_port=self.sPort)
        # capture sequence now calls the __iter__  and __next__ functions for each frame read and
        # only returns when the iterator raises StopIteration
        self.printbufflog()
        self.parent.activities['movedetect'].requestFinish()
        self.endDeclare()

    def addbufflog(self, msg, buffi):
        with self.bufflock:
            self.bufflog[self.buffli]=(time.time(), buffi, msg)
            self.buffli += 1
            if self.buffli >= len(self.bufflog):
                self.buffli=0

    def printbufflog(self):
        for le in self.bufflog[self.buffli+1:-1]:
            if not le is None:
                self.printlogent(le)
        for le in self.bufflog[0:self.buffli+1]:
            if not le is None:
                self.printlogent(le)

    def printlogent(self, le):
        print('{:12.2f} {:d} {:s}'.format(le[0]-self.clockatstart, le[1], le[2]))

    def startedlogmsg(self):
        return super().startedlogmsg()+' size {}, format {}, channel {}'.format(
                self.vars['resize'].getValue('app'), 
                self.vars['imgmode'].getValue('app'),
                self.vars['channel'].getValue('app'),
                )

    def __iter__(self):
        return self

    def __next__(self):
        if self.requstate=='stop':
            if not self.currentBuff is None:
                self.addbufflog('final return', self.currentBuff)
                self.freebuffs.append(self.currentBuff)
                self.currentBuff=None
            raise StopIteration
        self.procCount+=1
        framediv=self.vars['framediv'].getValue('app')
        if not self.currentBuff is None:
            if self.procCount > self.vars['startskip'].getValue('app') and (framediv==1 or self.procCount % framediv == 0):
                self.addbufflog('buff to proc', self.currentBuff)
                self.checkQueue.put(self.currentBuff)
            else:
                self.addbufflog('immed recycle', self.currentBuff)
                self.freebuffs.append(self.currentBuff)
        try:
            while True:
                fromq=self.returnQueue.get(block=False)
                self.addbufflog('return from proc',fromq)
                self.freebuffs.append(fromq)
        except queue.Empty:
            pass
        try:
            self.currentBuff=self.freebuffs.pop()
            self.addbufflog('from buff pool', self.currentBuff)
        except IndexError:
            self.printbufflog()
            raise RuntimeError('Oh gawd, ran out of buffers')
        return self.numpyBuffs[self.currentBuff]

############################################################################################
# user interface setup for cpu move detection - web page version 
############################################################################################
EMPTYDICT={}

cpumovetable=(
    (pchtml.htmlStatus  , pchtml.HTMLSTATUSSTRING),

    (pchtml.htmlAutoStart, EMPTYDICT),

    (pchtml.htmlStreamSize, {'streamsizes': pcf.minisizes, 'writersOn':('app', 'pers')}),
    (pchtml.htmlInt,        {
            'readersOn': ('app', 'pers', 'html'),
            'writersOn': ('app', 'pers', 'user'),
            'name'     : 'startskip', 'minv':0, 'maxv':100, 'clength':4, 'fallbackValue': 10,
            'label'    : 'skip on start',
            'shelp'    : 'on startup, number of frames to skip before detection starts'}),
    (pchtml.htmlInt,        {
            'readersOn': ('app', 'pers', 'html'),
            'writersOn': ('app', 'pers', 'user'),
            'name' : 'framediv', 'minv':1, 'maxv':10, 'clength':4, 'fallbackValue':1,
            'label': 'frame ratio',
            'shelp': 'process only every nth frame (1-> every frame, 3 -> every third frame)'}),
    (pchtml.htmlInt,        {
            'readersOn': ('app', 'pers', 'html'),
            'writersOn': ('app', 'pers', 'user'),
            'name' : 'cellthreshold', 'minv':1, 'maxv': 200, 'clength':4, 'fallbackValue':10,
            'label': 'cell threshold',
            'shelp': 'minimum difference for a cell to trigger'}),
    (pchtml.htmlInt,        {'name' : 'cellcount', 'minv':1, 'maxv': 5000, 'clength':4, 'fallbackValue':100,
            'readersOn' : ('app', 'pers', 'html'),
            'writersOn' : ('app', 'pers', 'user'),
            'label'     : 'cell count',
            'shelp'     : 'minimum number of cells over trigger level to cause movement trigger'}),
    (pchtml.htmlChoice, {
            'name': 'imgmode', 'vlists': ('rgb', 'yuv'), 'fallbackValue': 'yuv',    
            'readersOn' : ('app', 'pers', 'html'),
            'writersOn' : ('app', 'pers', 'user'),
            'label'     : 'image mode',
            'shelp'     : 'defines if images are captured in rgb or yuv - only takes effect when next started.'}),
    (pchtml.htmlInt,        {'name' : 'channel', 'minv':0, 'maxv': 2, 'clength':2, 'fallbackValue':0,
            'readersOn' : ('app', 'pers', 'html'),
            'writersOn' : ('app', 'pers', 'user'),
            'label'     : 'channel for test',
            'shelp'     : 'movement is analysed using a single channel from yuv or rgb'}),
    (pchtml.htmlString, {
            'name': 'maskfolder',
            'readersOn' : ('app', 'pers', 'html', 'webv'),
            'writersOn' : ('app', 'pers'),
            'fallbackValue': '~/movemasks', 'clength':15,
            'label'     : 'image masks folder',
            'shelp'     : 'folder to hold image mask files'            
    }),
    (pchtml.htmlFolderFile, {
            'name'      : 'mask', 'loglvl':logging.DEBUG,
            'basefoldervar': '../maskfolder',
            'readersOn' : ('app', 'pers', 'html', 'webv'),
            'writersOn' : ('app', 'pers', 'user'),
            'label'     : 'use image mask',
            'shelp'     : 'enable / select image mask file'
    }),
    (pchtml.htmlChoice, {
            'name': 'logdetect', 'vlists': ('OFF', 'ON'), 'fallbackValue': 'OFF',    
            'readersOn' : ('app', 'pers', 'html'),
            'writersOn' : ('app', 'pers', 'user'),
            'label'     : 'logdetect',
            'shelp'     : 'When on, the difference images used to detect motion are saved.'}),
    (pchtml.htmlCyclicButton, {
            'name' : 'run',  'fallbackValue': 'start now', 'alist': ('start now', 'stop now '),
            'onChange'  : ('dynamicUpdate','user'),
            'label': 'enable detection', 
            'shelp': 'enables / disables this motion detection method',
    }),
    (pchtml.htmlInt,        {
            'name'      : 'triggercount', 'fallbackValue': 0,
            'readersOn' : ('html', 'app', 'webv'),
            'writersOn' : ('app', 'pers'),
            'onChange'  : ('dynamicUpdate','app'),
            'label'     : 'triggers',
            'shelp'     : 'number of triggers this session'}),
    (pchtml.htmlTimestamp, {'name': 'lasttrigger', 'fallbackValue':0,
            'strft': '%H:%M:%S' , 'unset':'never',
            'onChange': ('dynamicUpdate','app'),
            'label': 'last trigger time',
            'shelp': 'time last triggered occurred'}),
    (pchtml.htmlStartedTimeStamp, EMPTYDICT),
    (pchtml.htmlStoppedTimeStamp, EMPTYDICT),
)
