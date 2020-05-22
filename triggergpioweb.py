import triggergpio, pagelink

from pootlestuff.watchables import myagents

from webstrings import tablefieldinputhtml, tablefielddropdnhtml, tablefieldcyclicbtndnhtml, tablesectwrapper

class gpiotrigweb(triggergpio.gpiotrigger):
    def streaminfo(self, pagelist):
        fields = pagelink.wwlink(wable=self.status, pagelist=pagelist, userupa=None, liveupa=myagents.app,
                        label = 'status', shelp='gpio trigger activity status').webitem(fformat=tablefieldinputhtml)
        if hasattr(self, 'autostart'):
            fields += \
                pagelink.wwenumbtn(wable=self.startstopbtn, pagelist=pagelist, userupa=myagents.user, liveupa = None,
                    label='start / stop watching' , shelp='start / stops monitoring the gpio pin').webitem(fformat=tablefieldcyclicbtndnhtml) +\
                pagelink.wwenum(wable=self.autostart, pagelist=pagelist, userupa=myagents.user, liveupa=None,
                    label = 'auto start', shelp='starts monitoring when app runs').webitem(fformat=tablefielddropdnhtml)
        fields += pagelink.wwenumbtn(wable=self.usertrigger, pagelist=pagelist, userupa=myagents.user, liveupa = None,
                    label='trigger now' , shelp='manually set / clear the trigger').webitem(fformat=tablefieldcyclicbtndnhtml)
        if hasattr(self, 'autostart'):
            fields += \
                pagelink.wwlink(wable=self.pinno, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:2d}',
                    label = 'pin no.', shelp='broadcom pin no to watch').webitem(fformat=tablefieldinputhtml) + \
                pagelink.wwenum(wable=self.pullud, pagelist=pagelist, userupa=myagents.user, liveupa=None,
                    label = 'pull up setting', shelp='sets pull-up pull down or neither on the trigger pin').webitem(fformat=tablefielddropdnhtml) + \
                pagelink.wwenum(wable=self.triglvl, pagelist=pagelist, userupa=myagents.user, liveupa=None,
                    label = 'trigger level', shelp='sets if logic high or low causes trigger').webitem(fformat=tablefielddropdnhtml) + \
                pagelink.wwlink(wable=self.steadytime, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:2.4f}',
                    label = 'de-jitter steady time', shelp='time (in seconds) the pin must be stable at trigger level before trigger is set').webitem(fformat=tablefieldinputhtml) + \
                pagelink.wwlink(wable=self.holdtime, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:2.4f}',
                    label = 'de-jitter hold time', shelp='once triggered, the trigger remains for at least this much time (in deconds)').webitem(fformat=tablefieldinputhtml) + \
                pagelink.wwlink(wable=self.trigcount, pagelist=pagelist, userupa=None, liveupa=myagents.app, liveformat='{wl.varvalue:4d}',
                    label = 'trigger count', shelp='number of times this trigger has fired this session').webitem(fformat=tablefieldinputhtml) + \
                pagelink.wwtime(wable=self.lasttrigger, pagelist=pagelist, userupa=None, liveupa=myagents.app, liveformat='%H:%M:%S',
                    label = 'last trigger', shelp='time  last active').webitem(fformat=tablefieldinputhtml) +\
                pagelink.wwtime(wable=self.lastactive, pagelist=pagelist, userupa=None, liveupa=myagents.app, liveformat='%H:%M:%S',
                    label = 'last active', shelp='time streaming last active').webitem(fformat=tablefieldinputhtml)
        return tablesectwrapper.format(style='gpio_triggerstyle', flipid='xtrigset', fields=fields, title='gpio trigger Settings')
