#!/usr/bin/python3

import os, sys, time, argparse, pathlib, importlib, socket, errno, json, logging, traceback, threading
from urllib.parse import urlparse, parse_qs
import http.server
from socketserver import ThreadingMixIn
import utils

def logException(log, text1, excInfo):
    if not log is None:
        exc_type, exc_value, exc_traceback=excInfo
        log.critical('exception {} in {}\n    value: {}\n{}'.format(str(exc_type), text1, str(exc_value), '\n'.join(traceback.format_tb(exc_traceback))))

    
#     exc_type, exc_value, exc_traceback = sys.exc_info()
#        print( {'fail': 'exception', 'type':str(exc_type), 'value':str(exc_value)
#                , 'trace':(''.join(traceback.format_tb(exc_traceback)) )
#                , 'fromlink':0})

appobpages=('appPage', 'vidstream', 'genstream', 'datafunc','download', 'upload')
        # pathdef pagetypes that refer to an object to be used

appobfuncs=('appPage', 'vidstream', 'datafunc', 'download', 'upload')
        #pathdef pagetypes that name an object method to call

class pywebhandler(http.server.BaseHTTPRequestHandler):
    def breakdown(self, requtype):
        pr = urlparse(self.path)
        pf = pr.path.split('/')
        params = parse_qs(pr.query) if pr.query else {}
        pname=pf[-1]
        serverconf=self.server.mypyconf
        if pname in serverconf[requtype]:
            pathdef=serverconf[requtype][pname]         # fetch the info / definition about this path
            if 'obid' in pathdef:                                   # if this needs access to a named object, get hold of the object
                obid=pathdef['obid']
                if obid in self.server.mypyobjects:
                    targetob=self.server.mypyobjects[obid]
                else:
                    #try and setup the object
                    targetob=None
                    if obid in serverconf['obdefs']:
                        if 'ondemand' in serverconf['obdefs'][obid]:
                            obdef=serverconf['obdefs'][obid]['ondemand']
                            params = {k:v if len(v)>1 else v[0] for k, v in  params.items()}
                            params.update(obdef)
                            targetob=utils.makeClassInstance(**params)
                            self.server.mypyobjects[obid]=targetob
                        else:
                            print("no ondemand info for object", obid)
                            return False, 500,'object setup error - object info for %s not found' % pname
                    else:
                        print("failed to find object definition for % in config['obdefs']" % obid)
                        return False, 500, 'object setup error - object for %s not found' % pname
            else:
                targetob=None
            pagetype=pathdef.get('pagetype', None)
            if pagetype in appobpages and targetob is None:
                print('missing object / object id in path %s with pathdef %s' % (pname, str(pathdef)))
                return False, 500, 'app setup error - no function specified'
            if pagetype in appobfuncs:
                if not 'func' in pathdef:
                    print("no 'func' value available in pathdef for", pname) 
                    return False, 500, 'app setup error - no function specified'
                ofunc=getattr(targetob, pathdef['func'])
                if not callable(ofunc):
                    print("the attribute %s in object %s (of type (%s) is not callable" % (pathdef['datafunc'], str(targetob), type(targetob).__name__))
                    return False, 500, 'page {} does not reference a callable'.format(pname)
            else:
                ofunc=None
            return True, pname, pathdef, pagetype, targetob, ofunc, params
        else:
            print('pywebhandler.do_GET/POST rejected', pf, 'no entry in paths')
            return False, 404, 'unknown page {} requested'.format(pname)

    def do_POST(self):
        pathchecked=self.breakdown('postpaths')
        if pathchecked[0]:
            pname, pathdef, pagetype,  targetob, ofunc, params = pathchecked[1:]
            th=self.headers['Content-Type']
            if th=='application/json':
                dlength=int(self.headers['Content-Length'])
                ddata=self.rfile.read(dlength)
                if len(ddata) != dlength:
                    print("HELEPELPELPELEPLEPELEPLE")
                    self.send_error(501,'oops')
                else:
                    jdata=json.loads(ddata.decode('utf-8'))
                    result=ofunc(jdata)
                    # result is a dict with:
                    #   resp: the response code - if 200 then good else bad
                    #   rdata: (only if resp==200) data (typically a dict) to json encode and return as the data
                    #   rmsg: (only if resp != 200) the message to return with the fail code
                    if result['resp']==200:
                        datats=json.dumps(result['rdata'])
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json; charset=utf-8')
                        self.end_headers()
                        self.wfile.write(datats.encode('utf-8'))
                    else:
                        self.send_error(result['resp'], result['rmsg'])
            else:
                boundary = th.split("=")[1]
                bytesleft = int(self.headers['Content-length'])
                line = self.rfile.readline().decode("utf-8")
                bytesleft-= len(line)
                if not boundary in line:
                    self.send_error(505,'Content NOT begin with boundary')
                    return
                line = self.rfile.readline().decode("utf-8")
                bytesleft-= len(line)
                while not line.startswith('{'):
                    line = self.rfile.readline().decode("utf-8")
                    bytesleft-= len(line)
                updata=line
                while len(updata) < bytesleft:
                    line = self.rfile.readline().decode("utf-8")
                    bpos=line.find(boundary)
                    if bpos==-1:
                        updata+=line
                    else:
                        bytesleft -= len(line)
                        if bytesleft>len(updata):
                            print('puzzled bytesleft {}, data length {}'.format(bytesleft, len(updata)))
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(b'ok')
                ofunc(updata)
        else:
            self.send_error(pathchecked[1],pathchecked[2])
        

    def do_GET(self):
        """
        There are just a few basic paths that this uses (the part after the host:port and before the '?'):
            <empty>: uses the 'defaultgetpage' entry in the server parameters
            'runm' : 
        """
        pathchecked=self.breakdown('getpaths')
        if pathchecked[0]:
            pname, pathdef, pagetype,  targetob, ofunc, params = pathchecked[1:]
            if 'datafunc'==pagetype:
                try:
                    result = ofunc(**params)
                except:
                    logException(self.server.log, 'failed handling {}'.format(pname), sys.exc_info())
                    self.send_error(500,'do get datafunc call crashed')
                    return
                # result is a dict with:
                #   resp: the response code - if 200 then good else bad
                #   rdata: (only if resp==200) data (typically a dict) to json encode and return as the data
                #   rmsg: (only if resp != 200) the message to return with the fail code
                if result['resp']==200:
                    datats=json.dumps(result['rdata'])
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(datats.encode('utf-8'))
                else:
                    self.send_error(result['resp'], result['rmsg'])

            elif 'static'==pagetype:
                staticfilename=self.server.p_filepath(presetfolder=pathdef.get('folder','static'), filepart=pathdef.get('pagefile', 'nopage'))
                sfx=staticfilename.suffix
                self.send_response(200)
                self.send_header(*serverconf['sfxlookup'][sfx])
                self.end_headers()
                with staticfilename.open('rb') as sfile:
                    cont=sfile.read()
                    self.wfile.write(cont)
                if 'log' in pathdef:
                    if self.server.loglvl <= logging.DEBUG:
                        self.server.log.debug('pywebhandler.do_GET file {} length {} sent in response to {} using headers {} using.'.format(
                            str(staticfilename), len(cont), pname, str(serverconf['sfxlookup'][sfx]), pathdef) )

            elif 'appPage'==pagetype:
                try:
                    cont, psuffix = ofunc(**params)
                    self.send_response(200)
                    self.send_header(*serverconf['sfxlookup'][psuffix])
                    self.end_headers()
                    self.wfile.write(cont.encode())
                    if 'log' in pathdef:
                        if self.server.loglvl <= logging.DEBUG:
                            self.server.log.debug('pywebhandler.do_GET appPage called {} length {} sent in response to {} using headers {} using.'.format(
                                pathdef['func'], len(cont), pname, str(serverconf['sfxlookup'][psuffix]), pathdef) )
                except:
                    logException(self.server.log, 'failed handling {}'.format(pname), sys.exc_info())
                    self.send_error(500,'do get datafunc call crashed')
            elif 'vidstream'==pagetype:
                output=ofunc()
                self.send_response(200)
                self.send_header('Age', 0)
                self.send_header('Cache-Control', 'no-cache, private')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
                self.end_headers()
                try:
                    while True:
                        with output.condition:
                            output.condition.wait()
                            frame = output.frame
                        self.wfile.write(b'--FRAME\r\n')
                        self.send_header('Content-Type', 'image/jpeg')
                        self.send_header('Content-Length', len(frame))
                        self.end_headers()
                        self.wfile.write(frame)
                        self.wfile.write(b'\r\n')
                except BrokenPipeError:
                    pass
                except Exception as e:
                    logException(self.server.log, 'Removed streaming client %s: %s' % (self.client_address, str(e)), sys.exc_info())
                targetob.stopLiveStream()

            elif 'genstream'==pagetype:
                if 'func' in pathdef:
                    ofunc=getattr(targetob, pathdef['func'])
                    if not callable(ofunc):
                        if not self.server.log is None:
                            self.server.log.critical("the attribute %s in object %s (of type (%s) is not callable" % (
                                    pathdef['datafunc'], str(targetob), type(targetob).__name__))
                        self.send_error(500,'page {} does not reference a callable'.format(pname))
                    else:
                        sequob=ofunc()
                else:
                    sequob=targetob
                tickinterval=pathdef['period']
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
                self.end_headers()
                running=True
                while running:
                    datats=json.dumps(next(sequob))
                    try:
                        self.wfile.write(('data: %s\n\n' % datats).encode('utf-8'))
                    except Exception as e:
                        running=False
                        if e.errno!=errno.EPIPE:
                            raise
                        else:
                            print(type(e).__name__)
                            print('genstream client %s terminated' % str(self.client_address))
                    time.sleep(tickinterval)
            elif 'dynupdates'==pagetype:
                if self.server.requestDynUpdates():
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
                    self.end_headers()
                    lasttime=0
                    running=True
                    while True:
                        upcount=self.server.getCountSince(lasttime)
                        time.sleep(.5)
                        tickat=time.time()
                        if upcount>0:
                            dupd=json.dumps(self.server.getUpdatesSince(lasttime))
                            try:
                                self.wfile.write(('data: %s\n\n' % dupd).encode('utf-8'))
                                print('webserv sends updates', dupd)
                            except Exception as e:
                                print('webserv sends updates FAILS', dupd)
                                running=False
                                if e.errno!=errno.EPIPE:
                                    self.server.stopDynUpdates()
                                    raise
                                else:
                                    print(type(e).__name__)
                                    print('dynamic updates finished')
                            lasttime=tickat
                        elif tickat > lasttime+8:
                            lasttime=tickat
                            try:
                                self.wfile.write(('data: kwac\n\n').encode('utf-8'))
                            except Exception as e:
                                print('webserv kwac for updates FAILS')
                                running=False
                                if e.errno!=errno.EPIPE:
                                    self.server.stopDynUpdates()
                                    raise
                                else:
                                    print(type(e).__name__)
                                    print(e)
                                    print('dynamic updates finished')
                                    return
                    self.server.stopDynUpdates()            
                else:
                    self.send_error(405,'no dynamic update stream')
            elif 'download'==pagetype:
                resp = ofunc(**params)
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.send_header('Content-Disposition', 'attachment;filename=\"settings.txt\"')
                self.end_headers()
                self.wfile.write(resp.encode('utf-8'))
            else:
                if not self.server.log is None:
                    self.server.log.critical('pywebhandler.do_GET unsupported pagetype in path definition:', pathdef)
                self.send_error(500,'something went a bit wrong!')
        else:
            self.send_error(pathchecked[1],pathchecked[2])

