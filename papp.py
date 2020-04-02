#!/usr/bin/python3

import pathlib, json
from pootlestuff import pvars
import pvarfolderfiles as pvarf
from logging import CRITICAL

settingsdefaultfolder   = '~/camfiles'
settingsdefaultfile     = 'default'

appvardefs=(
    {'name': 'genapp', '_cclass': pvars.groupVar, 'childdefs': (
        {'name': 'setsfold',        '_cclass': pvars.folderVar,     'fallbackValue': settingsdefaultfolder, 'filters': ['pers']},
        {'name': 'setsfile',        '_cclass': pvarf.selectFileVar, 'fvpath': 'setsfold', 'noneopt': 'default', 'changeagent': 'driver', 'filters': ['pers']},
        )},
)

class appManager(pvars.rootVar):
    """
    This class supports apps that use appVar's to control and manage their behaviour.
    
    It can load and save the values of all the appVar's (with a filter value of 'pers') to save and restore particular settings 
    """
    def __init__(self, settingsfile=None, value=None, childdefs=None, **kwargs):
        """
        provides var persistence for an pvars tree.
        
        if value is not None, then it is used to iniitialise pvar values.
        
        otherwise if value is None and settingsfile is an existing file (in json format), then the file is loaded and used to initialise the pvar tree value
        
        if both are none then the default settings file is used if present else pvar's default values are used.
        """
        if value is None:
            print('check for settings in', settingsfile)
            if settingsfile is None:
                spath=(pathlib.Path(settingsdefaultfolder).expanduser()/settingsdefaultfile).with_suffix('.cfg')
            else:
                spath=pathlib.Path(settingsfile).expanduser().with_suffix('.cfg')
                if not spath.is_file():
                    spath=(pathlib.Path(settingsdefaultfolder).expanduser()/settingsdefaultfile).with_suffix('.cfg')
            if spath.is_file():
                with spath.open('r') as sfo:
                    value=json.load(sfo)
                    print('loaded settings from', spath)
            else:
                value={}
        children=appvardefs
        if not childdefs is None:
            children += childdefs
        super().__init__(value=value, childdefs=children, **kwargs)

    def close(self):
        """
        close just sets the flag to show we no longer want to run. the run loop should cleanly close everything down.
        """
        self.running=False

    def saveValues(self, filename):
        sf=pathlib.Path(filename).expanduser()
        with sf.open('w') as sfo:
            json.dump(self.getFiltered('pers'), fp=sfo, indent=4)
        print('============================= saved')

    def criticalreport(self, message):
        self.log(CRITICAL, message)
        print('======================================')
        print(message)