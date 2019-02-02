#!/usr/bin/python3
"""
piCamFields provides a set of classes derived from pforms xxxVar that handle the various camera and stream settings 
that can be changed.like resolution, rotation, awb mode etc. for the camera and resize etc. for the streams.

These classes both handle the setting and make it easy for other software to save groups of settings and build a gui
to the control the camera.

All these classes define 2 views, 'app' and 'pers' that are used by the piCamHander.cameraManager class. 
'app' is used as the standard internal representation of the var. 'pers' is the view used when loading / saving settings
in a settings file.
"""

import logging
import pforms

#################################################################################################
# The first group of classes are for the direct camera settings
#################################################################################################
class picamAttrMixin():
    """
    a mixin class for pforms classes that syncs the value with a picamera.PiCamera attribute when the camera is active.
    
    The parent object should have an attribute 'picam' which is None or a picamera.PiCamera and an attribute
    'camType' which should be ‘ov5647’ (V1 module) or ‘imx219’ (V2 module).
    
    This class overrides getValue and setValue so they access the camera when available.
    
    Framerate and resolution, which can only be set if the camera is inactive, are just updated in the instance and are applied
    when the camera is next started.
    
    The 'app' view must return a value that can be written to the PiCamera class' attribute.
    
    Inheriting var classes can provide a default name, as this default is used by the cameraManager class, best not change it!
    """
    def __init__(self, *, camAttr, liveUpdate, name=None, **kwargs):
        """
        Uses a locally held value and the actual camera attribute when the camera is active.
        
        camAttr     : the attribute in a PiCamera that handles this var
        
        liveUpdate  : if True then this camera attribute can be updated while the camera is running, otherwise 
                      just update the locally held value, to be applied on next camera open

        name        : If the name passed in is None then uses a class level default name for convenience.
        """
        self.camAttr=camAttr
        self.liveUpdate=liveUpdate
        obname=self.defaultName if name is None else name
        try:
            super().__init__(name=obname, **kwargs)
        except TypeError:
            print('TypeError calling constructor from picamAttrMixin with parameters {}'.format(kwargs))
            print(kwargs)
            sig=signature(super().__init__)
            for pname in sig.parameters.keys():
                print(pname)
            raise
        
    def setValue(self, view, value):
        """
        After checking the value is valid, this updates the camera attribute if relevant /applicable.
        """
        updated=super().setValue(view, value)
        if self.liveUpdate and not self.app.picam is None:
            setattr(self.app.picam, self.camAttr, super().getValue('app'))

    def readRealCamera(self):
        val=getattr(self.app.picam, self.camAttr)
        return self._camconvertReadVal(val)

    def _camconvertReadVal(self,camval):
        """
        Converts the value read from the camera to the format we want to use here. - should be the 'app' format
        """
        return camval

    def _applyVar(self):
        aval=self.getValue('app')
        setattr(self.app.picam, self.camAttr, aval)
        if self.loglvl <= logging.INFO:
            self.log.info('var {} value {} applied to camera attribute {}'.format(self.name, aval, self.camAttr))

    def setupLogMsg(self):
        self.log.info('camera attribute ({}) {} set to {}.'.format(('not live' if self.app.picam is None else 'live'),
                    self.camAttr, self._getVar()))

class camResolution(picamAttrMixin, pforms.listVar):
    """
    handles the resolution parameter of a picamera. The set of resolutions we preset have to match the camera type.
    
    This var allows any reasonable value to be entered by the user, and also accepts whatever value the PiCmera class gives us back.
    
    The canonical value is held as a 2-tuple of integers.
    """
    resolutions={
        'ov5647' : (('3280x2464', '1640x1232', '1640x922', '1920x1080', '1280x720', '640x480'),
                    '1640x1232'),
                    
        'imx219' : (('2592x1944','1296x972','640x480'),
                    '1296x972')
        }
    defaultName='resolution'

    def __init__(self, app, parent, readers, writers, **kwargs):
        """
        Parent is a multiCam object with camType already setup
        
        If the value parameter is not valid for the current camera it silently resets to a sensible value
        """
        appValues, default=self.resolutions[app.camType]
        super().__init__(parent=parent, fallbackValue=default, app=app,
                readers=pforms.extendViews(readers, {'app':'_getValue', 'pers': '_getValue'}),
                writers=pforms.extendViews(writers, {'app': '_validValue', 'pers': '_validValue'}),
                camAttr='resolution', liveUpdate=False,
                label='camera resolution',
                shelp='camera resolution with standard values that try to use the full frame',
                vlists={v: appValues for v in app.allviews},
                **kwargs)

    def _validAppValue(self, view, value):
        """
        as read and read from PiCamera, value will be a string 'nnnxmmm'
        """
        twonums=[int(x) for x in value.split('x')]
        if len(twonums)==2:
            return value
        else:
            raise ValueError('{} does not appear to be a valid resolution'.format(value))

    def _validUserValue(self, view, value):
        twonums=[int(x) for x in value.split('x')]
        if len(twonums)==2:
            if 16<twonums[0]< 4000 and 16 < twonums[1] < 3000:
                return 'x'.join([str(x) for x in twonums])
            else:
                raise ValueError('the numbers in {} does not appear to be a valid resolution'.format(value))    
        else:
            raise ValueError('{} does not appear to be a valid resolution'.format(value))

    def _camconvertVal(self,camval):
        return '{}x{}'.format(camval.width,camval.height)

    def _setVar(self, val):
        if isinstance(val,str):
            raise TypeError('{} is not a valid canonical value'.format(val))
        super()._setVar(val)

