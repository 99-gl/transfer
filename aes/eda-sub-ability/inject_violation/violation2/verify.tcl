# Usage: innovus -nowin -files verify.tcl
set TASK_DIR [file dirname [file normalize [info script]]]
set REPORT_DIR [file join $TASK_DIR reports]
set INPUT_ENC [file join $TASK_DIR outputs fanout_task0003.enc]
file mkdir $REPORT_DIR

# The checkpoint .enc is an Innovus Tcl entry point and must be sourced.
source $INPUT_ENC

redirect -file [file join $REPORT_DIR check_place.rpt] {
    checkPlace
}
verifyConnectivity -type all -error 1000 -warning 1000 -report [file join $REPORT_DIR connectivity.rpt]
verify_drc -report [file join $REPORT_DIR drc.rpt]
puts "FANOUT_TASK0003_VERIFY_COMPLETE"
exit
