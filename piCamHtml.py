#!/usr/bin/python3
"""
mixins and extensions for pforms and piCamFields classes that support web page generation and access
"""

import logging

import pforms
import piCamFields as pcf

class htmlgenBase():
    """
    mixin for pforms fields that makes html parts for the field.
    
    It has a default way of handling output only fields, but input fields use 
    subclasses. 
    
    When an html view of the field is requested it returns a dict with (so far) 3 parts:
        'label': html for the field's label
        'cont' : html for the field's content
        'shelp': html for the field's short help
    """
    genLabel =          '<label for="{f.fhtmlid:}" class="cw-label">{f.label:}:</label>'
                    # the label value defines the constru   ction of the label text
    genFixedContent =   '<span id="{f.fhtmlid:}" >{sval:}</span>'
                    # the content when the field cannot be changed by the user on the web page
    genShelp =          '{f.shelp:}'
                    # the short help

    def __init__(self, **kwargs):
#        print('htmlgenBase constructor starts')
        super().__init__(**kwargs)
        self.fhtmlid=self.getHierName()
#        print('htmlgenBase constructor ends')
        
    def _getHtmlValue(self, view):
        """
        """
        return {
            'label': self.genLabel.format(f=self),
            'cont' : self._getHtmlInputValue() if 'html' in self.viewUpdate else self._getHtmlOutputValue(),
            'shelp': self.genShelp.format(f=self),
            }

    def _getHtmlOutputValue(self):
        return self.genFixedContent.format(f=self, sval=str(self._getVar()))

    def _getHtmlInputValue(self):
        raise NotImplementedError('unable to create html for user editable field {} of class {}'.format(
                self.getHierName(), type(self).__name__))

class htmlgenOption(htmlgenBase):
    """
    specialisation of htmlgenBase for fields to be shown as drop down list
    """
    optionhtml = '<option value="{oval}"{sel}>{odisp}</option>'
    selecthtml = '''<select id="{f.fhtmlid:}" onchange="appNotify(this, 'abcd')" >{optall:}</select>'''

    def __init__(self, readers=None, writers=None, **kwargs):
        super().__init__(
                readers=pforms.extendViews(readers, {'html': '_getHtmlValue', 'expo': '_getValue'}),
                writers=pforms.extendViews(writers, {'html': '_validValue'}),
                **kwargs
        )

    def _getHtmlInputValue(self):
        cval=self._getVar()
        opts=[
            self.optionhtml.format(
                oval=optval, odisp=optval, sel=' selected' if optix==cval else '')
                for optix, optval in enumerate(self.viewlists['html'])]
        mv=self.selecthtml.format(f=self, optall=''.join(opts))
        if self.loglvl <= logging.DEBUG:
            self.log.debug('_getHtmlInputValue returns %s' % mv)
        return mv

    def webUpdateValue(self, value):
        if self.setValue('html', value[0]):
            return {'resp':200, 'rdata': '{} updated to {}'.format(self.name, self.getValue('expo'))}
        else:
            return {'resp':200, 'rdata': '{} unchanged at {}'.format(self.name, self.getValue('expo'))}

class htmlgenText(htmlgenBase):
    txtinputhtml = ('<input id="{f.fhtmlid:}" type="text" value="{sval:}" '
                   '''style="width: {f.clength:}em" onchange="appNotify(this, 'abcd')" />''')
    def __init__(self, clength=6, **kwargs):
        self.clength=clength
        super().__init__(**kwargs)

    def _getHtmlInputValue(self):
        cval=self._getVar()
        mv=self.txtinputhtml.format(f=self, sval=cval)
        if self.loglvl <= logging.INFO:
            self.log.info('_getHtmlInputValue returns %s' % mv)
        return mv

    def _getSValue(self, view):
        return self._getVar()

    def webUpdateValue(self, value):
        if self.setValue('app', value[0]):
            return {'resp':200, 'rdata': '{} updated to {}'.format(self.name, self.getValue('expo'))}
        else:
            return {'resp':200, 'rdata': '{} unchanged at {}'.format(self.name, self.getValue('expo'))}

