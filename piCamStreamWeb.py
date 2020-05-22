import piCamStreamer, pagelink

from pootlestuff.watchables import myagents

from webstrings import tablefieldinputhtml, tablefielddropdnhtml, tablefieldcyclicbtndnhtml, tablesectwrapper

class webStream(piCamStreamer.Streamer):
    def streaminfo(self, pagelist):
        fields = \
            pagelink.wwlink(wable=self.status, pagelist=pagelist, userupa=None, liveupa=myagents.app,
                    label = 'status', shelp='streaming activity status').webitem(fformat=tablefieldinputhtml) + \
            pagelink.wwlink(wable=self.str_width, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:3d}',
                label = 'stream video width', shelp='camera output resized for streaming').webitem(fformat=tablefieldinputhtml) + \
            pagelink.wwlink(wable=self.str_height, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:3d}',
                label = 'stream video height', shelp='camera output resized for streaming').webitem(fformat=tablefieldinputhtml) + \
            pagelink.wwlink(wable=self.timeout, pagelist=pagelist, userupa=myagents.user, liveupa=None,
                label ='timeout', shelp='inactivity timeout after which stream port closes').webitem(fformat=tablefieldinputhtml) + \
            pagelink.wwtime(wable=self.lastactive, pagelist=pagelist, userupa=None, liveupa=myagents.app, liveformat='%H:%M:%S',
                label = 'last active', shelp='time streaming last active').webitem(fformat=tablefieldinputhtml) + \
            pagelink.wwlink(wable=self.realframerate, pagelist=pagelist, userupa=None, liveupa=myagents.app, liveformat='{wl.varvalue:4.2f}',
                label = 'framerate', shelp='rate frames being received from camera').webitem(fformat=tablefieldinputhtml)
        return tablesectwrapper.format(style='camstreamstyle', flipid='xstrmset', fields=fields, title='Live streaming Settings')
