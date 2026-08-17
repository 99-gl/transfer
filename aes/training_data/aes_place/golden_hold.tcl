# Usage (inside the isolated EDA VM):
#   innovus -nowin -files golden_hold.tcl
#
# Generates only hold.golden.json for the aes_place checkpoint.
# Run report_hold.tcl first so the report Beginpoint is available.

set SCRIPT_DIR [file dirname [file normalize [info script]]]
set CHECKPOINT /home/host/aes_baseline/outputs/aes_place.enc
set DATABASE /home/host/aes_baseline/outputs/aes_place.enc.dat
set REPORT_FILE [file join $SCRIPT_DIR hold.rpt]
set GOLDEN_FILE [file join $SCRIPT_DIR hold.golden.json]

if {![file exists $CHECKPOINT] || ![file isdirectory $DATABASE]} {
    error "Checkpoint pair not found: $CHECKPOINT and $DATABASE"
}
if {![file exists $REPORT_FILE]} {
    error "Missing $REPORT_FILE. Run report_hold.tcl first."
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

set paths [get_timing_paths -delay_type min -max_paths 1]
if {$paths eq "0x0" || $paths eq ""} {
    error "No hold timing path returned for $CHECKPOINT"
}

set sta_startpoint [get_object_name [get_property $paths startpoint]]
set endpoint [get_object_name [get_property $paths endpoint]]
set path_group [get_object_name [get_property $paths path_group]]
set slack [get_property $paths slack]

# Innovus startpoint is the launch clock pin. The report Beginpoint is the
# data-path startpoint expected by this timing-report understanding task.
set startpoint $sta_startpoint
set fh [open $REPORT_FILE r]
while {[gets $fh line] >= 0} {
    if {[regexp {^Beginpoint:\s+([^ ]+)} $line -> value]} {
        set startpoint $value
        break
    }
}
close $fh

set fh [open $GOLDEN_FILE w]
puts $fh "{\"checkpoint\":\"aes_place.enc\",\"stage\":\"aes_place\",\"analysis\":\"hold\",\"status\":\"ok\",\"startpoint\":\"$startpoint\",\"sta_startpoint_pin\":\"$sta_startpoint\",\"endpoint\":\"$endpoint\",\"slack_ns\":$slack,\"path_group\":\"$path_group\"}"
close $fh

exit