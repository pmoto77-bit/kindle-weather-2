#!/bin/sh
# Keeps Closet Dash running. Starts dash.sh and, if it ever stops without a clean exit
# (a crash, or the system killing it), starts it again a minute later - so a frozen
# picture can't sit on the screen looking current. A clean exit (EXIT TO KINDLE, Stop,
# a cancelled auto-start countdown, "already running") ends this script too.
# Started by start.sh (KUAL) and boot.sh (auto-start).
trap ':' HUP   # a handler, not an ignore: dash.sh must still be able to trap TERM itself
DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN="/tmp/closetdash"
LOG="$DIR/dash-log.txt"
mkdir -p "$RUN"

if [ -f "$RUN/run.pid" ] && kill -0 "$(cat "$RUN/run.pid")" 2>/dev/null; then
	exit 0
fi
echo $$ > "$RUN/run.pid"

n=0
while :; do
	/bin/sh "$DIR/bin/dash.sh" < /dev/null > /dev/null 2>&1
	code=$?
	[ "$code" = "0" ] && break
	n=$((n + 1))
	echo "$(date '+%m-%d %H:%M:%S') watchdog: Closet Dash stopped unexpectedly (code $code) - restart $n in 1 min" >> "$LOG"
	unset CLOSETDASH_BOOT   # no boot countdown on a restart
	sleep 60
	[ "$n" -ge 5 ] && sleep 540   # keeps failing: try every 10 minutes instead
done
rm -f "$RUN/run.pid"
