import piCamStreamer, pagelink

from pootlestuff.watchables import myagents

from webstrings import tablefieldinputhtml, tablefielddropdnhtml, tablefieldcyclicbtndnhtml, tablesectwrapper

allStreamDefs=(
    (pagelink.wwlink,   'status',       myagents.app,   'status',               tablefieldinputhtml,    'streaming activity status'),
    (pagelink.wwlink,   'str_width',    myagents.user,  'stream video width',   tablefieldinputhtml,    'camera output resized for streaming',
                                                    {'liveformat': '{wl.varvalue:3d}'}),
    (pagelink.wwlink,   'str_height',   myagents.user,   'stream video height', tablefieldinputhtml,    'camera output resized for streaming',
                                                    {'liveformat': '{wl.varvalue:3d}'}),
    (pagelink.wwlink,   'timeout',      myagents.user,  'timeout',              tablefieldinputhtml,    'inactivity timeout after which stream port closes'),
    (pagelink.wwtime,   'lastactive',   myagents.app,   'last active',          tablefieldinputhtml,    'time streaming last active',
                                                    {'liveformat': '%H:%M:%S'}),
    (pagelink.wwlink,   'realframerate',myagents.app,   'framerate',            tablefieldinputhtml,    'rate frames being received from camera',
                                                    {'liveformat': '{wl.varvalue:4.2f}'}),
)

class webStream(piCamStreamer.Streamer):
    def allfields(self, pagelist, fielddefs):
        fieldstrs = [defn[0](wable=getattr(self, defn[1]), pagelist=pagelist, updators=defn[2], label=defn[3], shelp=defn[5], **(defn[6] if len(defn) > 6 else {})).
                webitem(fformat=defn[4]) for defn in fielddefs]
        return ''.join(fieldstrs)

    def makePanel(self, pagelist):
        return tablesectwrapper.format(style='camstreamstyle', flipid='xstrmset', fields=self.allfields(pagelist, allStreamDefs), title='Live streaming Settings')
