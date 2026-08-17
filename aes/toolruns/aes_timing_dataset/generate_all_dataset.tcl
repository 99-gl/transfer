# Usage (inside the isolated EDA VM):
#   innovus -nowin -files /tmp/generate_all_dataset.tcl
#
# Generates timing reports and structured golden/task JSON files for every
# checkpoint in /home/host/aes_baseline/outputs.

set ROOT /home/host/aes_baseline
set OUT_ROOT /tmp/aes_timing_dataset
set OUTPUTS [file join $ROOT outputs]
file mkdir $OUT_ROOT

proc json_clean {value} {
    set value [string map [list "\\" "\\\\" "\"" "'" "\n" " " "\r" " "] $value]
    return $value
}

proc count_objects {objects} {
    if {$objects eq "0x0" || $objects eq ""} { return 0 }
    return [llength $objects]
}

proc write_failure_json {path checkpoint stage analysis error_message} {
    set fh [open $path w]
    set msg [json_clean $error_message]
    puts $fh "{\"checkpoint\":\"$checkpoint\",\"stage\":\"$stage\",\"analysis\":\"$analysis\",\"status\":\"unavailable\",\"error\":\"$msg\"}"
    close $fh
}

proc report_beginpoint {path fallback} {
    if {![file exists $path]} { return $fallback }
    set fh [open $path r]
    set result $fallback
    while {[gets $fh line] >= 0} {
        if {[regexp {^Beginpoint:\s+([^ ]+)} $line -> value]} {
            set result $value
            break
        }
    }
    close $fh
    return $result
}

set manifest_path [file join $OUT_ROOT manifest.jsonl]
set manifest [open $manifest_path w]
set checkpoints [lsort [glob -nocomplain -directory $OUTPUTS *.enc]]

foreach enc $checkpoints {
    set stage [file rootname [file tail $enc]]
    set stage_dir [file join $OUT_ROOT $stage]
    file mkdir $stage_dir
    set db [file join $OUTPUTS "${stage}.enc.dat"]
    set checkpoint_name [file tail $enc]

    if {![file isdirectory $db]} {
        set msg "missing paired database directory $db"
        foreach analysis {setup hold} {
            write_failure_json [file join $stage_dir "${analysis}.golden.json"] $checkpoint_name $stage $analysis $msg
        }
        puts $manifest "{\"checkpoint\":\"$checkpoint_name\",\"stage\":\"$stage\",\"status\":\"unavailable\",\"error\":\"[json_clean $msg]\"}"
        continue
    }

    set restore_error ""
    if {[catch {source $enc} restore_error]} {
        set msg "restore failed: $restore_error"
        foreach analysis {setup hold} {
            write_failure_json [file join $stage_dir "${analysis}.golden.json"] $checkpoint_name $stage $analysis $msg
        }
        puts $manifest "{\"checkpoint\":\"$checkpoint_name\",\"stage\":\"$stage\",\"status\":\"unavailable\",\"error\":\"[json_clean $msg]\"}"
        continue
    }

    set active_modes [all_constraint_modes -active]
    if {$active_modes eq ""} {
        set msg "no active constraint mode after restore"
        foreach analysis {setup hold} {
            write_failure_json [file join $stage_dir "${analysis}.golden.json"] $checkpoint_name $stage $analysis $msg
        }
        puts $manifest "{\"checkpoint\":\"$checkpoint_name\",\"stage\":\"$stage\",\"status\":\"unavailable\",\"error\":\"$msg\"}"
        continue
    }

    set constraint_error ""
    if {[catch {
        set_interactive_constraint_modes $active_modes
        set_load 10.0 [all_outputs]
        set_max_capacitance 50.0 [current_design]
        set_propagated_clock [all_clocks]
        set_interactive_constraint_modes {}
    } constraint_error]} {
        set msg "constraint setup failed: $constraint_error"
        foreach analysis {setup hold} {
            write_failure_json [file join $stage_dir "${analysis}.golden.json"] $checkpoint_name $stage $analysis $msg
        }
        puts $manifest "{\"checkpoint\":\"$checkpoint_name\",\"stage\":\"$stage\",\"status\":\"unavailable\",\"error\":\"[json_clean $msg]\"}"
        continue
    }

    set stage_status "available"
    foreach spec {"setup max late" "hold min early"} {
        lassign $spec analysis delay_type report_switch
        set report_path [file join $stage_dir "${analysis}.rpt"]
        set golden_path [file join $stage_dir "${analysis}.golden.json"]
        set task_path [file join $stage_dir "${analysis}.task.json"]
        set report_error ""

        if {[catch {redirect -file $report_path "report_timing -$report_switch -max_paths 20 -path_type full_clock"} report_error]} {
            set stage_status "partial"
        }

        set path_error ""
        if {[catch {set paths [get_timing_paths -delay_type $delay_type -max_paths 1]} path_error]} {
            write_failure_json $golden_path $checkpoint_name $stage $analysis "timing path query failed: $path_error"
            set stage_status "partial"
            continue
        }

        if {$paths eq "0x0" || $paths eq ""} {
            write_failure_json $golden_path $checkpoint_name $stage $analysis "no timing path returned"
            set stage_status "partial"
            continue
        }

        set start_obj [get_property $paths startpoint]
        set end_obj [get_property $paths endpoint]
        set group_obj [get_property $paths path_group]
        set sta_startpoint [json_clean [get_object_name $start_obj]]
        set startpoint [json_clean [report_beginpoint $report_path $sta_startpoint]]
        set endpoint [json_clean [get_object_name $end_obj]]
        set path_group [json_clean [get_object_name $group_obj]]
        set slack [get_property $paths slack]

        set fh [open $golden_path w]
        puts $fh "{\"checkpoint\":\"$checkpoint_name\",\"stage\":\"$stage\",\"analysis\":\"$analysis\",\"status\":\"ok\",\"startpoint\":\"$startpoint\",\"sta_startpoint_pin\":\"$sta_startpoint\",\"endpoint\":\"$endpoint\",\"slack_ns\":$slack,\"path_group\":\"$path_group\"}"
        close $fh

        set q [expr {$analysis eq "setup" ? "setup" : "hold"}]
        set fh [open $task_path w]
        puts $fh "{\"task_id\":\"${stage}_${analysis}_worst_path\",\"checkpoint\":\"$checkpoint_name\",\"stage\":\"$stage\",\"analysis\":\"$analysis\",\"report\":\"${analysis}.rpt\",\"question\":\"Find the worst $q path startpoint, endpoint, slack, and path group.\",\"golden\":{\"startpoint\":\"$startpoint\",\"endpoint\":\"$endpoint\",\"slack_ns\":$slack,\"path_group\":\"$path_group\"}}"
        close $fh

        puts $manifest "{\"task_id\":\"${stage}_${analysis}_worst_path\",\"checkpoint\":\"$checkpoint_name\",\"stage\":\"$stage\",\"analysis\":\"$analysis\",\"status\":\"ok\"}"
    }

    puts "DATASET_STAGE $stage STATUS $stage_status"
}

close $manifest
exit
