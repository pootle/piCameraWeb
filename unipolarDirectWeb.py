import unipolarDirect, pagelink

from pootlestuff.watchables import myagents

from webstrings import tablefieldinputhtml, tablefielddropdnhtml, tablefieldcyclicbtndnhtml, tablesectwrapper

allfielddefs=(
    (pagelink.wwlink, 'status',         myagents.app,   'status',       tablefieldinputhtml,    'focus status'),
    (pagelink.wwenum, 'drive_mode',     myagents.user,  'motor mode',   tablefielddropdnhtml,   'sets the motor mode - use only goto'),
    (pagelink.wwenum, 'drive_stepmode', myagents.user,  'motor step type',tablefielddropdnhtml, 'sets the step type used for the motor'),
    (pagelink.wwlink, 'drive_uStepPos', myagents.app,   'current ustep pos',tablefieldinputhtml,
                                            'shows the current motor position', {'liveformat': '{wl.varvalue:7d}'}),
    (pagelink.wwlink, 'drive_target_pos',myagents.user, 'target ustep pos', tablefieldinputhtml,    
                                            'for goto mode - the targett motor position', {'liveformat': '{wl.varvalue:7d}'}),
    (pagelink.wwlink, 'drive_target_intvl',myagents.user,'step interval', tablefieldinputhtml,
                                            'when moving, this is the time between steps in seconds', {'liveformat': '{wl.varvalue:5.4f}'}),
    (pagelink.wwlink, 'drive_step_intvl',myagents.app,   'current step interval', tablefieldinputhtml, 'step interval active'),
    (pagelink.wwenum, 'drive_reverse',  myagents.user,   'invert motor direction', tablefielddropdnhtml, 'motor goes the other way, nothing else changes'),
    (pagelink.wwlink, 'drive_backlash', myagents.user,   'backlash adjustment', tablefieldinputhtml,
                        'in goto mode this adjustment is made to the current location when the motor direction reverses', {'liveformat': '{wl.varvalue:4d}'}),
    (pagelink.wwlink, 'drive_hold_power', myagents.user, 'hold power factor', tablefieldinputhtml,
                                    'in range 0 -> 1 defines the multiplier used for actual power to hold position (0 for none, 1 for full)'),
    (pagelink.wwlink, 'drive_slow_power', myagents.user, 'slow power factor', tablefieldinputhtml,
                                    'in range 0 -> 1 defines the multiplier used for actual power when slow stepping (0 for non, 1 for full)'),
    (pagelink.wwlink, 'drive_fast_power', myagents.user, 'fast power factor', tablefieldinputhtml,
                                    'in range 0 -> 1 defines the multiplier used for actual power when fast stepping (0 for non, 1 for full)'),
    (pagelink.wwlink, 'drive_slow_limit', myagents.user, 'transition intvl', tablefieldinputhtml,'sets the step interval below which fast power factor is used'),
    (pagelink.wwlink, 'drive_PWM_frequency',myagents.NONE,'PWM_frequency', tablefieldinputhtml, 'requested PWM frequency (Hz)'),
    (pagelink.wwlink, 'drive_actual_frequency',myagents.NONE,'actual frequency', tablefieldinputhtml, 'actual PWM frequency in use (Hz)'),
    (pagelink.wwlink, 'drive_pins',       myagents.NONE, 'broadcom pin numbers', tablefieldinputhtml,   '4 broadcom pin numbers in order'),
)

savedef = (
    (pagelink.wwbutton,'save_settingsbtn',  myagents.user, 'save default settings', tablefieldcyclicbtndnhtml, 'saves current settings as default'),
)

class webStepper(unipolarDirect.SimpleUniStepper):
    def allfields(self, pagelist, fielddefs):
        fieldstrs = [defn[0](wable=getattr(self, defn[1]), pagelist=pagelist, updators=defn[2], label=defn[3], shelp=defn[5], **(defn[6] if len(defn) > 6 else {})).
                webitem(fformat=defn[4]) for defn in fielddefs]
        return ''.join(fieldstrs)

    def makePanel(self, pagelist):
        return tablesectwrapper.format(style='focusstyle', flipid='xfcs', fields=self.allfields(pagelist,allfielddefs), title='focus stepper controls')

    def makeMainPage(self, pagelist, qp, pp, page):
        fvars={
            'pageid'    : pagelist.pageid,
            'fields'    : self.allfields(pagelist=pagelist, fielddefs=allfielddefs+savedef),
        }
        with open(page,'r') as pf:
            templ=pf.read()
        return {'resp':200, 'headers': (('Content-Type', 'text/html; charset=utf-8'),), 'data':templ.format(**fvars)}
