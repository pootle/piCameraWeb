import triggergpio, pagelink

from pootlestuff.watchables import myagents

from webstrings import tablefieldinputhtml, tablefielddropdnhtml, tablefieldcyclicbtndnhtml, tablesectwrapper

allfielddefs=(
    (pagelink.wwenum,       'status',         myagents.app,   'status',     tablefielddropdnhtml,     'gpio trigger activity status'),
    (pagelink.wwenum,       'pintrigger',     myagents.app,   'pin state',  tablefielddropdnhtml,
                                                    'shows if the pin is currently triggered (even if not setting the main trigger'),
    (pagelink.wwenumbtn,    'startstopbtn',   myagents.user,  'start / stop', tablefieldcyclicbtndnhtml, 'start / stops monitoring the gpio pin'),
    (pagelink.wwenum,       'autostart',      myagents.user,  'auto start',  tablefielddropdnhtml,    'starts monitoring when app runs'),
    (pagelink.wwenumbtn,    'usertrigger',    myagents.user,  'trigger now', tablefieldcyclicbtndnhtml,'manually set / clear the trigger'),
    (pagelink.wwlink,       'pinno',          myagents.user,  'pin no.',     tablefieldinputhtml,      'broadcom pin no to watch',
                                                    {'liveformat': '{wl.varvalue:2d}'}),
    (pagelink.wwenum,       'pullud',         myagents.user,  'pull up setting', tablefielddropdnhtml, 'sets pull-up pull down or neither on the trigger pin'),
    (pagelink.wwenum,       'triglvl',        myagents.user,  'trigger level', tablefielddropdnhtml,   'sets if logic high or low causes trigger'),
    (pagelink.wwlink,       'steadytime',     myagents.user,  'steady time', tablefieldinputhtml,
                            'time (in seconds) the pin must be stable at trigger level before trigger is set', {'liveformat': '{wl.varvalue:2.4f}'}),
    (pagelink.wwlink,       'holdtime',       myagents.user,  'hold time',   tablefieldinputhtml,
                            'once triggered, the trigger remains for at least this much time (in seconds)', {'liveformat': '{wl.varvalue:2.4f}'}),
    (pagelink.wwlink,       'trigcount',      myagents.app,   'trigger count', tablefieldinputhtml, 
                            'number of times this trigger has fired this session', {'liveformat': '{wl.varvalue:4d}'}),
    (pagelink.wwtime,       'lasttrigger',    myagents.app,   'last trigger', tablefieldinputhtml,      'time  last active', {'liveformat': '%H:%M:%S'}),
    (pagelink.wwtime,       'lastactive',     myagents.app,   'last active',  tablefieldinputhtml,      'time streaming last active', {'liveformat': '%H:%M:%S'}),
)

savedef = (
    (pagelink.wwbutton,     'save_settingsbtn',myagents.user, 'save default settings', tablefieldcyclicbtndnhtml, 'saves current settings as default'),
)

class webtriggergpio(triggergpio.gpiotrigger):
    def allfields(self, pagelist, fielddefs):
        fieldstrs = [defn[0](wable=getattr(self, defn[1]), pagelist=pagelist, updators=defn[2], label=defn[3], shelp=defn[5], **(defn[6] if len(defn) > 6 else {})).
                webitem(fformat=defn[4]) for defn in fielddefs]
        return ''.join(fieldstrs)

    def makePanel(self, pagelist):
        return tablesectwrapper.format(style='gpio_triggerstyle', flipid='xgptrig', fields=self.allfields(pagelist, allfielddefs), title='gpio trigging')

    def makeMainPage(self, pagelist, qp, pp, page):
        fvars={
            'pageid'    : pagelist.pageid,
            'fields'    : self.allfields(pagelist=pagelist, fielddefs=allfielddefs+savedef),
        }
        with open(page,'r') as pf:
            templ=pf.read()
        return {'resp':200, 'headers': (('Content-Type', 'text/html; charset=utf-8'),), 'data':templ.format(**fvars)}

