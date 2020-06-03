import piCamHandler
from pootlestuff.watchables import myagents
import pagelink
from webstrings import tablefieldinputhtml, tablefielddropdnhtml, tablefieldcyclicbtndnhtml, tablesectwrapper, spanfieldinputhtml

class piCamWeb(piCamHandler.cameraManager):
    def makeMainPage(self, pagelist, qp, pp, page, parts):
        panels=[self.activities[p].makePanel(pagelist) for p in parts]
        fvars={
            'pageid'        : pagelist.pageid,
            'camstat'       : pagelink.wwlink(wable=self.cam_summary, pagelist=pagelist, updators=myagents.app,
                label = 'camera state', shelp='shows if camera is active').webitem(fformat=spanfieldinputhtml),
            'camsettings'   : tablesectwrapper.format(style='camsetstyle', flipid='xcamset', fields=self.allfields(pagelist=pagelist, fielddefs=allfielddefs),
                                                     title='Camera Settings'),
            'actparts'      : ''.join(panels),
        }
        with open(page,'r') as pf:
            templ=pf.read()
        return {'resp':200, 'headers': (('Content-Type', 'text/html; charset=utf-8'),), 'data':templ.format(**fvars)}



    def allfields(self, pagelist, fielddefs):
        fieldstrs = [defn[0](wable=getattr(self, defn[1]), pagelist=pagelist, updators=defn[2], label=defn[3], shelp=defn[5], **(defn[6] if len(defn) > 6 else {})).
                webitem(fformat=defn[4]) for defn in fielddefs]
        return ''.join(fieldstrs)

