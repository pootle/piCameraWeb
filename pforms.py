#!/usr/bin/python3
"""
provides a number of classes (called xxVar) to abstract between application variables and the rest of the world.

They supports multiple views into data, updates are policed and a change notification mechanism
is provided.

This base set of Var classes provide core functionality, separate sets of mixin classes allow different
client or user views / interface styles to be supported.

A variable has a single (canonical) value, and multiple views, The canonical value may or may not match
the representation of 1 of the views. Views are translated on the fly (unless performance demands otherwise).

Each additional view can be independently enabled for writing / update.

Vars form a tree structure (single parent), so each Var has a parent except the top of the tree which has no parent.
"""
import sys,pathlib

from collections import Hashable, OrderedDict
from collections.abc import Mapping
from inspect import signature
import datetime, json
import logging
from pathlib import Path

import ptree, treefiles

class baseVar(ptree.treeob):
    """
    A base class for single variables and groups of variables with multiple potential views of the data.
    
    The current value is held in a standard (for each type of var) single format which is always accessed via
    _getVar and setVar.
    """
    label=None
    shelp=None
    defaultFormat='{value:}'

    def __init__(self, *, value, writers, writersOn, readers, readersOn, valueView, fallbackValue=None, onChange=None,
                formatString='{value:}',
                label=None, shelp=None, loglvl=None, **kwargs):
        """
        value           : the initial value for the var, expressed in valueView (see below) format
        
        fallbackValue   : if, during initialisation, the value is invalid, this value is tried

        valueView       : the view in which the value is expressed.

        writers         : a dict of the views which can be 'written'and the function that validates the new value and 
                          converts it to the var's canonical form and returns the canonical value.
                          The function must take the parameters 'view' and 'value'.

        writersOn       : a list of the writers to actually allow in this var.

        readers         : a dict of the views which can be 'read' and the function that returns the data as a
                          view appropriate object.
                          The function must have the parameter 'view'

        readersOn       : a list of the readers to actually allow in this var.
                          
        onChange        : notification (function and view) called when the var's value changes, the function is a callable
                          with four named parameters:
                            oldValue: previous value
                            newValue: new value
                            var     : this class instance
                            view    : the view that triggered the change
                          
                          Note view can be a list of views or a single view

                          If 'function' is a string (rather than a callable) it specifies a member function on the app
                          which will be called.

        formatString: This is used as the formatString for this Var when a string 
                      representation is required. Format is called with 2 named params
                            value:  Current canonical value (via _getVar)
                            var  : this object

        label           : (user) label for this field.
        
        shelp           : short help for this field.

        loglvl          : set to a python logging value to get logging for this field.

        various Exceptions can be raised.
        """
        self.log=None if loglvl is None else logging.getLogger(__loader__.name+'.'+type(self).__name__)
        self.loglvl=1000 if loglvl is None else loglvl
        self.__lvvalue=None               # this is the place we keep the canonical value of the variable - always access
                                          # via _getVar / _setVar
        super().__init__(**kwargs)
        self.viewUpdate=self._fbuilder(writers, writersOn)
        if len(self.viewUpdate)==0:
            raise RuntimeError('var type {} has no views for update!'.format(type(self).__name__))
        self.viewGets=self._fbuilder(readers, readersOn)
        if len(self.viewGets)==0:
            raise RuntimeError('var type {} has no views for reading!'.format(type(self).__name__))
        self.onChange={}                # setup empty notify set then set the value before adding notifications
        self.setInitialValue(valueView, value, fallbackValue)
        if not onChange is None:
            self.addNotify(*onChange)
        if not label is None:
            self.label=label
        if not shelp is None:
            self.shelp=shelp
        self.formatString = formatString
        if self.loglvl <= logging.INFO:
            self.setupLogMsg()

    def setInitialValue(self, view, value, fallbackValue):
        try:
            self.setValue(view, value)
            return
        except:
            pass
        self.setValue(view, fallbackValue)

    def addNotify(self, func, view):
        """
        Adds a single notification function that will be called when the canonical value of the var is changed using the given view.
        
        func: a callable with parameters 'var', 'view', 'newValue' and 'oldValue', any other parameters must not be mandatory.
                can also be a string in which case must be the name of a member function on the app.
        
        view: view can be a string, or a list of strings. Only writes / updates using this / these views will trigger the callback.
        
        returns Nothing
        
        raises: ValueError for various inconsistencies in the parameters
        """
        if isinstance(view,str):
            if not view in self.app.allviews:
                raise ValueError('the view {} requested in addNotify for var of type {} is not known to this tree -{}'.format(
                    view, type(self).__name__, self.app.allviews))
            if isinstance(func,str):
                try:
                    f=getattr(self.app, func)
                except AttributeError:
                    raise ValueError('the function {} requested in addNotify for var of type {} is not a member of the app {}'.format(
                    func, type(self).__name__, type(self.app).__name__))
            else:
                f=func
            if callable(f):
                sig = signature(f)
                if 'var' in sig.parameters and 'view' in sig.parameters and 'oldValue' in sig.parameters and 'newValue' in sig.parameters:
                    if view in self.onChange:
                        self.onChange[view].append(f)
                    else:
                        self.onChange[view]=[f]
                else:
                    raise ValueError("the function {} does not have named parameters ('var' and/or  'view') for of type {}".format(
                        f.__name__, type(self).__name__))
            else:
               raise ValueError("the 'func' parameter ({}) for var of type {} is not callable".format(f, type(self).__name__))
        else:
            for v in view:
                self.addNotify(func, v)

    def removeNotify(self, func, view):
        raise NotImplementedError()

    def _fbuilder(self, fdict, allowed):
        funcdict={}
        for v in allowed:
            assert v in self.app.allviews, 'var {}, view >{}< not found in list {}'.format(self.name, v, self.app.allviews)
            if v in fdict:
                f=fdict[v]
                if not callable(f):
                    cf=getattr(self,f)
                    if not callable(cf):
                        raise TypeError('{} is not callable in var of type {} using {}'.format(f, type(self).__name__, v))
                    f=cf
                sig = signature(f)
                assert 'view' in sig.parameters, 'the function {}, given for view {} does not have "view" as a parameter'.format(
                        f.__name__, v)
                funcdict[v]=f
            else:
                raise ValueError('var {} of type {} requested access view {} not found in view dict {}'.format(
                        self.name, type(self).__name__, v, fdict))
        return funcdict                

    def setupLogMsg(self):
        if self.loglvl <= logging.DEBUG:
            self.log.info('setup var {}, with readers for {} and writers for {}, value is {}'.format(self.name,
                            self.viewGets.keys(), self.viewUpdate.keys(), self._getVar()))
        else:
            self.log.info('setup {}'.format(self))

    def __repr__(self):
        return "{}(value={}, loglvl={})".format(self.__class__.__name__, self.getValue('app'), self.loglvl)

    def __str__(self):
        return self.formatString.format(value=self._getVar(),var=self)

    def _getFValue(self, view):
        """
        returns the value using the formatString
        """
        return self.__str__()

    def getValue(self, view):
        """
        fetches the var's value as expressed in the given view
        
        view       : name of the view to be used
                
        returns the var's value using the given view
        
        raises RuntimeError if the view is not known
        """
        if view in self.viewGets:
            return self.viewGets[view](view)
        else:
            raise RuntimeError('view {} not known in var {}'.format(view, self.name))

    def setValue(self, view, value):
        """
        Sets the var's value after conversion from the given view. Calls any onChange callbacks
        if the value changes.
        
        view: name of the view to be used.
        
        value: new value expressed in the given view
        
        returns True if the value changes, else False
        
        raises  RuntimeError if the view is not known
                ValueError if the value is not valid in the given view
        """
        if view in self.viewUpdate:
            newv=self.viewUpdate[view](view, value)
            oldValue=self._getVar()
            if oldValue==newv:
                if self.loglvl <= logging.DEBUG:
                    self.log.debug('var {} view {} with value {} is unchanged'.format(self.name, view, value))
                return False
            else:
                self._setVar(newv)
                if self.loglvl <= logging.DEBUG:
                    self.log.debug('var {} view {} with value {} updated {} to {}'.format(self.name, view, value, oldValue, newv))
                if view in self.onChange:
                    for f in self.onChange[view]:
                        f(oldValue=oldValue, newValue=newv, view=view, var=self)
                return True
        else:
            raise RuntimeError('view {} not known in field {}'.format(view, self.name))

    def _setVar(self, value):
        self.__lvvalue=value

    def _getVar(self):
        return self.__lvvalue

