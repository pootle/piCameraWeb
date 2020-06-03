import piCamRecorder, pagelink

from pootlestuff.watchables import myagents

from webstrings import tablefieldinputhtml, tablefielddropdnhtml, tablefieldcyclicbtndnhtml, tablesectwrapper
allfields=(
    (pagelink.wwlink,   'status',       myagents.app,   'status',               tablefieldinputhtml,        'video recorder status'),
    (pagelink.wwenumbtn,'startstopbtn', myagents.user,  'start / stop recorder',tablefieldcyclicbtndnhtml,  'start / stop recorder activity'),
    (pagelink.wwenum,  'autostart',   myagents.user,    'auto start',           tablefielddropdnhtml,       'starts recorder when app runs'),
    (pagelink.wwenumbtn,  'recordnow',   myagents.user, 'record now',           tablefieldcyclicbtndnhtml,  'start recording if recorder waiting'),
    (pagelink.wwenum,  'cpudetect',   myagents.user,    'enable cpu detect trigger',tablefielddropdnhtml,   'triggers recording when cpu movement detection triggers'),
    (pagelink.wwenum,  'gpiodetect',   myagents.user,   'enable gpio trigger',  tablefielddropdnhtml,       'triggers recording when gpio input triggers'),
    (pagelink.wwenum,  'format',   myagents.user,       'recording format',     tablefielddropdnhtml,       'video type to record'),
    (pagelink.wwlink,  'rec_width',   myagents.user,    'recorded video width', tablefieldinputhtml,        'camera output resized for streaming',
                            {'liveformat': '{wl.varvalue:3d}'}),
    (pagelink.wwlink,  'rec_height',   myagents.user,   'recorded video height',tablefieldinputhtml,        'recorded video height',
                            {'liveformat': '{wl.varvalue:3d}'}),
    (pagelink.wwlink,  'recordback',   myagents.user,   'pre-trigger time',     tablefieldinputhtml,
                            'saves video for (roughly) specified period before the trigger happened (seconds) - values less than .25 s may not work',
                            {'liveformat': '{wl.varvalue:4.2f}'}),
    (pagelink.wwlink,  'recordfwd',   myagents.user,    'post trigger time',    tablefieldinputhtml, 
                            'records video for this period after trigger condition ceases',
                            {'liveformat': '{wl.varvalue:4.2f}'}),
    (pagelink.wwlink,  'splitrecord',   myagents.user,  'split recording time', tablefieldinputhtml,
                            'When recording, start a new file after this number of minutes',
                            {'liveformat': '{wl.varvalue:7.2f}'}),
    (pagelink.wwlink,  'maxvidlength',  myagents.user,  'max video length',     tablefieldinputhtml,        'number of h264 files to merge to a single MP4 file',
                            {'liveformat': '{wl.varvalue:3d}'}),
    (pagelink.wwenum,  'saveh264',   myagents.user,     'save h264 files',      tablefielddropdnhtml,
                            'keeps the h264 video files after mp4 conversion (otherwise they are deleted)'),
    (pagelink.wwlink,  'vidfold',   myagents.user,      'base folder for videos',tablefieldinputhtml,
                            'The base folder is combined with the video filename to create the full video filename path'),
    (pagelink.wwlink,  'vidfile',   myagents.user, 'recorded video filename',   tablefieldinputhtml,        'This is combined with the base folder to create the full video path'),
    (pagelink.wwlink,  'recordcount',  myagents.app,    'recordings made',      tablefieldinputhtml,        'number of recordings this session',
                            {'liveformat': '{wl.varvalue:4d}'}),
    (pagelink.wwtime,  'lasttrigger',   myagents.app,   'last recording',       tablefieldinputhtml,        'time of last recording',
                            {'liveformat': '%H:%M:%S'}),
    (pagelink.wwtime,  'lastactive',  myagents.app,     'last active',          tablefieldinputhtml,        'time recorder last active',
                            {'liveformat': '%H:%M:%S'}),
)

class webVideoRec(piCamRecorder.VideoRecorder):
     def allfields(self, pagelist, fielddefs):
        fieldstrs = [defn[0](wable=getattr(self, defn[1]), pagelist=pagelist, updators=defn[2], label=defn[3], shelp=defn[5], **(defn[6] if len(defn) > 6 else {})).
                webitem(fformat=defn[4]) for defn in fielddefs]
        return ''.join(fieldstrs)

     def makePanel(self, pagelist):
        return tablesectwrapper.format(style='trig_recordstyle', flipid='xtrvset', fields=self.allfields(pagelist,allfields), title='triggered recording Settings')
