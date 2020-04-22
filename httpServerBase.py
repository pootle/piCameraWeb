#!/usr/bin/python3

from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
import http.server
import json, time, errno, threading, logging, pathlib
from htmlmaker import pageupdatelist

pageid=900

def makepageref():
    """
    returns a unique id that can be used for each page
    """
    global pageid
    pageid +=1
    return str(pageid)

class ThreadedHTTPServer(ThreadingMixIn, http.server.HTTPServer):
    """
    Handle requests in a separate thread.
    
    This allows multiple pages to be in progress, and in particular it allows the webserver to send out an event stream for extended periods
    without blocking other requests.
    
    Also it allows queues of status messages to be setup which are served up as event streams on request. No session control etc. here though
    """
    def __init__(self, *args, config, **kwargs):
        self.config=config
        self.logger=logging.getLogger(__loader__.name+'.'+type(self).__name__)
        self.loglvl=logging.DEBUG
        self.logger.setLevel(self.loglvl)
        self.serverrunning=True
        self.activeupdates={}
        th=threading.Thread(name='listchecker', target=self.runner)
        th.start()
        super().__init__(*args, **kwargs)

    def close(self):
        self.serverrunning=False
        self.socket.close()
        for closefunc in self.config['oncloseapps']:
            try:
                closefunc()
            except:
                pass

    def runner(self):   # watcher to discard unused lists
        while self.serverrunning:
            deadlist = [k for k, l in self.activeupdates.items() if l.hasexpired()]
            for k in deadlist:
                uplist=self.activeupdates.pop(k)
                uplist.closelist()
            time.sleep(5)
            
    def log(self, level, *args, **kwargs):
        if level >= self.loglvl:
            self.logger.log(level, *args, **kwargs)

class requHandler(http.server.BaseHTTPRequestHandler):
    """
    added functionality for handling individual requests.
    
    A new instance of this class is created to process each incoming request to the service, which (if the server uses the Threading Mixin) will
    also be running in a new thread.
    """ 
    def do_GET(self):
        """
        parses various info about the request runs the code appropriate for the request
        """
        serverconfig=self.server.config    # put the config in a convenient place
        try:
            validrequs=serverconfig[self.command]
        except:
            self.send_error(501, 'no GET list specified for this server')
            return
        parsedpath=urlparse(self.path)
        if parsedpath.path.startswith(serverconfig['staticroot']['root']):
            self.servestatic(statfile=parsedpath.path[len(serverconfig['staticroot']['root']):])
            return
        queryparams=None if parsedpath.query=='' else parse_qs(parsedpath.query)
        try:
            requinfo=validrequs[parsedpath.path]
        except:
            self.send_error(404, 'I know nothing of the page you have requested! (%s)' % self.path)
            return
        if 'request' in requinfo:
            hfunc=requinfo['request']
            good, data = hfunc(parsedpath=parsedpath, requinfo=requinfo, **queryparams)
            if good:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            else:
                self.send_error(500, data)
        elif 'static' in requinfo:
            # serves up a static file - either a fixed file or file with the terminal name in the request
            self.servestatic(statfile=parsedpath.path[1:] if requinfo['static'] == '*' else requinfo['static'])
        elif 'updator' in requinfo:
            # user changed a value on web page; this updates the var's value by calling the updator's webset method.
            if 't' in queryparams and 'v' in queryparams and 'p' in queryparams and queryparams['p'][0] in self.server.activeupdates:
                updatelist=self.server.activeupdates[queryparams['p'][0]]
                resp=updatelist.applyUpdate(queryparams['t'], queryparams['v'])
            elif 't' in queryparams and 'v' in queryparams and 'p' in queryparams:
                print('%s not found in %s' % (queryparams['p'][0], list(self.server.activeupdates.keys())))
                resp=b'list error in request'
            else:
                print('ooopsy tvp error', queryparams)
                resp=b'fail parameter error in request'
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(resp)
        elif 'streamhandler' in requinfo:
            # ongoing stream to feed updated values to the web browser
            genob=requinfo['streamhandler'](**queryparams)
            tickinterval=1.11
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
            self.end_headers()
            running=True
            self.server.log(30, 'streamhandler client %s starts' %   str(self.client_address))
            while running and self.server.serverrunning:
                try:
                    datats=json.dumps(next(genob))
                except StopIteration:
                    datats=None
                    running=False
                if running:
                    try:
                        self.wfile.write(('data: %s\n\n' % datats).encode('utf-8'))
                    except BrokenPipeError:
                        running=False
                        self.server.log(30, 'streamhandler client %s terminated' %   str(self.client_address))
                    time.sleep(tickinterval)
        elif 'camstreamhandler' in requinfo:
            try:
                camstreaminfo=requinfo['camstreamhandler']()
            except StopIteration:
                self.send_error(402, 'no source for stream')
                return
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            running=True
            self.server.log(30, 'camstreamhandler client %s starts' %   str(self.client_address))
            try:
                while running and self.server.serverrunning:
                    try:
                        frame, conttype, datalen=camstreaminfo.nextframe()
                    except StopIteration:
                        running=False
                    if running:
                        try:
                            self.wfile.write(b'--FRAME\r\n')
                            self.send_header('Content-Type', conttype)
                            self.send_header('Content-Length', datalen)
                            self.end_headers()
                            self.wfile.write(frame)
                            self.wfile.write(b'\r\n')
                        except BrokenPipeError:
                            running=False
                self.server.log(30, 'camstreamhandler client %sterminated' %   str(self.client_address))
            except Exception as e:
                self.server.log(30, 'camstreamhandler client %s crashed %s' %   (str(self.client_address), str(e)))
        elif 'updatestreamhandler' in requinfo:
            if 'updatename' in queryparams:
                uplistname= queryparams['updatename'][0]
                print('update stream using list', uplistname)
                if uplistname in self.server.activeupdates:
                    uplist=self.server.activeupdates[uplistname]
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
                    self.end_headers()
                    updatetimeout=0
                    pipeOK=True
                    try:
                        while self.server.serverrunning and pipeOK:
                            dupd=uplist.getupdates()
                            try:
                                self.wfile.write(('data: %s\n\n' % dupd).encode('utf-8'))
                                updatetimeout=time.time()+3
                            except BrokenPipeError:
                                pipeOK=False
                            time.sleep(2.5)
                    except Exception as e:
                        print('it blew up')
                        raise
                else:
                    self.send_error(402, 'cannot find update list %s' % uplistname)
                    return
            else:
                self.send_error(402, 'no updatename supplied')
                return
        elif 'pagemaker' in requinfo:
            pageid=makepageref()
            pageupdater=pageupdatelist(pageid)
            phtml = requinfo['pagemaker'](apps=self.server.config['apps'], pup=pageupdater, qp=queryparams, **requinfo['params'])
            if pageupdater.haslinks():
                  self.server.activeupdates[pageid]=pageupdater
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', len(phtml))
            self.end_headers()
            self.wfile.write(phtml.encode())
        elif 'vidstreamhandler' in requinfo:
            streamparams=requinfo['vidstreamhandler']
            tp=streamparams['resolve'](queryparams)
            if tp.exists():
                tsize=tp.stat().st_size
                if True:
                    rbits=self.headers.get('Range').strip().split('=')
                    if rbits[0]=='bytes':
                        rstarts, rends=rbits[1].split('-')
                        start=0 if len(rstarts)==0 else int(rstarts)
                        end=tsize-1 if len(rends)==0 else int(rends)
                        if end >=tsize:
                            end=tsize-1
                        if end-start > 65535:
                            end=start+65535
                        with tp.open('rb') as tpo:
                            if start != 0:
                                tpo.seek(start)
                            self.send_response(206)
                            self.send_header(*self.mimetypeforfile('.mp4'))
                            self.send_header('Content-Length', str(end-start+1))
                            self.send_header('Content-Range', 'bytes %s-%s/%s' % (start, end, tsize))
                            self.send_header('Accept-Ranges','bytes')
                            self.end_headers()
                            rdat=tpo.read(end-start)
                            if rdat:
                                self.wfile.write(rdat)
                        return
                    else:
                        print('nobytes!')
