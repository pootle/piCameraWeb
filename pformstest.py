#!/usr/bin/python3
"""
Some tests for pforms module to check things are working as expected
"""
import sys, os, traceback
import pforms

def cTest(testid, cls, params, ex=None):
    """
    Tests a constructor for a class or related list of classes.
    
    Each class' constructor is called with params as **kwargs and the result (an object or an specific exception) 
    is checked
    
    testid: id of this test
    
    cls   : class or list of classes to be tested
    
    params: keyword args for constructor
    
    ex    : Expected exception class, or None if the constructor should return an object
    """
    if isinstance(cls, type):
        if ex is None:
            try:
                ob=cls(**params)
            except Exception as e:
                raise RuntimeError('test {} on class {}, failed with unexpected exception of type {} in constructor test'.format(
                        testid, cls.__name__, type(e).__name__))
            return ob
        else:
            try:
                ob=cls(**params)
            except ex:
                return
            except Exception as e:
                raise RuntimeError('test {} on class {}, unexpected exception type {}'.format(testid, cls.__name__, type(e).__name__))
            raise RuntimeError('test{} on class {} did not raise expected exception type {}'.format(testid, cls.__name__, ex.__name__))
    else:
        for c in cls:
            cTest(testid, c, params, ex)

def mTest(testid, ob, obmeth, params, result=None, ex=None):
    """
    call the function obmeth on the object ob with params and checks the result

    testid: id of this test
    
    ob    : object under test
    
    obmeth: name of method to test
    
    params: keyword dict of params
    
    result: expected result or None
    
    ex    : class of exception expected
    """
    if hasattr(ob, obmeth):
        f=getattr(ob, obmeth)
        if callable(f):
            try:
                r=f(**params)
            except Exception as e:
                if not ex is None and isinstance(e, ex):
                    return
                print('test {} failed, unexpected exception'.format((testid, )))
                r=None
                exc_type, exc_value, exc_traceback = sys.exc_info()
                print('{}: {}\n'.format(type(e).__name__,str(exc_value)),
                    (''.join(traceback.format_tb(exc_traceback))))
            if r==result:
                return r
            else:
                print('called', f, 'with', params)
                raise RuntimeError('test {} failed, result >{}< of type {} does not match expected result >{}< of type {}'.format(
                    testid, str(r), type(r).__name__, str(result), type(result).__name__))
        else:
            raise RuntimeError('test {} failed, {} is not a method for object {}'.format(testid, obmeth, ob.name))
            sys.exit(-1)
    else:
        raise RuntimeError('test {} failed to find method {} on object {}'.format(testid, obmeth, ob.name))
        sys.exit(-1)

class localNumVar(pforms.cvmixin, pforms.numVar):
    pass

class localIntervalVar(pforms.cvmixin, pforms.intervalVar):
    pass

def testCons():
    # test all classes require the base set of mandatory params
    allclass=(pforms.baseVar, pforms.numVar, pforms.intervalVar, pforms.listVar)
    allparams={'name': 'test1', 'parent': None, 'value': None, 'updateEnable': {}, 'readEnable': {}}
    for p in allparams.keys():
        paramtest=allparams.copy()
        paramtest.pop(p)
        cTest('cons  2', allclass, params={}, ex=TypeError)

def testNumVar(vtype=localNumVar):
    cTest('numvar 1', vtype, ex=RuntimeError, params={
        'name': 'test1', 'parent': None, 'value': None, 'updateEnable': vtype.validators, 'readEnable': {}})
    cTest('numvar 2', vtype, ex=RuntimeError, params={
        'name': 'test1', 'parent': None, 'value': None, 'updateEnable': {}, 'readEnable': vtype.getters})
    cTest('numvar 3', vtype, ex=TypeError, params={
        'name': 'test1', 'parent': None, 'value': None,
        'updateEnable': vtype.validators, 'readEnable': vtype.getters})
    t=cTest('numvar 4', vtype, ex=None, params={
        'name': 'test1', 'parent': None, 'value': 0,
        'updateEnable': vtype.validators, 'readEnable': vtype.getters})
    mTest('numvar 4', t, 'getValue', params={'view':'fred'}, result=None, ex=RuntimeError)
    mTest('numvar 5', t, 'getValue', params={'view':pforms.APPVIEW}, result=0, ex=None)
    mTest('numvar 6', t, 'getValue', params={'view':pforms.EXPOVIEW}, ex=None,
            result='0.0' if vtype==localNumVar else '0' , )
    mTest('numvar 7', t, 'setValue', params={'view': 'fred', 'value':None}, result=None, ex=RuntimeError)
    mTest('numvar 8', t, 'setValue', params={'view': 'app', 'value':42.42}, result=True, ex=None)
    mTest('numvar 9', t, 'getValue', params={'view': 'app'}, ex=None,
            result=42.42 if vtype==localNumVar else 42,)
    mTest('numvar10', t, 'setValue', params={'view': 'app', 'value':17}, result=True, ex=None)
    mTest('numvar11', t, 'getValue', params={'view': 'app'}, result=17, ex=None)
    mTest('numvar12', t, 'getValue', params={'view': 'exp'}, ex=None,
            result='17.0' if vtype==localNumVar else '17',)
    mTest('numvar13', t, 'setValue', params={'view': 'exp', 'value': 'asd'}, result=None, ex=ValueError)
    t=cTest('numvar14', vtype, ex=ValueError, params={
        'name': 'test1', 'parent': None, 'value':-3, 'minv': 0, 'maxv':50,
        'updateEnable': vtype.validators, 'readEnable': vtype.getters})
    t=cTest('numvar15', vtype, ex=None, params={
        'name': 'test1', 'parent': None, 'value':13, 'minv': 0, 'maxv':50,
        'updateEnable': vtype.validators, 'readEnable': vtype.getters})
    mTest('numvar16', t, 'getValue', params={'view': 'app'}, result=13, ex=None)
    cTest('numvar17', vtype, ex=TypeError, params={'duff':None,
        'name': 'test1', 'parent': None, 'value':-3, 'minv': 0, 'maxv':50,
        'updateEnable': vtype.validators, 'readEnable': vtype.getters})
    t=cTest('numvar18', vtype, ex=None, params={
        'formatString': '{var.name}:{value:5.1f}',
        'name': 'test1', 'parent': None, 'value':13.13, 'minv': 0, 'maxv':50,
        'updateEnable': vtype.validators, 'readEnable': localNumVar.getters})
    mTest('numvar19', t, 'getValue', params={'view':'exp'}, ex=None,
            result='test1: 13.1' if vtype==localNumVar else 'test1: 13.0',)

