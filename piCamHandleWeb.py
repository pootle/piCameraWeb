import piCamHandler
from pootlestuff.watchables import myagents
import pagelink
from webstrings import tablefieldinputhtml, tablefielddropdnhtml, tablefieldcyclicbtndnhtml, tablesectwrapper, spanfieldinputhtml

class piCamWeb(piCamHandler.cameraManager):
    def makeMainPage(self, pagelist, qp, pp):
        links={
            'pageid'        : pagelist.pageid,
            'camstat'       : pagelink.wwlink(wable=self.cam_summary, pagelist=pagelist, userupa=None, liveupa=myagents.app,
                label = 'camera state', shelp='shows if camera is active').webitem(fformat=spanfieldinputhtml),
            'camsettings'   : self.camsettings(pagelist),
            'streaminfo'    : '\n'.join([act.streaminfo(pagelist) for act in self.activities.values()])
        }
        return {'resp':200, 'headers': (('Content-Type', 'text/html; charset=utf-8'),), 'data': '''
            <html>
                <header>
                    <script src="static/pymon.js"></script>
                    <script type="text/javascript">
                        window.onload=startup

                        function startup() {{
                            liveupdates("{pageid}")
                        }}
                    </script>
                    <link rel="stylesheet" href="static/some.css">
                </header>
                <body><form autocomplete="off">
                   <div>
                       {camstat}
                   </div>
                   <div class="overpnl">
                       <div>
                           <div>
                               <span onclick="livestreamflip(this)" title="click to start / stop live view" class="btnlike" style="width:135px" >show livestream</span>
                               <span onclick="detstreamflip(this)" title="click to start / stop cpu detection overlay" class="btnlike" style="width:135px" >show detection</span>
                               <span onclick="maskeditflip(this)" title="click to start / stop cpu mask edit" class="btnlike" style="width:135px" >edit mask</span>
                           </div>
                           <div style="position: relative; height: 800px; width: 600px;">
                                <img id="livestreamimg" src="static/nocam.png" width="800px" height="600px" style="z-index:1;"/>
                                <div id="detstreamdiv" style="display:none; position:absolute; top:0px; left:0px; width:100%; height:100%; z-index:2;"></div>
                                <div id="livemaskdiv" style="display:none; position:absolute; top:0px; left:0px; width:100%; height:100%; z-index:3;">
                                          <canvas id="livemaskcanv"></canvas>
                                </div>
                           </div>
                       </div>
                   </div>
                    <h3>hello from app1</h3>
                    <table style="border-spacing: 0px;">
                       <col style="width:220px;">
                       <col style="width:320px;">
                       <col style="width:90px;">
                        {camsettings}
                        {streaminfo}
                    </table>
                </form></body>
            </html>'''.format(**links)}

    def camsettings(self, pagelist):
        fieldhtml=\
            pagelink.wwlink(wable=self.cam_framerate, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:5.2f}',
                label = 'frame rate', shelp='frame rate in fps - note the framerate limits the maximum exposure time', 
                doclink ='https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.framerate').webitem(fformat=tablefieldinputhtml) +\
            pagelink.wwenum(wable=self.cam_resolution, pagelist=pagelist, userupa=myagents.user, liveformat=None,
                label = 'resolution', shelp='camera resolution with standard values that try to use the full frame - only takes effect when camera (re)starts)',
                doclink = 'https://picamera.readthedocs.io/en/release-1.13/fov.html#camera-modes').webitem(fformat=tablefielddropdnhtml) +\
            pagelink.wwlink(wable=self.cam_u_width, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:4d}',
                label='special width', shelp = 'user defined camera width (when resolution is "special" may zoom the image').webitem(fformat=tablefieldinputhtml) +\
            pagelink.wwlink(wable=self.cam_u_height, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:4d}',
                label = 'special height', shelp='user defined camera height (when resolution is "special" may zoom the image').webitem(fformat=tablefieldinputhtml) +\
            pagelink.wwenum(wable=self.cam_rotation, pagelist=pagelist, userupa=myagents.user, liveformat=None,
                label = 'image rotation', shelp='allows the image to be rotated in 90 degree increments',
                doclink = 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.rotation').webitem(fformat=tablefielddropdnhtml) +\
            pagelink.wwenum(wable=self.cam_hflip, pagelist=pagelist, userupa=myagents.user,
                label = 'horizontal flip', shelp='flip image left<->right').webitem(fformat=tablefielddropdnhtml) +\
            pagelink.wwlink(wable=self.zoomleft, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:5.2f}',
                label = 'zoom left edge', shelp='sets the left edge of zoomed area (0 - 1, 0 is left edge)', 
                doclink ='https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.zoom').webitem(fformat=tablefieldinputhtml) +\
            pagelink.wwlink(wable=self.zoomright, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:5.2f}',
                label = 'zoom right edge', shelp='sets the right edge of zoomed area (0 - 1, 1 is right edge)', 
                doclink ='https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.zoom').webitem(fformat=tablefieldinputhtml) +\
            pagelink.wwlink(wable=self.zoomtop, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:5.2f}',
                label = 'zoom top edge', shelp='sets the upper edge of zoomed area (0 - 1, 0  is top edge)', 
                doclink ='https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.zoom').webitem(fformat=tablefieldinputhtml) +\
            pagelink.wwlink(wable=self.zoombottom, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:5.2f}',
                label = 'zoom bottom edge', shelp='sets the lower edge of zoomed area (0 -1, 1 is bottom edge)', 
                doclink ='https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.zoom').webitem(fformat=tablefieldinputhtml) +\
            pagelink.wwenum(wable=self.cam_awb_mode, pagelist=pagelist, userupa=myagents.user, liveformat=None,
                label = 'white balance', shelp = 'camera white balance mode',
                doclink = 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.awb_mode').webitem(fformat=tablefielddropdnhtml) +\
            pagelink.wwenum(wable=self.cam_exposure_mode, pagelist=pagelist, userupa=myagents.user, liveformat=None,
                label = 'exposure mode', shelp = 'camera exposure mode',
                doclink = 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.exposure_mode').webitem(fformat=tablefielddropdnhtml) +\
            pagelink.wwenum(wable=self.cam_meter_mode, pagelist=pagelist, userupa=myagents.user, liveformat=None,
                label = 'metering mode', shelp = 'exposure metering mode',
                doclink = 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.meter_mode').webitem(fformat=tablefielddropdnhtml) +\
            pagelink.wwenum(wable=self.cam_drc_strength, pagelist=pagelist, userupa=myagents.user, liveformat=None,
                label = 'compression', shelp = 'dynamic range compression mode',
                doclink = 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.drc_strength').webitem(fformat=tablefielddropdnhtml) +\
            pagelink.wwlink(wable=self.cam_contrast, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:2d}',
                label = 'contrast', shelp = 'sets contrast (-100 to +100, 0 is default)',
                doclink = 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.contrast').webitem(fformat=tablefieldinputhtml) +\
            pagelink.wwlink(wable=self.cam_brightness, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:3d}',
                label = 'brighness', shelp = 'sets brightness (0 to 100, 50 is default)',
                doclink = 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.brightness').webitem(fformat=tablefieldinputhtml) +\
            pagelink.wwlink(wable=self.cam_exp_comp, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:3d}',
                label = 'exp compensation', shelp = 'sets exposure compensation in 1/6th stop increments from -4 1/6 stops to +4 1/6 stops (-25 to +25)',
                doclink = 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.exposure_compensation').webitem(fformat=tablefieldinputhtml) +\
            pagelink.wwlink(wable=self.cam_exp_speed, pagelist=pagelist, userupa=None, liveupa=myagents.app,
                label='exposure time', shelp='current exposure time (microseconds)').webitem(fformat=tablefieldinputhtml) +\
            pagelink.wwlink(wable=self.cam_shutter_speed, pagelist=pagelist, userupa=myagents.user, liveupa=None,
                label = 'set shutter time (0->auto)', shelp='set the camera exposure speed in microseconds',
                doclink = 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.shutter_speed').webitem(fformat=tablefieldinputhtml) +\
            pagelink.wwenum(wable=self.cam_iso, pagelist=pagelist, userupa=myagents.user, liveupa=None,
                label = 'set iso', shelp='set iso value in use by camera (= ->auto)',
                doclink = 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.iso').webitem(fformat=tablefielddropdnhtml) +\
            pagelink.wwlink(wable=self.cam_analog_gain, pagelist=pagelist, userupa=None, liveupa=myagents.app,
                label = 'current analogue gain ', shelp='last reported analog gain in use by camera',
                doclink = 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.analog_gain').webitem(fformat=tablefieldinputhtml) +\
            pagelink.wwlink(wable=self.cam_digital_gain, pagelist=pagelist, userupa=None, liveupa=myagents.app,
                label = 'current digital gain', shelp='alast reported analog gain in use by camera',
                doclink = 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.digital_gain').webitem(fformat=tablefieldinputhtml) +\
            pagelink.wwbutton(wable=self.savedefaultbtn, pagelist=pagelist, userupa=myagents.user, liveupa=None,
                label = 'save default settings', shelp='saves current settings as default').webitem(fformat=tablefieldcyclicbtndnhtml) +\
            pagelink.wwenum(wable=self.cam_autoclose, pagelist=pagelist, userupa=myagents.user, liveformat=None,
                label = 'auto close', shelp = 'close camera automatically when inactive',).webitem(fformat=tablefielddropdnhtml) +\
            pagelink.wwlink(wable=self.cam_autoclose_time, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:3d}',
                label = 'timeout for autoclose', shelp = 'sets time (seconds) after all activity stops for the camera to be closed').webitem(fformat=tablefieldinputhtml) +\
            pagelink.wwbutton(wable=self.cam_close_btn, pagelist=pagelist, userupa=myagents.user, liveupa=None,
                label = 'force close camera now', shelp='closes the camera irrespective of activity').webitem(fformat=tablefieldcyclicbtndnhtml)    
        return tablesectwrapper.format(style='camsetstyle', flipid='xcamset', fields=fieldhtml, title='Camera Settings')
        