class textVar(baseVar): 
    """
    A refinement of baseVar for text strings.

    The canonical form is a string
    """
    def _validStr(self, view, value):
        """
        view    : the view the value is using
        
        value   : the requested new value for the field, can be anything that float(x) can handle that is between minv and maxv
        
        returns : the valid new value (this is always a str)
        
        raises  : ValueError if the provided value is invalid
        """
        if value is None:
            raise ValueError('text var cannot be >None<')
        return str(value)

    def _getStr(self, view):
        """
        returns the canonical form as this is already a string        
        """
        return self._getVar()

class numVar(baseVar):
    """
    A refinement of baseVar that restricts the value to numbers - simple floating point
    
    To force integers, use an intervalVar with interval of 1.
    """
    def __init__(self, maxv=sys.float_info.max, minv=-sys.float_info.max, **kwargs):
        """
        Makes a field a float with given min and max values - by default min and max are the values of the underlying float type.
        
        minv        : the lowest allowed value - use 0 to allow only positive numbers
        
        maxv        : the highest value allowed
        """
        minvf=float(minv)
        maxvf=float(maxv)
        assert minvf < maxvf, "minimum value ({}) must be less than maximum value({})".format(minv,maxv)
        self.maxv=maxvf
        self.minv=minvf
        super().__init__(**kwargs)

    def _validNum(self, view, value):
        """
        view    : the view the value is using
        
        value   : the requested new value for the field, can be anything that float(x) can handle that is between minv and maxv
        
        returns : the valid new value (this is always a float)
        
        raises  : ValueError if the provided value is invalid
        
        because float(x) accepts strings or generic numbers we only need 1 conversion function.
        """
        av=float(value)
        if self.minv <= av <= self.maxv:
            return av
        else:
            raise ValueError("{} is not a valid value for field {}".format(value, self.name))

    def _getCValue(self, view):
        """
        returns the internal representation (which in the base class is always a float).
        """
        return self._getVar()

    def _getSValue(self, view):
        """
        returns the value as a string
        """
        return '{}'.format(self._getVar())