#                except:
#                    print('oops')
#                    raise
            else:
                print('fileooops', str(tp))
                self.send_error(502, 'video would be nice')
        else:
            self.send_error(502, 'request type fails in requinfo >%s<' % requinfo) 

    def mimetypeforfile(self, fileext):
        return {
        '.css' :('Content-Type', 'text/css; charset=utf-8'),
        '.html':('Content-Type', 'text/html; charset=utf-8'),
        '.js'  :('Content-Type', 'text/javascript; charset=utf-8'),
        '.ico' :('Content-Type', 'image/x-icon'),
#        '.py'  :('Content-Type', 'text/html; charset=utf-8'),   # python template files we assume return html for now
        '.jpg' :('Content-Type', 'image/jpeg'),
        '.png' :('Content-Type', 'image/png'),
        '.mp4' :('Content-Type', 'video/mp4'),
        '.svg' :('Content-Type', 'image/svg+xml'),
        }[fileext]
 
    def do_POST(self):
        serverconfig=self.server.config    # put the config in a convenient place
        try:
            validrequs=serverconfig[self.command]
        except:
            self.send_error(501, 'no POST list specified for this server')
            return
        th=self.headers['Content-Type']
        print('+++++++++++++', self.path)
        if th.startswith('application/json'):
            dlength=int(self.headers['Content-Length'])
            ddata=self.rfile.read(dlength)
            if len(ddata) != dlength:
                print("HELEPELPELPELEPLEPELEPLE")
                self.send_error(501,'oops')
            elif self.path in validrequs:
                pathinf=validrequs[self.path]
                jdata=json.loads(ddata.decode('utf-8'))
                result=pathinf['function'](pathinf, **jdata)
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
                self.send_error(404, ('no page for %s' % self.path[1:]))
        else:
            self.send_error(500,'what is ' + th) 

    def servestatic(self, statfile):
        staticinf=self.server.config['staticroot']
        staticfile=staticinf['path']/statfile
        if staticfile.is_file():
            try:
                sfx=self.mimetypeforfile(staticfile.suffix)
            except:
                self.send_error(501, "no mime type found in server config['mimetypes'] for %s" % staticfile.suffix)
                return
            self.send_response(200)
            self.send_header(*sfx)
            with staticfile.open('rb') as sfile:
                cont=sfile.read()
                self.send_header('Content-Length', len(cont))
                self.end_headers()
                self.wfile.write(cont)
        else:
            self.send_error(404, 'file %s not present or not a file' % str(staticfile))

class xxchunker():
    def __init__(self, fileish, startat, length, blocksize=8192):
        self.fileish = fileish
        self.fileish.seek(startat)
        self.remaining = length
        self.blocksize = blocksize

    def close(self):
        if hasattr(self.fileish, 'close'):
            self.filelike.close()

    def __iter__(self):
        return self

    def __next__(self):
        if self.remaining <= 0:
            raise StopIteration()
        data = self.filelike.read(min(self.remaining, self.blksize))
        if not data:
            raise StopIteration()
        self.remaining -= len(data)
        return data
