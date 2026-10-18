#!/bin/sh
# Closet Dash - main program (run by run.sh, which start.sh starts from KUAL and boot.sh
# after a reboot; run.sh restarts it if it ever stops without a clean exit).
# Pauses the Kindle's reading interface, shows the weather picture and keeps it current.
# Exit: tap the screen -> menu -> EXIT TO KINDLE -> YES, EXIT. Or restart the Kindle.

trap '' TERM HUP   # survive the reading interface being stopped (same process group)

DIR="$(cd "$(dirname "$0")/.." && pwd)"
. "$DIR/bin/settings.sh"
RUN="/tmp/closetdash"
LOG="$DIR/dash-log.txt"
PIDFILE="$RUN/dash.pid"
CACERT="$DIR/cacert.pem"
IMG="$DIR/img"
TCONF="$DIR/touch.conf"
TAPS="$RUN/taps"
UI_JOBS="framework lab126_gui"
TICK=5
WARN_SHOWN=""
WPID=""
TAPS_SEEN=0
TOUCH_OK=""
VERSION="kindle-weather-2 v0.9 (PW3)"

mkdir -p "$RUN"
[ -f "$LOG" ] && [ "$(wc -l < "$LOG")" -gt 2000 ] && tail -n 1000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
exec >> "$LOG" 2>&1

log() {
	echo "$(date '+%m-%d %H:%M:%S') $*"
}

sys() {   # anything that changes the Kindle; CLOSETDASH_DRY=1 only logs it (PC testing)
	if [ -n "$CLOSETDASH_DRY" ]; then log "DRY: $*" >> "$LOG"; else "$@"; fi
}

num() {   # "0530" -> 530 (no octal surprises)
	echo "$1" | sed 's/^0*//; s/^$/0/'
}

state() {   # state NAME [DEFAULT]
	cat "$RUN/$1" 2>/dev/null || echo "${2:-}"
}

now_vars() {
	if [ -n "$FAKE_NOW" ]; then
		set -- $(date -d "$FAKE_NOW" '+%s %Y-%m-%d %H%M %S')
	else
		set -- $(date '+%s %Y-%m-%d %H%M %S')
	fi
	EPOCH=$1
	TODAY=$2
	HHMM=$3
	SECS=$4
}

minutes() {   # "0530" -> 330 (minutes since midnight)
	echo $(( $(num "${1%??}") * 60 + $(num "${1#??}") ))
}

battery() {
	lipc-get-prop com.lab126.powerd battLevel 2>/dev/null
}

# ------------------------------------------------------------------ reading interface
ui_stop() {   # keeps any list a crashed run left behind, so Exit still restarts those jobs
	touch "$RUN/stopped_jobs"
	for j in $UI_JOBS; do
		if initctl status "$j" 2>/dev/null | grep -q running; then
			sys stop "$j" > /dev/null 2>&1
			grep -q "^$j$" "$RUN/stopped_jobs" || echo "$j" >> "$RUN/stopped_jobs"
			log "stopped $j"
		fi
	done
}

ui_start() {
	for j in $(state stopped_jobs); do
		sys start "$j" > /dev/null 2>&1
		log "started $j"
	done
	rm -f "$RUN/stopped_jobs"
}

# ------------------------------------------------------------------ Wi-Fi, clock, downloads
wifi_up() {
	[ "$(lipc-get-prop com.lab126.wifid cmState 2>/dev/null)" = "CONNECTED" ] && return 0
	sys lipc-set-prop com.lab126.cmd wirelessEnable 1
	i=0
	while [ $i -lt 30 ]; do
		sleep 2
		[ "$(lipc-get-prop com.lab126.wifid cmState 2>/dev/null)" = "CONNECTED" ] && return 0
		i=$((i + 1))
	done
	return 1
}

wifi_down() {
	[ "$WIFI_OFF_BETWEEN" = "1" ] && sys lipc-set-prop com.lab126.cmd wirelessEnable 0
}

get() {   # get URL FILE: verified download first, then unverified (-k); sets METHOD
	rm -f "$2"
	if curl -f -sS --max-time 30 --cacert "$CACERT" -o "$2" "$1" 2> "$RUN/curl.err" && [ -s "$2" ]; then
		METHOD="verified"
		return 0
	fi
	e1="$(tr '\n' ' ' < "$RUN/curl.err")"
	if curl -f -k -sS --max-time 30 -o "$2" "$1" 2> "$RUN/curl.err" && [ -s "$2" ]; then
		METHOD="unverified"
		log "note: verified download failed (${e1:-no detail}), used unverified"
		return 0
	fi
	log "download failed: ${1##*/}: ${e1:-no detail} / $(tr '\n' ' ' < "$RUN/curl.err")"
	return 1
}

