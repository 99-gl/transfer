if {![namespace exists ::IMEX]} { namespace eval ::IMEX {} }
set ::IMEX::dataVar [file dirname [file normalize [info script]]]
set ::IMEX::libVar ${::IMEX::dataVar}/libs

create_library_set -name nangate45_typical\
   -timing\
    [list ${::IMEX::libVar}/mmmc/NangateOpenCellLibrary_typical.lib]
create_rc_corner -name nangate45_rc_typical\
   -preRoute_res 1\
   -postRoute_res 1\
   -preRoute_cap 1\
   -postRoute_cap 1\
   -postRoute_xcap 1\
   -preRoute_clkres 0\
   -preRoute_clkcap 0\
   -T 25
create_delay_corner -name nangate45_delay_typical\
   -library_set nangate45_typical\
   -rc_corner nangate45_rc_typical
create_constraint_mode -name functional\
   -sdc_files\
    [list ${::IMEX::dataVar}/mmmc/modes/functional/functional.sdc]
create_analysis_view -name functional_typical -constraint_mode functional -delay_corner nangate45_delay_typical -latency_file ${::IMEX::dataVar}/mmmc/views/functional_typical/latency.sdc
set_analysis_view -setup [list functional_typical] -hold [list functional_typical]
