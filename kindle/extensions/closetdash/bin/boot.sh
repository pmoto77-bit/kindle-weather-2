#!/bin/sh
# Run once per boot by /etc/upstart/closetdash.conf (installed by "Enable auto-start").
# Starts Closet Dash in boot mode: a countdown that any tap cancels.
DIR="$(cd "$(dirname "$0")/.." && pwd)"
. "$DIR/bin/settings.sh"

[ -f "$DIR/AUTOSTART" ] || exit 0                 # auto-start switched off
[ -f /mnt/us/STOP_CLOSETDASH ] && exit 0          # kill switch: file at the Kindle drive's top level
[ -f /tmp/closetdash-autostarted ] && exit 0      # only once per boot (/tmp is cleared at boot)
touch /tmp/closetdash-autostarted

sleep "$BOOT_WAIT"
export CLOSETDASH_BOOT=1
if [ -x /usr/bin/setsid ]; then
	/usr/bin/setsid /bin/sh "$DIR/bin/run.sh" < /dev/null > /dev/null 2>&1 &
else
	/bin/sh "$DIR/bin/run.sh" < /dev/null > /dev/null 2>&1 &
fi
