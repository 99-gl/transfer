if {![namespace exists ::IMEX]} { namespace eval ::IMEX {} }
set ::IMEX::dataVar [file dirname [file normalize [info script]]]
set ::IMEX::libVar ${::IMEX::dataVar}/libs

create_library_set -name LIBSET_TYP\
   -timing\
    [list ${::IMEX::libVar}/mmmc/NangateOpenCellLibrary_typical.lib]
create_rc_corner -name RC_TYP\
   -cap_table ${::IMEX::libVar}/mmmc/NangateOpenCellLibrary.captable\
   -preRoute_res 1\
   -postRoute_res 1\
   -preRoute_cap 1\
   -postRoute_cap 1\
   -postRoute_xcap 1\
   -preRoute_clkres 0\
   -preRoute_clkcap 0\
   -T 25
create_delay_corner -name DELAY_TYP\
   -library_set LIBSET_TYP\
   -rc_corner RC_TYP
create_constraint_mode -name FUNC\
   -sdc_files\
    [list ${::IMEX::dataVar}/mmmc/modes/FUNC/FUNC.sdc]
create_analysis_view -name VIEW_TYP -constraint_mode FUNC -delay_corner DELAY_TYP -latency_file ${::IMEX::dataVar}/mmmc/views/VIEW_TYP/latency.sdc
set_analysis_view -setup [list VIEW_TYP] -hold [list VIEW_TYP]
