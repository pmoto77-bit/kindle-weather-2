#!/bin/sh
# From KUAL: forget the touch setup; the next Start shows the 3 dots again.
DIR="$(cd "$(dirname "$0")/.." && pwd)"
rm -f "$DIR/touch.conf"
sleep 2
eips 1 30 "Touch setup cleared - press Start to redo it" > /dev/null 2>&1
