#!/bin/sh
# Closet Dash - device check. Read-only: changes nothing on the Kindle.
# Writes device-check.txt (in this extension's folder, visible over USB) with the facts
# the program depends on that can differ between Kindle models and firmware versions,
# then runs the download test (test-result.txt).
DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$DIR/device-check.txt"

sec() { echo; echo "=== $1"; }
run() { echo "\$ $*"; "$@" 2>&1; }
prop() { echo "$1 $2 = $(lipc-get-prop "$1" "$2" 2>&1)"; }

eips 1 2 "Device check running (about 1 minute)..." > /dev/null 2>&1
{
	echo "device-check $(date '+%Y-%m-%d %H:%M:%S %Z')  (UTC $(date -u '+%H:%M'))"
	sec "firmware"
	run cat /etc/prettyversion.txt
	run uname -a
	grep -e Hardware -e Revision /proc/cpuinfo 2>&1
	sec "screen (eips -i)"
	run eips -i
	sec "upstart jobs (initctl list)"
	run initctl list
	sec "input devices"
	run cat /proc/bus/input/devices
	sec "front light"
	for f in $(find /sys -name '*intensity*' 2>/dev/null) /sys/class/backlight/*/brightness \
	         /sys/class/backlight/*/max_brightness /sys/class/backlight/*/actual_brightness; do
		[ -f "$f" ] && echo "$f: $(cat "$f" 2>&1)"
	done
	prop com.lab126.powerd flIntensity
	prop com.lab126.powerd flMaxIntensity
	sec "power"
	prop com.lab126.powerd battLevel
	prop com.lab126.powerd isCharging
	prop com.lab126.powerd status
	prop com.lab126.powerd preventScreenSaver
	sec "wi-fi"
	prop com.lab126.wifid cmState
	prop com.lab126.wifid signalStrength
	prop com.lab126.cmd wirelessEnable
	sec "tools"
	echo "busybox: $(busybox 2>&1 | head -n 1)"
	echo "applets: $(busybox --list 2>/dev/null | tr '\n' ' ')"
	for t in curl openssl wget hd hexdump timeout setsid mntroot crond rtcwake lipc-get-prop eips; do
		echo "which $t: $(which $t 2>/dev/null || echo MISSING)"
	done
	run curl --version
	run openssl version
	sec "cron"
	run ls -l /etc/crontab
	run cat /etc/crontab/root
	sec "updates (OTA programs; renamed or missing = updates blocked)"
	run ls -l /usr/bin/otaupd /usr/bin/otav3 /usr/bin/otaupd.bck /usr/bin/otav3.bck
	ls /mnt/us/*.bin /mnt/us/*.partial 2>/dev/null | sed 's/^/pending update file: /'
	sec "storage"
	run df -h /mnt/us /tmp /var/local
	sec "processes"
	run ps
} > "$OUT" 2>&1
sync
eips 1 3 "Device check saved: device-check.txt" > /dev/null 2>&1
sleep 2
exec /bin/sh "$DIR/bin/test-download.sh"
