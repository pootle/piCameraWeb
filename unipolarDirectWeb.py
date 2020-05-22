import unipolarDirect, pagelink

from pootlestuff.watchables import myagents

from webstrings import tablefieldinputhtml, tablefielddropdnhtml, tablefieldcyclicbtndnhtml, tablesectwrapper

class webStepper(unipolarDirect.SimpleUniStepper):
    def streaminfo(self, pagelist):
        fields = \
            pagelink.wwlink(wable=self.status, pagelist=pagelist, userupa=None, liveupa=myagents.app,
                    label = 'status', shelp='focus status').webitem(fformat=tablefieldinputhtml) +\
            pagelink.wwenum(wable=self.drive_mode, pagelist=pagelist, userupa=myagents.user, liveupa=None,
                label = 'focus motor mode', shelp='sets the motor mode - use only goto' ).webitem(fformat=tablefielddropdnhtml) +\
            pagelink.wwenum(wable=self.drive_stepmode, pagelist=pagelist, userupa=myagents.user, liveupa=None,
                label = 'motor step type', shelp='sets the step type used for the motor' ).webitem(fformat=tablefielddropdnhtml) +\
            pagelink.wwlink(wable=self.drive_uStepPos, pagelist=pagelist, userupa=None, liveupa=myagents.app, liveformat='{wl.varvalue:7d}',
                label = 'current ustep pos', shelp='shows the current motor position').webitem(fformat=tablefieldinputhtml) +\
            pagelink.wwlink(wable=self.drive_target_pos, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:7d}',
                label = 'target ustep pos', shelp='for goto mode - the targett motor position').webitem(fformat=tablefieldinputhtml) +\
            pagelink.wwlink(wable=self.drive_target_intvl, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:5.4f}',
                label = 'step interval', shelp = 'when moving, this is the time between steps in seconds').webitem(fformat=tablefieldinputhtml) +\
            pagelink.wwlink(wable=self.drive_backlash, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:4d}',
                label = 'backlash adjustment',
                shelp='in goto mode this adjustment is made to the current location when the motor direction reverses').webitem(fformat=tablefieldinputhtml)


        return tablesectwrapper.format(style='focusstyle', flipid='xfocset', fields=fields, title='focusser')
