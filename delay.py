#! /usr/bin/python

# This script provides a random delay and is intended for use ONLY on the server.

import random, time

def delay_min (n_minutes_max):
    n_sec_max = n_minutes_max * 60
    n_sec = random.uniform (0, n_sec_max)
    n_minutes = n_sec/60
    print "Delay (minutes): " + str(n_minutes)
    time.sleep (random.uniform (0, n_sec))

delay_min (30)
