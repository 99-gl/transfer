# Usage (inside the isolated EDA VM):
#   innovus -nowin -files /data2/glwu/aes_timing_audit/generate_route_report.tcl

set ENC /home/host/aes_baseline/outputs/aes_route.enc
set DB [file join [file dirname $ENC] aes_route.enc.dat]
if {[file exists /data2/glwu/aes_timing_audit]} {
    set OUT /data2/glwu/aes_timing_audit/reports
} else {
    set OUT /tmp/aes_timing_audit/reports
}
file mkdir $OUT

if {![file exists $ENC] || ![file exists $DB]} {
    error "Checkpoint pair not found: $ENC and $DB"
}
source $ENC

# Restore the same interactive constraint setup used by the route flow.
set ACTIVE_CONSTRAINT_MODES [all_constraint_modes -active]
if {$ACTIVE_CONSTRAINT_MODES eq ""} {
    error "No active constraint mode found"
}
set_interactive_constraint_modes $ACTIVE_CONSTRAINT_MODES
set_load 10.0 [all_outputs]
set_max_capacitance 50.0 [current_design]
set_propagated_clock [all_clocks]
set_interactive_constraint_modes {}

redirect -file [file join $OUT setup.rpt] {
    report_timing -late -max_paths 20 -path_type full_clock
}

redirect -file [file join $OUT hold.rpt] {
    report_timing -early -max_paths 20 -path_type full_clock
}

redirect -file [file join $OUT summary.rpt] {
    puts "CHECKPOINT = $DB"
    puts "CONSTRAINT_MODES = $ACTIVE_CONSTRAINT_MODES"
    report_timing -late -max_paths 1
    report_timing -early -max_paths 1
}

exit
