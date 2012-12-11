#! /usr/bin/python

# This script provides a random delay of 0 to 30 minutes.
# NOTE: This script is only needed on the server.

import time, random

def delay_min (n_minutes):
    n_sec = n_minutes * 60
    print "Delay of " + str(n_minutes) + " minutes"
    time.sleep (random.uniform (0, n_sec))

delay_min (30)
