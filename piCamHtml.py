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

    def __init__(self, readers, writers, **kwargs):
        """
        generic setup for html / web based client with other handy bits
        """
        assert 'html' in readers and 'app' in readers and 'pers' in readers and 'webv' in readers
        assert 'app' in writers and 'pers' in writers and 'user' in writers
        super().__init__(readers=readers, writers=writers, **kwargs)
        self.fhtmlid=self.getHierName()
        
    def _getHtmlValue(self, view):
        """
        """
        return {
            'label': self.genLabel.format(f=self),
            'cont' : self._getHtmlInputValue() if 'user' in self.viewUpdate else self._getHtmlOutputValue(),
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
                readers=pforms.extendViews(readers, {'app': '_getValue', 'pers': '_getValue', 'html': '_getHtmlValue', 'webv': '_getValue'}),
                writers=pforms.extendViews(writers, {'app': '_validValue', 'pers': '_validValue', 'user': '_validValue'}),
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
        if self.setValue('user', value[0]):
            return {'resp':200, 'rdata': '{} updated to {}'.format(self.name, str(self.getValue('app')))}
        else:
            return {'resp':200, 'rdata': '{} unchanged at {}'.format(self.name, str(self.getValue('app')))}

class htmlgenText(htmlgenBase):
    txtinputhtml = ('<input id="{f.fhtmlid:}" type="text" value="{sval:}" '
                   '''style="width: {f.clength:}em" onchange="appNotify(this, 'abcd')" />''')
    def __init__(self, readers=None , writers=None , clength=6, **kwargs):
        self.clength=clength
        super().__init__(
                readers=pforms.extendViews(readers, {'app': '_getSValue', 'html': '_getHtmlValue', 'webv': '_getSValue', 'pers':'_getSValue'}),
                writers=pforms.extendViews(writers, {'app': '_validStr', 'pers': '_validStr', 'user': '_validStr'}),
                **kwargs)
 
    def _getHtmlInputValue(self):
        cval=self._getVar()
        mv=self.txtinputhtml.format(f=self, sval=cval)
        if self.loglvl <= logging.INFO:
            self.log.info('_getHtmlInputValue returns %s' % mv)
        return mv

    def _getSValue(self, view):
        return self._getVar()

    def webUpdateValue(self, value):
        if self.setValue('user', value[0]):
            return {'resp':200, 'rdata': '{} updated to {}'.format(self.name, str(self.getValue('app')))}
        else:
            return {'resp':200, 'rdata': '{} unchanged at {}'.format(self.name, str(self.getValue('app')))}

class htmlgenPlainText(htmlgenBase):
    """
    a var which displays as a span only and is not editable
    """
    def __init__(self, readers=None , writers=None , clength=6, **kwargs):
        self.clength=clength
        super().__init__(
                readers=pforms.extendViews(readers, {'app': '_getSValue', 'html': '_getHtmlValue', 'webv': '_getSValue', 'pers':'_getSValue'}),
                writers=pforms.extendViews(writers, {'app': '_validStr', 'pers': '_validStr', 'user': '_validStr'}),
                **kwargs)

    def _getHtmlOutputValue(self):
        return self.genFixedContent.format(f=self, sval=str(self._getVar()))

    def _getSValue(self, view):
        return self._getVar()

    

class htmlgenNumber(htmlgenBase):
    """
    specialisation of htmlBase for numeric fields
    """
    numinputhtml = ('<input id="{f.fhtmlid:}" type="number" value="{sval:}" '
                   '''min="{f.minv:}" max="{f.maxv:}" pattern="-?\d+" style="width: {f.clength:}em" onchange="appNotify(this, 'abcd')" />''')
                # the valueu values defines the content of the value cell when the user can change it (although the
                # user update can be separately disabled)
    def __init__(self, clength=3, numstr='{}', readers=None, writers=None, **kwargs):
        self.numstr=numstr
        self.clength=clength
        print('htmlgenNumber: {} using readers'.format(kwargs['name'] if 'name' in kwargs else self.defaultName), readers)
        rx=pforms.extendViews(readers, {'app': '_getCValue', 'html': '_getHtmlValue', 'webv': '_getSValue', 'pers': '_getCValue'})
        wx=pforms.extendViews(writers, {'app': '_validNum', 'user': '_validNum', 'pers': '_validNum'})
        super().__init__(readers=rx, writers=wx, **kwargs)
 
    def _getHtmlInputValue(self):
        cval=self.numstr.format(self._getVar())
        mv=self.numinputhtml.format(f=self, sval=cval)
        if self.loglvl <= logging.INFO:
            self.log.info('_getHtmlInputValue returns %s' % mv)
        return mv

    def webUpdateValue(self, value):
        if self.setValue('user', value[0]):
            return {'resp':200, 'rdata': '{} updated to {}'.format(self.name, str(self.getValue('app')))}
        else:
            return {'resp':200, 'rdata': '{} unchanged at {}'.format(self.name, str(self.getValue('app')))}

class htmlStreamSize(htmlgenOption, pcf.streamResize):
    def __init__(self, readersOn=('app', 'pers', 'html'), writersOn=('app', 'pers', 'user'), **kwargs):
        super().__init__(readersOn=readersOn, writersOn=writersOn, **kwargs)

class htmlTimestamp(htmlgenBase, pforms.timeVar):
    """
    timestamp fields to record the time something significant changed. This only supports app update and
    typically then updates the web browser on the fly.
    """
    def __init__(self, readers=None, writers=None, readersOn=('app', 'html', 'webv'), writersOn=('app',), **kwargs):
        super().__init__(
                readers=pforms.extendViews(readers, {'html': '_getHtmlValue', 'app': '_getCValue', 'webv': '_getSValue', 'pers': '_getCValue'}),
                readersOn=readersOn,
                writers=pforms.extendViews(writers, {'app': '_validstamp', 'pers': '_validstamp', 'user': '_validstamp'}),
                writersOn=writersOn,
                **kwargs)
            
    def _getHtmlOutputValue(self):
        return self.genFixedContent.format(f=self, sval=self._getSValue('html'))
    
class htmlString(htmlgenText, pforms.textVar):
    pass

HTMLSTATUSSTRING={
    'name': 'status', 'fallbackValue': 'off',
    'onChange'  : ('dynamicUpdate','app'),
    'label'     : 'state',
    'shelp'     : 'current status of this activity',
    'readersOn' : ('html', 'webv'),
    'writersOn' : ('app',)}

class htmlPlainString(htmlgenPlainText, pforms.textVar):
    pass

class htmlFloat(htmlgenNumber, pforms.numVar):
    """
    generic html float
    """
    pass

class htmlInt(htmlgenNumber, pforms.intervalVar):
    pass

class htmlCyclicButton(htmlgenBase, pforms.listVar):
    def __init__(self, alist, app,
            readers={'html': '_getHtmlValue', 'app':'_getValue', 'pers': '_getValue', 'webv': '_getValue'},
            readersOn=('app', 'html', 'webv'),
            writers={'user': '_validValue', 'app': '_validValue', 'pers': '_validValue'},
            writersOn=('app', 'user'),
            **kwargs):
        super().__init__(readers=readers, readersOn=readersOn, writers=writers, writersOn=writersOn, app=app,
                vlists={v: alist for v in app.allviews}, **kwargs)

    def webUpdateValue(self, value):
        self._increment('user', value)
        return {'resp':200, 'rdata': '{} updated to {}'.format(self.name, str(self.getValue('app')))}

    def _getHtmlInputValue(self):
        mv = '''<span id="{f.fhtmlid:}" title="{f.shelp}" class="clicker clicker0" onclick="appNotify(this, 'abcd')" >{sval:}</span>'''.format(
                sval=self.getValue('webv'), f=self)       
        if self.loglvl <= logging.DEBUG:
            self.log.debug('_getHtmlInputValue returns %s' % mv)
        return mv

class htmlFolder(htmlgenBase, pforms.folderVar):
    tophtml='<h3>{topname}</h3><ul>{dlist}{flist}</ul>\n'
    folderitemhtml="<li><span>{0[path].name:14s} ({0[count]:3})</span></li>\n"
    fileitemhtml="<li><span>{0[path].name:14s} ({0[size]:3.2f}MB)</span></li>\n"

    def __init__(self, readers=None, writers=None, **kwargs):
        super().__init__(
                readers=pforms.extendViews(readers, {'html': '_getHtmlValue', 'app': '_getAppValue', 'webv': '_getStrValue', 'pers': '_getStrValue'}),
                writers=pforms.extendViews(writers, {'user': '_validValue', 'app': '_validValue', 'pers': '_validValue'}),
                **kwargs)
        
    def _getHtmlInputValue(self):
#        print('trees')
        dets=self._getDictValue(None)
#        print(dets)
        topname=list(dets.keys())[0]
        entries=sorted([v for v in dets[topname]['inner'].values() if v['type'] is None], key=lambda x: x['path'].name)
        dlist='\n'.join([self.folderitemhtml.format(e) for e in entries])
        entries=sorted([v for v in dets[topname]['inner'].values() if not v['type'] is None], key=lambda x: x['path'].name)
        flist='\n'.join([self.fileitemhtml.format(e) for e in entries])
        return self.tophtml.format(topname=topname, dlist=dlist, flist=flist)
        
    def _setVar(self, val):
        if val is None:
            x=17/0
        else:
            print('setting value', val)
            super()._setVar(val)

