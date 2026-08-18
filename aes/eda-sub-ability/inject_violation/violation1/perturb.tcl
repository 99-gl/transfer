set TASK_DIR   [file dirname [file normalize [info script]]]
set INJECT_DIR [file normalize [file join $TASK_DIR ..]]

set REPORT_DIR [file join $TASK_DIR reports]
set OUTPUT_DIR [file join $TASK_DIR outputs]

file mkdir $REPORT_DIR
file mkdir $OUTPUT_DIR

restoreDesign \
    [file join \
        $INJECT_DIR \
        clean_baseline \
        aes_route.enc.dat] \
    aes_cipher_top

setEcoMode \
    -batchMode true \
    -refinePlace false \
    -updateTiming false \
    -honorFixedNetWire false

ecoDeleteRepeater \
    -inst {FE_PHC917_00140}

ecoDeleteRepeater \
    -inst {FE_PHC1249_00140}

setEcoMode -batchMode false

ecoRoute
extractRC

timeDesign \
    -postRoute \
    -outDir [file join $REPORT_DIR setup]

timeDesign \
    -postRoute \
    -hold \
    -outDir [file join $REPORT_DIR hold]

saveDesign \
    [file join $OUTPUT_DIR aes_task1_violated.enc]

puts "TASK1_PERTURBATION_COMPLETE"
exit