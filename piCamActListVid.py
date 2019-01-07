#!/usr/bin/python3
"""
Module to list and download recorded videos
"""
import piCamHtml as pchtml


class htmlClickButton(pchtml.htmlCyclicButton):
    def webUpdateValue(self, value):
        rval=super().webUpdateValue(value)
        print('hello bozo')
        return rval

class fileGetter(pchtml.htmlFolderList):
    def webUpdateValue(self, value):
        res=super().webUpdateValue(value)
        if res['resp']==200:
            targetfile=self.getFile()
            if not targetfile is None:
                res['dload']=targetfile
        return res

vidlisttable=(
    (htmlClickButton, {
            'name' : 'list',  'fallbackValue': 'show list', 'alist': ('show list', ' show list '),
            'onChange'  : ('dynamicUpdate','user'),
            'label': 'update video list', 
            'shelp': 'updates the list of available videos',
    }),
    (fileGetter, {
            'name'          : 'foldercont',
            'fallbackValue' : '~/',
            'label'         : 'files and folders',
            'shelp'         : 'files and folders available',
            'readersOn'     : ('app', 'pers', 'html'),
            'writersOn'     : ('app', 'pers', 'user'),
    }),

)
