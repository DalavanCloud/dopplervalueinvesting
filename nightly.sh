#!/bin/bash
# Proper header for a Bash script.

# This is the script called by cron on the remote server.  
# This script is NOT intended for use in the development environment.

python $HOME/webapps/scripts_doppler/dopplervalueinvesting/delay.py
python $HOME/webapps/scripts_doppler/dopplervalueinvesting/screen.py
