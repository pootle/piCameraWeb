#!/usr/bin/python3
"""
This module provides a class for node based trees, the class provided can be used as a base or mixin
for hierarchical object trees.

The primary class inherits from OrderedDict, so child nodes can be selected using standard dict notation.
In addition __getitem__ is redefined to allow filesystem like navigation using '..' and '/'. This does mean
that '/'  and '..' can't be used as part of node names.

Examples:
    node['childx']      - selects the child node named 'childx' of the current node.
    node['../siblingx'] - selects the sibling node named 'siblingx' of the current node - that is the 
                          child node 'siblingx' of the parent of the current node.
"""

from collections import Hashable
from collections import OrderedDict

class treeob(OrderedDict):
    """
    A class that places an object within a tree. Each node is basically a dict (empty for leaf nodes)
    """
    def __init__(self, *, name, parent, app, childdefs=None): # * forces all args to be used as keywords
        """
        Creates a node and links it from the parent (if present)

        name        : a hashable name for the node
        
        parent      : if not None, then the child will be added as an offspring of this parent
        
        app         : the top parent (root node) of the tree, can hold various tree constant info, None only
                      for the root node itself.
        
        childdefs   : iterable of definitions for child nodes, each to be the kwargs for calling makeChild

        raises ValueError is the parent already has a child with this name, or if the name is not Hashable
        """
        assert isinstance(name, Hashable), 'the name given for variable {} is not hashable'.format(name)
        self.name=name
        self.parent=parent
        self.app=app
        super().__init__()
        if not parent is None:
            parent[self.name]=self
        if not childdefs is None:
            for cdef in childdefs:
                self.makeChild(**cdef)
   
    def makeChild(self, _cclass, **kwargs):
        """
        default makeChild creates a child with parent and app defined automatically.
        """
        return _cclass(parent=self, app=self.app, **kwargs)

    def __getitem__(self, nname):
        splitname=nname.split('/')
        if len(splitname)==1:
            try:
                return super().__getitem__(nname)
            except KeyError:
                raise KeyError('key %s not found in %s' % (nname, str(self.keys())))
        cnode=self
        for pname in splitname:
            if pname=='':
                cnode=self.app
            elif pname=='..':
                cnode=cnode.parent
            else:
                try:
                    cnode=cnode.__getitem__(pname)
                except KeyError:
                    raise KeyError('key %s not found in %s' % (pname, str(cnode.keys())))
        return cnode

    hiernamesep='*'

    def getHierName(self):
        """
        returns the hierarchic name of this variable.
        
        Returns a string using hiernamesep to separate each ancestor's name. 
        """
        if self.parent is None:
            return self.name
        else:
            return self.parent.getHierName()+self.hiernamesep+self.name

    def __repr__(self):
        if self.children is None:
            return "{} name={}, carries {}".format(self.__class__.__name__, self.name, self.target)
        else:
            return "{} name={}, carries {}, children {}".format(self.__class__.__name__, self.name, self.target, list(self.children.keys()))