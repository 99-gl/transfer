set TASK_DIR \
    [file dirname [file normalize [info script]]]

set REPORT_DIR \
    [file join $TASK_DIR reports]

set INPUT_DB \
    [file join \
        $TASK_DIR \
        outputs \
        aes_task1_violated.enc.dat]

file mkdir $REPORT_DIR

# 恢复注入违例后的 checkpoint
restoreDesign \
    $INPUT_DB \
    aes_cipher_top

# Placement 检查
redirect -file \
    [file join $REPORT_DIR check_place.rpt] {
        checkPlace
    }

# Connectivity 检查
verifyConnectivity \
    -type all \
    -error 1000 \
    -warning 1000 \
    -report \
    [file join $REPORT_DIR connectivity.rpt]

# DRC 检查
verify_drc \
    -report \
    [file join $REPORT_DIR drc.rpt]

puts "TASK1_VERIFY_COMPLETE"
exit