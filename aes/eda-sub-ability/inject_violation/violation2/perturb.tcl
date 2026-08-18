# Usage: innovus -nowin -files perturb.tcl
# Inject the task_0003-style max-fanout violation into the isolated AES design.
set TASK_DIR [file dirname [file normalize [info script]]]
set OUTPUT_DIR [file join $TASK_DIR outputs]
set REPORT_DIR [file join $TASK_DIR reports]
set SCENARIO fanout_task0003
set target_net_name {done}
set load_count 25

file mkdir $OUTPUT_DIR
file mkdir $REPORT_DIR

# The baseline .enc is an Innovus Tcl entry point and must be sourced.
source /home/host/aes_baseline/outputs/aes_route.enc

set target_net {}
foreach candidate [dbGet top.nets] {
    if {[dbGet $candidate.name] eq $target_net_name} {
        set target_net $candidate
        break
    }
}
if {$target_net eq "" || $target_net eq "0x0"} {
    error "Missing target net $target_net_name"
}
set drivers [dbGet $target_net.instTerms.isOutput 1 -p]
if {$drivers eq "" || $drivers eq "0x0"} {
    error "Target net $target_net_name has no instance driver"
}

# Legal empty row sites from the baseline floorplan.
set load_locations {
    {32.30 164.08} {34.20 164.08} {36.10 164.08}
    {38.00 164.08} {39.90 164.08} {41.80 164.08}
    {43.70 164.08} {45.60 164.08} {47.50 164.08}
    {53.20 164.08} {55.10 164.08} {57.00 164.08}
    {58.90 164.08} {60.80 164.08} {62.70 164.08}
    {64.60 164.08} {66.50 164.08}
    {32.30 162.68} {34.20 162.68} {36.10 162.68}
    {38.00 162.68} {39.90 162.68} {41.80 162.68}
    {43.70 162.68} {45.60 162.68}
}
if {[llength $load_locations] != $load_count} {
    error "Load site list does not match load count"
}

set added_loads {}
for {set index 0} {$index < $load_count} {incr index} {
    set load_pt [lindex $load_locations $index]
    set load_name [format {AES_FANOUT_T0003_LOAD_%02d} $index]
    addInst -cell BUF_X2 -inst $load_name -loc $load_pt -ori R0 -status placed
    attachTerm $load_name A $target_net_name
    lappend added_loads $load_name
}
catch {editDelete -net $target_net_name}
ecoRoute
extractRC

set fanout_report [file join $REPORT_DIR ${SCENARIO}.fanout.rpt]
redirect -file $fanout_report {reportFanoutViolation}
set report_handle [open $fanout_report r]
set report_data [read $report_handle]
close $report_handle
if {![regexp -nocase {there (is|are) [1-9][0-9]* max[_ ]fanout(?: load)? violations?} $report_data]} {
    error "Expected max-fanout violation was not created"
}
foreach load_name $added_loads {
    set load_inst [dbGet -p top.insts.name $load_name]
    if {$load_inst eq "" || $load_inst eq "0x0" || [dbGet $load_inst.cell.name] ne "BUF_X2"} {
        error "Load postcondition failed for $load_name"
    }
}
redirect -file [file join $REPORT_DIR ${SCENARIO}.check.rpt] {checkDesign -all}
saveDesign [file join $OUTPUT_DIR ${SCENARIO}.enc]
if {![file exists [file join $OUTPUT_DIR ${SCENARIO}.enc]] || ![file isdirectory [file join $OUTPUT_DIR ${SCENARIO}.enc.dat]]} {
    error "Checkpoint pair was not created for $SCENARIO"
}
puts "${SCENARIO}_PERTURBATION_COMPLETE"
exit
