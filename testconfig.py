#!/usr/bin/python3

from httpServerBase import ThreadedHTTPServer as basicserver

from httpServerBase import requHandler

from piCamHandler import cameraManager

from folderapp import fileManager

import htmlmaker

import pathlib, sysinfo

BRIGHTPI    =False
GPIOTRIG    =True
RECORDER    =True
CPUMOVE     =True
LIVESTREAM  =True

enables=[]
if GPIOTRIG:
    enables.append('gpio_trigger')
if RECORDER:
    enables.append('trig_record')
if CPUMOVE:
    enables.append('cpumove')
if LIVESTREAM:
    enables.append('camstream')
if BRIGHTPI:
    enables.append('brightpi')

appfields=(
    {'app': 'camera', 'varlocal': 'setsfold', 'fieldmaker': htmlmaker.make_strVar, 'userupa': 'user',
            'label': 'mask files folder', 'shelp': 'folder containing mask files'},
    {'app': 'camera', 'varlocal': 'setsfile', 'fieldmaker': htmlmaker.make_enumVar, 'userupa': 'user',
            'label': 'mask file', 'shelp': 'mask file used to exclude areas from motion detection'},
)

cameraFields=[
    {'app': 'camera', 'varlocal': 'resolution', 'fieldmaker': htmlmaker.make_enumVar, 'userupa':'user',
            'label': 'resolution',
            'shelp': 'camera resolution with standard values that try to use the full frame - only takes effect when camera (re)starts)',
            'webdetails': 'https://picamera.readthedocs.io/en/release-1.13/fov.html#camera-modes',},
    {'app': 'camera', 'varlocal': 'framerate',    'fieldmaker': htmlmaker.make_numVar, 'userupa':'user', 'updclass':  htmlmaker.varfloatupdater,
            'label': 'framerate', 'shelp': 'sets the framerate - note this limits the exposure time to 1/framerate'},
    {'app': 'camera', 'varlocal': 'rotation',     'fieldmaker': htmlmaker.make_enumVar, 'userupa':'user',
            'label': 'rotation', 'shelp': 'rotation applied to the image in 90 degree increments',
            'webdetails': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.rotation',},
    {'app': 'camera', 'varlocal': 'exposure_mode', 'fieldmaker': htmlmaker.make_enumVar, 'userupa':'user',
            'label': 'exposure mode', 'shelp':'camera exposure mode',
            'webdetails': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.exposure_mode'},
    {'app': 'camera', 'varlocal': 'meter_mode',   'fieldmaker': htmlmaker.make_enumVar, 'userupa':'user',
                'label': 'metering mode', 'shelp': 'exposure metering mode',
                'webdetails': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.meter_mode'},
    {'app': 'camera', 'varlocal': 'awb_mode',     'fieldmaker': htmlmaker.make_enumVar, 'userupa':'user',
            'label': 'white balance', 'shelp': 'camera white balance mode',
            'webdetails': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.awb_mode'},
    {'app': 'camera', 'varlocal': 'drc_strength', 'fieldmaker': htmlmaker.make_enumVar, 'userupa':'user',
                'label': 'dynamic range compression', 'shelp': 'dynamic range compression mode',
                'webdetails': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.drc_strength'},
    {'app': 'camera', 'varlocal': 'contrast',     'fieldmaker': htmlmaker.make_numVar, 'updclass': htmlmaker.varintupdater, 'userupa':'user',
                'label':'contrast', 'shelp':'sets contrast (-100 to +100, 0 is default)',
                'webdetails': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.contrast'},
    {'app': 'camera', 'varlocal': 'brightness',   'fieldmaker': htmlmaker.make_numVar, 'updclass': htmlmaker.varintupdater, 'userupa':'user',
                'label':'brighness', 'shelp':'sets brightness (0 to 100, 50 is default)',
                'webdetails': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.brightness'},
    {'app': 'camera', 'varlocal': 'exp_comp',     'fieldmaker': htmlmaker.make_numVar, 'updclass': htmlmaker.varintupdater, 'userupa':'user',
                'label':'exp compensation', 'shelp':'sets exposure compensation in 1/6th stop increments from -4 1/6 stops to +4 1/6 stops)',
                'webdetails': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.exposure_compensation'},
]
if BRIGHTPI:
    cameraFields.append(
         {'app': 'camera', 'varlocal': 'lights',       'fieldmaker': htmlmaker.make_enumVar, 'userupa':'user',
                'label': 'brightpi LEDs', 'shelp': 'controls brightpi LEDs',})

streamingFields=(
    {'app': 'camera', 'varlocal': 'status', 'fieldmaker': htmlmaker.make_enumVar, 'liveupa': 'driver',
            'label': 'status', 'shelp': 'streaming activity status'},
    {'app': 'camera', 'varlocal': 'width', 'fieldmaker': htmlmaker.make_numVar, 'updclass': htmlmaker.varintupdater, 'userupa':'user',
            'label': 'video width', 'shelp': 'camera output resized for streaming',
            'webdetails': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.start_recording'},
    {'app': 'camera', 'varlocal': 'height', 'fieldmaker': htmlmaker.make_numVar, 'updclass': htmlmaker.varintupdater, 'userupa':'user',
            'label': 'video height', 'shelp': 'camera output resized for streaming',
            'webdetails': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.start_recording'},
    {'app': 'camera', 'varlocal': 'lastactive', 'fieldmaker': htmlmaker.make_timeVar, 'liveupa': 'driver', 
            'label': 'last active at', 'shelp': 'last time streaming was active - not totally up to date when stream is running'},
)

gpioFields=(
    {'app': 'camera', 'varlocal': 'status', 'fieldmaker': htmlmaker.make_enumVar, 'liveupa': 'driver',
            'label': 'status', 'shelp': 'gpio trigger activity status'},
    {'app': 'camera', 'varlocal': 'startstop', 'fieldmaker': htmlmaker.make_enumBtn, 'userupa':'user', 'liveupa': 'driver',
            'label': 'start / stop', 'shelp': 'start / stop trigger on gpio'},
    {'app': 'camera', 'varlocal': 'lasttrigger', 'fieldmaker': htmlmaker.make_timeVar, 'liveupa': 'driver',
            'label': 'last trigger time', 'shelp': 'last time gpio pin triggered'},
    {'app': 'camera', 'varlocal': 'pinno', 'fieldmaker': htmlmaker.make_numVar, 'updclass': htmlmaker.varintupdater, 'userupa':'user',
            'label': 'gpio pin', 'shelp': 'broadcom pin to monitor'},
    {'app': 'camera', 'varlocal': 'pullud', 'fieldmaker': htmlmaker.make_enumVar, 'userupa':'user',
            'label': 'pullup/down/off', 'shelp': 'sets the pullup for the monitored pin',
            'webdetails': 'http://abyz.me.uk/rpi/pigpio/python.html#set_pull_up_down'},
    {'app': 'camera', 'varlocal': 'triglvl', 'fieldmaker': htmlmaker.make_enumVar, 'userupa':'user',
            'label': 'trigger level', 'shelp': 'gpio trigger activity status'},
    {'app': 'camera', 'varlocal': 'trigcount', 'fieldmaker': htmlmaker.make_numVar, 'updclass': htmlmaker.varintupdater, 'liveupa': 'driver',
            'label': 'number of triggers', 'shelp': 'count of times triggered this session'},
    {'app': 'camera', 'varlocal': 'lastactive', 'fieldmaker': htmlmaker.make_timeVar, 'liveupa': 'driver',
            'label': 'last enabled', 'shelp': 'last time the watching enabled'},
)

recordfields=(
    {'app': 'camera', 'varlocal': 'status', 'fieldmaker': htmlmaker.make_enumVar, 'liveupa': 'driver',
            'label': 'status', 'shelp': 'recorder activity status'},
    {'app': 'camera', 'varlocal': 'cpudetect', 'fieldmaker': htmlmaker.make_enumVar, 'userupa':'user',
            'label': 'use cpu detection', 'shelp':'uses the cpu movement triggered flag to trigger recording (only works if cpu movement detection  status is on)'},
    {'app': 'camera', 'varlocal': 'gpiodetect', 'fieldmaker': htmlmaker.make_enumVar, 'userupa':'user',
            'label': 'use gpio detection', 'shelp': 'uses gpio level flag to trigger recording (only works if gpio triggering status is on)'},
    {'app': 'camera', 'varlocal': 'startstop', 'fieldmaker': htmlmaker.make_enumBtn, 'userupa':'user', 'liveupa': 'driver',
            'label': 'start / stop', 'shelp': 'start / stop record when triggered'},
    {'app': 'camera', 'varlocal': 'recordcount', 'fieldmaker': htmlmaker.make_numVar, 'updclass': htmlmaker.varintupdater, 'liveupa': 'driver',
            'label': 'number of triggers', 'shelp': 'count of times triggered this session'},
    {'app': 'camera', 'varlocal': 'lastactive', 'fieldmaker': htmlmaker.make_timeVar, 'liveupa': 'driver',
            'label': 'last enabled', 'shelp': 'last time the triggering enabled'},
    {'app': 'camera', 'varlocal': 'lasttrigger', 'fieldmaker': htmlmaker.make_timeVar, 'liveupa': 'driver',
            'label': 'last trigger time', 'shelp': 'last time a recording started'},
    {'app': 'camera', 'varlocal': 'recordnow', 'fieldmaker': htmlmaker.make_enumBtn, 'userupa':'user', 'liveupa': 'driver',
            'label': 'record now', 'shelp': "start recording now (only works when status is 'on'"},
    {'app': 'camera', 'varlocal': 'width', 'fieldmaker': htmlmaker.make_numVar, 'updclass': htmlmaker.varintupdater, 
            'label': 'video width', 'shelp': 'camera output resized for recording',
            'webdetails': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.start_recording'},
    {'app': 'camera', 'varlocal': 'height', 'fieldmaker': htmlmaker.make_numVar, 'updclass': htmlmaker.varintupdater,
            'label': 'video height', 'shelp': 'camera output resized for recording',
            'webdetails': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.start_recording'},
    {'app': 'camera', 'varlocal': 'saveX264', 'fieldmaker': htmlmaker.make_enumVar, 'userupa':'user',
            'label': 'saveX264', 'shelp': 'keeps the X264 video files after mp4 conversion (otherwise they are deleted)'},
    {'app': 'camera', 'varlocal': 'recordback', 'fieldmaker': htmlmaker.make_numVar, 'updclass': htmlmaker.varfloatupdater, 'userupa':'user',
            'label': 'pre-trigger time', 'shelp': 'saves video for (roughly) specified period before the trigger happened (seconds) - values less than .25 s may not work'},
    {'app': 'camera', 'varlocal': 'recordfwd', 'fieldmaker': htmlmaker.make_numVar, 'updclass': htmlmaker.varfloatupdater, 'userupa':'user',
            'label':'post trigger time', 'shelp': 'saves video for this period after trigger condition ceases'},
    {'app': 'camera', 'varlocal': 'vidfold', 'fieldmaker': htmlmaker.make_strVar, 'userupa':'user',
            'label': 'base folder', 'shelp': 'base folder for recorded videos'},
    {'app': 'camera', 'varlocal': 'vidfile', 'fieldmaker': htmlmaker.make_strVar, 'userupa':'user',
            'label': 'filename', 'shelp':'file within basefold for videos - include \\ for subfolders'},
)

cpumovefields=(
    {'app': 'camera', 'varlocal': 'status', 'fieldmaker': htmlmaker.make_enumVar, 'liveupa': 'driver',
            'label': 'status', 'shelp': 'move detection activity status'},
    {'app': 'camera', 'varlocal': 'startstop', 'fieldmaker': htmlmaker.make_enumBtn, 'userupa':'user', 'liveupa': 'driver',
            'label': 'start / stop', 'shelp': 'start / stop movement detection'},
    {'app': 'camera', 'varlocal': 'autostart', 'fieldmaker': htmlmaker.make_enumVar, 'userupa':'user',
            'label': 'autostart', 'shelp': 'starts move detection automatically when app starts'},
    {'app': 'camera', 'varlocal': 'width', 'fieldmaker': htmlmaker.make_numVar, 'updclass': htmlmaker.varintupdater,
            'label': 'video width', 'shelp': 'camera output resized for cpu movement analysis',
            'webdetails': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.start_recording'},
    {'app': 'camera', 'varlocal': 'height', 'fieldmaker': htmlmaker.make_numVar, 'updclass': htmlmaker.varintupdater,
            'label': 'video height', 'shelp': 'camera output resized for cpu movement analysis',
            'webdetails': 'https://picamera.readthedocs.io/en/release-1.13/api_camera.html#picamera.PiCamera.start_recording'},
    {'app': 'camera', 'varlocal': 'imagemode', 'fieldmaker': htmlmaker.make_enumVar, 'userupa':'user',
            'label': 'image mode', 'shelp': 'defines if image analysis used rgb or yuv encoded data (only used on activity start)'},
    {'app': 'camera', 'varlocal': 'imagechannel', 'fieldmaker': htmlmaker.make_enumVar, 'userupa':'user',
            'label': 'image channel', 'shelp': 'Only a single channel of the image is analysed for motion: 0 -> R or Y, 1 -> G or U, 2 -> B or V. Use R for night mode with IR cameras.'},
    {'app': 'camera', 'varlocal': 'cellthresh', 'fieldmaker': htmlmaker.make_numVar, 'updclass': htmlmaker.varintupdater, 'userupa':'user',
            'label': 'pixel threshold', 'shelp': 'difference in pixel value to count as changed pixel'},
    {'app': 'camera', 'varlocal': 'celltrigcount', 'fieldmaker': htmlmaker.make_numVar, 'updclass': htmlmaker.varintupdater, 'userupa':'user',
            'label': 'cell count', 'shelp': 'Number of cells over threshold needed to trigger'},
    {'app': 'camera', 'varlocal': 'latchtime', 'fieldmaker': htmlmaker.make_numVar, 'updclass': htmlmaker.varfloatupdater, 'userupa':'user',
            'label': 'latch time', 'shelp': 'trigger only releases after no movement for this time'}, 
    {'app': 'camera', 'varlocal': 'maskfold', 'fieldmaker': htmlmaker.make_strVar, 'userupa':'user',
            'label': 'mask files folder', 'shelp': 'folder containing mask files'},
    {'app': 'camera', 'varlocal': 'maskfile', 'fieldmaker': htmlmaker.make_enumVar, 'userupa':'user',
            'label': 'mask file', 'shelp': 'mask file used to exclude areas from motion detection'},

    {'app': 'camera', 'varlocal': 'triggercount', 'fieldmaker': htmlmaker.make_numVar, 'updclass': htmlmaker.varintupdater, 'liveupa': 'driver',
            'label': 'triggercount', 'shelp': 'count of times triggered this session'},        
    {'app': 'camera', 'varlocal': 'lastactive', 'fieldmaker': htmlmaker.make_timeVar, 'liveupa': 'driver',
            'label': 'last enabled', 'shelp': 'last time the analysis enabled'},
    {'app': 'camera', 'varlocal': 'lasttrigger', 'fieldmaker': htmlmaker.make_timeVar, 'liveupa': 'driver',
            'label': 'last trigger time', 'shelp': 'last time movement detected'},
    {'app': 'camera', 'varlocal': 'skippedcount', 'fieldmaker': htmlmaker.make_numVar, 'updclass': htmlmaker.varintupdater, 'liveupa': 'driver',
            'label': 'dropped', 'shelp': 'The number of frames that did not get analysed because the analyser was busy'},
    {'app': 'camera', 'varlocal': 'analysedcount', 'fieldmaker': htmlmaker.make_numVar, 'updclass': htmlmaker.varintupdater, 'liveupa': 'driver',
            'label': 'analysed', 'shelp': 'The number of frames analysed'},
    {'app': 'camera', 'varlocal': 'overruns', 'fieldmaker': htmlmaker.make_numVar, 'updclass': htmlmaker.varintupdater, 'liveupa': 'driver',
            'label': 'buffer overruns', 'shelp': 'number of frames discarded from analysis queue'},
    {'app': 'camera', 'varlocal': 'analbusy', 'fieldmaker': htmlmaker.make_numVar, 'updclass': htmlmaker.varfloatupdater, 'liveupa': 'driver',
            'updparams': {'updateformat': '{varval:4.2f}'}, 'label': 'analyse busy', 'shelp': 'analysis thread busy time'},
    {'app': 'camera', 'varlocal': 'analcpu', 'fieldmaker': htmlmaker.make_numVar, 'updclass': htmlmaker.varfloatupdater, 'liveupa': 'driver',
            'updparams': {'updateformat': '{varval:4.2f}'}, 'label': 'analyse cpu', 'shelp': 'analysis thread cpu %age'},
)

sectwrap="""<tr {bodyatt}><td colspan="3" class="sectheadtext" >{title}
                <span class="sectheadoc" onclick="flipme('{gtag}', '{gtag}x')"><img class="cbtn" id="{gtag}x" src="opendnarrow.svg" /></span></td></tr>\n
                <tbody id="{gtag}" {bodyatt} style="display: none;">{fs}</tbody>\n"""

page4={
    'defs': [
        ('camsettings', htmlmaker.make_list_group, {
            'defs'          : cameraFields,
            'fieldfunc'     : htmlmaker.make_table_field,
            'varprefix'     : 'camsettings',
            'groupname'     : 'fs',
            'outerparams'   : {'bodyatt': 'class="camsetstyle"', 'title': 'Camera Settings', 'gtag': 'xcamset'},
            'outerwrap'     : sectwrap,}),
        ('streamsettings', htmlmaker.make_list_group, {
            'defs'          : streamingFields,
            'fieldfunc'     : htmlmaker.make_table_field,
            'varprefix'     : 'activities/camstream',
            'groupname'     : 'fs',
            'outerparams'   : {'bodyatt': 'class="camstreamstyle"', 'title': 'Live stream Settings', 'gtag': 'xstreamset'},
            'outerwrap'     : sectwrap,}),
        ('gpioSettings', htmlmaker.make_list_group, {
            'defs'          : gpioFields,
            'fieldfunc'     : htmlmaker.make_table_field,
            'varprefix'     : 'activities/gpio_trigger',
            'groupname'     : 'fs',
            'outerparams'   : {'bodyatt': 'class="gpio_triggerstyle"', 'title': 'gpio trigger settings', 'gtag': 'xgpioset'},
            'outerwrap'     : sectwrap,}),
        ('trigrecSettings', htmlmaker.make_list_group, {
            'defs'          : recordfields,
            'fieldfunc'     : htmlmaker.make_table_field,
            'varprefix'     : 'activities/trig_record',
            'groupname'     : 'fs',
            'outerparams'   : {'bodyatt': 'class="trig_recordstyle"', 'title': 'triggered recording settings', 'gtag': 'xtrigrecset'},
            'outerwrap'     : sectwrap,}),
        ('camrun', htmlmaker.make_strVar, {'app': 'camera', 'varname': 'camstate/camactive', 'liveupa': 'driver'}),
        ('camsumry', htmlmaker.make_numVar, {'app': 'camera', 'varname': 'camsettings/framerate', 'updclass': htmlmaker.varfloatupdater, 
                'liveupa': 'driver', 'fstring': '{nstr:4.2f}fps'}),
        ('saver', htmlmaker.make_enumVar, {'app': 'camera', 'varname': 'saveset', 'userupa':'user',}),
        ('camacthead', htmlmaker.makecameraactheads, {}),
        ('camactvals', htmlmaker.makecameraactstats, {}),
        ],
    'outerwrap': """
<html>
   <head>
       <script src="stat/pymon.js"></script>
       <script src="stat/pymask.js"></script>
       <script type="text/javascript">
            window.onload=startup

            function startup() {{
                liveupdates("{pageid}")
            }}
       </script>
        <link rel="stylesheet" href="stat/some.css">
   </head>
   <body><form autocomplete="off">
       <div class="overpnl">
           <div id="header">
               <table style="color:white;">
                   <tr><td class="camsetstyle" style="text-align: center;" >camera status</td>{camacthead}<td>{saver}</td><td rowspan="2"><span class="btnlike"><a href="filer.html">show videos</a></span></td></tr>\n
                   <tr><td class="camsetstyle" style="text-align: center;" >{camrun}</td>{camactvals}</tr>\n
                   <tr><td class="camsetstyle" style="text-align: center;" >{camsumry}</td></tr>\n
                   <tr><td colspan=4 id="appmessage">messages go here</td></tr>
               </table>
           </div>
           <div>
               <div>
                   <span onclick="livestreamflip(this)" title="click to start / stop live view" class="btnlike" style="width:135px" >show livestream</span>
                   <span onclick="detstreamflip(this)" title="click to start / stop cpu detection overlay" class="btnlike" style="width:135px" >show detection</span>
                   <span onclick="maskeditflip(this)" title="click to start / stop cpu mask edit" class="btnlike" style="width:135px" >edit mask</span>
               </div>
               <div style="position: relative; height: 480px; width: 640px;">
                    <img id="livestreamimg" src="stat/nocam.png" width="640px" height="480px" style="z-index:1;"/>
                    <div id="detstreamdiv" style="display:none; position:absolute; top:0px; left:0px; width:100%; height:100%; z-index:2;"></div>
                    <div id="livemaskdiv" style="display:none; position:absolute; top:0px; left:0px; width:100%; height:100%; z-index:3;">
                              <canvas id="livemaskcanv"></canvas>
                    </div>
               </div>
           </div>
       </div>
       <div class="stgpnl"><table style="border-spacing: 0px;">
           <col style="width:220px;">
           <col style="width:320px;">
           <col style="width:90px;">
           {camsettings}
           {streamsettings}
           {gpioSettings}
           {trigrecSettings}
           {cpumoveSettings}
       </table></div>
   </form></body>
</html>
"""
}
if 'cpumove' in enables:
    page4['defs'].append(
        ('cpumoveSettings', htmlmaker.make_list_group, {
            'defs'          : cpumovefields,
            'fieldfunc'     : htmlmaker.make_table_field,
            'varprefix'     : 'activities/cpumove',
            'groupname'     : 'fs',
            'outerparams'   : {'bodyatt': 'class="cpumovestyle"', 'title': 'cpu movement settings', 'gtag': 'xcpumset'},
            'outerwrap'     : sectwrap,}))


consolelogformat={
    'fmt'     : '%(asctime)s %(levelname)7s (%(process)d)%(threadName)12s  %(module)s.%(funcName)s: %(message)s',
    'datefmt' : "%M:%S",
}

filelogformat={
    'fmt'     : '%(asctime)s %(levelname)7s (%(process)d)%(threadName)12s  %(module)s.%(funcName)s: %(message)s',
    'datefmt' : "%H:%M:%S",
}

# set the loglevel - 10 for DEBUG, 20 for INFO, 40 for ERROR, 50 for FATAL (bigger the value, less is logged)
loglevel=10
# logfile='log.log'  # uncomment to use logfile

pistatApp   =sysinfo.systeminfo

cameraApp   =cameraManager(agentlist=('driver','user','device'), features=enables, parent=None, app=None, loglvl=10, logformat=consolelogformat)
foldapp     =fileManager(basefolder=cameraApp['activities/trig_record/vidfold'], agentlist=('driver', 'user'), parent=None, app=None, loglvl=10, logformat=consolelogformat)

config={
    'port'              : 8000,         # this is the port the webserver will respond to
    'serverclass'       : basicserver,  # class (derived from) threaded http server to run the http server
    'handlerclass'      : requHandler,  # class (derived from) http.server.BaseHTTPRequestHandler at least or probably httpserverbase.requHandler
    'GET'               : { # all valid gets and what to do with them 
        '/'                     : {'pagemaker': htmlmaker.make_group, 'params': page4},
        '/index.html'           : {'pagemaker': htmlmaker.make_group, 'params': page4},
        '/filer.html'           : {'pagemaker': foldapp.make_page, 'params': {}},
        '/test.html'            : {'static': '*'},
        '/test2.html'           : {'static': '*'},
        '/test3.html'           : {'static': '*'},
        '/test4.html'           : {'static': '*'},
        '/testv.html'           : {'static': '*'},
        '/testz.html'           : {'static': '*'},
        '/openuparrow.svg'      : {'static': '*'},
        '/opendnarrow.svg'      : {'static': '*'},
        '/updateSetting'        : {'updator': 17},
        '/pistatus'             : {'streamhandler': pistatApp},
        '/camstream.mjpg'       : {'camstreamhandler': cameraApp['activities/camstream'].getStream},
        '/updates'              : {'updatestreamhandler': 23},
        '/vs.html'              : {'pagemaker': foldapp.vidpage, 'params': {}},
        '/vs.mp4'               : {'vidstreamhandler': {'resolve': foldapp.resolvevidfile}},
        '/vx.mp4'               : {'static': '/home/pi/Videos/20/02/15/09_39_43.mp4'},
            },
    'staticroot'                : {'path':pathlib.Path(__file__).parent/'static', 'root':'/stat/'},
    'apps'                      : {'camera': cameraApp},
    'oncloseapps'               : (sysinfo.closeall, cameraApp.safeStopCamera),
    'POST'              : {
        
        },
}
if 'cpumove' in enables:
    config['GET']['/detstream.png']        = {'camstreamhandler': cameraApp['activities/cpumove'].getStream}
    config['GET']['/fetchmask']            = {'request': cameraApp['activities/cpumove'].fetchmaskinfo}
    config['POST']['/savemask']            = {'function': cameraApp['activities/cpumove'].savemask}