def testIntervalVar():
    testNumVar(vtype=localIntervalVar)
    cTest('intervalvar 1', localIntervalVar, ex=RuntimeError, params={
        'name': 'test1', 'parent': None, 'value': None, 'updateEnable': localIntervalVar.validators, 'readEnable': {}})
    cTest('intervalvar 2', localIntervalVar, ex=RuntimeError, params={
        'name': 'test1', 'parent': None, 'value': None, 'updateEnable': {}, 'readEnable': localIntervalVar.getters})
    cTest('intervalvar 3',localIntervalVar, ex=TypeError, params={
        'name': 'test1', 'parent': None, 'value': None,
        'updateEnable': localIntervalVar.validators, 'readEnable': localIntervalVar.getters})
    cTest('intervalvar 4', localIntervalVar,ex=TypeError, params={'duff':None,
        'name': 'test1', 'parent': None, 'value':-3, 'minv': 0, 'maxv':50,
        'updateEnable': localIntervalVar.validators, 'readEnable': localIntervalVar.getters})
    t=cTest('intervalvar 5', localIntervalVar, ex=None, params={
        'name': 'test1', 'parent': None, 'value': 0,
        'updateEnable': localIntervalVar.validators, 'readEnable': localIntervalVar.getters})
    mTest('intervalvar 6', t, 'getValue', params={'view':'app'},result=0, ex=None)
    

def testField():
    o=cTest('field 10', pforms.field, params={'name':'f1', 'parent': None, 'appValue':'a', 'userUpdateable': False, 'appUpdateable': False}, ex=None)
    mTest('field 11', o, 'getValue', params={'view':'app'}, result='a')
    mTest('field 12', o, 'setValue', params={}, ex=TypeError)
    mTest('field 13', o, 'setValue', params={'view':'app'}, ex=TypeError)
    mTest('field 14', o, 'setValue', params={'value':'aa'}, ex=TypeError)
    mTest('field 15', o, 'setValue', params={'view': 'az', 'value':'b'}, ex=RuntimeError)
    mTest('field 16', o, '__str__', params={}, result='a')
    mTest('field 17', o, 'setValue', params={'view': 'user', 'value':5}, ex=TypeError)
    o=cTest('field 20', pforms.field, params={'name':'f1', 'parent': None, 'appValue':'a', 'userUpdateable': False, 'appUpdateable': True}, ex=None)
    mTest('field 21', o, 'setValue', params={'view': 'user', 'value':5}, ex=RuntimeError)
    mTest('field 22', o, 'setValue', params={'view': 'app', 'value':'b'}, result=True)
    mTest('field 23', o, 'getValue', params={'view':'app'}, result='b')
    mTest('field 24', o, '__str__', params={}, result='b')
    mTest('field 25', o, 'setValue', params={'view': 'app', 'value':'b'}, result=False)
    o=cTest('field 30', pforms.field, params={'name':'f1', 'parent': None, 'appValue':'xxx', 'userUpdateable': True, 'appUpdateable': True,
                                 'strformat': 'a-{0.fValue:}-a', 'clength':15, 'label':'a label', 'shelp':'some help'}, ex=None)
    mTest('field 31', o, 'getValue', params={'view': 'app'}, result='xxx')
    mTest('field 32', o, '__str__', params={}, result='a-xxx-a')

def testGroup():
    g1=cTest('group  1', pforms.fieldGroup, params={
        'name':'g1', 'parent': None, 'userUpdateable':True, 'appUpdateable': True, 'fieldlist': (
           (pforms.field, {'name':'f1', 'appValue':'a', 'strformat': 'uuu{0.appValue:}', 'userUpdateable': False, 'appUpdateable': True}),
           (pforms.field, {'name':'f2', 'appValue':'b', 'userUpdateable': True, 'appUpdateable': False}),
           (pforms.field, {'name':'f3', 'appValue':'c', 'userUpdateable': True, 'appUpdateable': True}),
           (pforms.field, {'name':'f4', 'appValue':'d', 'userUpdateable': False, 'appUpdateable': False}),
        )
    })
    mTest('group  2', g1, 'getAppValue', params={}, result={'f1':'a', 'f2':'b', 'f3':'c', 'f4':'d'})
    mTest('group  3', g1, 'getAppUpdates', params={}, result={})
    mTest('group  4', g1.fields['f1'], 'setAppValue', params={'appValue': 'fff'}, result=True)
    mTest('group  5', g1.fields['f1'], 'setAppValue', params={'appValue': 'fff'}, result=False)
    mTest('group  6', g1, 'getAppUpdates', params={}, result={'f1':'uuufff'})
