#!/usr/bin/python3
"""
experimental module that provides an app framework, based on pforms Vars for variables that 
require persistent state or interact with the user, and that can run a number of activities
on demand as part of the app.

The activities can run as additional threads or just respond to calls from elsewhere.
"""
import threading, time, logging, sys, traceback

import pforms

class appActivity():
    """
    A class that runs one activity for an app.
    
    It's overall state is represented by requstate and localstate
    
    requstate can be 'run' or 'stop' and is controlled by things that manage the activity.
    
    localstate can be 'starting', 'run' or 'complete' and is managed by this class (and / or it's descendents).
        Other values can be used during run phase defined by particular activity.
        'starting' is set in the constructor. 'run' is set when the activity is properly active and 'complete'
        is set when the activity has tidilly closed down. 'complete' is used as a flag by the managing app
        to discard the activity and any resources used to run it (such as a thread if it a threaded activity - see class
        appThreadAct below.
    
    This class provides no thread of execution, it is used where all the member functions are called from an existing
    thread or threads on events or conditions arising therein.
    """
    def __init__(self, name, parent, vars, loglvl=logging.INFO):
        self.clockatstart=time.time()
        self.name=name
        self.parent=parent
        self.requstate='run'
        self.vars=vars
        self.log=None if loglvl is None else logging.getLogger(__loader__.name+'.'+type(self).__name__)
        self.loglvl=1000 if loglvl is None else loglvl
        self.updateState('starting')
        if self.loglvl <= logging.INFO:
            self.log.info('Activity {} starting'.format(self.name))

    def updateState(self, newstate):
        self._localstate=newstate
        if 'status' in self.vars:
            self.vars['status'].setValue('app', newstate)

    def startedlogmsg(self):
        return 'Activity {} started'.format(self.name)

    def endedlogmsg(self):
        tdiff=time.time()-self.clockatstart
        runtime=time.strftime('%H:%M:%S',(time.struct_time(time.gmtime(tdiff))))+'{:0.2f}'.format(tdiff%1)[1:]
        return 'Activity {} completed, run time {}'.format(self.name,runtime)

    def start(self):
        self.startSetup()

    def startDeclare(self):
        """
        Does standard stuff when activity starts whether threaded or not
        """
        self.updateState('run')
        if self.loglvl <= logging.INFO:
            self.log.info(self.startedlogmsg())
        if 'started' in self.vars:
            self.vars['started'].setValue('app',time.time())
        
    def endDeclare(self):
        self.updateState('complete')
        if self.loglvl <= logging.INFO:
            self.log.info(self.endedlogmsg())
        if 'stopped' in self.vars:
            self.vars['stopped'].setValue('app',time.time())

    def requestFinish(self):
        self.requstate='stop'
        self.updateState('complete')
        if self.loglvl <= logging.INFO:
            self.log.info(self.endedlogmsg())

    def tidyclose(self):
        return True

    def onActExit(self):
        pass

