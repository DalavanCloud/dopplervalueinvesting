#!/bin/bash
# Proper header for a Bash script.

# This is the script called by cron on the remote server.

nice -n10 ionice -c2 -n5 python $HOME/webapps/scripts_doppler/dopplervalueinvesting/delay.py
nice -n10 ionice -c2 -n5 python $HOME/webapps/scripts_doppler/dopplervalueinvesting/screen.py
