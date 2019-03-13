#!/usr/bin/python3
from subprocess import check_output, STDOUT, CalledProcessError
try:
    import pathlib, picamera
    picapath=pathlib.Path(picamera.__file__).parent
    for pyfile in ('streams','camera','encoders'):
        pfp=picapath/pyfile
        pfp=pfp.with_suffix('.py')
        out='unset'
        if pfp.exists():
            try:
                out = check_output(['patch', "-zorig", '-b', str(pfp), pyfile+'.patch'], universal_newlines=True, stderr=STDOUT).split('\n')
            except CalledProcessError as ce:
                elines=ce.output.split('\n')
                for l in elines:
                    if l.startswith('Reversed'):
                        print('%s.py already patched - ignored' % pyfile)
                        break
                else:
                    print('patch went wrong for %s.py' % pyfile)
                    print(ce.output)
                    break
        else:
            print("can't find file to patch - ", pfp)

except:
    print('artgh')
    raise