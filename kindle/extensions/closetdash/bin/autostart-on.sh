#!/bin/sh
# From KUAL: turn auto-start on (separate script so KUAL never has to pass an argument).
/bin/sh "$(dirname "$0")/autostart.sh" enable
