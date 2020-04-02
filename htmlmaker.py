#!/usr/bin/python3
"""
module with functions that generates html fragments and pages for an app

Each var that appears in a web page will use a function here to create the html when the web page is requested.

Each var's html fragment uses the current value of the var in the generated html and can also setup the things needed
so that the data on the web page is kept up to date if the var's value is updated in the app or to allow changes by the user 
to the fields on the web page are passed back to the server to update the app.

For live update, a javascript function in the web page is run when the page has loaded (see liveupdates in pymon.js).
It makes an http request with an update list name when the page loads. The method run in the requesthandler then sets up to stream 
updates back to the javascript function at regular intervals, this will run until the connection is interrupted
(typically because the user has left the web page).

In detail:
=========    
Each var that appears on the web page is allocated a unique id (the first time a web page uses the var), this id is used for the lifetime
of the app.

Each web page request for a page that allows dynamic update (in either direction), is allocated a unique id (the current time timestamp is used).
As the page is assembled, each var that allows dynamic update has an 'updator' class instance created that has functions to map from var values 
to user interface value, and from user input values to var values. The particular updator subclass used is defined in the page definition.
A dict is built for each request for a dynamic web page that maps the var's id to the updator instance used to translate between the var and its UI
representation.

This allows a var to appear multiple times on a single page with different representations and (more normally) to appear on multiple pages with 
different representation.

old version......
=========
As a page is generated, a timestamp is used to create an id used by the web page to identify the set of entries it can update.
Each var is allocated a unique tag the first time it is used in this way, and this module keeps a map of tag -> var.
    'app'       : the application object with the var to be kept up to date
    'varlist'   : a list of 3-tuples for each var in that app to be kept up to date, the tuple entries are
        0:          the hierarchic name of the var with the app
        1:          the class used to link between the var and the html fragment
        2:          (some of) the parameters needed to call the link class' constructor

This class sets up a notification on the var, called whenever the value changes. The notification function adds an entry
to a list of var's that need updating (the various bits of the app are running in other threads.

The handler function polls the list on a regular basis, and sends back updates for the var's that changed. When the connection
between the server and the web page fails, all notifications are removed.
"""
import time, json
from threading import Lock

class varupdater():
    """
    An instance of this class is created for each field on a web page that the user or app can update dynamically It supports:
        
         The user updating the value on the web page dynamically (i.e. changes in the value on screen
            are automatically passed back to the webserver and then via an instance of this class the var's value is updated)

         Updates to the var's value are automatically pushed to the web page to update the displayed value linked via the instance
 
    An instance of this class is created for each updateable var when a web page is created. It will be dropped when
    the connection between that web page and the server breaks (typically when the user leaves the page).
    """
    def __init__(self, avar, pagelist, userupa, liveupa, updateformat=None):
        """
        sets up an updator that links an app var to a field on a web page
        
        avar        : the var in question
        
        pagelist    : the pageupdatelist instance this instance is used by
        
        liveupa : the name of the agent that will change a var that needs to be updated dynamically on the web page (or None if not)
    
        userupa : the name of the agent to be used when an incoming update top the web page needs to be update an appvar (or None if user cannot update)

        updateformat: a string to be used to format the new value when sent to the web browser, None means no formatting applied
                      string.format is applied to this string with varval containing getValue() result from the var
        """
        self.avar=avar
        self.pagelist=pagelist
        self.updateformat=updateformat
        self.userupa=userupa
        self.liveupa=liveupa
        if userupa or liveupa:
            self.fid=self.pagelist.add_field(userupa=userupa, liveupa=liveupa,upper=self)
            if liveupa:
                self.avar.addNotify(self.varchanged, liveupa)

    def varchanged(self, var=None, agent=None, newValue=None, oldValue=None):
        self.pagelist.markpending(self)

    def drop(self):
        if self.liveupa:
            self.avar.removeNotify(self.varchanged, self.liveupa)
        
    def getUpdate(self):
        return self.fid, self.avar.getValue() if self.updateformat is None else self.updateformat.format(varval=self.avar.getValue())

    def websetter(self, webval): # this should raise notimplementederror
        raise NotImplementedError('webset undefined for var' + self.avar.getHierName())