class ThreadedHTTPServer(ThreadingMixIn, http.server.HTTPServer):
    """
    Handle requests in a separate thread.
    
    This allows multiple pages to be in progress, and in particular it allows the webserver to send out an event stream for extended periods
    without blocking other requests.
    
    Also it allows queues of status messages to be setup which are served up as event streams on request. No session control etc. here though
    """
    def __init__(self, *args,  loglvl=logging.INFO, mypyconf, **kwargs):
        super().__init__(*args, **kwargs)
        self.log=None if loglvl is None else logging.getLogger(__loader__.name+'.'+type(self).__name__)
        self.loglvl=1000 if loglvl is None else loglvl
        self.mypyconf=mypyconf
        self.mypyobjects={}
        self.dynupdates=[]
        if 'obdefs' in self.mypyconf:
            descs=[]
            for oname, odef in self.mypyconf['obdefs'].items():
                if 'setup' in odef:
                    setupparams=odef['setup']
                    if 'webserver' in setupparams:
                        setupparams=setupparams.copy()
                        setupparams['webserver']=self
                    self.mypyobjects[oname]=utils.makeClassInstance(**setupparams)
                    descs.append('%s:(%s)' %(oname, type(self.mypyobjects[oname]).__name__))
                else:
                    assert 'ondemand' in odef
                    descs.append('%s will be setup on demand' % oname)
            smsg='added objects', ', '.join(descs)
        else:
            smsg='no associated objects created'
        if self.loglvl <= logging.INFO:
            self.log.info(smsg)
        self.validateConfig()           # does some setup as well
        

    def requestDynUpdates(self):
        """
        returns true if dynamic update stream available
        """
        return True
        
    def getCountSince(self, atime):
        """
        returns 1 if there are any updates since the given time
        """
        return 1 if len(self.dynupdates) > 0 and self.dynupdates[-1][0] > atime else 0

    def getUpdatesSince(self, atime):
        """
        returns a list of 2-tuples with entry 0 as the field id and 1 as the value
        """
        return [ent[1] for ent in self.dynupdates if ent[0] > atime]

    def stopDynUpdates(self):
        """
        cancels an interest in dynamic updates
        """
        pass

    def addDynUpdate(self, id, value):
        dropidx=None
        for idx, ent in enumerate(self.dynupdates):
            if id==ent[1][0]:
                dropidx=idx
                break
        if not dropidx is None:
            self.dynupdates.pop(dropidx)
            if self.loglvl <= logging.DEBUG:
                self.log.debug('dynupdates: previous {} dropped'.format(id))
        self.dynupdates.append((time.time(),(id,value)))
        if len(self.dynupdates) > 50:
            self.dynupdates.pop(0)

    def close(self): 
        self.socket.close()
        for appob in self.mypyobjects.values():
            try:
                appob.close()
            except:
                pass

    def validateConfig(self):
        self.mypyfolders={}
        if 'servefrom' in self.mypyconf:
            for k,v in self.mypyconf['servefrom'].items():
                p=pathlib.Path(v)
                if p.is_dir():
                    self.mypyfolders[k]=p
                else:
                    raise ValueError('the folder %s in config file entry servefrom for key %s is not a folder' % (v,k))
        if not 'getpaths' in self.mypyconf:
            raise ValueError('getpaths not found in config')
        for pn, pd in self.mypyconf['getpaths'].items():
            self.validPathdef(pn, pd)
        if 'postpaths' in self.mypyconf:
            for pn, pd in self.mypyconf['getpaths'].items():
                self.validPathdef(pn, pd)

    def validPathdef(self, pn, pd):
        if not 'pagetype' in pd:
            raise ValueError("missing 'pagetype' in config['pathdefs'] for %s" % pn)
        ptype=pd['pagetype']
        if ptype=='static':
            sfile = self.validateFile(pn, pd)
        elif ptype=='dynupdates':
            pass
        elif ptype in appobpages:
            if not 'obid' in pd:
                raise ValueError("'obid' in definition getpaths['{}'] not found in configuration 'obdefs'.".format(pn))
            if ptype in appobfuncs:
                if not 'func' in pd:
                    raise ValueError("'func' in definition getpaths['{}'] not found in configuration 'obdefs'.".format(pn))
                if pd['obid'] in self.mypyobjects: # if not dynamic object....... check func present
                    if not hasattr(self.mypyobjects[pd['obid']], pd['func']):
                        raise ValueError("failed to find method {} in object {} of class {}".format(pd['func'], pd['obid'],
                                type(self.mypyobjects[pd['obid']]).__name__))
            if ptype=='genstream':
                if not 'period' in pd:
                    raise ValueError("no 'period' found in pathdef for", pn) 
        else:
            raise ValueError("unknown pagetype %s in config['pathdefs'] %s"% (ptype, pn))

    def validateFile(self, pn, pd):
        if not 'pagefile' in pd:
            raise ValueError("no 'pagefile' entry is config['pathdefs'] %s" % pn)
        fname=pd.get('folder', 'static')
        if not fname in self.mypyfolders:
            raise ValueError("'folder' entry ( none or %s) in confid['pathdefs'] %s not found in config['servefrom']" % (fname, pn))
        sfile=self.mypyfolders[fname]/pd['pagefile']
        if not sfile.is_file():
            try:
                fp=sfile.absolute()
            except:
                fp=p
            raise ValueError("unable to locate file %s referenced from config['pathdefs'] %s using servefrom folder %s" % (str(fp), pn, pd.get('folder', 'static')))
        if not sfile.suffix in self.mypyconf['sfxlookup']:
            raise ValueError("unknown suffix %s in file %s reference from config['pathdefs'] %s - no entry in sfxlookup" % (sfile.suffix, str(sfile), pn))
        return sfile

    def p_filepath(self, presetfolder, filepart):
        return server.mypyfolders[presetfolder]/filepart

