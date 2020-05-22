import piCamRecorder, pagelink

from pootlestuff.watchables import myagents

from webstrings import tablefieldinputhtml, tablefielddropdnhtml, tablefieldcyclicbtndnhtml, tablesectwrapper

class webVideoRec(piCamRecorder.VideoRecorder):
    def streaminfo(self, pagelist):
        fields = \
            pagelink.wwlink(wable=self.status, pagelist=pagelist, userupa=None, liveupa=myagents.app,
                    label = 'status', shelp='video recorder activity status').webitem(fformat=tablefieldinputhtml) + \
            pagelink.wwenumbtn(wable=self.startstopbtn, pagelist=pagelist, userupa=myagents.user, liveupa = None,
                    label='start / stop recorder' , shelp='start / stop recorder activity').webitem(fformat=tablefieldcyclicbtndnhtml) +\
            pagelink.wwenum(wable=self.autostart, pagelist=pagelist, userupa=myagents.user, liveupa=None,
                    label = 'auto start', shelp='starts recorder when app runs').webitem(fformat=tablefielddropdnhtml) +\
            pagelink.wwenumbtn(wable=self.recordnow, pagelist=pagelist, userupa=myagents.user, liveupa=None,
                    label = 'record now', shelp='start recording if recorder waiting').webitem(fformat=tablefieldcyclicbtndnhtml) +\
            pagelink.wwenum(wable=self.cpudetect, pagelist=pagelist, userupa=myagents.user, liveupa=None,
                    label = 'enable cpu detect trigger', shelp='triggers recording when cpu movement detection triggers').webitem(fformat=tablefielddropdnhtml) + \
            pagelink.wwenum(wable=self.gpiodetect, pagelist=pagelist, userupa=myagents.user, liveupa=None,
                    label = 'enable gpio trigger', shelp='triggers recording when gpio input triggers').webitem(fformat=tablefielddropdnhtml) + \
            pagelink.wwenum(wable=self.format, pagelist=pagelist, userupa=myagents.user, liveupa=None,
                    label = 'recording format', shelp='video type to record').webitem(fformat=tablefielddropdnhtml) + \
            pagelink.wwlink(wable=self.rec_width, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:3d}',
                label = 'recorded video width', shelp='camera output resized for streaming').webitem(fformat=tablefieldinputhtml) + \
            pagelink.wwlink(wable=self.rec_height, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:3d}',
                label = 'recorded video height', shelp='camera output resized for streaming').webitem(fformat=tablefieldinputhtml) + \
            pagelink.wwlink(wable=self.recordback, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:4.2f}',
                label = 'pre-trigger time', shelp='saves video for (roughly) specified period before the trigger happened (seconds) - values less than .25 s may not work'
                        ).webitem(fformat=tablefieldinputhtml) + \
            pagelink.wwlink(wable=self.recordfwd, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:4.2f}',
                label = 'post trigger time', shelp='records video for this period after trigger condition ceases').webitem(fformat=tablefieldinputhtml) + \
            pagelink.wwlink(wable=self.splitrecord, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:7.2f}',
                label = 'split recording time', shelp='When recording, start a new file after this numer of minutes').webitem(fformat=tablefieldinputhtml) + \
            pagelink.wwlink(wable=self.maxvidlength, pagelist=pagelist, userupa=myagents.user, liveupa=None, liveformat='{wl.varvalue:3d}',
                label = 'max video length', shelp='number of h264 files to merge to a single MP4 file').webitem(fformat=tablefieldinputhtml) + \
            pagelink.wwenum(wable=self.saveh264, pagelist=pagelist, userupa=myagents.user, liveupa=None,
                    label = 'save h264 files', shelp='keeps the h264 video files after mp4 conversion (otherwise they are deleted)').webitem(fformat=tablefielddropdnhtml) +\
            pagelink.wwlink(wable=self.vidfold, pagelist=pagelist, userupa=myagents.user, liveupa=None,
                label = 'base folder for videos', shelp='The base folder is combined with the video filename to create the full video filename path').webitem(fformat=tablefieldinputhtml) + \
            pagelink.wwlink(wable=self.vidfile, pagelist=pagelist, userupa=myagents.user, liveupa=None,
                label = 'recorded video filename', shelp='This is combined with the base folder to create the full video path').webitem(fformat=tablefieldinputhtml) + \
            pagelink.wwlink(wable=self.recordcount, pagelist=pagelist, userupa=None, liveupa=myagents.app, liveformat='{wl.varvalue:4d}',
                label = 'recordings made', shelp='number of recordings this session').webitem(fformat=tablefieldinputhtml) + \
            pagelink.wwtime(wable=self.lasttrigger, pagelist=pagelist, userupa=None, liveupa=myagents.app, liveformat='%H:%M:%S',
                label = 'last recording', shelp='time of last recording').webitem(fformat=tablefieldinputhtml) +\
            pagelink.wwtime(wable=self.lastactive, pagelist=pagelist, userupa=None, liveupa=myagents.app, liveformat='%H:%M:%S',
                label = 'last active', shelp='time streaming last active').webitem(fformat=tablefieldinputhtml)

        return tablesectwrapper.format(style='trig_recordstyle', flipid='xtrvset', fields=fields, title='triggered recording Settings')
