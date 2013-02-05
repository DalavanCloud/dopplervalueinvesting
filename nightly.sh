#!/bin/bash
# Proper header for a Bash script.

nice -n10 ionice -c2 -n5 /usr/local/bin/python2.7 /home/doppler/webapps/scripts_doppler/dopplervalueinvesting/delay.py

nice -n10 ionice -c2 -n5 /usr/local/bin/python2.7 /home/doppler/webapps/scripts_doppler/dopplervalueinvesting/screen.py

nice -n10 ionice -c2 -n5 /usr/local/bin/python2.7 /home/doppler/webapps/scripts_doppler/dopplervalueinvesting/stock.py
