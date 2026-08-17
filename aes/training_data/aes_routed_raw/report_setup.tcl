# Usage (inside the isolated EDA VM):
#   innovus -nowin -files report_setup.tcl
#
# Generates only setup.rpt for the aes_routed_raw checkpoint.

set SCRIPT_DIR [file dirname [file normalize [info script]]]
set CHECKPOINT /home/host/aes_baseline/outputs/aes_routed_raw.enc
set DATABASE /home/host/aes_baseline/outputs/aes_routed_raw.enc.dat
set REPORT_FILE [file join $SCRIPT_DIR setup.rpt]

if {![file exists $CHECKPOINT] || ![file isdirectory $DATABASE]} {
    error "Checkpoint pair not found: $CHECKPOINT and $DATABASE"
}

source $CHECKPOINT

set active_modes [all_constraint_modes -active]
if {$active_modes eq ""} {
    error "No active constraint mode after restoring $CHECKPOINT"
}
set_interactive_constraint_modes $active_modes
set_load 10.0 [all_outputs]
set_max_capacitance 50.0 [current_design]
set_propagated_clock [all_clocks]
set_interactive_constraint_modes {}

redirect -file $REPORT_FILE {
    report_timing -late -max_paths 20 -path_type full_clock
}

exit