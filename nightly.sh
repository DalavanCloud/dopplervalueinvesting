#!/bin/bash

# This script is strictly for the cron execution in the web server environment.
# The nice command makes the script a sufficiently low priority to avoid impacting performance.
# The screen output is logged and saved.

#nice -n10 ionice -c2 -n5 python2.7 /home/doppler/webapps/scripts_doppler/dopplervalueinvesting/screen.py &>> $HOME/logs/user/screen.txt

python2.7 /home/doppler/webapps/scripts_doppler/dopplervalueinvesting/screen.py &>> $HOME/logs/user/screen.txt