if __name__ == '__main__':
    clparse = argparse.ArgumentParser(description='runs a simple python webserver.')
    clparse.add_argument('-c', '--config', help='path to configuration file.')
    clparse.add_argument('-l', '--logfile', help='if present sets logging to log to this file')
    clparse.add_argument('-v', '--consolelog', default=1000, type=int, help='level of logging for the console log (stderr), if absent there is no console log')
    clparse.add_argument('-i', '--interactive', action='store_true', help='run webserver in separate thread to allow interaction with python interpreter while running')
    args=clparse.parse_args()
    zlogfmtargs={
        'fmt'     : '%(asctime)s %(levelname)7s (%(process)d)%(threadName)12s  %(module)s.%(funcName)s: %(message)s',
        'datefmt' : "%H:%M:%S",
    }
    # setup primary log
    toplog=logging.getLogger()
    toplog.setLevel(logging.DEBUG)
    zform=logging.Formatter(**zlogfmtargs)
    # if appropriate, add a handler to write to console
    if args.consolelog<1000:
        h=logging.StreamHandler()
        h.setFormatter(zform)
        toplog.addHandler(h) # do I need zlogargs again?
    # check for and add log to file if necessary
    if not args.logfile is None:
        logp=pathlib.Path(args.logfile).expanduser()
        h=logging.FileHandler(str(logp))
        h.setFormatter(zform)
        toplog.addHandler(h)
    if args.config is None:
        toplog.critical('No configuration file given - exiting')
        sys.exit('no configuration file given.')
    configpath=pathlib.Path(args.config)
    if not configpath.with_suffix('.py').is_file():
        exm='cannot find configuration file ' + str(configpath.with_suffix('.py'))
        toplog.critical(exm)
        sys.exit(exm)
    incwd=str(configpath.parent) == '.'
    if not incwd:
        sys.path.insert(1,str(configpath.parent))
    try:
        configmod=importlib.import_module(configpath.stem)
    except:
        exm='failed to load server config file', str(configpath)
        toplog.critical(exm)
        sys.exit(exm)
    serverconf=configmod.serverdef
    ips=utils.findMyIp(10)
    if len(ips)==0:
        smsg='starting webserver on internal IP only (no external IP addresses found), port %d' % (serverconf['port'])
    elif len(ips)==1:
        smsg='Starting webserver on %s:%d' % (ips[0], serverconf['port'])
    else:
        smsg='Starting webserver on multiple ip addresses (%s), port:%d' % (str(ips), server['port'])
    print(smsg)
    toplog.info(smsg)
    server = ThreadedHTTPServer(('',serverconf['port']),pywebhandler, mypyconf=serverconf)
    if args.interactive:
        print('interactive mode')
        sthread=threading.Thread(target=server.serve_forever)
        sthread.start()
    else:
        print('normal mode')
        try:
            server.serve_forever()
            smsg='webserver closed'
        except KeyboardInterrupt:
            smsg='webserver got KeyboardInterrupt'
        except Exception as e:
            smsg='webserver exception '+ type(e).__name__+' with '+e.msg
        finally:
            server.close()
        toplog.info(smsg)