set_clock() {   # fix the Kindle clock from the web server's Date header if it is >2 min off
	d="$(curl -k -sSI --max-time 20 "$BASE/status.txt" 2>/dev/null | sed -n 's/^[Dd]ate: *//p' | tr -d '\r')"
	set -- $d   # Sun, 12 Oct 2026 01:32:59 GMT
	[ $# -ge 5 ] || return
	case "$3" in
		Jan) m=01 ;; Feb) m=02 ;; Mar) m=03 ;; Apr) m=04 ;; May) m=05 ;; Jun) m=06 ;;
		Jul) m=07 ;; Aug) m=08 ;; Sep) m=09 ;; Oct) m=10 ;; Nov) m=11 ;; Dec) m=12 ;;
		*) return ;;
	esac
	stamp="$4-$m-$2 $5"
	server=$(date -u -d "$stamp" +%s 2>/dev/null) || return
	diff=$((server - $(date +%s)))
	[ $diff -lt 0 ] && diff=$((-diff))
	if [ $diff -gt 120 ]; then
		sys date -u -s "$stamp" > /dev/null
		sys hwclock -u -w 2>/dev/null
		log "clock corrected by ${diff}s"
	fi
}

# ------------------------------------------------------------------ schedule
last_slot_epoch() {   # epoch of the latest scheduled time already reached today (0 = none yet)
	now_min=$(minutes "$HHMM")
	best=0
	for t in $FETCH_TIMES; do
		t_min=$(minutes "$t")
		if [ "$now_min" -ge "$t_min" ]; then
			best=$(( EPOCH - (now_min - t_min) * 60 - $(num "$SECS") ))
		fi
	done
	echo "$best"
}

image_ok() {   # is the picture on screen for the right day?
	s="$(state shown_for)"
	[ -n "$s" ] || return 1
	if [ "$(num "$HHMM")" -lt "$(num "$TOMORROW_FROM")" ]; then
		[ "$s" = "$TODAY" ]
	else
		awk -v a="$s" -v b="$TODAY" 'BEGIN { exit !(a > b) }'
	fi
}

new_build() {   # has the server published a newer build than the one on screen? (status.txt only, tiny)
	echo "$EPOCH" > "$RUN/last_check"
	wifi_up || { log "build check skipped: no Wi-Fi"; return 1; }
	if get "$BASE/status.txt" "$RUN/status.txt"; then
		b="$(sed -n 's/^built=//p' "$RUN/status.txt")"
		wifi_down
		[ -n "$b" ] && [ "$b" != "$(state last_built)" ] && { log "new build on server: $b"; return 0; }
		return 1
	fi
	log "build check failed (will look again in $CHECK_MIN min)"
	wifi_down
	return 1
}

due() {
	fails=$(state fails 0)
	if [ "$fails" -gt 0 ]; then
		wait=$RETRY_MIN
		[ "$fails" -ge "$RETRY_FAST_TRIES" ] && wait=$RETRY_SLOW_MIN
		[ $((EPOCH - $(state last_try 0))) -ge $((wait * 60)) ]
		return
	fi
	slot=$(last_slot_epoch)
	[ "$slot" -gt 0 ] && [ "$(state last_ok 0)" -lt "$slot" ] && return 0
	image_ok || return 0
	if [ $((EPOCH - $(state last_check 0))) -ge $((CHECK_MIN * 60)) ]; then
		new_build && return 0
	fi
	return 1
}

fail() {
	f=$(( $(state fails 0) + 1 ))
	echo "$f" > "$RUN/fails"
	echo "$(date '+%a %H:%M') $1" > "$RUN/last_error"
	log "FAIL ($f): $1"
	wifi_down
}

