#!/usr/bin/python3

import logging

serverdef={
    'port':8000,            # this is the port the webserver will respond to
    'sfxlookup':{
        '.css' :('Content-Type', 'text/css; charset=utf-8'),
        '.html':('Content-Type', 'text/html; charset=utf-8'),
        '.js'  :('Content-Type', 'text/javascript; charset=utf-8'),
        '.ico' :('Content-Type', 'image/x-icon'),
        '.py'  :('Content-Type', 'text/html; charset=utf-8'),   # python template files we assume return html for now
        '.jpg' :('Content-Type', 'image/jpeg'),
        '.png' :('Content-Type', 'image/png'),
        '.mp4' :('Content-Type', 'video/mp4'),
        },
    'servefrom' : {         # paths static files relative to cwd
            'static'  : 'static',        # the default folder for entries with no 'foldname' key
            'template': 'templates',     # files that are processed before use
            },
    'getpaths' : {          # paths to be handled by pywebhandler.do_GET for GETs
            'nocam.png'      : {'pagetype': 'static',      'pagefile': 'nocam.png'},
            'camweb.css'     : {'pagetype': 'static',      'pagefile': 'camweb.css'},
            'smoothie.js'    : {'pagetype': 'static',      'pagefile': 'smoothie.js'},
            'pipyscripts.js' : {'pagetype': 'static',      'pagefile': 'pipyscripts.js', 'log':0},
            'pimaskedit.js'  : {'pagetype': 'static',      'pagefile': 'pimaskedit.js'},
            'newweb.js'      : {'pagetype': 'static',      'pagefile': 'newweb.js'},
            'test.html'      : {'pagetype': 'static',      'pagefile': 'testmain.html'},
            'favicon.ico'    : {'pagetype': 'static',      'pagefile': 'rasppi.ico', 'log':0},
            'streamstats'    : {'pagetype': 'genstream',   'obid': 'pootlecam', 'func': 'streamstates', 'period': 5.45},
            'pistatus'       : {'pagetype': 'genstream',   'obid': 'pistat', 'period': 1.9},
            ''               : {'pagetype': 'appPage',     'obid': 'pootlecam', 'func': 'topPage'},
            'index.html'     : {'pagetype': 'appPage',     'obid': 'pootlecam', 'func': 'topPage'},
            'vstream.mjpg'   : {'pagetype': 'vidstream',   'obid': 'pootlecam', 'func': 'startLiveStream'},
            'detstream.mjpg' : {'pagetype': 'vidstream',   'obid': 'pootlecam', 'func': 'startDetectStream'},
            'updateSetting'  : {'pagetype': 'datafunc',    'obid': 'pootlecam', 'func': 'updateSetting'},
            'dynupdates'     : {'pagetype': 'dynupdates'},
            'fetchmask'      : {'pagetype': 'datafunc',    'obid': 'pootlecam', 'func': 'fetchmask'},
            'settings'       : {'pagetype': 'download',    'obid': 'pootlecam', 'func': 'fetchSettings'},
            'setdefaults'    : {'pagetype': 'datafunc',    'obid': 'pootlecam', 'func': 'saveDefaultSettings'},
            },
    'postpaths': {          # paths to be handled by do_POST
            'setSettings'    : {'pagetype': 'upload',      'obid': 'pootlecam', 'func': 'putSettings'},
            'setdetectmask'  : {'pagetype': 'datafunc',    'obid': 'pootlecam', 'func': 'setdetectmask'},
        },
    'obdefs'   : {
        'pistat'        : {'ondemand': {'className': 'utils.systeminfo', 'fields': ('busy', 'cputemp')}},
        'pootlecam'     : {'setup'   : {'className': 'piCamWeb.testcam2', 'webserver': None, 'loglvl':logging.DEBUG}},
        },
}
