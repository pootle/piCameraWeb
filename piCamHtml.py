#!/usr/bin/python3
"""
mixins and extensions for pforms and piCamFields classes that support web page generation and access
"""

import logging
import pathlib

import pforms, ptree, treefiles
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
        assert 'app' in writers and 'pers' in writers#and 'user' in writers
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

    def _getHtmlOutputValue(self):
        return self.genFixedContent.format(f=self, sval=self.getValue('pers'))

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

class htmlStatus(htmlString):
    genFixedContent =   '<span id="{f.fhtmlid:}" style="font-size:160%; font-weight: bold;" >{sval:}</span>'

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
    generic html float var
    """
    pass

class htmlInt(htmlgenNumber, pforms.intervalVar):
    """
    generic html int var
    """
    pass

class htmlChoice(htmlgenOption, pforms.listVar):
    """
    generic choice field for simple drop down lists
    """
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
        dets=self._getDictValue(None)
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
            super()._setVar(val)

class xhtmlFolder2(htmlgenBase, pforms.folderVar):
    """
    This displays a folder and allows basic navigation - typically from other fields.
    
    The root folder is stops navigation above this point
    """
    def __init__(self, root, readers=None, writers=None, **kwargs):
        self.root=pathlib.Path(root).expanduser()
        super().__init__(
                readers=pforms.extendViews(readers, {'html': '_getHtmlValue', 'app': '_getAppValue', 'webv': '_getStrValue', 'pers': '_getStrValue'}),
                writers=pforms.extendViews(writers, {'app': '_validValue', 'pers': '_validValue'}), #'user': '_validValue', 
                readersOn= ('app', 'html', 'webv'),
                writersOn= ('app', ),
                **kwargs)

class folderVar(pforms.listVar):
    """
    Allows user to select a file from within a folder, the folder name is specified in a related var.
    
    Note: Currently this var must follow the basefoldervar in setup.
    """
    def __init__(self, name, parent, app, value, basefoldervar, valueView='app', **kwargs):
#        super(ptree.treeob).__init__(name=name, parent=parent, app=app)
# Truly horrible bit follows until I work out how to do it properly! this is the init code for a treeob in ptree
        self.name=name
        self.parent=parent
        self.app=app
        if not parent is None:
            parent[self.name]=self
# horrible ends
        self.base=pathlib.Path(self[basefoldervar].getValue(valueView)).expanduser()
        if self.base.exists():
            assert self.base.is_dir()
        else:
            self.base.mkdir(parents=True, exist_ok=True)
#        fl=[f.name for f in self.base.iterdir() if not f.name.startswith('.')]
#        fl.insert(0, '-off-')
        self.valuePath=pathlib.Path(self.base)
        flist=self._makelists()
        if value is None:
            value='-off-'
        super().__init__(name=name, parent=parent, app=app, value=value, vlists=flist, valueView=valueView, **kwargs)

    def getFile(self):
        """
        If the value is a file, returns a pathlib Path for the file, otherwise returns None
        """
        vidx=self._getVar()
        if vidx == 0:
            return None
        fpath=self.base/self.getValue('app')
        return fpath if fpath.is_file() else None        

    def setValue(self, view, value):
        """
        Sets the var's value after conversion from the given view. Calls any onChange callbacks
        if the value changes.
        
        This updates the list of values as the user navigates through the directory tree
        
        view: name of the view to be used.
        
        value: new value expressed in the given view 
        
        returns True if the value changes, else False
        
        raises  RuntimeError if the view is not known
                ValueError if the value is not valid in the given view
        """
        if view in self.viewUpdate:
            print('htmlFolderFile.setValue using value',value)
            newv=self.viewUpdate[view](view, value)
            oldValue=self._getVar()
            if newv==0:
                self.valuePath=self.valuePath.parent
                changed=True
            elif newv==1:
                if oldValue==1:
                    changed=False
                else:
                    changed=True
            else:
                if self.valuePath.is_dir():
                    self.valuePath=self.valuePath/value
                    changed=True
                    if self.valuePath.is_dir():
                        newv=0
                    else:
                        self.valuePath=self.valuePath.parent
                else:
                    print('NNNNNNNNNNNNNNNNNNNNNNNEVER HERE')
                    if newv==oldValue:
                        changed=False
                    else:
                        self.valuePath=self.valuePath.parent/value
                        changed=True
            print('folderVar.setValue checkpoint, changed is',changed)
            if changed:
                self._setVar(newv)
                flist=self._makelists()
                self.viewlists={k:flist for k in self.viewlists.keys()}
                if self.loglvl <= logging.DEBUG:
                    self.log.debug('var {} view {} with value {} updated {} to {}'.format(self.name, view, value, oldValue, newv))
                if view in self.onChange:
                    for f in self.onChange[view]:
                        f(oldValue=oldValue, newValue=newv, view=view, var=self)
                return True
            else:
                if self.loglvl <= logging.DEBUG:
                    self.log.debug('var {} view {} with value {} is unchanged'.format(self.name, view, value))
                return False
        else:
            raise RuntimeError('view {} not known in field {}'.format(view, self.name))

    def _makelists(self):
        v=self.valuePath
        if v.exists():
            if v.is_dir():
               flist=[f.name for f in v.iterdir() if not f.name.startswith('.')]  
               value='-off-'
            else:
               w=v.parent
               flist=[f.name for f in w.iterdir() if not f.name.startswith('.')]  
               value=v.name
        else:
            flist=[]
            value='-off-'
        flist.insert(0, '-off-')
        flist.insert(0, '..')
        return flist

class htmlFolderFile(htmlgenOption, folderVar):
    """
    allows navigation and selection of files / folder on the server using a drop down list
    """
    selecthtml = '''<select id="{f.fhtmlid:}" onchange="smartNotify(this, 'abcd')" >{optall:}</select>'''
    def webUpdateValue(self, value):
        """
        This works in conjunction with the js function smartNotify to apply updates and return data to update the webpage appropriately
        """
        print('webUpdateValue in', self.name)
        if self.setValue('user', value[0]):
            rdata={'msg': '{} updated to {}'.format(self.name, str(self.getValue('app'))),
                  }
        else:
            rdata={'msg': '{} unchanged at {}'.format(self.name, str(self.getValue('app'))),
                  }
        cval=self._getVar()
        rdata['innerHTML']= ''.join([
            self.optionhtml.format(
                oval=optval, odisp=optval, sel=' selected' if optix==cval else '')
                for optix, optval in enumerate(self.viewlists['html'])])
        if self.loglvl <= logging.DEBUG:
            self.log.debug('update for {} returns {}'.format(self.fhtmlid, rdata))
        return {'resp':200, 'rdata': rdata}



class folderVar2(pforms.baseVar):
    """
    Allows user to navigate filestore, selecting a file or a folder.
    """
    def __init__(self, allowcreate=False, **kwargs):
        self.allowcreate=allowcreate
        super().__init__(**kwargs)

    def setInitialValue(self, view, value, fallbackValue):
        try:
            v=pathlib.Path(value).expanduser()
            self._setVar(v)
        except:
            v=None
        if v is None:
            v=pathlib.Path(fallbackValue).expanduser()
        if v.exists():
            if not (v.is_dir() or v.is_file()):
                raise ValueError('path {} is not a file or folder'.format(str(v)))
        elif self.allowcreate:
            v.mkdir(parents=True)
        else:
            raise ValueError('path {} does not refer to an existing file or folder'.format(str(v)))
        self._setVar(v)

    def getFile(self):
        """
        If the value is a file, returns a pathlib Path for the file, otherwise returns None
        """
#        vidx=self._getVar()
#        if vidx == 0:
#            return None
        fpath=self.getValue('app')
        return fpath if fpath.is_file() else None        

    def _validValue(self, view, value):
        """
        value: navigation from current folder:
                    '.' no change
                    '..' move to parent folder
                    <str> move to subfolder or file <str> if <str> is not a file or folder within the current folder
                            and allowcreate is True, then create a folder <str>
        
        returns : existing pathlib.Path (unchanged) or new pathlib.Path of the new folder or file
        
        raises  : ValueError if the provided value is invalid
        """
        if value=='.':
            return self._getVar()
        elif value=='..':
            newf=self._getVar().parent
            if not newf.is_dir():
                raise ValueError('Cannot move to parent of ({})'.format(str(self._getVar())))
        else:
            oldv=self._getVar()
            newf=oldv/value if oldv.is_dir() else oldv.parent/value
            if not newf.exists():
#                if self.allowcreate:
#                    newf.mkdir()
#                else:
                    raise ValueError('Cannot find folder {} within folder {}'.format(newf.name, str(self._getVar())))
        return newf

    def _getAppValue(self, view):
        return self._getVar()

    def _getStrValue(self, view):
        return str(self._getVar())

    def _makelists(self):
        v=self.valuePath
        if v.exists():
            if v.is_dir():
               flist=[f.name for f in v.iterdir() if not f.name.startswith('.')]  
            else:
               w=v.parent
               flist=[f.name for f in w.iterdir() if not f.name.startswith('.')]  
        else:
            flist=[]
        flist.insert(0, '..')
        return flist

class htmlFolderList(htmlgenBase, folderVar2):
    """
    allows navigation and selection of files / folders on the server using an exploded (visible list)
    """
    entryfoldupd='''<tr class="clickable" onclick="baseSmartNotify(document.getElementById('{fid}'), '{path.name}')"><td>{path.name}</td><td>files:{count:3d}</td></tr>\n'''
    entryfileupd='''<tr class="clickable" onclick="baseSmartNotify(document.getElementById('{fid}'), '{path.name}')"><td>{path.name}</td><td>size :{size:4d}</td></tr>\n'''
    entryupupd  ='''<tr class="clickable" onclick="baseSmartNotify(document.getElementById('{fid}'), '..')"><td>..</td></tr>\n'''

    entryfoldop='<tr><td>{path.name}</td><td>files:{count:3d}</td></tr>\n'
    entryfileop='<tr><td>{path.name}</td><td>size :{size:4d}</td></tr>\n'

    def __init__(self, readers=None, writers=None, **kwargs):
        super().__init__(
                readers=pforms.extendViews(readers, {'app': '_getAppValue', 'pers': '_getStrValue', 'html': '_getHtmlValue', 'webv': '_getStr Value'}),
                writers=pforms.extendViews(writers, {'app': '_validValue', 'pers': '_validValue', 'user': '_validValue'}),
                **kwargs
        )

    def webUpdateValue(self, value):
        """
        This works in conjunction with the js function smartNotify to apply updates and return data to update the webpage appropriately
        """
        print('webUpdateValue in', self.name, 'with', value)
        update=False
        try:
            update= self.setValue('user', value[0])
            rdata={'msg'   : '{} updated to {}'.format(self.name, str(self.getValue('app'))) if update else '{} unchanged at {}'.format(
                            self.name, str(self.getValue('app'))),
                  }
        except ValueError:
            rdata={'msg': '{} invalid value requested {}'.format(self.name, value[0]),}
        if update:
            rdata['innerHTML']=self._getHtmlInputValue()
        if self.loglvl <= logging.DEBUG:
            self.log.debug('update for {} returns {}'.format(self.fhtmlid, rdata))
        return {'resp':200, 'rdata': rdata}

    def _getHtmlOutputValue(self):
        folderinfo=list(treefiles.pl(current if current.is_dir() else current.parent))[0]
        bi=[]
        for name, info in folderinfo['inner'].items():
            if info['type'] is None:
                bi.append(self.entryfoldop.format(fid=self.fhtmlid, **info))
            else:
                bi.append(self.entryfileop.format(fid=self.fhtmlid, **info))
        output='<table><tr><td colspan="2"><h3>{head}</h3></td></tr>\n{flist}</table>'.format(head=str(self._getVar()), flist=''.join(bi))
        return self.genFixedContent.format(f=self, sval=output)

    def _getHtmlInputValue(self):
        current = self._getVar()
        folderinfo=list(treefiles.pl(current if current.is_dir() else current.parent).values())[0]
        bi=[]
        bi.append(self.entryupupd.format(fid=self.fhtmlid))
        for name, info in folderinfo['inner'].items():
            if info['type'] is None:
                bi.append(self.entryfoldupd.format(fid=self.fhtmlid, **info))
            else:
                bi.append(self.entryfileupd.format(fid=self.fhtmlid, **info))
        output='<table><tr><td colspan="2"><span>{head}</span></td></tr>\n{flist}</table>'.format(flist=''.join(bi), head=str(self._getVar()))
        return self.genFixedContent.format(f=self, sval=output)

class htmlFile(htmlgenOption, pforms.listVar):
    """
    experimental - tracks a file and provides simple navigation through file system.
    """

    selecthtml = '''<select id="{f.fhtmlid:}" onchange="smartNotify(this, 'abcd')" >{optall:}</select>'''

    def __init__(self, value, fallbackValue='~/', valueView='app', readers=None, writers=None, **kwargs):
        if value is None:
            v=pathlib.Path(fallbackValue).expanduser()
            value='-off-'
        else:
            try:
                v=pathlib.Path(value).expanduser()
            except:
                v=None
            if v is None:
                v=pathlib.Path(fallbackValue).expanduser()
        if v.is_dir():
            value='-off-'
        else:
            value=v.name
        self.valuePath=v
        flist=self._makelists()
        rdr=pforms.extendViews(readers, {'html': '_getHtmlValue', 'app': '_getAppValue', 'webv': '_getStrValue', 'pers': '_getStrValue'})
        wtr=pforms.extendViews(writers, {'user': '_validValue', 'app': '_validValue', 'pers': '_validValue'})
        s=set(rdr.keys()).union(wtr.keys())
        vlists={k:flist for k in s}
        print('htmlfile.__init__ calls super constructor with value {}'.format(value))
        super().__init__(readers=rdr, writers=wtr, value=value, vlists=vlists, fallbackValue=None, valueView=valueView, **kwargs)

    def getFile(self):
        """
        If the value is a file, returns a pathlib Path for the file, otherwise returns None
        """
        return self.valuePath if self.valuePath.is_file() else None

    def _makelists(self):
        v=self.valuePath
        if v.exists():
            if v.is_dir():
               flist=[f.name for f in v.iterdir() if not f.name.startswith('.')]  
               value='-off-'
            else:
               w=v.parent
               flist=[f.name for f in w.iterdir() if not f.name.startswith('.')]  
               value=v.name
        else:
            flist=[]
            value='-off-'
        flist.insert(0, '-off-')
        flist.insert(0, '..')
        return flist

    def setValue(self, view, value):
        """
        Sets the var's value after conversion from the given view. Calls any onChange callbacks
        if the value changes.
        
        This updates the list of values as the user navigates through the directory tree
        
        view: name of the view to be used.
        
        value: new value expressed in the given view 
        
        returns True if the value changes, else False
        
        raises  RuntimeError if the view is not known
                ValueError if the value is not valid in the given view
        """
        if view in self.viewUpdate:
            newv=self.viewUpdate[view](view, value)
            oldValue=self._getVar()
            if newv==0:
                self.valuePath=self.valuePath.parent
                changed=True
            elif newv==1:
                if oldValue==1:
                    changed=False
                else:
                    changed=True
            else:
                if self.valuePath.is_dir():
                    self.valuePath=self.valuePath/value
                    changed=True
                    newv=0
                else:
                    if newv==oldValue:
                        changed=False
                    else:
                        self.valuePath=self.valuePath.parent/value
                        changed=True
            if changed:
                self._setVar(newv)
                flist=self._makelists()
                self.viewlists={k:flist for k in self.viewlists.keys()}
                if self.loglvl <= logging.DEBUG:
                    self.log.debug('var {} view {} with value {} updated {} to {}'.format(self.name, view, value, oldValue, newv))
                if view in self.onChange:
                    for f in self.onChange[view]:
                        f(oldValue=oldValue, newValue=newv, view=view, var=self)
                return True
            else:
                if self.loglvl <= logging.DEBUG:
                    self.log.debug('var {} view {} with value {} is unchanged'.format(self.name, view, value))
                return False
        else:
            raise RuntimeError('view {} not known in field {}'.format(view, self.name))

    def webUpdateValue(self, value):
        """
        This works in conjunction with the js function smartNotify to apply updates and return data to update the webpage appropriately
        """
        if self.setValue('user', value[0]):
            rdata={'msg': '{} updated to {}'.format(self.name, str(self.getValue('app'))),
                  }
        else:
            rdata={'msg': '{} unchanged at {}'.format(self.name, str(self.getValue('app'))),
                  }
        cval=self._getVar()
        rdata['innerHTML']= ''.join([
            self.optionhtml.format(
                oval=optval, odisp=optval, sel=' selected' if optix==cval else '')
                for optix, optval in enumerate(self.viewlists['html'])])
        if self.loglvl <= logging.DEBUG:
            self.log.debug('update for {} returns {}'.format(self.fhtmlid, rdata))
        return {'resp':200, 'rdata': rdata}

    def _getAppValue(self, view):
        return self.valuePath

    def _getStrValue(self, view):
        return str(self.valuePath)