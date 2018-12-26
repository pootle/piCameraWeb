#!/usr/bin/python3

"""
a simple pure python handler for netpbm images that does not require any external image handling libraries.
It is used only to load and save files from arrays of data and does not do ANY image manipuation. Plenty of
other software exists for that.
"""

import pathlib

class basep():
    """
    The basic class for a netpbm file that can be of any netpbm type 
    
    It knows basic properties of the various file types (2 color, greyscale and colour), and holds the image as a 2d array
    """
    def __init__(self, isbinary=False, maxval=None, width=None, height=None, fname=None, datapos=None, comments=None, imgdata=None):
        self.fname=fname
        self.datapos=datapos
        self.isbinary=isbinary
        self.width=width
        self.height=height
        self.maxval=maxval
        self.comments=comments if comments is None else [c.encode() if isinstance(c, str) else c for c in comments]
        self.imgdata=imgdata
        if not self.imgdata is None:
            self.height=len(imgdata)
            self.width=len(imgdata[0])
        if not self.imgdata is None and self.maxval is None:
            self.maxval=max([max(row) for row in imgdata])

    def writeFile(self, filename):
        fp=pathlib.Path(filename).expanduser().with_suffix(self.namesuffix())
        with fp.open(mode='wb') as wf:
            wf.write(b'%s\n%s%d %d\n%s' % (
                    self.magic(),
                    b'' if self.comments is None else b''.join([b'# %s\n' % cl for cl in self.comments]),
                    self.width,
                    self.height,
                    self.maxvalstr(),
                    ))
            for n in self.imgdata:
                wf.write(self.encodeline(n))

def stripbins(fo):
    bk=fo.read(5000)
    while len(bk) > 0:
        for ch in bk:
            if ch==49:
                yield 0
            elif ch==48:
                yield 1
        bk=fo.read(5000)
    raise EOFError

class pbm(basep):
    """
    for bitmap (binary format)
    """
    def loadImage(self):
        """
        if the image is not already in imgdata, then load it from the file
        """
        if not self.imgdata is None:
            return
        filep=pathlib.Path(self.fname).expanduser()
        if not filep.is_file():
            raise ValueError('{} does not appear to be a file I can find'.format(str(fp)))

        with filep.open(mode='rb') as fo:
            fo.seek(self.datapos)
            ypos=0
            if self.isbinary:
                raise NotImplementedError
            else:
                grabber=stripbins(fo)
                self.imgdata=[[next(grabber) for x in range(self.width)] for y in range(self.height)]

    def imgtype(self):
        return 'PBM'

    def namesuffix(self):
        return '.pbm'

    def magic(self):
        return b'P4' if self.isbinary else b'P1'

    def maxvalstr(self):
        """
        returns an empty byte string for this type
        """
        return b''

    def encodeline(self,linedata):
        ld=bytes([49 if pix is 0 else 48 for pix in linedata])
        return ld+b'\n'

class pgm(basep):
    """
    for graymap format
    """
    pass

class ppm(basep):
    """
    for pixmap format
    """
    pass

NETPBMTYPES={
    b'P1': ('PBM', False, pbm),
    b'P2': ('PGM', False, pgm),
    b'P3': ('PPM', False, ppm),
    b'P4': ('PBM', True, pbm),
    b'P5': ('PGM', True, pgm),
    b'P6': ('PPM', True, ppm),}


def getnoncomment(openfile, comments):
    al=openfile.readline()
    if len(al)==0:
        return ''
    aline=al.strip()
    while len(aline) == 0 or aline.startswith(b'#'):
        if len(aline) > 0:
            comments.append(aline)
        al=openfile.readline()
        if len(al)==0:
            return ''
        aline=al.strip()
    return aline

def open(filename):
    """
    given a filename (as string) of pathlib Path, this opens the file and creates an instance of the appropriate image class with various
    properties setup. The image itself is loaded into an array of arrays
    """
    fp=pathlib.Path(filename).expanduser()
    if not fp.is_file():
        raise ValueError('{} does not appear to be a file I can find'.format(str(fp)))
    else:
        with fp.open(mode='rb') as nf:
            ftype=nf.read(2).strip()
            if ftype in NETPBMTYPES.keys():
                imgtype, isbinary, pclass=NETPBMTYPES[ftype]
                comments=[]
                sline=getnoncomment(nf, comments)
                try:
                    width, height = [int(num) for num in sline.split()]
                except:
                    print(sline)
                    raise ValueError('unable to parse width and height of image from the line >'+sline.decode()+'<')
                if imgtype == 'PGM' or imgtype == 'PPM':
                    sline=getnoncomment(nf, comments)
                    maxval=int(line)
                else:
                    maxval=1
                dpos=nf.tell()
                img=pclass(isbinary=isbinary, maxval=maxval, 
                            width=width, height=height, fname=fp, datapos=dpos, comments=comments)
            else:
                raise ValueError('{} does not appear to be a netpbm file - magic number {} not valid.'.format(str(fp),ftype))
        return img