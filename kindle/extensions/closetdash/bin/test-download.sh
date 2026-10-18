#!/bin/sh
# Closet Dash - download test. Read-only: changes nothing on the Kindle.
# Tries each way this Kindle might fetch the weather files over HTTPS,
# shows a summary on screen and writes details to test-result.txt
# (in this extension's folder, visible over USB).

BASE="https://pmoto77-bit.github.io/kindle-weather-2"
DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$DIR/test-result.txt"
TMP="/tmp/closetdash-test"
ROW=2
WORKED_NAME=""
WORKED_CMD=""

say() {   # one line on screen and in the log
	eips 1 "$ROW" "$1" >/dev/null 2>&1
	ROW=$((ROW + 1))
	echo "$1" >> "$LOG"
}

log() {
	echo "$1" >> "$LOG"
}

try() {   # try NAME COMMAND... (command takes: <outfile> <url>)
	name="$1"
	shift
	rm -f "$TMP/status.txt"
	log ""
	log "--- $name: $* <file> $BASE/status.txt"
	"$@" "$TMP/status.txt" "$BASE/status.txt" >> "$LOG" 2>&1
	rc=$?
	if grep -q '^today=' "$TMP/status.txt" 2>/dev/null; then
		say "OK    $name"
		if [ -z "$WORKED_CMD" ]; then
			WORKED_NAME="$name"
			WORKED_CMD="$*"
			cp "$TMP/status.txt" "$TMP/status-ok.txt"
		fi
	else
		say "FAIL  $name (code $rc)"
	fi
}

mkdir -p "$TMP"
: > "$LOG"
sleep 3   # let KUAL close before drawing
eips -c >/dev/null 2>&1

say "CLOSET DASH - DOWNLOAD TEST"
say "Kindle clock: $(date '+%Y-%m-%d %H:%M')"
log "firmware: $(cat /etc/prettyversion.txt 2>/dev/null)"
log "uname: $(uname -a 2>&1)"

wifi="$(lipc-get-prop com.lab126.wifid cmState 2>/dev/null)"
say "Wi-Fi: ${wifi:-unknown}"
[ "$wifi" = "CONNECTED" ] || say "(Wi-Fi off? Turn it on and retry.)"

log "curl: $(curl --version 2>&1 | head -1)"
log "wget: $(wget --help 2>&1 | head -1)"
log "openssl: $(openssl version 2>&1)"
log "battery: $(lipc-get-prop com.lab126.powerd battLevel 2>&1)"
log "frontlight: $(lipc-get-prop com.lab126.powerd flIntensity 2>&1)"
log "preventScreenSaver: $(lipc-get-prop com.lab126.powerd preventScreenSaver 2>&1)"

say ""
try "curl + bundled certs" curl --cacert "$DIR/cacert.pem" -sS --max-time 30 -o
try "curl"     curl -sS --max-time 30 -o
try "curl -k"  curl -k -sS --max-time 30 -o
try "wget"     wget -q -T 30 -O
try "wget -k"  wget --no-check-certificate -q -T 30 -O
say ""

if [ -n "$WORKED_CMD" ]; then
	log ""
	log "status.txt as downloaded:"
	cat "$TMP/status-ok.txt" >> "$LOG" 2>/dev/null
	$WORKED_CMD "$TMP/today.png" "$BASE/today.png" >> "$LOG" 2>&1
	log "today.png: $(ls -l "$TMP/today.png" 2>&1)"
	say "Best method: $WORKED_NAME"
	say "Showing today.png in 10 seconds."
	say "Then press Home to go back."
	sleep 10
	if eips -f -g "$TMP/today.png" >/dev/null 2>&1; then
		log "image shown: yes"
	else
		log "image shown: FAILED"
		say "Could not show the image."
	fi
else
	say "No method worked."
	say "Plug in USB and send Claude:"
	say "extensions/closetdash/test-result.txt"
	say "Press Home to go back."
fi
log ""
log "done: $(date '+%Y-%m-%d %H:%M:%S')"
