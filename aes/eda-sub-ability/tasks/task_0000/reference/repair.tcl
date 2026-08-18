# Source step 1: validation_innovus_19_10/remediation/round3/actions/dataset_repair_v1/state_0001/repair.tcl
# Innovus 19.10 legalization: temporarily remove physical-only fillers.
deleteFiller -prefix FILLER
# state_0001 candidate resize__17917__OAI21_X2
# Allowed mutations: ecoChangeCell for resize OR ecoAddRepeater for repeater repair.
setEcoMode -batchMode true -refinePlace true -updateTiming false
ecoChangeCell -inst {_17917_} -cell OAI21_X2
setEcoMode -batchMode false
ecoRoute
extractRC
set repaired [dbGet -p top.insts.name {_17917_}]
if {$repaired eq "" || $repaired eq "0x0" || [dbGet $repaired.cell.name] ne "OAI21_X2"} { error "resize postcondition failed" }

refinePlace
addFiller -cell {FILLCELL_X32 FILLCELL_X16 FILLCELL_X8 FILLCELL_X4 FILLCELL_X2 FILLCELL_X1} -prefix FILLER
ecoRoute
extractRC
