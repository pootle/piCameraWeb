#!/usr/bin/python3
"""
Module to provide cpu based movement detection, within a piCamHandler environment
"""

import papps
import piCamHtml as pch
import piCamFields as pcf

class changedImage():
    """
    A class to compare 2 images, by using a separate class it is easy to 
    implement very different comparison techniques.
    
    This class compares a new image against the previous image by counting all cells where the difference
    between images is greater than a threshold value, then checking how many such cells there are.
    """
    def __init__(self, vars, imagesize):
        """
        sets up a change test. Only Y value is used
        
        vars     : pforms var group with useful parameters
        
        imagesize: tuple of the size of the image we expect (any passed image is cropped to this size)
        """
        self.vars=vars
        self.imagesize=imagesize
        self.workarray=numpy.empty((self.imagesize[1], self.imagesize[0]), dtype=numpy.int16)
        self.prevImage=False
        self.hitcount=0

    def check(self, newimage):
        """
        checks the given image for change against the previous image
        
        newimage: a numpy image of shape 3, >=width, >= height
        
        returns   a boolean, True if change detected
        """
        imin=newimage[0, :self.imagesize[1], :self.imagesize[0]]
        if self.prevImage:
            self.workarray -= imin
            numpy.absolute(self.workarray, self.workarray)
            self.hits=(self.workarray >= self.vars['cellthreshold'].getValue('app')).nonzero()
            self.hitcount=len(self.hits[0])
            found=self.hitcount >= self.vars['cellcount'].getValue('app')
        else:
            found=False
        numpy.copyto(self.workarray, imin)
        self.prevImage=True
        return found

class ciActivity(papps.appThreadAct):
    def __init__(self, inQ, outQ, analyser, analyserparams, **kwargs):
        self.inQ = inQ
        self.outQ= outQ
        self.engine=analyser(**analyserparams)
        super().__init__(**kwargs)

    def run(self):
        self.startDeclare()
        self.vars['triggercount'].setValue('app',0)
        while self.requstate != 'stop':
            try:
                img=self.inQ.get(block=True, timeout=.3)
            except queue.Empty:
                img=None
            if not img is None:
                detect=self.engine.check(img)
                if detect:
                    self.vars['triggercount'].setValue('app',self.vars['triggercount'].getValue('app'))
                    self.vars['lasttrigger'].setValue('app',time.time())
                    print('it moved, hitcount {} from {}'.format(self.engine.hitcount, type(self.engine.hits).__name__))
                self.outQ.put(img)
        self.endDeclare()

def calcbuff(width, height):
    """
    when using numpy capture we need to round up the array size
    pass"""
    return (3, int((height+15)/16)*16, int((width+31)/32)*32)

class mover(papps.appThreadAct):
    """    
    When movement detected, variables 'triggercount' and 'lasttrigger' are updated.
    
    The actual analysis is run in a separate thread. Since most of the work is in numpy, this thread does not block
    other python threads from running.
    """
    def __init__(self, splitterport, **kwargs):
        self.sPort=splitterport
        super().__init__(**kwargs)

    def run(self):
        imgsize=self.vars['resize'].getValue('app')
        self.checkQueue=queue.Queue()
        self.returnQueue=queue.Queue()
        self.parent.startActivity(actname='movedetect', actclass=ciActivity, vars=self.vars,
                    inQ=self.checkQueue, outQ=self.returnQueue,
                    analyser=changedImage,
                    analyserparams={
                        'imagesize': imgsize,
                        'vars':self.vars})
        narsize=calcbuff(*imgsize)
        self.numpyBuffs=[numpy.empty(narsize, dtype=numpy.uint8) for _ in range(2)]
        picam=self.parent.picam
        self.currentBuff=None
        self.procCount=0
        self.startDeclare()
        self.parent.picam.capture_sequence(self, resize=imgsize, format='yuv', use_video_port=True, splitter_port=self.sPort)
        # capture sequence now calls the __iter__  and __next__ functions for each frame read and
        # only returns when the iterator raises StopIteration
        self.parent.activities['movedetect'].requestFinish()
        self.endDeclare()

    def __iter__(self):
        return self

    def __next__(self):
        if self.requstate=='stop':
            if not self.currentBuff is None:
                self.numpyBuffs.append(self.currentBuff)
                self.currentBuff=None
            raise StopIteration
        self.procCount+=1
        framediv=self.vars['framediv'].getValue('app')
        if not self.currentBuff is None:
            if self.procCount > self.vars['startskip'].getValue('app') and (framediv==1 or self.procCount % framediv == 0):
                self.checkQueue.put(self.currentBuff)
            else:
                self.numpyBuffs.append(self.currentBuff)
        try:
            while True:
                self.numpyBuffs.append(self.returnQueue.get(block=False))
        except queue.Empty:
            pass
        try:
            self.currentBuff=self.numpyBuffs.pop()
        except IndexError:
            print('Oh gawd, ran out of buffers')
            raise StopIteration
        if self.procCount % 25==0:
            print('done',self.procCount)
        return self.currentBuff


