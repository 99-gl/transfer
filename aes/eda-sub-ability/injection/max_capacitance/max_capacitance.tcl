# Usage (guest): innovus -nowin -files max_capacitance.tcl
# Injects a max-capacitance electrical violation into an isolated AES checkpoint.
set scenario max_capacitance
set output_dir /home/host/injection_delivery
file mkdir $output_dir
source /home/host/aes_baseline/outputs/aes_route.enc

set active_modes [all_constraint_modes -active]
if {$active_modes eq ""} { error "No active constraint mode after restoring baseline" }
set_interactive_constraint_modes $active_modes
set_max_capacitance 0.001 [current_design]
set_interactive_constraint_modes {}
extractRC
timeDesign -postRoute -outDir [file join $output_dir ${scenario}_timing]
catch {redirect -file [file join $output_dir ${scenario}.constraint.rpt] {report_constraint -all_violators}} constraint_error
catch {redirect -file [file join $output_dir ${scenario}.check.rpt] {checkDesign -all}} check_error
set save_path [file join $output_dir ${scenario}.enc]
saveDesign $save_path
if {![file exists $save_path] || ![file isdirectory ${save_path}.dat]} {
    error "Checkpoint pair was not created for $scenario"
}
exit
