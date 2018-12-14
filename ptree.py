#!/usr/bin/python3
"""
This module provides a class for node based trees, the class provided can be used as a base or mixin
for hierarchical object trees
"""

from collections import Hashable
from collections import OrderedDict

class treeob(OrderedDict):
    """
    A class that places an object within a tree. Each node is basically a dict (empty for leaf nodes)
    """
    def __init__(self, *, name, parent, app): # * forces all args to be used as keywords
        """
        Creates a node and links it from the parent (if present)

        name        : a hashable name for the node
        
        parent      : if not None, then the child will be added as an offspring of this parent
        
        app         : the top parent (root node) of the tree, can hold various tree constant info, None only
                      for the root node itself.
        
        raises ValueError is the parent already has a child with this name, or if the name is not Hashable
        """
        assert isinstance(name, Hashable), 'the name given for variable {} is not hashable'.format(name)
        self.name=name
        self.parent=parent
        self.app=app
        if not parent is None:
            parent[self.name]=self

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