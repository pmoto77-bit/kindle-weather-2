Closet Dash troubleshooting tools (for the helper, not for daily use)

These are kept out of the Kindle library so the only item there is "Start Weather".
To use one: connect the Kindle by USB, copy the file into the Kindle's "documents"
folder, eject, and tap it in the library. Delete it from "documents" when done.

  ClosetDash_Device_Check.sh      read-only; writes device-check.txt and test-result.txt
  ClosetDash_Test_Download.sh     read-only; writes test-result.txt
  ClosetDash_Light_Test.sh        one-minute light test; writes light-test-result.txt
  ClosetDash_AutoStart_ON.sh      start by itself after every restart (already on)
  ClosetDash_AutoStart_OFF.sh     stop starting by itself after a restart
  ClosetDash_Redo_Touch_Setup.sh  forget the touch setup; next start shows the 3 dots
  ClosetDash_Stop.sh              stop the display (same as menu > EXIT TO KINDLE)

All results are written to extensions/closetdash/. The running log is dash-log.txt.
