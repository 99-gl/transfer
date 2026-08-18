# Usage (guest): innovus -nowin -files placement_overlap.tcl
# Creates a deliberate standard-cell placement overlap in an isolated AES checkpoint.
set scenario placement_overlap
set output_dir /home/host/injection_delivery
file mkdir $output_dir
source /home/host/aes_baseline/outputs/aes_route.enc

# FE_PHC1771_text_in_0 is a placed BUF_X1. The target is the occupied location
# of another placed BUF_X1, FE_PHC1772_00144, so the overlap is deterministic.
placeInstance FE_PHC1771_text_in_0 32.11 19.88 R0
extractRC
catch {redirect -file [file join $output_dir ${scenario}.place.rpt] {checkPlace}} place_error
catch {redirect -file [file join $output_dir ${scenario}.check.rpt] {checkDesign -all}} check_error
set save_path [file join $output_dir ${scenario}.enc]
saveDesign $save_path
if {![file exists $save_path] || ![file isdirectory ${save_path}.dat]} {
    error "Checkpoint pair was not created for $scenario"
}
exit
