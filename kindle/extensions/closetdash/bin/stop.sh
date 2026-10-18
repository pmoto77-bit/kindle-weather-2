#!/bin/sh
# Ask a running Closet Dash to exit; it restores the reading interface itself.
touch /tmp/closetdash/exit 2>/dev/null
P="$(cat /tmp/closetdash/dash.pid 2>/dev/null)"
[ -n "$P" ] && kill "$P" 2>/dev/null
exit 0
