#!/bin/sh
# Launched from KUAL: start run.sh (which runs dash.sh and restarts it after a crash) in
# the background so it keeps running after KUAL and the reading interface close.
# Writes start-log.txt for troubleshooting.
DIR="$(cd "$(dirname "$0")/.." && pwd)"
L="$DIR/start-log.txt"
{
	echo "$(date '+%Y-%m-%d %H:%M:%S') start.sh"
	echo "busybox: $(busybox 2>&1 | head -1)"
	echo "applets: $(busybox --list 2>/dev/null | tr '\n' ' ')"
} > "$L" 2>&1

# Use a 'setsid' helper only if this Kindle really has one (new session = safest).
S=""
for p in /usr/bin/setsid /bin/setsid /usr/sbin/setsid /sbin/setsid; do
	[ -x "$p" ] && S="$p" && break
done
if [ -z "$S" ] && busybox setsid true > /dev/null 2>&1; then
	S="busybox setsid"
fi

if [ -n "$S" ]; then
	$S /bin/sh "$DIR/bin/run.sh" < /dev/null >> "$L" 2>&1 &
else
	/bin/sh "$DIR/bin/run.sh" < /dev/null >> "$L" 2>&1 &
fi
echo "launched pid $! via ${S:-plain background}" >> "$L"
sleep 5   # stay alive briefly so the program is settled before KUAL tidies up
echo "dash running: $(cat /tmp/closetdash/dash.pid 2>/dev/null || echo 'no pid file yet')" >> "$L"