fetch() {
	echo "$EPOCH" > "$RUN/last_try"
	wifi_up || { fail "no Wi-Fi connection"; return 1; }
	set_clock
	now_vars
	get "$BASE/status.txt" "$RUN/status.txt" || { fail "could not download status.txt"; return 1; }
	st_today="$(sed -n 's/^today=//p' "$RUN/status.txt")"
	st_tom="$(sed -n 's/^tomorrow=//p' "$RUN/status.txt")"
	st_built="$(sed -n 's/^built=//p' "$RUN/status.txt")"

	pick=""
	if [ "$(num "$HHMM")" -ge "$(num "$TOMORROW_FROM")" ]; then
		[ "$st_today" = "$TODAY" ] && pick="tomorrow" && cover="$st_tom"
	elif [ "$st_today" = "$TODAY" ]; then
		pick="today" && cover="$st_today"
	elif [ "$st_tom" = "$TODAY" ]; then
		pick="tomorrow" && cover="$st_tom"
	fi
	[ -n "$pick" ] || { fail "no picture for the right day yet (server today=$st_today)"; return 1; }

	get "$BASE/$pick.png" "$RUN/new.png" || { fail "could not download $pick.png"; return 1; }
	[ "$(dd if="$RUN/new.png" bs=1 skip=1 count=3 2>/dev/null)" = "PNG" ] || { fail "$pick.png is not a picture"; return 1; }
	mv "$RUN/new.png" "$RUN/current.png"
	echo "$cover" > "$RUN/shown_for"
	echo "$EPOCH" > "$RUN/last_ok"
	echo "$st_built" > "$RUN/last_built"
	date '+%a %H:%M' > "$RUN/last_ok_text"
	echo 0 > "$RUN/fails"
	log "OK $pick.png for $cover ($METHOD; built $st_built; battery $(battery)%)"
	wifi_down
	WARN_SHOWN="(redraw)"
	return 0
}

# ------------------------------------------------------------------ screen
warning_text() {   # warning lines separated by '|' (each kept under ~44 characters)
	w=""
	if [ "$(state fails 0)" -ge "$RETRY_FAST_TRIES" ]; then
		if [ -f "$RUN/current.png" ] && ! image_ok; then
			w="NOT UPDATED - forecast is for $(state shown_for | cut -c6-)"
		elif [ -f "$RUN/last_ok_text" ]; then
			w="Update failing since $(state last_ok_text) - check Wi-Fi"
		else
			w="No update yet - check Wi-Fi"
		fi
		w="$w|Still stuck? Hold the power button 40 sec"
	fi
	b="$(battery)"
	if [ -n "$b" ] && [ "$b" -lt "$LOW_BATTERY" ] 2>/dev/null; then
		w="$w${w:+|}Battery $b% - please charge"
	fi
	echo "$w"
}

show() {   # full redraw: picture (or a message) plus any warning lines
	w="$(warning_text)"
	if [ -f "$RUN/current.png" ]; then
		sys eips -f -g "$RUN/current.png" > /dev/null 2>&1
	else
		sys eips -c > /dev/null 2>&1
		sys eips 1 3 "Waiting for the first download..." > /dev/null 2>&1
	fi
	if [ -n "$w" ]; then
		row=0
		rest="$w"
		while [ -n "$rest" ]; do
			line="${rest%%|*}"
			[ "$line" = "$rest" ] && rest="" || rest="${rest#*|}"
			sys eips 0 $row "$line" > /dev/null 2>&1
			row=$((row + 1))
		done
		sys eips 0 $row "Tap the screen for the menu." > /dev/null 2>&1
	fi
	WARN_SHOWN="$w"
}

chip_level() {   # light chip's real level; the file reads "FrontLight(Intensity) = 1"
	v="$(cat "$FL_FILE" 2>/dev/null)"
	echo "${v##*= }"
}

chip_off() {   # truly off: on a PW1, powerd level 0 still leaves the LEDs at 1 (a faint glow)
	[ -n "$FL_FILE" ] || return
	if [ -n "$CLOSETDASH_DRY" ] && [ -z "$CLOSETDASH_FL" ]; then
		log "DRY: echo 0 > $FL_FILE"   # PC test without a fake chip file
	else
		echo 0 > "$FL_FILE"
	fi
}

light() {
	n=$(num "$HHMM")
	want=0
	if [ "$n" -ge "$(num "$LIGHT_ON")" ] && [ "$n" -lt "$(num "$LIGHT_OFF")" ]; then
		want=$LIGHT_LEVEL
	fi
	if [ "$want" != "$(state light)" ]; then
		sys lipc-set-prop com.lab126.powerd flIntensity "$want"
		[ "$want" = "0" ] && chip_off
		echo "$want" > "$RUN/light"
		log "front light $want"
	elif [ "$want" = "0" ] && [ -n "$FL_FILE" ] && [ "$(chip_level)" != "0" ]; then
		chip_off   # something brought the LEDs back up: switch them off again
		if [ $((EPOCH - $(state light_fix 0))) -ge 600 ]; then
			echo "$EPOCH" > "$RUN/light_fix"
			log "front light: LEDs had come back on - switched off again"
		fi
	fi
}