class intervalVar(numVar):
    """
    A refinement of numVar that restricts the field value to numbers within a range on interval boundaries.
    
    use an integer interval to force the field to be integer rather than float
    """
    def __init__(self, interval=1, rounding=True, maxv=sys.float_info.max, minv=-sys.float_info.max, 
                 **kwargs):
        """
        minv     : repeated from numField so we can use int if appropriate
        maxv     : repeated from numField so we can use int if appropriate
        interval : the interval between valid values, integer values of interval mean the appValue is always an integer
        
        rounding : if True then values not on interval boundaries are rounded to the nearest interval boundary, otherwise 
                   validation will fail
        """
        if round(interval)==interval:
            self.isint=True
            self.interval=int(interval)
        else:
            self.isint=False
            self.interval=interval
        self.rounding=rounding
        super().__init__(minv=int(minv) if self.isint else minv, maxv=int(maxv) if self.isint else maxv, **kwargs)

    def _validNum(self, view, value):
        try:
            fval=int(value)
        except:
            fval=float(value)
        if self.interval is 1:                                 # 'cos in Python there is only 1 1. For just an int, an easier test is done
            if self.rounding:
                av=round(fval)
            else:
                testv=round(fval)
                if testv==fval:
                    av=testv
                else:
                    raise ValueError("{} is not a valid value for field {}".format(appValue, 'xxxxx'))
        else:
            testv=round(fval/self.interval,0)*self.interval   # can fail if interval very small and number is approaching max float value
            if self.rounding:
                av=testv
            elif testv==fval:
                av=testv
            else:
                raise ValueError("{} is not a valid value for field {}".format(appValue, 'xxxxx'))
            if self.isint:
                av=int(av)
        if self.minv <= av <= self.maxv:
            return av
        else:
            raise ValueError("{} is not a valid value for field {}".format(value, self.name))