class appThreadAct(appActivity):
    """
    A class for activities that need to run in their own thread.
    
    While similar to a simple appActivity, this variant starts a new execution thread that the activity can use in any
    appropriate manner. Such classes should override the member function innerrun, using this class's innerrun as a model. The time between
    checking for self.requstate should preferably not exceed 1 second.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.actThread=threading.Thread(target=self.run, name='thread_'+self.name)

    def endedlogmsg(self):
        line1=super().endedlogmsg()
        threadt=time.clock_gettime(time.CLOCK_THREAD_CPUTIME_ID)
        threadtime=time.strftime('%H:%M:%S',(time.struct_time(time.gmtime(threadt))))+'{:0.2f}'.format(threadt%1)[1:]
        elapsed=time.time()-self.clockatstart
        ratio=threadt/elapsed
        return '{} processor time {}, cpu {:2.2f}'.format(line1, threadtime, ratio*100)

    def start(self):
        self.actThread.start()

    def innerrun():
        self.startSetup()
        while self.requstate != 'stop':
            time.sleep(1)
        self.updateState('complete')
        if self.loglvl <= logging.INFO:
            self.log.info(self.endedlogmsg())

    def run(self):
        try:
            self.innerrun()
        except:
            if not self.log is None:
                exc_type, exc_value, exc_traceback=sys.exc_info()
                self.log.critical('exception {} in thread\n    value: {}\n{}'.format(str(exc_type), str(exc_value), 
                        '\n'.join(traceback.format_tb(exc_traceback))))
        self.onActExit()

    def requestFinish(self):
        if self.loglvl <= logging.INFO:
            self.log.info('activity {} requeststate now stop'.format(self.name))
        self.requstate='stop'

    def tidyclose(self):
        self.actThread.join(timeout=.2)
        return not self.actThread.isAlive()

class appManager(pforms.appVar):
    """
    This class supports apps that use appVar's to control and manage their behaviour.
    
    It can run a number of optional 'activities' that are run directly or as additional threads, and 
    load and save the values of all the appVar's to save and restore particular settings 
    """
    def __init__(self, **kwargs):
        """
        initialises an (empty) activity dict
        """
        self.running=True
        self.activities={}
        super().__init__(**kwargs)

    def close(self):
        """
        close just sets the flag to show we no longer want to run. the run loop should cleanly close everything down.
        """
        if 'alarmact' in self.activities:
            self.activities['alarmact'].requestFinish()
        self.running=False        

    def startActivity(self, actname, actclass, vars=None, **actparams):
        """
        checks if the activity is already running and runs up a activity from the passed parameters for the activity.
        
        Activities are expected to be single instance.

        actname  : the name for the activity - used to identify the activity and link it to it's control var's
        
        actclass : the class to be instantiated for the new activity-  normally a class that inherits from appActivity.
                   Many activities will run a new thread, some trivial ones will not need to do this. This is handled by
                   the appActivity class.
        
        actparams: any parameters the new class will need (that aren't already in the activity's vars)
        
        loglvl   : the log level the new activity will be setup with.
        """
        if actname in self.activities:
            raise ValueError('Activity {} already active'.format(actname))
        if self.loglvl <= logging.INFO: # use app's loglvl to report activity start and stop
            self.log.info('Activity {} being started'.format(actname))
        self.activities[actname]=actclass(name=actname, parent=self,
                        vars=self['settings'].get(actname) if vars is None else vars,   # there may be no actname in settings
                        **actparams)
        self.activities[actname].start()
        return self.activities[actname]

    def addAlarm(self, **kwargs):
        if 'alarmact' in self.activities:
            aact=self.activities['alarmact']
        else:
            aact=self.startActivity('alarmact', alarmAct, vars={})
        aact.addAlarm(**kwargs)

    def checkActivities(self):
        """
        This function should be called periodically (say every second or 2) to check if any activities have terminated
        so it can release the relevant resources. Because activities can run is separate threads, and may take a couple
        of seconds to finish when requested to stop, we don't want to hold up important threads when they ask an activity to stop.
        """
        finishers=[]
        for act in self.activities.values():
            if act._localstate=='complete':
                finishers.append(act)
        for act in finishers:
            self.activities.pop(act.name)
            gone=act.tidyclose()
            if gone:
                act.onActExit()
                if self.loglvl <= logging.INFO: # use app's loglvl to report activity start and stop
                    self.log.info('Activity {} has gone'.format(act.name))
            else:
                if self.loglvl <= logging.INFO: # use app's loglvl to report activity start and stop
                    self.log.info('Activity {} shutdown pending'.format(act.name))
                self.activities[act.name]=act
        for act in self.activities.values():  # also check threaded activities to see if it has died - the ultimate backstop?
            actThread=getattr(act,'actThread', None)
            if not actThread is None:
                if not actThread.isAlive():
                    print("papps.checkActivities dead activity {} detected".format(act.name))

class alarmAct(appThreadAct):
    """
    A threaded activity that provides a runafter / runat facility for delayed action or slow timer type functionality.
    
    All alarms are one shot, the alarm needs to recreate itself for periodic alarms   
    """
    def __init__(self, **kwargs):
        self.timedacts=[]
        self.datasem=threading.Lock()
        super().__init__(**kwargs)

    def addAlarm(self, func, runat=None, runafter=None, **kwargs):
        """
        adds a timed callback to run the given func at the required time, note if the required delay is less
        than the loop interval, the callback can be late (by not more than the loop interval)
        """
        assert not(runat is None and runafter is None)
        targettime=runat if runafter is None else time.time()+runafter
        newentry=(targettime, func, kwargs)
        lloc=None
        with self.datasem:
            if self.timedacts:
                for idx, alarm in enumerate(self.timedacts):
                    if targettime < alarm[0]:
                        lloc=idx
                        break
            if lloc is None:
                self.timedacts.append(newentry)
            else:
                self.timedacts.insert(lloc, newentry)

    def innerrun(self):
        while self.requstate != 'stop':
            time.sleep(1)
            while self.timedacts and self.timedacts[0][0] < time.time():
                with self.datasem:
                    runthis=self.timedacts.pop(0)
                runthis[1](**runthis[2])
        self.updateState('complete')
        if self.loglvl <= logging.INFO:
            self.log.info(self.endedlogmsg())
