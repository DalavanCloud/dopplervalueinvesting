#! /usr/bin/python

# This script provides a random delay of 0 to 30 minutes.
# NOTE: This script is only needed on the server.

import time, random

def delay_min (n_minutes_max):
    n_sec_max = n_minutes * 60
    n_sec = random.uniform (0, n_sec)
    print "Delay (minutes): " + str(n_sec/60)
    time.sleep (random.uniform (0, n_sec))

delay_min (0)