class varfloatupdater(varupdater):
    """
    subclass for float vars.
    
    Expects a single string in the array vals, it checks it converts to a float
    """
    def convertone(self, vals):
        return float(vals[0])

    def websetter(self, webval):
        try:
            vv=self.convertone(webval)
        except:
            return b'fail variable failed to convert to float'
        try:
            self.avar.setValue(vv, self.pagelist.useragent)
        except:
            return ('failed to update %s to value %f' % (self.avar.getHierName(), vv)).encode()
        return b'OK '

class varintupdater(varfloatupdater):
    """
    subclass for float vars.
    
    Expects a single string in the array vals, it checks it converts to a float
    """
    def convertone(self, vals):
        return int(vals[0])

class vartimeupdater(varupdater):
    """
    subclass for float vars containing a unix timestamp.
    """
    def getUpdate(self):
        tstamp=self.avar.getValue()
        tstring='never' if tstamp==0 else time.strftime('%H:%M:%S', time.localtime(tstamp))
        return self.fid, tstring

class varenumcyclic(varupdater):
    """
    class for (typically a button like) enum var, where the label on the var cycles through the 
    list of values.
    """
    def websetter(self, valuelist):
        self.avar.increment(1, 'driver') # use driver update here to trigger an update to web page
        return b'OK '

class varenumupdater(varupdater):
    def websetter(self, valuelist):
        try:
            self.avar.setValue(valuelist[0], self.pagelist.useragent)
        except:
            return ('failed to update %s to value %s' % (self.avar.getHierName(), str(valuelist[0]))).encode()
        return b'OK '

class varstrupdater(varfloatupdater):
    def convertone(self, vals):
        return vals[0]
        
def make_enumVar(userupa=None, formatextras={}, updclass=varenumupdater, **kwargs):
    """
    given a pvar.enumVar (defined by apps, app and varname which are handled by field_prepare), returns html for that field 
    using a drop down if user can update the field

    userupa     : if not None, then the user can change the field and it is notified back to the app

    formatextras: extra keywords for the format string
    """
    avar, attribset = field_prepare(userupa=userupa, updclass=updclass, **kwargs)
    optionhtml = '<option value="{oval}"{sel}>{odisp}</option>'
    selecthtml = '''<select {attribstr} >{optall}</select>'''
    noinputhtml= '''<span {attribstr}>{vstr}</span>'''
    cval=avar.getValue()
    attribstr=make_attribstr(attribset)
    if userupa:
        opts=[
            optionhtml.format(
                oval=optname, odisp=optname, sel=' selected' if optname==cval else '')
                    for optname in avar.vlist]
        return selecthtml.format(f=avar, attribstr=attribstr, optall=''.join(opts), **formatextras)
    else:
        return noinputhtml.format(f=avar, attribstr=attribstr, vstr=cval, **formatextras)

def make_enumBtn(updclass=varenumcyclic, **kwargs):
    avar, attribset = field_prepare(updclass=updclass, **kwargs)
    if 'onchange' in attribset:
        attribset['onclick']=attribset['onchange']
        del attribset['onchange']
    attribstr=make_attribstr(attribset)
    return '<div class="btnlike" {attribstr}>{astring}</div>'.format(astring=avar.getValue(), attribstr=attribstr)

def make_numVar(fstring='{nstr}', clength=5, liveupd=False, userupa=None, **kwargs):
    """
    returns html for that field, using a format statement to 
    create the text string

    fstring   : string used to format the number itself - separate from the overall format as this will be changed far more
                often than the overall field's html
    
    userupa   : if not None, then the user can change the field and it is notified back to the app
    """
    avar, attribset = field_prepare(userupa=userupa, **kwargs)
    ns=fstring.format(nstr=avar.getValue())
    if userupa:
        attribset['type']='text'
        attribset['value']=ns
        attribset['style']="width: {clength}em"
        basestring='<input {attribstr} />'
    else:
        basestring='<span {attribstr} >{astring}</span>'
    attribstr=make_attribstr(attribset)
    return basestring.format(f=avar, astring=ns, attribstr=attribstr)

