# Usage (inside the isolated EDA VM):
#   innovus -nowin -files /tmp/probe_timing_api.tcl

set ENC /home/host/aes_baseline/outputs/aes_route.enc
source $ENC
set active [all_constraint_modes -active]
set_interactive_constraint_modes $active
set_load 10.0 [all_outputs]
set_max_capacitance 50.0 [current_design]
set_propagated_clock [all_clocks]
set_interactive_constraint_modes {}

foreach spec {"setup max" "hold min"} {
    lassign $spec kind delay_type
    puts "=== $kind ==="
    if {[catch {set paths [get_timing_paths -delay_type $delay_type -max_paths 1]} err]} {
        puts "GET_PATHS_ERROR=$err"
        continue
    }
    puts "PATHS=$paths"
    foreach attr {startpoint beginpoint endpoint slack path_group} {
        if {[catch {set v [get_property $paths $attr]} err]} {
            puts "PROPERTY_$attr=ERROR:$err"
        } else {
            if {$attr eq "slack"} {
                puts "PROPERTY_$attr=$v"
            } elseif {[catch {set names [get_object_name $v]} name_err]} {
                puts "PROPERTY_$attr=OBJECT_ERROR:$name_err"
            } else {
                puts "PROPERTY_$attr=$names"
            }
        }
        if {[catch {set v2 [get_attribute $paths $attr]} err2]} {
            puts "ATTRIBUTE_$attr=ERROR:$err2"
        } else {
            if {$attr eq "slack"} {
                puts "ATTRIBUTE_$attr=$v2"
            } elseif {[catch {set names2 [get_object_name $v2]} name_err2]} {
                puts "ATTRIBUTE_$attr=OBJECT_ERROR:$name_err2"
            } else {
                puts "ATTRIBUTE_$attr=$names2"
            }
        }
    }
}
exit
