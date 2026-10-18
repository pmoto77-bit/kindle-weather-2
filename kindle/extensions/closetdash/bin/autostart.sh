#!/bin/sh
# autostart.sh enable|disable - from KUAL. Installs or removes /etc/upstart/closetdash.conf.
# Writes autostart-log.txt and shows the result at the bottom of the screen.
DIR="$(cd "$(dirname "$0")/.." && pwd)"
L="$DIR/autostart-log.txt"
JOB="/etc/upstart/closetdash.conf"
MNT="$(which mntroot 2>/dev/null)"

say() {
	echo "$1" >> "$L"
	sleep 2
	eips 1 30 "$1                    " > /dev/null 2>&1
}

echo "$(date '+%Y-%m-%d %H:%M:%S') autostart.sh $1 (mntroot: ${MNT:-not found})" >> "$L"
case "$1" in
	enable)
		[ -n "$MNT" ] || { say "Auto-start: can't (mntroot missing)"; exit 1; }
		touch "$DIR/AUTOSTART"
		mntroot rw >> "$L" 2>&1
		cp "$DIR/upstart/closetdash.conf" "$JOB" >> "$L" 2>&1
		sync
		mntroot ro >> "$L" 2>&1
		if [ -f "$JOB" ]; then say "Auto-start is ON"; else say "Auto-start FAILED - see autostart-log.txt"; fi
		;;
	disable)
		rm -f "$DIR/AUTOSTART"   # this alone already stops auto-start
		if [ -f "$JOB" ] && [ -n "$MNT" ]; then
			mntroot rw >> "$L" 2>&1
			rm -f "$JOB" >> "$L" 2>&1
			sync
			mntroot ro >> "$L" 2>&1
		fi
		say "Auto-start is OFF"
		;;
	*)
		echo "usage: autostart.sh enable|disable" >> "$L"
		;;
esac
ls -l "$JOB" >> "$L" 2>&1
