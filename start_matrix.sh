#!/bin/bash
source /home/jesper/snake_server/server_venv/bin/activate

umask 000
/home/jesper/snake_server/server_venv/bin/python -m home_led_matrix.main
deactivate
