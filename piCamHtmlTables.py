#!/usr/bin/python3

import pforms

class htmlgentable(pforms.groupVar):
    """
    mixin for pforms field groups that create an html table for all the fields
    """
    groupwrapper='<table>{childfields}</table>'
    childwrapper='<tr><th scope="row">{label:}</th><td class="value">{cont:}</td><td class="helpbtn" title="{shelp:}">?</td></tr>\n'
    def _getHtmlValue(self, view):
        rows='\n'.join([self.childwrapper.format(**ch.getValue('html')) for ch in self.values()])
        return self.groupwrapper.format(childfields=rows,f=self)

class htmlgentabbedgroups(htmlgentable):
    groupwrapper=('<input name="tabgroup1" id="{f.name}" type="radio" >'
                        '<section>\n'
                        '    <h1><label for="{f.name}">{f.label}</label></h1>\n'
                        '    <div><table>\n{childfields}</table></div>'
                        '</section>\n')
    def __init__(self, readers=None, readersOn=('app', 'html', 'pers'), writers=None,writersOn=('app', 'pers'), **kwargs):
        super().__init__(
                readers=pforms.extendViews(readers, {'app':'_getValueDict', 'html': '_getHtmlValue', 'pers':'_getValueDict'}),
                readersOn=readersOn,
                writers=pforms.extendViews(writers, {'app':'_setValueDict', 'pers': '_setValueDict'}),
                writersOn=writersOn,
                **kwargs)