############################################################################################
# user interface setup for cpu move detection - web page version 
############################################################################################

cpumovetable=(
    (pch.htmlStringnp, {'name': 'status', 'fallbackValue': 'off',
            'onChange': ('dynamicUpdate','app'),
            'label'   : 'state',
            'shelp'   : 'current status of this activity',
            'readers' : {'html': '_getHtmlValue', 'expo':'_getSValue', 'webv': '_getSValue'}}),
    (pch.htmlStreamSize, {'streamsizes': pcf.minisizes}),
    (pch.htmlInt,        {
            'name' : 'startskip', 'minv':0, 'maxv':100, 'clength':4, 'fallbackValue': 1,
            'label': 'skip on start',
            'shelp': 'on startup, number of frames to skip before detection starts'}),
    (pch.htmlInt,        {
            'name' : 'framediv', 'minv':1, 'maxv':10, 'clength':4, 'fallbackValue':1,
            'label': 'frame ratio',
            'shelp': 'process only every nth frame (1-> every frame, 3 -> every third frame)'}),
    (pch.htmlInt,        {
            'name' : 'cellthreshold', 'minv':1, 'maxv': 200, 'clength':4, 'fallbackValue':10,
            'label': 'cell threshold',
            'shelp': 'minimum difference for a cell to trigger'}),
    (pch.htmlInt,        {'name' : 'cellcount', 'minv':1, 'maxv': 5000, 'clength':4, 'fallbackValue':100,
                      'label': 'cell count',
                      'shelp': 'minimum number of cells over trigger level to cause movement trigger'}),
    (pch.htmlCyclicButton, {
            'name' : 'run',  'fallbackValue': 'start now', 'alist': ('start now', 'stop now '),
            'label': 'enable detection', 
            'shelp': 'enables / disables this motion detection method',
    }),
    (pch.htmlInt,        {
            'name' : 'triggercount', 'fallbackValue': 0,
            'readers' : {'html': '_getHtmlValue', 'app': '_getCValue', 'expo':'_getSValue', 'webv': '_getSValue'},
            'writers' : {'app': '_validNum'},
            'onChange': ('dynamicUpdate','app'),
            'label': 'recordings',
            'shelp': 'number of recorded videos this session'}),
    (pch.htmlTimestamp, {'name': 'lasttrigger', 'fallbackValue':0,
            'strft': '%H:%M:%S' , 'unset':'never',
            'onChange': ('dynamicUpdate','app'),
            'label': 'time of last recording',
            'shelp': 'time last video recording triggered'}),
    (pch.htmlTimestamp, {'name': 'started', 'fallbackValue':0,
            'strft': '%H:%M:%S' , 'unset':'never',
            'onChange': ('dynamicUpdate','app'),
            'label': 'started at',
            'shelp': 'last time this view was started'}),
    (pch.htmlTimestamp, {'name': 'stopped', 'fallbackValue':0,
            'strft': '%H:%M:%S' , 'unset':'never',
            'onChange': ('dynamicUpdate','app'),
            'label': 'stopped at',
            'shelp': 'last time this view stopped'}),
)