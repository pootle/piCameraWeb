#!/usr/bin/python3
"""
Some helpful functions to extract info from the filesystem.

Each file / folder is represented as a dict with:
    type: None for a folder, otherwise the file extension (empty string if there is no extension)
    path: pathlib.Path for the file or folder 
    size: The size of the file (for files) or all files within the folder (and its children) for folders
    inner: (only present for folders) a dict with key as the file / folder name, and value as one of these dicts
    count: (only present for folders) the number of files within this folder (and its children)
"""

import pathlib
from collections import OrderedDict

def prettyprint(dt, indent=0):
    for n,f in dt.items():
        if f['type'] is None:
            print('  '*indent, '{:15s} ({})'.format(n,f['count']))
            prettyprint(f['inner'],indent+1)
        else:
            print('  '*indent, '{:15s} ({:3.2f}MB)'.format(n,f['size']/1048576))

lifile='<li class="vfile"><a href=fetch?f={}>{}</a></li>'
lifold=('{indent:}<li class="vdir"><label for="{path:}"> ({count:4d}) {name:}</label> <input type="checkbox" {top:}id="{path}" /><ol>\n'
        '{inside:}'
        '{indent:}</ol></li>\n'
)

def prettyhtml(dt, indent=0):
    r='<ol class="vtree">' if indent==0 else ''
    for n,f in dt.items():
        if f['type'] is None:
            r+=lifold.format(indent='  '*indent, name=n, path=f['path'], count=f['count'], top='checked ', inside=prettyhtml(f['inner'],indent+1))
        else:
            r+=' '*indent+lifile.format(n,f['path'])+'\n'
    if indent==0:
        return r+'</ol>'
    else:
        return r

def pl(folder):
    if not isinstance(folder, pathlib.Path):
        folder=pathlib.Path(folder).expanduser()
    nd=folddict(folder)
    return {folder.name: {'type': None, 'path': folder, 'inner': nd, 
                        'count':sum([v['count'] if v['type'] is None else 1 for v in nd.values() ]),
                        'size': folder.stat().st_size + sum(v['size'] for v in nd.values())}}
       
def folddict(folder):
    plx=folder.iterdir()
    folds=[]
    files=[]
    for pli in plx:
        if not pli.name.startswith('.'):
            if pli.is_file():
                files.append((pli.name,{'type': pli.suffix[1:], 'path': pli, 'size':pli.stat().st_size}))
            elif pli.is_dir():
                nd=folddict(pli)
                folds.append((pli.name, {'type': None, 'path': pli, 'inner': nd, 
                            'count':sum([v['count'] if v['type'] is None else 1 for v in nd.values() ]), 
                            'size': pli.stat().st_size + sum(v['size'] for v in nd.values())}))
            else:
                print('eeeeeeeeeeeeeek', str(pli))
    x=OrderedDict(folds)
    x.update(files)
    return x
    