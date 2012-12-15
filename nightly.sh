#!/bin/bash
# Proper header for a Bash script.

nice -n10 ionice -c2 -n5 /usr/local/bin/python2.7 /home/doppler/webapps/scripts_doppler/dopplervalueinvesting/delay.py >> /home/doppler/logs/user/delay.txt

nice -n10 ionice -c2 -n5 /usr/local/bin/python2.7 /home/doppler/webapps/scripts_doppler/dopplervalueinvesting/screen.py >> /home/doppler/logs/user/screen.txt