# ------------------------------------------------------------------ touch: taps with positions
find_touch() {
	awk '/^N:/ { name = $0 }
	     /^H:/ { if (name ~ /zforce|[Tt]ouch|cyttsp|mxt|[Ss]creen/ && match($0, /event[0-9]+/)) {
	                 print "/dev/input/" substr($0, RSTART, RLENGTH); exit } }' /proc/bus/input/devices 2>/dev/null
}

# hd output (one 16-byte input_event per line) -> "x y" of the first touch position, or "? ?".
# Event layout: time(8) type(2) code(2) value(4), little-endian. ABS_X/Y = 0/1, ABS_MT_POSITION_X/Y = 53/54.
PARSE='
function h(s) { return (index(HX, substr(s, 1, 1)) - 1) * 16 + index(HX, substr(s, 2, 1)) - 1 }
BEGIN { HX = "0123456789abcdef"; x = ""; y = "" }
NF >= 17 {
	type = h($10) + 256 * h($11)
	code = h($12) + 256 * h($13)
	val = h($14) + 256 * h($15) + 65536 * h($16) + 16777216 * h($17)
	if (type == 3 && (code == 0 || code == 53) && x == "") x = val
	if (type == 3 && (code == 1 || code == 54) && y == "") y = val
}
END { if (x != "" && y != "") print x, y; else print "? ?" }'

watch_touch() {   # background: append one line per touch gesture to $TAPS ("rawx rawy" or "? ?")
	exec 3< "$TOUCH" || return
	while :; do
		ev="$(dd bs=1024 count=1 <&3 2>/dev/null | hd)"   # waits for a touch
		if [ -z "$ev" ]; then
			sleep 1
			continue
		fi
		# the rest of the same gesture: keep reading until the screen has been quiet for ~1 s
		# (inner subshell: its "Terminated" notice when timeout stops dd goes to /dev/null)
		while more="$( ( $TMO dd bs=1024 count=1 <&3 | hd ) 2>/dev/null )" && [ -n "$more" ]; do
			ev="$ev
$more"
		done
		xy="$(echo "$ev" | awk "$PARSE")"
		echo "$xy" >> "$TAPS"
		if [ "$xy" = "? ?" ] && [ ! -f "$RUN/dumped" ]; then
			touch "$RUN/dumped"
			log "touch: no position found; first events:"
			echo "$ev" | head -n 12
		fi
	done
}

tap_count() {
	if [ -f "$TAPS" ]; then echo $(( $(wc -l < "$TAPS") )); else echo 0; fi
}

skip_taps() {   # forget taps made before now
	TAPS_SEEN=$(tap_count)
}

next_tap() {   # next_tap SECONDS: wait for a new tap; sets TAP ("rawx rawy"); fails on timeout
	i=0
	while [ $i -lt "$1" ]; do
		if [ "$(tap_count)" -gt "$TAPS_SEEN" ]; then
			TAPS_SEEN=$((TAPS_SEEN + 1))
			TAP="$(sed -n "${TAPS_SEEN}p" "$TAPS")"
			return 0
		fi
		sleep 1
		i=$((i + 1))
	done
	return 1
}

calib_point() {   # screen position of calibration dot N, from img/buttons.txt
	awk -v n="$1" '$1 == "calib" && $2 == n { print $3, $4 }' "$IMG/buttons.txt"
}

map_tap() {   # map_tap RAWX RAWY -> "SX SY" (screen pixels), using touch.conf
	awk -v rx="$1" -v ry="$2" -v ta="$TA" -v a0="$TA0" -v a1="$TA1" -v tb="$TB" -v b0="$TB0" -v b1="$TB1" \
	    -v c="$(calib_point 1) $(calib_point 2) $(calib_point 3)" 'BEGIN {
		split(c, p, " ")
		ra = (ta == "x") ? rx : ry
		rb = (tb == "x") ? rx : ry
		printf "%d %d\n", p[1] + (ra - a0) * (p[3] - p[1]) / (a1 - a0), p[2] + (rb - b0) * (p[6] - p[2]) / (b1 - b0)
	}'
}