class listVar(baseVar):
    """
    A var with a number of fixed valid values, there are matching lists provided for the various views.
    The canonical value is the index into the list
    """
    def __init__(self, vlists, app, **kwargs):
        """
        vlists: a dict with 1 entry per view, the value of each entry is the list of values for that view.
                all lists must be the same length. There must be an entry for each views entry.
        """
        assert isinstance(vlists, Mapping), 'vlist parameter is not a mapping, it is a {}'.format(type(vlists).__name__)
        vlen=None
        for v,l in vlists.items():
            assert v in app.allviews
            if vlen is None:
                vlen=len(l)
            else:
                assert vlen==len(l),'vlist lengths inconsistent - {} and {}' .format( vlen, len(l))
        self.viewlists=vlists
        super().__init__(app=app, **kwargs)

    def _validValue(self, view, value):
        """
        Validates the given value by finding it's index in the list.
        
        returns the index for the value
        
        raises ValueError if the value is not in the list
        """
        inlist=self.viewlists[view]
        try:
            ix=inlist.index(value)
            return ix
        except:
            msg="{} is not a valid value for var {} of type {} (not in {})".format(
                   value, getattr(self,'name', 'unknown'), type(self).__name__, str(inlist))
            raise ValueError(msg)

    def _getValue(self, view):
        """
        This returns the value of the variable mapped using the appropriate view
        """
        try:
            return self.viewlists[view][self._getVar()]
        except TypeError:
            print('var {} TypeError in _getValue. Canonical value {}, failed list lookup'.format(self.name, self._getVar()))
            raise
        except KeyError:
            msg='var {} of type {}, no lookup for view {}'.format(self.name, type(self).__name__, view)
            print(self.viewlists.keys())
            print(self.app.allviews)
            if self.log is None:
                print(msg)
            else:
                self.log.critical()
            raise

    def _increment(self, view, value):
        """
        A handy shortcut to cycle through the range of values, cycling back to start when the end is reached.
        """
        inlist=self.viewlists[view]   # check update in this view is allowed and fetch the list
        nv=self._getVar()+1
        if nv >= len(inlist):
            nv=0
        return self.setValue(view, inlist[nv])

class timeVar(baseVar):
    """
    A refinement of baseVar that holds a timestamp. The value 0 is used to mean nothing is set
    
    The held value is a timestamp - i.e. a float
    """
    def __init__(self, strft, unset, **kwargs):
        """
        strft:  format string to use with strftime for text version
        
        unset:  string to return for text version when unset 
        """
        self.strft=strft
        self.unset=unset
        check=datetime.datetime.now().strftime(self.strft) #just check the format string doesn't blow up
        super().__init__(**kwargs)

    def _validstamp(self, view, value):
        """
        checks that the value is a float (or converts to a float) - i.e. a valid timestamp
               
        raises  : ValueError if the provided value is invalid
        
        because float(x) accepts strings or generic numbers we only need 1 conversion function.
        """
        return float(value)

    def _validstr(self, view, value):
        """
        checks that the passed string converts to a timestamp and returns timestamp
        """
        return datetime.datetime.strptime().timestamp()

    def _getCValue(self, view):
        """
        returns the internal representation (which in the base class is always a float).
        """
        return self._getVar()

    def _getSValue(self, view):
        """
        returns the value as a string
        """
        vv=self._getVar()
        if vv == 0:
            return self.unset
        else:
            return datetime.datetime.fromtimestamp(vv).strftime(self.strft)