class htmlgenNumber(htmlgenBase):
    """
    specialisation of htmlBase for numeric fields
    """
    numinputhtml = ('<input id="{f.fhtmlid:}" type="number" value="{sval:}" '
                   '''min="{f.minv:}" max="{f.maxv:}" pattern="-?\d+" style="width: {f.clength:}em" onchange="appNotify(this, 'abcd')" />''')
                # the valueu values defines the content of the value cell when the user can change it (although the
                # user update can be separately disabled)
    def __init__(self, clength=3, numstr='{}',
            readers={'html': '_getHtmlValue', 'expo':'_getSValue'},
            writers={'html': '_validNum',}, 
            **kwargs):
        self.numstr=numstr
        self.clength=clength
        super().__init__(readers=readers, writers=writers, **kwargs)
 
    def _getHtmlInputValue(self):
        cval=self.numstr.format(self._getVar())
        mv=self.numinputhtml.format(f=self, sval=cval)
        if self.loglvl <= logging.INFO:
            self.log.info('_getHtmlInputValue returns %s' % mv)
        return mv

    def webUpdateValue(self, value):
        if self.setValue('app', value[0]):
            return {'resp':200, 'rdata': '{} updated to {}'.format(self.name, self.getValue('expo'))}
        else:
            return {'resp':200, 'rdata': '{} unchanged at {}'.format(self.name, self.getValue('expo'))}

class htmlStreamSize(htmlgenOption, pcf.streamResize):
    pass

class htmlTimestamp(htmlgenBase, pforms.timeVar):
    """
    timestamp fields to record the time something significant changed. This only supports app update and
    typically then updates the web browser on the fly.
    """
    def __init__(self,
            readers={'html': '_getHtmlValue', 'app': '_getCValue', 'expo':'_getSValue', 'webv': '_getSValue'},
            writers={'app': '_validstamp'}, **kwargs):
        super().__init__(readers=readers, writers=writers, **kwargs)
            
    def _getHtmlOutputValue(self):
        return self.genFixedContent.format(f=self, sval=self._getSValue('html'))
    
class htmlStringnp(htmlgenText, pforms.textVar):
    def __init__(self, readers= None, writers= None, **kwargs):
        super().__init__(
            readers=pforms.extendViews(readers, {'app': '_getSValue', 'html': '_getHtmlValue', 'expo':'_getSValue'}),
            writers=pforms.extendViews(writers, {'app': '_validStr'}),
            **kwargs)

class htmlString(htmlStringnp):
    def __init__(self, readers=None, writers=None, **kwargs):
        super().__init__(
            readers=pforms.extendViews(readers, {'pers':'_getSValue'}),
            writers=pforms.extendViews(writers, {'pers': '_validStr'}), 
            **kwargs)

class htmlFloat(htmlgenNumber, pforms.numVar):
    """
    float with persistance
    """
    def __init__(self,
            readers = {'app': '_getCValue', 'html': '_getHtmlValue', 'expo':'_getSValue', 'pers':'_getCValue'},
            writers = {'app': '_validNum', 'html': '_validNum', 'pers': '_validNum'}, **kwargs):
        super().__init__(
                readers=readers, writers=writers, **kwargs)

class htmlFloatnp(htmlgenNumber, pforms.numVar):
    """
    float without persistence
    """
    def __init__(self,
            readers = {'app': '_getCValue', 'html': '_getHtmlValue', 'expo':'_getSValue'},
            writers = {'app': '_validNum', 'html': '_validNum'}, **kwargs):
        super().__init__(
                readers=readers, writers=writers, **kwargs)

class htmlInt(htmlgenNumber, pforms.intervalVar):
    def __init__(self,
            readers = {'html': '_getHtmlValue', 'expo':'_getSValue', 'pers': '_getCValue'},
            writers = {'html': '_validNum', 'app': '_validNum', 'pers': '_validNum'}, **kwargs):
        super().__init__(readers=readers, writers=writers, **kwargs)

class htmlIntnp(htmlgenNumber, pforms.intervalVar):
    def __init__(self,
            readers = {'html': '_getHtmlValue', 'expo':'_getSValue'},
            writers = {'html': '_validNum', 'app': '_validNum'}, **kwargs):
        super().__init__(readers=readers, writers=writers, **kwargs)

class htmlCyclicButton(htmlgenBase, pforms.listVar):
    def __init__(self, alist, app,
            readers={'html': '_getHtmlValue', 'app':'_getValue', 'expo': '_getValue'},
            writers={'html': '_validValue', 'app': '_validValue'},
            **kwargs):
        super().__init__(readers=readers, writers=writers, app=app,
                vlists={v: alist for v in app.allviews}, **kwargs)

    def webUpdateValue(self, value):
        self._increment('html', value)
        return {'resp':200, 'rdata': '{} updated to {}'.format(self.name, self.getValue('expo'))}

    def _getHtmlInputValue(self):
        mv = '''<span id="{f.fhtmlid:}" title="{f.shelp}" class="clicker clicker0" onclick="appNotify(this, 'abcd')" >{sval:}</span>'''.format(
                sval=self.getValue('expo'), f=self)       
        if self.loglvl <= logging.DEBUG:
            self.log.debug('_getHtmlInputValue returns %s' % mv)
        return mv
