# Usage:
#   pwsh -File scaffold_task_tcls.ps1
#
# Creates one report Tcl and one golden Tcl for each setup/hold task in
# ../training_data/<checkpoint-stage>/. Run this script from any directory.

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $PSCommandPath
$aesDir = Split-Path -Parent (Split-Path -Parent $scriptDir)
$trainingData = Join-Path $aesDir 'training_data'
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)

$reportTemplate = @'
# Usage (inside the isolated EDA VM):
#   innovus -nowin -files report___ANALYSIS__.tcl
#
# Generates only __ANALYSIS__.rpt for the __STAGE__ checkpoint.

set SCRIPT_DIR [file dirname [file normalize [info script]]]
set CHECKPOINT /home/host/aes_baseline/outputs/__STAGE__.enc
set DATABASE /home/host/aes_baseline/outputs/__STAGE__.enc.dat
set REPORT_FILE [file join $SCRIPT_DIR __ANALYSIS__.rpt]

if {![file exists $CHECKPOINT] || ![file isdirectory $DATABASE]} {
    error "Checkpoint pair not found: $CHECKPOINT and $DATABASE"
}

source $CHECKPOINT

set active_modes [all_constraint_modes -active]
if {$active_modes eq ""} {
    error "No active constraint mode after restoring $CHECKPOINT"
}
set_interactive_constraint_modes $active_modes
set_load 10.0 [all_outputs]
set_max_capacitance 50.0 [current_design]
set_propagated_clock [all_clocks]
set_interactive_constraint_modes {}

redirect -file $REPORT_FILE {
    report_timing -__REPORT_SWITCH__ -max_paths 20 -path_type full_clock
}

exit
'@

$goldenTemplate = @'
# Usage (inside the isolated EDA VM):
#   innovus -nowin -files golden___ANALYSIS__.tcl
#
# Generates only __ANALYSIS__.golden.json for the __STAGE__ checkpoint.
# Run report___ANALYSIS__.tcl first so the report Beginpoint is available.

set SCRIPT_DIR [file dirname [file normalize [info script]]]
set CHECKPOINT /home/host/aes_baseline/outputs/__STAGE__.enc
set DATABASE /home/host/aes_baseline/outputs/__STAGE__.enc.dat
set REPORT_FILE [file join $SCRIPT_DIR __ANALYSIS__.rpt]
set GOLDEN_FILE [file join $SCRIPT_DIR __ANALYSIS__.golden.json]

if {![file exists $CHECKPOINT] || ![file isdirectory $DATABASE]} {
    error "Checkpoint pair not found: $CHECKPOINT and $DATABASE"
}
if {![file exists $REPORT_FILE]} {
    error "Missing $REPORT_FILE. Run report___ANALYSIS__.tcl first."
}

source $CHECKPOINT

set active_modes [all_constraint_modes -active]
if {$active_modes eq ""} {
    error "No active constraint mode after restoring $CHECKPOINT"
}
set_interactive_constraint_modes $active_modes
set_load 10.0 [all_outputs]
set_max_capacitance 50.0 [current_design]
set_propagated_clock [all_clocks]
set_interactive_constraint_modes {}

set paths [get_timing_paths -delay_type __DELAY_TYPE__ -max_paths 1]
if {$paths eq "0x0" || $paths eq ""} {
    error "No __ANALYSIS__ timing path returned for $CHECKPOINT"
}

set sta_startpoint [get_object_name [get_property $paths startpoint]]
set endpoint [get_object_name [get_property $paths endpoint]]
set path_group [get_object_name [get_property $paths path_group]]
set slack [get_property $paths slack]

# Innovus startpoint is the launch clock pin. The report Beginpoint is the
# data-path startpoint expected by this timing-report understanding task.
set startpoint $sta_startpoint
set fh [open $REPORT_FILE r]
while {[gets $fh line] >= 0} {
    if {[regexp {^Beginpoint:\s+([^ ]+)} $line -> value]} {
        set startpoint $value
        break
    }
}
close $fh

set fh [open $GOLDEN_FILE w]
puts $fh "{\"checkpoint\":\"__STAGE__.enc\",\"stage\":\"__STAGE__\",\"analysis\":\"__ANALYSIS__\",\"status\":\"ok\",\"startpoint\":\"$startpoint\",\"sta_startpoint_pin\":\"$sta_startpoint\",\"endpoint\":\"$endpoint\",\"slack_ns\":$slack,\"path_group\":\"$path_group\"}"
close $fh

exit
'@

$analyses = @(
    @{ Name = 'setup'; ReportSwitch = 'late'; DelayType = 'max' },
    @{ Name = 'hold'; ReportSwitch = 'early'; DelayType = 'min' }
)

Get-ChildItem -Directory $trainingData | ForEach-Object {
    $stage = $_.Name
    foreach ($analysis in $analyses) {
        $reportText = $reportTemplate.Replace('__STAGE__', $stage).Replace('__ANALYSIS__', $analysis.Name).Replace('__REPORT_SWITCH__', $analysis.ReportSwitch)
        $goldenText = $goldenTemplate.Replace('__STAGE__', $stage).Replace('__ANALYSIS__', $analysis.Name).Replace('__DELAY_TYPE__', $analysis.DelayType)

        [System.IO.File]::WriteAllText((Join-Path $_.FullName "report_$($analysis.Name).tcl"), $reportText, $utf8NoBom)
        [System.IO.File]::WriteAllText((Join-Path $_.FullName "golden_$($analysis.Name).tcl"), $goldenText, $utf8NoBom)
    }
}
