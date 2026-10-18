#!/bin/sh
# Closet Dash - front light test (diagnostic, about 1 minute; puts the light back afterwards).
# Steps the light through each way of turning it off and logs what the hardware reports.
# Watch the screen in a dark room and note which STEP is fully dark.
DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$DIR/light-test-result.txt"
ROW=2

say() {   # one line on screen and in the log
	eips 1 "$ROW" "$1" > /dev/null 2>&1
	ROW=$((ROW + 1))
	echo "$(date '+%H:%M:%S') $1" >> "$LOG"
}

log() {
	echo "$(date '+%H:%M:%S') $1" >> "$LOG"
}

values() {   # what powerd and the light driver report right now
	v="powerd=$(lipc-get-prop com.lab126.powerd flIntensity 2>&1)"
	for f in $FILES; do
		v="$v | $f=$(cat "$f" 2>&1)"
	done
	log "    $v"
}

: > "$LOG"
sleep 3   # let KUAL close
eips -c > /dev/null 2>&1
say "CLOSET DASH - LIGHT TEST (about 1 minute)"
say "Watch the glow. Note which STEP is fully dark."
log "firmware: $(cat /etc/prettyversion.txt 2>/dev/null)"

ORIG="$(lipc-get-prop com.lab126.powerd flIntensity 2>/dev/null)"
log "light level before the test: ${ORIG:-unknown}"
FILES="$(find /sys/devices/system -name '*intensity*' 2>/dev/null) $(ls /sys/class/backlight/*/brightness 2>/dev/null)"
log "light driver files found: $(echo $FILES)"
for d in /sys/devices/system/fl_* /sys/class/backlight/*; do
	[ -d "$d" ] && log "  $d: $(ls "$d" 2>&1 | tr '\n' ' ')"
done
values

say ""
say "STEP 1: light ON at level 8 (for comparison)"
lipc-set-prop com.lab126.powerd flIntensity 8
sleep 8
values

say "STEP 2: off the way Closet Dash does it now"
lipc-set-prop com.lab126.powerd flIntensity 0
sleep 10
values

say "STEP 3: off directly at the light chip"
for f in $FILES; do
	echo 0 > "$f" 2>> "$LOG" && log "    wrote 0 to $f"
done
sleep 10
values

say "STEP 4: same as step 3 - does it stay off?"
sleep 10
values

say ""
say "Done. Light set back to ${ORIG:-5}."
lipc-set-prop com.lab126.powerd flIntensity "${ORIG:-5}"
sleep 2
values
say "Plug in USB and send Claude"
say "extensions/closetdash/light-test-result.txt"
say "and which STEP looked fully dark."
