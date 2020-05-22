import subprocess
"""
A little bit of Python that returns info about wifi network interaces with info on signal strength and quality

Includes a simple utility function that returns just a list of (non loopback) IP4 adresses
"""
def wifinf():
    """
    parses the output from iwconfig' and returns key info.
    
    returns a dict with keys being the name of the interface and each value being a list of dicts:
    
        each dict with possible entries:
            'peer'      : ip4 host address (if there is one)
            'netmask'   : mask for this subnet
            'broadcast' : broadcast address
            'mac_addr'  : mac address
            plus any other parts found on the inet line as key / value pairs
    """
    co = subprocess.run(['/sbin/iwconfig'], capture_output=True, text=True)
    ifaces={}
    alines=co.stdout.split('\n')
    def lineget():
        if alines:
            return alines.pop(0)+'\n'
        else:
            return ''
    aline=lineget()
    while aline:
        if len(aline) > 10:
            prel=aline[:10].strip()
            post=aline[10:].strip()
            if prel != '':
                newlink={}
                newlinkname=prel
                ifaces[newlinkname] = newlink
            for tests in ('IEEE ', 'ESSID:', 'Frequency:', 'Bit Rate=', 'Tx-Power=', 'Link Quality=', 'Signal level='):
                ix = post.find(tests)
                if ix != -1:
                    rest=post[ix+len(tests):]
                    if tests=='ESSID:':
                        assert rest[0]=='"'
                        endstrix=rest.find('"',1)
                        assert endstrix != -1
                        newlink['ESSID'] = (rest[1:endstrix],'')
                    elif tests in ('Frequency:', 'Bit Rate=', 'Tx-Power=', 'Signal level='):
                        nums=rest.split(maxsplit=2)
                        val=float(nums[0])
                        units=nums[1]
                        newlink[tests[:-1]]=(val,units)
                    elif tests=='Link Quality=':
                        sp1=rest.split(maxsplit=1)
                        lqs=sp1[0].split('/')
                        newlink['Link Quality'] = int(lqs[0])/int(lqs[1])
                        
                        
                        
            
        aline=lineget()
    return ifaces