#!/usr/bin/python3
"""
a pvar that can watch a folder Var and allows a file to be selected. The list updates if the base folder
is changed or if its contents changes.

In a separate module as it requires additional non-standard library
"""

from pootlestuff import pvars

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

class foldertrigger(FileSystemEventHandler):

    def __init__(self, callback):
        self.callback = callback
        super().__init__()

    def on_any_event(self, event):
        self.callback(event)

class selectFileVar(pvars.enumVar):
    """
    acts as an enumVar using the list of files in a related folderVar, with one file (or none) selected. Can
    be set to refresh the list of files when triggered.
    """
    def __init__(self, fvpath, noneopt, changeagent, parent, **kwargs):
        """
        fvpath      : ptree path to a folderVar relative to the parent of this Var
        
        noneopt     : string to place at top of list, for no file to be selected
                        (if None then no extra option is used)
                        
        changeagent : when change detected, use this agent as the initiator of the new value for notifications
        """
        self.basefolder=parent[fvpath]
        self.noneopt=noneopt
        self.changeagent=changeagent
        vlist=self.basefolder.currentfilenames()
        if not self.noneopt is None:
            vlist.insert(0, self.noneopt)
        super().__init__(fallbackValue=vlist[0] if vlist else '', vlist = vlist, parent=parent, **kwargs)
        self.basefolder.addNotify(self.folderchanged, '*')
        self.ftrigger= foldertrigger(callback=self.contentchanged)
        self.fob     = Observer()
        self.watcher=self.fob.schedule(self.ftrigger, str(self.basefolder.getValue()))
        self.fob.start()

    def refresh(self, agent):
        oldv=self.getValue()
        vlist=self.basefolder.currentfilenames()
        if not self.noneopt is None:
            vlist.insert(0, self.noneopt)
        self.setVlist(vlist, agent)
        self.notify(agent=agent, oldValue=oldv, newValue=self.getValue())

    def contentchanged(self, event):
        """
        called if the folder this var is based on changes
        """
        self.refresh(self.changeagent)

    def folderchanged(self, oldValue, newValue, var, agent):
        self.fob.unschedule(self.watcher)
        self.watcher=self.fob.schedule(self.ftrigger, str(self.basefolder.getValue()))
        self.refresh(agent)