class groupVar(baseVar):
    """
    the base for all things made of multiple fields
    """
    def __init__(self, varlist, value, viewlist=None, **kwargs):
        """
        this simplest of field groups contains multiple fields and methods to handle them but no more.
        
        Its name (part of baseVar) is used as part of the hierarchic name used by the app to locate variables 
        
        varlist     : definitions for all child fields - a list of 2-typles, first is the class of the field, second is params for constructor
        
        viewlist    : defines the specific children, and their order, to be included in each view. A dict with view as a key and a list 
                      as the value. The lists is the names of the children to include in the view. By default the standard views can be used and 
                      include all children in their declared order.

        value       : dict with the initial values for the fields.
        """
        super().__init__(value=None, **kwargs)
        for cls, ckwargs in varlist:
            childname=ckwargs['name'] if 'name' in ckwargs else cls.defaultName
            try:
                newchild=cls(parent=self, app=self.app, value=None if value is None else value[childname] if childname in value else None, 
                                        valueView=kwargs['valueView'], **ckwargs)
            except Exception as e:
                fkwargs={k:'children' if k=='varlist' else v for k,v in ckwargs.items()}
                print('field creation failed {} for field {} of type {}\n {} with params:'.format(
                        type(e).__name__,childname,cls.__name__, e.args))
                arglist=['{:16s}:{}'.format(k,v) for k,v in fkwargs.items()]
                if len(arglist)==0:
                    print('\n    EMPTY!\n')
                else:
                    print('\n'.join(arglist), '\n')
                raise
        if viewlist is None:
            chlist=[ch.name for ch in self.values()]
            # Note this means all views use the same underlying list
            self.viewlist={v: chlist for v in self.app.allviews}
        else:
            self.viewlist=viewlist
        for v, vl in self.viewlist.items():
            assert v in self.app.allviews, 'failed to find {} in app.allviews {}'.format(v, self.app.allviews)
            for c in vl:
                assert c in self

    def setInitialValue(self, view, value, fallbackValue):
        pass

    def _getValueDict(self, view):
        """
        creates a dict with the values for all children that support the given view. If the child does
        not support the view it is not included in the dict
        """
        vd=OrderedDict()
        for f in self.values():
            try:
                fv=f.getValue(view)
                vd[f.name]=fv
            except RuntimeError:
                print('skipping var {} in groupvar {}'.format(f.name, self.name)) 
        return vd

    def setValue(self, view, value):
        if view in self.viewUpdate:
            return self.viewUpdate[view](view, value)
        else:
            raise RuntimeError('view {} not known in field {}'.format(view, self.name))


    def _setValueDict(self, view, value):
        """
        Updates one or more child variable values.

        view: the view in which the values are expressed
        
        value: a dict like object, keys must match names of children of this field,
        
        returns True if any field's value actually changed
        """
        updated=False
        for n, v in value.items():
            if n in self:
                if self[n].setValue(view, v):
                    updated=True
            else:
                raise RuntimeError('the child field {} not found in groupVar {}'.format(n, self.name, view))
        return updated

    def _validValue(self, view, value):
        return None

    def webUpdate(self, name, value):
        """
        called from an incoming request to the web server with a single field update request
        
        name :  a string with the hierarchic name of the field using self.hiernamesep as separator
        
        value: an array of strings with the new value(s) 
        """
        splitn=name.split(sep=self.hiernamesep, maxsplit=1)
        try:
            target=self[splitn[0]]
        except KeyError:
            return {'resp': 500, 'rmsg': 'field {} from {} is not a child of field {}'.format(splitn[0], name, self.name)}
        if len(splitn)==1: # we've reached the basic field
            return target.webUpdateValue(value)
        else:              # there's another level to go
            return target.webUpdate(splitn[1], value)

    def __repr__(self):
        return "{} is a {}".format(self.name, type(self).__name__)

