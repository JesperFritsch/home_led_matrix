#!/bin/bash
source /home/jesper/snake_server/server_venv/bin/activate

umask 000
python -m home_led_matrix.main
deactivate