hit() {   # hit SCREEN SX SY -> name of the button under that point (or nothing)
	awk -v s="$1" -v x="$2" -v y="$3" \
	    '$1 == s && NF == 6 && x >= $3 && x <= $5 && y >= $4 && y <= $6 { print $2; exit }' "$IMG/buttons.txt"
}

tap_on() {   # tap_on SCREEN: which button was the last tap on?
	[ -n "$TOUCH_OK" ] && [ "$TAP" != "? ?" ] || return
	hit "$1" $(map_tap $TAP)
}

calibrate() {   # tap 3 dots once -> touch.conf (raw touch axes -> screen pixels)
	for n in 1 2 3; do
		sys eips -f -g "$IMG/calib_$n.png" > /dev/null 2>&1
		skip_taps
		next_tap 60 || { log "touch setup: no tap for dot $n (menu off until next Start)"; return 1; }
		[ "$TAP" = "? ?" ] && { log "touch setup: tap had no position (menu off)"; return 1; }
		eval "R$n=\"\$TAP\""
		log "touch setup: dot $n raw $TAP"
	done
	if awk -v r1="$R1" -v r2="$R2" -v r3="$R3" 'BEGIN {
		split(r1, a, " "); split(r2, b, " "); split(r3, c, " ")
		dxx = b[1] - a[1]; if (dxx < 0) dxx = -dxx
		dxy = b[2] - a[2]; if (dxy < 0) dxy = -dxy
		if (dxx >= dxy) { ta = "x"; a0 = a[1]; a1 = b[1]; ca = c[1]; tb = "y"; b0 = a[2]; b1 = c[2] }
		else            { ta = "y"; a0 = a[2]; a1 = b[2]; ca = c[2]; tb = "x"; b0 = a[1]; b1 = c[1] }
		span = a1 - a0; if (span < 0) span = -span
		off = ca - a0;  if (off < 0) off = -off
		if (a1 == a0 || b1 == b0 || off * 3 > span) exit 1
		printf "TA=%s\nTA0=%d\nTA1=%d\nTB=%s\nTB0=%d\nTB1=%d\n", ta, a0, a1, tb, b0, b1 }' > "$TCONF.tmp"; then
		mv "$TCONF.tmp" "$TCONF"
		. "$TCONF"
		log "touch setup saved: $(tr '\n' ' ' < "$TCONF")"
		return 0
	fi
	rm -f "$TCONF.tmp"
	log "touch setup: those taps didn't line up (menu off until next Start)"
	return 1
}

menu() {   # tap -> menu; EXIT needs a second, separate tap on YES (kid-proof)
	sys eips -f -g "$IMG/menu.png" > /dev/null 2>&1
	WARN_SHOWN="(redraw)"
	skip_taps
	next_tap "$MENU_TIMEOUT" || { log "menu: closed by itself"; return; }
	b="$(tap_on menu)"
	log "menu: tap $TAP -> ${b:-no button}"
	case "$b" in
		refresh) FORCE=1 ;;
		info) show_info ;;
		exit)
			sys eips -f -g "$IMG/confirm.png" > /dev/null 2>&1
			skip_taps
			next_tap "$CONFIRM_TIMEOUT" || { log "exit: closed by itself"; return; }
			b="$(tap_on confirm)"
			log "exit: tap $TAP -> ${b:-no button}"
			[ "$b" = "yes" ] && cleanup
			;;
	esac
}

show_info() {   # DEVICE INFO: plain facts to photograph and send to the helper
	sys eips -c > /dev/null 2>&1
	r=2
	for line in "$VERSION" "" \
		"Last good update: $(state last_ok_text "none yet")" \
		"Forecast on screen: $(state shown_for none)" \
		"Wi-Fi: $(lipc-get-prop com.lab126.wifid cmState 2>/dev/null)" \
		"Battery: $(battery)%" \
		"Failed tries in a row: $(state fails 0)" \
		"Last problem: $(state last_error none)" \
		"Kindle clock: $(date '+%a %b %d %H:%M')" "" \
		"$HELP_LINE" "" \
		"Tap anywhere to go back."; do
		sys eips 1 $r "$(echo "$line" | cut -c1-$EIPS_COLS)" > /dev/null 2>&1
		r=$((r + 1))
	done
	skip_taps
	next_tap 60
	log "info screen closed"
}

boot_countdown() {   # after a reboot: any tap during the countdown cancels auto-start
	sys eips -f -g "$IMG/boot.png" > /dev/null 2>&1
	skip_taps
	left=$BOOT_COUNTDOWN
	while [ "$left" -gt 0 ]; do
		sys eips 1 2 "Starting in $left seconds...   " > /dev/null 2>&1
		next_tap 5 && { log "auto-start cancelled by a tap"; cleanup; }
		left=$((left - 5))
	done
	log "auto-start: countdown finished"
}

