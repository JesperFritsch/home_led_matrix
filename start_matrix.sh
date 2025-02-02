#!/bin/bash
#. /home/pi/home_led_matrix/matrix_venv/bin/activate

umask 000
nice -n -10 python -m home_led_matrix.main
