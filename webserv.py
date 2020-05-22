#!/usr/bin/python3
"""
Startup for web service to process command line arguments and start up the web server.

The main web service is normally (inherits from) http.server.HTTPServer), and the message handler from http.server.BaseHTTPRequestHandler.
The classes used are defined in the config file - which is the only mandatory argument.

Optionally, the web server can be started in a thread, so a python prompt  is available (when run from an interactive shell), allowing
the objects to be accessed from the prompt.

A KeyboardInterrupt should stop the entire service ruuning and exit.
 """
import sys, argparse, pathlib, importlib, logging, http.server

from pootlestuff import netinf

if __name__ == '__main__':
    clparse = argparse.ArgumentParser(description='runs a simple python webserver.')
    clparse.add_argument('-c', '--config', help='path to configuration file.')
    clparse.add_argument('-l', '--logfile', help='if present sets logging to log to this file (overrides config logfile)')
    clparse.add_argument('-v', '--consolelog', type=int, help='level of logging for the console log (stderr), if absent / 0 there is no console log')
    clparse.add_argument('-i', '--interactive', action='store_true', 
                    help='run webserver in separate thread to allow interaction with python interpreter from console while running')
    args=clparse.parse_args()

    if args.config is None:
        sys.exit('no configuration file given.')
    configpath=pathlib.Path(args.config).expanduser()
    if not configpath.with_suffix('.py').is_file():
        sys.exit('cannot find configuration file ' + str(configpath.with_suffix('.py')))
    if not str(configpath.parent) == '.' and not configpath.parent in sys.path:
        sys.path.insert(1,str(configpath.parent))
    configmodule=importlib.import_module(configpath.stem)
    
    # setup logging
    loglevel=getattr(configmodule,'loglevel',50)
    if loglevel < 0 or loglevel > 100:
        sys.exit('invalid loglevel in config file - must be between 0..100, found %s' % loglevel)
    toplog=logging.getLogger()
    toplog.setLevel(loglevel)

    if args.consolelog is None:
        print('no console log')
    else:
        print('setting console log, loglevel', args.consolelog)
        chandler=logging.StreamHandler()
        if hasattr(configmodule, 'consolelogformat'):
            chandler.setFormatter(logging.Formatter(**configmodule.consolelogformat))
        chandler.setLevel(args.consolelog)
        toplog.addHandler(chandler)
 
    logfile=args.logfile if args.logfile else config.logfile if hasattr(configmodule,'logfile') else None
    if logfile is None:
        print('No logfile')
    else:
        print('using logfile', logfile)
        logp=pathlib.Path(args.logfile).expanduser()
        lfh=logging.FileHandler(str(logp))
        if hasattr(configmodule, 'filelogformat'):
            lfh.setFormatter(logging.Formatter(**configmodule.filelogformat))
        toplog.addHandler(lfh)

    assert hasattr(configmodule, 'webport')
    assert hasattr(configmodule, 'config')
    assert hasattr(configmodule, 'httpserverclass')
    assert hasattr(configmodule, 'httprequestclass')
    assert hasattr(configmodule, 'config')

    config=configmodule.config
    assert isinstance(config, dict)
    
    ips=netinf.allIP4()
    if len(ips)==0:
        smsg='starting webserver on internal IP only (no external IP addresses found), port %d' % (configmodule.webport)
    elif len(ips)==1:
        smsg='Starting webserver on %s:%d' % (ips[0], configmodule.webport)
    else:
        smsg='Starting webserver on multiple ip addresses (%s), port:%d' % (str(ips), configmodule.webport)
    toplog.info(smsg)

    server = configmodule.httpserverclass(('',configmodule.webport),configmodule.httprequestclass, config=config)
    assert isinstance(server, http.server.HTTPServer)
    if args.interactive:
        toplog.info('interactive mode - start at server.mypyobjects')
        sthread=threading.Thread(target=server.serve_forever)
        sthread.start()
    else:
        toplog.info('normal mode')
        try:
            server.serve_forever()
            smsg='webserver closed'
        except KeyboardInterrupt:
            smsg='webserver got KeyboardInterrupt'
        except Exception as e:
            smsg='webserver exception '+ type(e).__name__+' with '+e.msg
        server.close()
        toplog.info(smsg)
