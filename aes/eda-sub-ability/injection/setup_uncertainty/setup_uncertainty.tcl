# Usage (guest): innovus -nowin -files setup_uncertainty.tcl
# Injects a setup timing violation into an isolated copy of the AES route checkpoint.
set scenario setup_uncertainty
set output_dir /home/host/injection_delivery
file mkdir $output_dir
source /home/host/aes_baseline/outputs/aes_route.enc

set active_modes [all_constraint_modes -active]
if {$active_modes eq ""} { error "No active constraint mode after restoring baseline" }
set_interactive_constraint_modes $active_modes
set_clock_uncertainty -setup 0.500 [all_clocks]
set_interactive_constraint_modes {}
extractRC
timeDesign -postRoute -outDir [file join $output_dir ${scenario}_timing]
redirect -file [file join $output_dir ${scenario}.timing.rpt] {
    report_timing -late -max_paths 10 -path_type full_clock
}
catch {redirect -file [file join $output_dir ${scenario}.check.rpt] {checkDesign -all}} check_error
set worst [get_timing_paths -delay_type max -max_paths 1]
if {$worst eq "" || $worst eq "0x0" || [get_property $worst slack] >= 0.0} {
    error "Expected setup violation was not created"
}
set save_path [file join $output_dir ${scenario}.enc]
saveDesign $save_path
if {![file exists $save_path] || ![file isdirectory ${save_path}.dat]} {
    error "Checkpoint pair was not created for $scenario"
}
exit
