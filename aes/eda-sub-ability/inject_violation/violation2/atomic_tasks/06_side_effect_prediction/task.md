# Task 002_6：ECO 副作用预测

## 任务目标

根据已确定的 buffer ECO 方案，预测该修改对 Hold、Setup、面积、功耗和拥塞的影响方向。

## 输入数据

从以下路径加载初始设计：

`initial_state/design.enc`

当前违例信息：

`inputs/worst_hold_path.json`

准备执行的 ECO 方案：

`inputs/eco_plan.json`

## 任务要求

获取当前设计的 Setup、Hold、面积、功耗和拥塞信息，并根据当前设计和 ECO 方案预测修改后各项指标的变化方向。本任务只进行副作用预测，不执行具体修改。

## 结果要求

提交可重放的 Innovus Tcl 脚本：`analyze.tcl`

同时将预测结果保存为：`answer.json`

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

其中 timing 字段填写 `improve`、`degrade` 或 `unchanged`；其余字段填写 `increase`、`decrease` 或 `unchanged`。

## 验证方式

验证器会根据 `inputs/eco_plan.json` 中的动作及隔离 Innovus 核实结果检查副作用预测结果。
