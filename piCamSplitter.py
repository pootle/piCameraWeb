#!/usr/bin/python3

class camSplitterAct():
    """
    mixin class for activities that use the splitter port
    """
    def __init__(self, splitterport, **kwargs):
        self.sPort=splitterport
        super().__init__(**kwargs)
        self.parent.cameraTimeout=None
        
    def onActExit(self):
        sport=self.sPort
        self.sPort=None
        if not sport is None:
            print("+++++++++++++++++++++++++++++++++releasing with",sport)
            self.parent._releaseSplitterPort(self, sport)