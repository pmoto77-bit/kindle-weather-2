#!/bin/sh
# Closet Dash: start the weather display (tap the screen any time for the menu).
# Hands off and returns at once: the library's launcher must finish before Closet Dash
# pauses the reading interface, or the Kindle shows an "application error".
/usr/bin/setsid /bin/sh /mnt/us/extensions/closetdash/bin/start.sh < /dev/null > /dev/null 2>&1 &
exit 0
