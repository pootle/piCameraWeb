import piCamMovecpu, pagelink

from pootlestuff.watchables import myagents

from webstrings import tablefieldinputhtml, tablefielddropdnhtml, tablefieldcyclicbtndnhtml, tablesectwrapper

allRecordDefs=(
    (pagelink.wwlink,   'status',       myagents.app,   'status',           tablefieldinputhtml,        'cpu detection activity status'),
    (pagelink.wwenumbtn,'startstopbtn', myagents.user,  'start / stop',     tablefieldcyclicbtndnhtml,  'start / stop cpu based detection activity'),
    (pagelink.wwenum,   'autostart',    myagents.user,  'auto start',       tablefielddropdnhtml,       'starts monitoring when app runs'),
    (pagelink.wwlink,   'width',        myagents.user,  'analysis width',   tablefieldinputhtml,        'camera output resized for analysis',       {'liveformat': '{wl.varvalue:3d}'}),
    (pagelink.wwlink,   'height',       myagents.user,  'stream video height',tablefieldinputhtml,      'camera output resized for sanalysis',      {'liveformat': '{wl.varvalue:3d}'}),
    (pagelink.wwenum,   'imagemode',    myagents.user,  'format',           tablefielddropdnhtml,       'set rgb or yuv for analysis'),
    (pagelink.wwenum,   'imagechannel', myagents.user,  'channel',          tablefielddropdnhtml,       'sets a single channel tor all channels (*) to use for analysis'),
    (pagelink.wwtime,   'lasttrigger',  myagents.app,   'last trigger time',tablefieldinputhtml,        'time of last trigger',                     {'liveformat': '%H:%M:%S'}),
    (pagelink.wwlink,   'triggercount', myagents.app,   'trigger count',    tablefieldinputhtml,        'number of times this trigger has fired this session', {'liveformat': '{wl.varvalue:4d}'}),
    (pagelink.wwlink,   'maskfold',     myagents.user,  'mask folder',      tablefieldinputhtml,        'folder for masks'),
    (pagelink.wwlink,   'maskfile',     myagents.user,  'mask file',        tablefieldinputhtml,        'filename for png file to use as mask (-off- for no mask)'),
)


class webcpumove(piCamMovecpu.MoveDetectCPU):
    def allfields(self, pagelist, fielddefs):
        fieldstrs = [defn[0](wable=getattr(self, defn[1]), pagelist=pagelist, updators=defn[2], label=defn[3], shelp=defn[5], **(defn[6] if len(defn) > 6 else {})).
                webitem(fformat=defn[4]) for defn in fielddefs]
        return ''.join(fieldstrs)

    def makePanel(self, pagelist):
        return tablesectwrapper.format(style='cpumovestyle', flipid='xcpum', fields=self.allfields(pagelist,allRecordDefs), title='cpu movement detection settings')