camRotations=(0,90,180,270)

class camRotation(picamAttrMixin, pforms.listVar):
    """
    handles the rotation attribute of a picamera
    """
    defaultName='rotation'

    def __init__(self, app, readers, writers, **kwargs):
        super().__init__(fallbackValue=camRotations[0],
                readers=pforms.extendViews(readers, {'app':'_getValue', 'pers': '_getValue'}),
                writers=pforms.extendViews(writers, {'app': '_validValue', 'pers': '_validValue'}),
                app=app,
                vlists={k:camRotations for k in app.allviews},
                camAttr='rotation', liveUpdate=True,
                label='rotation',
                shelp='rotates image in 90 degree increments',
                **kwargs)

class camFramerate(picamAttrMixin, pforms.intervalVar):
    defaultName='framerate'

    def __init__(self, readers, writers, **kwargs):
        super().__init__(fallbackValue=30,
                readers=pforms.extendViews(readers, {'app': '_getCValue', 'pers': '_getCValue'}),
                writers=pforms.extendViews(writers, {'app': '_validNum', 'pers': '_validNum'}),
                minv=.1, maxv=90, interval=.01,
                camAttr='framerate', liveUpdate=False,
                label='frame rate in fps',
                shelp='frame rate between 1 every 10 seconds and 90 per second',
                **kwargs)

class camBrightness(picamAttrMixin, pforms.intervalVar):
    defaultName='brightness'

    def __init__(self, readers, writers, **kwargs):
        super().__init__(fallbackValue=50,
                minv=0, maxv=100, interval=1, rounding=True,
                readers=pforms.extendViews(readers, {'app': '_getCValue', 'pers': '_getCValue'}),
                writers=pforms.extendViews(writers, {'app': '_validNum', 'pers': '_validNum'}),
                camAttr='brightness', liveUpdate=True,
                label='brightness',
                shelp='sets camera brightness 0-100, 50 is default',
                **kwargs)

class camContrast(picamAttrMixin, pforms.intervalVar):
    defaultName='contrast'

    def __init__(self, readers, writers, **kwargs):
        super().__init__(fallbackValue=0,
                minv=-100, maxv=100, interval=1, rounding=True,
                readers=pforms.extendViews(readers, {'app': '_getCValue', 'pers': '_getCValue'}),
                writers=pforms.extendViews(writers, {'app': '_validNum', 'pers': '_validNum'}),
                camAttr='contrast', liveUpdate=True,
                label='contrast',
                shelp='sets camera contrast lower (-100 - 0, or higher (0 to +100)',
                **kwargs)

class camAwb_mode(picamAttrMixin, pforms.listVar):
    defaultName='awbMode'

    def __init__(self, app, readers, writers, **kwargs):
        if app.picam is None:
            newlist=['auto','off']
        else:
            relist={v:k for k,v in app.picam.AWB_MODES.items()}
            listorder=sorted(relist.keys())
            newlist=[relist[k] for k in listorder]
        super().__init__(fallbackValue='auto', app=app,
                vlists={v: newlist for v in app.allviews},
                readers=pforms.extendViews(readers, {'app':'_getValue', 'pers': '_getValue'}),
                writers=pforms.extendViews(writers, {'app': '_validValue', 'pers': '_validValue'}),
                camAttr='awb_mode', liveUpdate=True,
                label='awb mode',
                shelp='white balance mode',
                **kwargs)

class camExpoMode(picamAttrMixin, pforms.listVar):
    defaultName='expMode'

    def __init__(self, app, readers, writers, **kwargs):
        if app.picam is None:
            newlist=['auto','off']
        else:
            relist={v:k for k,v in app.picam.EXPOSURE_MODES.items()}
            listorder=sorted(relist.keys())
            newlist=[relist[k] for k in listorder]
        super().__init__(fallbackValue='auto', app=app,
                vlists={v: newlist for v in app.allviews},
                readers=pforms.extendViews(readers, {'app':'_getValue', 'pers': '_getValue'}),
                writers=pforms.extendViews(writers, {'app': '_validValue', 'pers': '_validValue'}),
                camAttr='exposure_mode', liveUpdate=True,
                label='exposure mode',
                shelp='sets the mode for exposure calculation',
                **kwargs)

