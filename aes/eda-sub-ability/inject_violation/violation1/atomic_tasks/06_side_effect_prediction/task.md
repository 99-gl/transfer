# Task 001_6：ECO 副作用预测

## 任务目标

根据已经确定的 buffer ECO 方案，预测该修改对 Hold、其他 Setup 路径、面积、功耗和拥塞的影响。

## 输入数据

从以下路径加载初始设计：
`initial_state/design.enc`

该 checkpoint 是自包含的，其中包括 MMMC 时序配置和物理设计数据。

最差 Hold 路径信息：
`inputs/worst_hold_path.json`

准备执行的 ECO 方案：
`inputs/eco_plan.json`

## 任务要求

编写 Innovus Tcl 脚本，获取当前设计的 Setup、Hold、面积、功耗和拥塞信息，并将结果保存到：
`reports/baseline_analysis.rpt`

根据当前设计和 ECO 方案，预测修改后各项指标的变化方向。本次只进行副作用预测，不执行具体修改。

## 提交要求

提交可重放的 Innovus Tcl 脚本：
`analyze.tcl`

同时将预测结果保存为：
`answer.json`

格式如下：

```json
{
  "hold_timing": "",
  "setup_timing": "",
  "area": "",
  "power": "",
  "congestion": ""
}
```

Timing 字段填写 `improve`、`degrade` 或 `unchanged`；其余字段填写 `increase`、`decrease` 或 `unchanged`。

## 验证方式

验证器会在初始设计上执行 `inputs/eco_plan.json` 中的修改，然后比较修改前后的全局时序、面积、功耗和拥塞结果，判断预测是否正确。