# ------------------------------------------------------------------ start / stop
cleanup() {
	trap '' TERM INT HUP
	[ -n "$WPID" ] && { kill -9 "$WPID"; wait "$WPID"; } > /dev/null 2>&1
	sys lipc-set-prop com.lab126.powerd preventScreenSaver 0
	sys lipc-set-prop com.lab126.powerd flIntensity "$(state light_before 5)"
	sys lipc-set-prop com.lab126.cmd wirelessEnable 1
	ui_start
	rm -f "$PIDFILE" "$TAPS" "$RUN/dumped" "$RUN/watch.pid" "$RUN/light_before"
	log "stopped - back to normal Kindle"
	exit 0
}

if [ -f "$PIDFILE" ] && kill -0 "$(state dash.pid)" 2>/dev/null; then
	log "already running"
	exit 0
fi
echo $$ > "$PIDFILE"
if [ -f "$RUN/watch.pid" ]; then   # a crashed run's touch reader would double every tap
	kill -9 "$(state watch.pid)" 2> /dev/null && log "stopped a leftover touch reader"
	rm -f "$RUN/watch.pid"
fi
rm -f "$RUN/light" "$RUN/fails" "$TAPS" "$RUN/dumped"
log "=== $VERSION starting${CLOSETDASH_BOOT:+ after reboot} (battery $(battery)%)"
ui_jobs() {
	initctl list 2>/dev/null | grep -e framework -e lab126_gui -e pillow -e kppmainapp -e webreader -e statusbar | tr '\n' ';'
}
log "ui jobs: $(ui_jobs)"
if timeout -t 1 true > /dev/null 2>&1; then TMO="timeout -t 1"; else TMO="timeout 1"; fi   # BusyBox 1.17 vs 1.34
[ -f "$RUN/light_before" ] || lipc-get-prop com.lab126.powerd flIntensity > "$RUN/light_before" 2>/dev/null
# light chip: a PW1 has fl_intensity ("FrontLight(Intensity) = N"); a PW3 has a backlight brightness file (N)
FL_FILE="${CLOSETDASH_FL-$( (find /sys/devices/system -name fl_intensity; ls /sys/class/backlight/*/brightness) 2>/dev/null | head -n 1)}"
log "light chip: ${FL_FILE:-not found (light can only go down to powerd 0)}"

sleep 3   # let KUAL close
ui_stop
log "ui jobs after stop: $(ui_jobs)"
trap cleanup TERM INT
sys lipc-set-prop com.lab126.powerd preventScreenSaver 1

TOUCH="${CLOSETDASH_TOUCH-$(find_touch)}"
if [ -n "$TOUCH" ] && ! which hd > /dev/null 2>&1; then
	log "touch: 'hd' command missing - menu off (exit by restarting the Kindle)"
	TOUCH=""
fi
log "touch device: ${TOUCH:-none found (exit by restarting the Kindle)}"
if [ -n "$TOUCH" ]; then
	watch_touch &
	WPID=$!
	echo "$WPID" > "$RUN/watch.pid"
	[ -f "$TCONF" ] && . "$TCONF" && TOUCH_OK=1
fi

[ -n "$CLOSETDASH_BOOT" ] && boot_countdown
if [ -n "$TOUCH" ] && [ -z "$TOUCH_OK" ]; then
	calibrate && TOUCH_OK=1
fi

sys eips -c > /dev/null 2>&1
sys eips 1 3 "Closet Dash is starting..." > /dev/null 2>&1
sys eips 1 5 "Tap the screen any time for the menu." > /dev/null 2>&1

FORCE=1
while :; do
	now_vars
	light
	if [ "$(tap_count)" -gt "$TAPS_SEEN" ]; then
		skip_taps
		if [ -n "$TOUCH_OK" ]; then
			menu
		else
			log "tap (touch not set up): refresh"
			FORCE=1
		fi
		WARN_SHOWN="(redraw)"
		now_vars
	fi
	if [ -n "$FORCE" ] || due; then
		FORCE=""
		fetch
	fi
	[ "$(warning_text)" != "$WARN_SHOWN" ] && show
	[ -n "$CLOSETDASH_ONCE" ] && cleanup
	sleep $TICK
done