allfielddefs=(
    (pagelink.wwlink, 'cam_framerate', myagents.user, 'frame rate',     tablefieldinputhtml,
                                    'frame rate in fps - note the framerate limits the maximum exposure time', 
                                    {'doclink': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.framerate'}),
    (pagelink.wwenum, 'cam_resolution', myagents.user, 'resolution',    tablefielddropdnhtml,
                                    'camera resolution with standard values that try to use the full frame - only takes effect when camera (re)starts)',
                                    {'doclink': 'https://picamera.readthedocs.io/en/release-1.13/fov.html#camera-modes'}),
    (pagelink.wwlink, 'cam_u_width', myagents.user,  'special width',   tablefieldinputhtml,
                                    'user defined camera width (when resolution is "special" may zoom the image)', {'liveformat': '{wl.varvalue:4d}',}),
    (pagelink.wwlink, 'cam_u_height', myagents.user, 'special height',   tablefieldinputhtml,
                                    'user defined camera height (when resolution is "special" may zoom the image)', {'liveformat': '{wl.varvalue:4d}'}),
    (pagelink.wwenum, 'cam_rotation', myagents.user, 'image rotation',  tablefielddropdnhtml,   'allows the image to be rotated in 90 degree increments',
                                    {'doclink': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.rotation'}),
    (pagelink.wwenum, 'cam_hflip', myagents.user,    'horizontal flip', tablefielddropdnhtml,  'flip image left<->right'),
    (pagelink.wwenum, 'cam_vflip', myagents.user,    'vertical flip',   tablefielddropdnhtml,  'flip image top<->bottom'),

    (pagelink.wwlink, 'zoomleft', myagents.user, 'zoom left edge',      tablefieldinputhtml,    'sets the left edge of zoomed area (0 - 1, 0 is left edge)', 
                    {'liveformat': '{wl.varvalue:5.2f}', 'doclink': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.zoom',
                     'fixedfid': 'cam_zoom_left'}),
                     
    (pagelink.wwlink, 'zoomright', myagents.user,   'zoom right edge',   tablefieldinputhtml,   'sets the right edge of zoomed area (0 - 1, 1 is right edge)', 
                {'liveformat': '{wl.varvalue:5.2f}', 'doclink': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.zoom',
                 'fixedfid': 'cam_zoom_right'}),

    (pagelink.wwlink, 'zoomtop', myagents.user,  'zoom top edge',       tablefieldinputhtml,    'sets the upper edge of zoomed area (0 - 1, 0  is top edge)', 
                {'liveformat': '{wl.varvalue:5.2f}', 'doclink': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.zoom',
                 'fixedfid': 'cam_zoom_top'}),

    (pagelink.wwlink, 'zoombottom', myagents.user,  'zoom bottom edge', tablefieldinputhtml,    'sets the lower edge of zoomed area (0 -1, 1 is bottom edge)', 
                {'liveformat': '{wl.varvalue:5.2f}', 'doclink': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.zoom',
                 'fixedfid': 'cam_zoom_bottom'}),

    (pagelink.wwenum, 'cam_awb_mode', myagents.user, 'white balance',   tablefielddropdnhtml,   'camera white balance mode',
                {'doclink': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.awb_mode'}),
    (pagelink.wwenum, 'cam_exposure_mode', myagents.user, 'exposure mode',tablefielddropdnhtml, 'camera exposure mode',
                {'doclink': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.exposure_mode'}),
    (pagelink.wwenum, 'cam_meter_mode', myagents.user,'metering mode',  tablefielddropdnhtml,   'exposure metering mode',
                {'doclink': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.meter_mode'}),
    (pagelink.wwenum, 'cam_drc_strength', myagents.user,'compression',  tablefielddropdnhtml,    'dynamic range compression mode',
                {'doclink': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.drc_strength'}),
    (pagelink.wwlink, 'cam_contrast', myagents.user, 'contrast',        tablefieldinputhtml,    'sets contrast (-100 to +100, 0 is default)',    
                {'liveformat': '{wl.varvalue:2d}', 'doclink': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.contrast'}),
    (pagelink.wwlink, 'cam_brightness', myagents.user, 'brighness',     tablefieldinputhtml,    'sets brightness (0 to 100, 50 is default)',
                {'liveformat': '{wl.varvalue:3d}', 'doclink': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.brightness'}),
    (pagelink.wwlink, 'cam_exp_comp', myagents.user,    'exp compensation',tablefieldinputhtml, 
                'sets exposure compensation in 1/6th stop increments from -4 1/6 stops to +4 1/6 stops (-25 to +25)', {'liveformat': '{wl.varvalue:3d}', 
                'doclink': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.exposure_compensation'}),
    (pagelink.wwlink, 'cam_exp_speed', myagents.app,    'exposure time',tablefieldinputhtml, 'current exposure time (microseconds)'),
    (pagelink.wwlink, 'cam_shutter_speed', myagents.user,'set shutter', tablefieldinputhtml,    'set the camera exposure time in microseconds',
                {'doclink': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.shutter_speed'}),
    (pagelink.wwenum, 'cam_iso',       myagents.user,   'set iso',      tablefielddropdnhtml,   'set iso value in use by camera (= ->auto)',
                {'doclink': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.iso'}),
    (pagelink.wwlink, 'cam_analog_gain',myagents.app,   'current analogue gain', tablefieldinputhtml, "last reported analog gain in use by camera - setable if exposure mode is 'off'",
                {'doclink': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.analog_gain'}),
    (pagelink.wwlink, 'cam_digital_gain',myagents.app,  'current digital gain', tablefieldinputhtml, "last reported analog gain in use by camera - setable if exposure mode is 'off'",
                {'doclink': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.digital_gain'}),
    (pagelink.wwbutton, 'savedefaultbtn', myagents.user,'save default settings',tablefieldcyclicbtndnhtml, 'saves current settings as default'),
    (pagelink.wwenum, 'cam_autoclose', myagents.user, 'auto close',     tablefielddropdnhtml, 'close camera automatically when inactive'),
    (pagelink.wwlink, 'cam_autoclose_time', myagents.user,'timeout for autoclose', tablefieldinputhtml,
                'sets time (seconds) after all activity stops for the camera to be closed', {'liveformat': '{wl.varvalue:3d}'}),
    (pagelink.wwbutton, 'cam_close_btn', myagents.user, 'force close camera now', tablefieldcyclicbtndnhtml, 'closes the camera irrespective of activity'),
)
        