def make_strVar(fstring=None,clength=20, userupa=None, updclass=varstrupdater, fextras={}, **kwargs):
    avar, attribset = field_prepare(userupa=userupa, updclass=updclass, **kwargs)
    ns = astring=avar.getValue() if fstring is None else fstring.format(astring=avar.getValue()) 
    if userupa:
        attribset['type']='text'
        attribset['value']=ns
        attribset['style']="width: {clength}em"
        basestring='<input {attribstr} />'
    else:
        basestring='<span {attribstr} >{astring}</span>'
    attribstr=make_attribstr(attribset)
    return basestring.format(f=avar, astring=ns, attribstr=attribstr, **fextras)

def make_timeVar(timestring='%X', updclass=vartimeupdater, **kwargs):
    """
    generates html for date / time string from a float avar (assumed to contain a unix timestamp)
    
    timestring: The string passed to strftime to make the text string to be displayed
    
    """
    avar, attribset = field_prepare(updclass=updclass, **kwargs)
    tstamp=avar.getValue()
    tstring='never' if tstamp==0 else time.strftime(timestring, time.localtime(avar.getValue()))
    attribstr=make_attribstr(attribset)
    return '<span {attribstr} >{tstr}</span>'.format(f=avar, tstr=tstring, attribstr=attribstr)

def make_attribstr(attribset):
    return ' '.join([('{attn}' if attval is None else '{attn}="{attval}"').format(attn=attn, attval=attval) for attn, attval in attribset.items()])

def field_prepare(apps, app, varname, pup, updclass, updparams={}, liveupa=None, userupa=None, attribset={}, ):
    """
    prepares a field for html generation:
        finds the field's var from the app
        creates the link object to connect the appvar to the html field
        updates the attribset with an id if appropriate

    apps    : dict of apps (allows late binding)
    
    app     : name of the app (within the apps)
    
    varname : hierarchic name of the var within the app
    
    pup     : pageupdatelist instance being assembled for the page in construction
    
    liveupa : the name of the agent that will change a var that needs to be updated dynamically on the web page (or None if not)
    
    userupa : the name of the agent to be used when an incoming update top the web page needs to be update an appvar (or None if user cannot update)
    
    attribset: dict of attributes (so far) for the field
    
    updclass: class of object to create to link the appvar to the web page field
    
    updparams: any keyword based params to use in constructing the updclass instance

    returns the var and attribset
    """
    avar=apps[app][varname]
    newattribs={} if attribset is None else attribset.copy()
    if (liveupa or userupa):
        updclass(avar=avar, pagelist=pup, userupa=userupa, liveupa=liveupa, **updparams)
        newattribs['id']=updclass(avar=avar, pagelist=pup, userupa=userupa, liveupa=liveupa, **updparams).fid
    if userupa:
        if avar.enabled:
            newattribs['onchange']='appNotify(this, {})'.format(pup.pageid)
        else:
            newattribs['disabled']=None
    return avar, newattribs

def make_table_field(apps, app, varname, fieldmaker, label, shelp=None, webdetails=None, **kwargs):
    """
    generates a table row html for a field with a label, tooltip and link to help as appropriate
    """
    labelfmt="{}:"
    fieldwrap= '''<tr><td class="fieldlabel" {shelp} >{flabel}</td><td>{field}</td>{morehelp}</tr>\n'''
    morelink= '''<td class="fieldhelp"><a class="fieldlink" href="{url}" rel="noopener noreferrer">details</a></td>'''
    nolink='<td></td>'
    html = fieldmaker(apps=apps, app=app, varname=varname, **kwargs)
    avar=apps[app][varname]
    return fieldwrap.format(
            f=avar,
            field=html,
            flabel=labelfmt.format(label) if not label is None else '',
            shelp='title="{}"'.format(shelp) if not shelp is None else '',
            morehelp=nolink if webdetails is None else morelink.format(url=webdetails))

def make_group(apps, defs, outerwrap, pup, outerparams={}, **extraparams):
    """
    """
    items={}
    for deflist in defs:
        if len(deflist)==3:
            iname, imaker, iparams = deflist
            try:
                html = imaker(apps=apps, pup=pup, **iparams)
            except:
                print('failed in field %s' % iname)
                raise
            if iname.endswith('*'):
                xname=iname[:-1]+'s'
                if xname in items:
                    items[xname]+=html
                else:
                    items[xname]=html
            else:
                items[iname]=html
        else:
            raise ValueError('group definition should have 3 parts, this has %d ->\n%s\n<-\n' % (len(deflist), deflist)) 
    try:
        return outerwrap.format(pageid=pup.pageid, **items, **outerparams, **extraparams)
    except KeyError as ke:
        print('make_group failed with KeyError using fields keys %s' % list(fields.keys()))
        raise