expCompList=(
    ( 25,' 4 1/6'), ( 24,' 4'),
    ( 23,' 3 5/6'), ( 22,' 3 2/3'), ( 21,' 3 1/2'), ( 20,' 3 1/3'), ( 19,' 3 1/6'), ( 18,' 3'),
    ( 17,' 2 5/6'), ( 16,' 2 2/3'), ( 15,' 2 1/2'), ( 14,' 2 1/3'), ( 13,' 2 1/6'), ( 12,' 2'),
    ( 11,' 1 5/6'), ( 10,' 1 2/3'), (  9,' 1 1/2'), (  8,' 1 1/3'), (  7,' 1 1/6'), (  6,' 1'),
    (  5,'  5/6'),  (  4,'  2/3'),  (  3,'  1/2'),  (  2,'  1/3'),  (  1,'  1/6'),  
    (  0,'0'),
    ( -1,'- 1/6'),  ( -2,'- 1/3'),  ( -3,'- 1/2'),  ( -4,'- 2/3'),  ( -5,'- 5/6'),  
    ( -6,'-1'),     ( -7,'-1 1/6'), ( -8,'-1 1/3'), ( -9,'-1 1/2'), (-10,'-1 2/3'), (-11,'-1 5/6'), 
    (-12,'-2'),     (-13,'-2 1/6'), (-14,'-2 1/3'), (-15,'-2 1/2'), (-16,'-2 2/3'), (-17,'-2 5/6'), 
    (-18,'-3'),     (-19,'-3 1/6'), (-20,'-3 1/3'), (-12,'-3 1/2'), (-22,'-3 2/3'), (-23,'-3 5/6'), 
    (-24,'-4'),     (-25,'-4 1/6'),
)

expCompCamValues=list([l[0] for l in expCompList])
expCompDisplays=list([l[1] for l in expCompList])

class camExpoComp(picamAttrMixin, pforms.listVar):
    defaultName='expComp'

    def __init__(self, app, readers, writers, value, valueView, **kwargs):
        vlists={k: expCompCamValues if k=='app' else expCompDisplays for k in app.allviews}
        print("========exposure compensation using value", value, " with view ", valueView)
        super().__init__(fallbackValue='0', app=app,
                vlists=vlists,
                value=value,
                valueView=valueView,
                readers=pforms.extendViews(readers, {'app':'_getValue', 'pers': '_getValue'}),
                writers=pforms.extendViews(writers, {'app': '_validValue', 'pers': '_validValue'}),
                camAttr='exposure_compensation', liveUpdate=True,
                label='exposure adjust',
                shelp='exposure compensation 1/6 stop changes +/- 4 1/6 stops, not always effective',
                **kwargs)

#################################################################################################
# The following classes are parameters used by 1 or more streams
#################################################################################################

stdstreamsizes={
    'ov5647' : (((1640,1232), (1230,924), (1200,900), (820,616), (800,600), (640,480), (410,308), (640,480)),
                (640,480)),
    'imx219' : (((1296,972), (972,729), (864,648), (800,600), (648,486), (640,480), (432,324), (324,243)),
                (640,480))
}

minisizes={ # table used for cpu based motion analysis with added smaller sizes
    'ov5647' : (((1640,1232), (1230,924), (1200,900), (820,616), (800,600), (640,480), (410,308), (640,480), (320, 240), 
                        (280, 210), (200, 150), (128, 96), (64, 48)),
                (64, 48)),
    'imx219' : (((1296,972), (972,729), (864,648), (800,600), (648,486), (640,480), (432,324), (320, 240), 
                        (280, 210), (200, 150), (128, 96), (64, 48)),
                (64, 48))
}

class streamResize(pforms.listVar):
    """
    activites that use a splitter port can resize the video, this provides a standard class to deal with this resizing
    """
    defaultName='resize'

    def __init__(self, app, parent, name=None, streamsizes=stdstreamsizes, **kwargs):
        """
        App is a multiCam object with camType already setup
        
        If the value parameter is not valid for the current camera it silently resets to a sensible value
        """
        obname=self.defaultName if name is None else name
        appValues, default=streamsizes[app.camType]
        vlists={v: ['{}x{}'.format(*s) for s in appValues] if v in ('html', 'pers', 'user') else appValues for v in app.allviews}
        super().__init__(name=obname, parent=parent, fallbackValue=default, app=app,
                label='stream resolution',
                shelp='the stream is resized to this resolution',
                vlists=vlists,
                **kwargs)