class appVar(groupVar):
    """
    The top level group in a tree - has no parent.
    """
    def __init__(self, views, value=None, valuefile=None, **kwargs):
        """
        the app should be the first thing setup as all other nodes link to it. It contains the list of views
        that will be used in this tree

        views       : a list of the views that this app can use - allows silly mistakes to be detected up front, rather 
                      than silently failing.
        
        valuefile   : name of file in JSON format with the values for the initial field Values, if not None this
                      overrides the value parameter.
        
        value       : a dict of values for some or all fields.
        """
        for v in views:
            assert isinstance(v, Hashable), 'the view {} is not hashable'.format(v)
        self.allviews=views
        if not valuefile is None:
            vf=Path(valuefile).expanduser()
            if not vf.isfile():
                raise ValueError('The settings file {} does not exist or is not a file'.format(str(vf)))
            with vf.open('r') as settings:
                value=json.load(settings)
        super().__init__(app=self, parent=None, value=value, **kwargs)

    def getSettings(self, view):
        """
        return the current values of all appvars.
        
        view        : The view to use in fetching the value of each var - this allows vars to select appropriate format for the data
                      or to avoid saving a value where this is inappropriate.
               
        """
        return json.dumps(obj=self.getValue(view), indent=2)

    def setSettings(self, view, jsonstr):
        sets=json.loads(jsonstr)
        print('applying settings')
        print(sets)
        self.setValue('pers', sets)

    def showTree(self, view='app'):
        td=self.getValue(view)
        print('  {f.name:15}'.format(f=self))
        print(self.showNode(td,indent=1))

    def showNode(self, n, indent=0):
        nstr='  '+'   '*indent+'{k:15}:{v:}\n'
        fstr=''
        for k,v in n.items():
            if isinstance(v,dict):
                fstr+=nstr.format(k=k,v='')+self.showNode(v,indent+1)
            else:
                fstr+=nstr.format(k=k,v=v)
        return fstr

    def _setVar(self, value):
        """
        dummy - this needs to be callable but take no action
        """
        pass

    def _getVar(self):
        """
        dummy - this needs to be callable but take no action
        """
        return None

class folderVar(baseVar):
    """
    Represents a folder, displaying files / folders in the current folder with simple navigation.
    
    The field holds a pathlib Path which is setup in the constructor. Thereafter 'sets' are interpreted
    as navigation rather than setting an absolute value.
    
    The 'app' view returns the internal Path object, and other views returns a simple dict of info about the
    current folder
    """
    def setInitialValue(self, view, value, fallbackValue):
        try:
            v=pathlib.Path(value).expanduser()
            self._setVar(v)
        except:
            v=None
        if v is None:
            v=pathlib.Path(fallbackValue).expanduser()
        if v.exists():
            if not v.is_dir():
                raise ValueError('path {} is not a folder'.format(str(v)))
        else:
            v.mkdir(parents=True)
        self._setVar(v)

    def _validValue(self, view, value):
        """
        appValue: navigation from current folder:
                    '.' no change
                    '..' move to parent folder
                    <str> move to subfolder <str> (ValueError if no such child, or child is not a folder)
        
        returns : existing pathlib.Path (unchanged) or new pathlib.Path of the new folder
        
        raises  : ValueError if the provided value is invalid
        """
        if value=='.':
            return self._getVar()
        elif value=='..':
            newf=self._getVar().parent
            if not newf.is_dir():
                raise ValueError('Cannot move to parent of ({})'.format(str(self._getVar())))
        else:
            newf=self._getVar()/value
            if not newf.is_dir():
                raise ValueError('Cannot find folder {} within folder {}'.format(newf.name, str(self._getVar())))
        return newf

    def _getAppValue(self, view):
        return self._getVar()

    def _getStrValue(self, view):
        return str(self._getVar())

    def _getDictValue(self, view):
        return treefiles.pl(self._getVar())

################################################################################
# housekeeping / general other stuff

def extendViews(incoming, local):
    """
    merges an incoming view dict with a local class view dict. The incoming dict takes precedence so inheriting
    classes can override methods.
    
    Used by any class that wants to define 'built in' views, that may be extended by inheriting classes.
    The incoming dict can be empty or even (for convenience) None.
    """
    if incoming is None or len(incoming) == 0:
        return local.copy()
    else:
        lcop=local.copy()
        lcop.update(incoming)
        return lcop

def kwargsToString(label, kwargs):
    """
    handy function to pretty print a dict (typically kwargs used here)
    """
    if kwargs:
        args=[]
        for k,v in kwargs.items():
            if k=='parent':
                args.append('\n    {}:{}'.format(k,'None' if v is None else v.name))
            else:
                args.append('\n    {}:{}'.format(k,v))
        return label+':'+''.join(args)
    else:
        return label+': <empty>'
