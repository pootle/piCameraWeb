import piCamMovecpu, pagelink

from pootlestuff.watchables import myagents

from webstrings import tablefieldinputhtml, tablefielddropdnhtml, tablefieldcyclicbtndnhtml, tablesectwrapper

class webcpumove(piCamMovecpu.MoveDetectCPU):
    def streaminfo(self, pagelist):
        fields = \
            pagelink.wwlink(wable=self.status, pagelist=pagelist, userupa=None, liveupa=myagents.app,
                    label = 'status', shelp='cpu detection activity status').webitem(fformat=tablefieldinputhtml) + \
            pagelink.wwenumbtn(wable=self.startstopbtn, pagelist=pagelist, userupa=myagents.user, liveupa = None,
                    label='start / stop cpu detect' , shelp='start / stop cpu based detection activity').webitem(fformat=tablefieldcyclicbtndnhtml) +\
            pagelink.wwenum(wable=self.autostart, pagelist=pagelist, userupa=myagents.user, liveupa=None,
                    label = 'auto start', shelp='starts cpu detection when app runs').webitem(fformat=tablefielddropdnhtml) +\
            pagelink.wwlink(wable=self.width, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:3d}',
                    label = 'analysis width', shelp='camera output resized for analysis').webitem(fformat=tablefieldinputhtml) + \
            pagelink.wwlink(wable=self.height, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:3d}',
                    label = 'analysis height', shelp='camera output resized for analysis').webitem(fformat=tablefieldinputhtml) + \
            pagelink.wwenum(wable=self.imagemode, pagelist=pagelist, userupa=myagents.user, liveupa=None,
                    label = 'format', shelp='set rgb or yuv for analysis').webitem(fformat=tablefielddropdnhtml) + \
            pagelink.wwenum(wable=self.imagechannel, pagelist=pagelist, userupa=myagents.user, liveupa=None,
                    label = 'channel', shelp='sets a single channel tor all channels (*) to use for analysis').webitem(fformat=tablefielddropdnhtml) +\
            pagelink.wwtime(wable=self.lasttrigger, pagelist=pagelist, userupa=None, liveupa=myagents.app, liveformat='%H:%M:%S',
                label = 'last trigger time', shelp='time of last trigger').webitem(fformat=tablefieldinputhtml) +\
            pagelink.wwlink(wable=self.triggercount, pagelist=pagelist, userupa=None, liveupa=myagents.app, liveformat='{wl.varvalue:4d}',
                    label = 'trigger count', shelp='number of times this trigger has fired this session').webitem(fformat=tablefieldinputhtml)

        return tablesectwrapper.format(style='cpumovestyle', flipid='xcpum', fields=fields, title='cpu movement detection settings')