def make_list_group(apps, defs, outerwrap, fieldfunc, varprefix, groupname, pup, outerparams={}, **extraparams):
    itemshtml=''
    for fielddef in defs:
        fixeddef=fielddef.copy()
        varname=varprefix+'/'+fixeddef.pop('varlocal')
        try:
            html = fieldfunc(apps=apps, varname=varname, pup=pup, **fixeddef)
        except:
            print('make_list_groups failed in field %s' % varname)
            raise
        itemshtml+=html
    try:
        return outerwrap.format(pageid=pup.pageid, **{groupname: itemshtml}, **outerparams, **extraparams)
    except KeyError as ke:
        print('make_group failed with KeyError using fields keys %s' % list(fields.keys()))
        raise

def makecameraactheads(apps, pup):
    camacts=apps['camera']['activities']
    return ''.join(['<td class="{aname}style" style="text-align: center;">{aname}</td>'.format(aname=a) for a in camacts])

def makecameraactstats(apps, pup):
    camacts=apps['camera']['activities']
    html=''
    for act in camacts.values():
        h = make_enumVar(apps=apps, app='camera', varname=act['status'].getHierName(), pup=pup, liveupa='driver', updclass=varupdater)
        html += '<td class="'+act.name+ 'style" style="text-align: center;" >'+h+'</td>'
    return html

def makecameraactshorts(apps, pup):
    camacts=apps['camera']['activities']
    html=''
    for act in camacts.values():
        if act.name=='':
            pass


class pageupdatelist():
    """
    when a web page is built using 'pagemaker' this class is instantiated to hold the links between app var's and
    fields on the web page. Fields on the web page that can update the app and vice-versa are given id's that uniquely
    identify the the field on the web page and the var to which they are connected. Vars that need to dynamically update fields on the
    web page use an onchange notification to alert this class, and periodically all outstandng updates are gathered and sent to the
    web page.
    
    There are 2 maps:
        var -> field id (which can be 1 to many)
        field id -> var (several fields can link to same var)
    """
    def __init__(self, pageid, useragent='user'):
        self.pageid=pageid
        self.useragent=useragent
        self.var_field_map={}  # maps vars to 1 or more fields on the web page
        self.field_var_map={}  # maps screen fields to vars 
        self.created=time.time()
        self.lastused=self.created  # keep a last used timestamp so we can run through the list and discard unused lists
        self.lock=Lock()
        self.pendingupdates=set()
        self.nextid=1

    def add_field(self, upper, userupa, liveupa):
        """
        called as the html for a field is created....
        If the field is dynamic (user can update or server can update) then allocate an id, otherwise we don't need one

        upper       : updater instance that handles updates between a var and a screen field
        
        userupa     : None if user cannot update via web page, otherwise the name to use as the agent when the user changes a field
        
        liveupa     : None if application updates to the field are not dynamically sent to update the web page, otherwise the 
                      agent name that will be used when such updates happen
        
        returns None if the web page field has no id, otherwise the id of the field
        """
        if userupa or liveupa:
            fid=str(self.nextid)
            self.nextid +=1
            if userupa:
                self.field_var_map[fid]=upper
            if liveupa:
                assert not upper in self.var_field_map
                self.var_field_map[upper]=fid
            return fid
        else:
            return None

    def applyUpdate(self, fid, value):
        return self.field_var_map[fid[0]].websetter(value)

    def haslinks(self):
        return len(self.var_field_map) > 0 or len(self.field_var_map) > 0

    def closelist(self):
        for upper in self.var_field_map.keys():
            upper.drop()

    def markpending(self, upd):
        with self.lock:
            self.pendingupdates.add(upd)

    def getupdates(self):
        with self.lock:
            toupdate=list(self.pendingupdates)
            self.pendingupdates.clear()
        self.lastused=time.time()
        return json.dumps([upd.getUpdate() for upd in toupdate]) if toupdate else 'kwac'

    def hasexpired(self):
        return (self.lastused+30) < time.time()