"""
This is an example config module for a pootleweb web server.

It provides all the info needed to start and run a webserver using pootleweb, with the various parts explained.

This module is loaded by webserv.py and various entries are used by webserv.py to start the webserver.

"""

import basichttpserver as httpbase   # this module should contain the classes httpserver and httprequh
import pathlib

import piCamHandleWeb
import folderapp
import sysinfo
from pootlestuff.watchables import loglvls

######################################################################################################
# The following fields are used directly by webserv.py
######################################################################################################

# set the loglevel - 10 for DEBUG, 20 for INFO, 40 for ERROR, 50 for FATAL (bigger the value, less is logged)
loglevel=10

# defines the log format used for logging direct to stderr. console log is switch on using -v param to webserv from
# the shell command. Without -v this is ignored.
consolelogformat={
    'fmt'     : '%(asctime)s %(levelname)7s (%(process)d)%(threadName)12s  %(module)s.%(funcName)s: %(message)s',
    'datefmt' : "%M:%S",
}

# a logfile can be specified in the shell command (-l) if the shell command option is specified it overrides any value here
# logfile='log.log'  # uncomment to use logfile 

#this specifies the port used for this web server
webport = 8000

# This is the class used to create the webserver
httpserverclass = httpbase.httpserver

# this is the class instantiated to handle each incoming http request
httprequestclass = httpbase.httprequh

###########################################################################
# The following defines the apps that are setup to support the web server #
###########################################################################

app1        =piCamHandleWeb.piCamWeb(loglevel=loglvls.DEBUG)
foldapp     =folderapp.fileManager(basefolder=app1.activities['triggervid'].vidfold)

config = {
    'staticroot'        : {'path':pathlib.Path(__file__).parent/'static', 'root':'/stat/'}, # specifies the folder in which static files are found
    'oncloseapps'       : (app1.safeStopCamera,),
    'GET'               : { # all valid GETs and what to do with them. each entry is a 2-tuple, with a keyword used by the httprequest handler to
                            # select how to process the request.
        'index.html'    : ('makedynampage', (app1.makeMainPage,{})),
        'filer.html'    : ('makedynampage', (foldapp.make_page, {})),
        'pistatus'      : ('updatestream',  (sysinfo.getsystemstats,{})),
        'appupdates'    : ('updatestream',  ('serv', 'getupdates')),
        'updateSetting' : ('updatewv', 0),
        'camstream.mjpg': ('camstream', app1.activities['camstream'].getStream),
        'vs.mp4'        : ('vidstream', {'resolve': foldapp.resolvevidfile}),
    }
}