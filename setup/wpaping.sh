#!/bin/bash
#
# Loop forever doing wpa_cli SCAN commands
#

sleeptime=120  # number of seconds to sleep. 2 minutes (120 seconds) is a good value

while [ 1 ];
do
    wpa_cli -i wlan0 scan
    sleep $sleeptime
done

