# Task 002_5：buffer 插入位置选择

## 任务目标

已确定通过插入 buffer 修复当前最大扇出违例。请结合目标网的驱动和负载连接关系，确定新 buffer 应连接的负载分支。

## 输入数据

从以下路径加载初始设计：

`initial_state/design.enc`

当前违例信息：

`inputs/worst_hold_path.json`

根因诊断结果：

`inputs/root_cause.json`

ECO 对象：

`inputs/eco_object.json`

ECO 动作：

`inputs/eco_action.json`

## 任务要求

查询目标网的 driver、sinks 及其连接关系，确定 buffer 插入到目标网的哪一组连接分支，以及哪些 sinks 应改由新 buffer 驱动。本任务只确定插入位置，不执行具体修改，分析结果保存到 `reports/location_analysis.rpt`。

## 结果要求

提交可重放的 Innovus Tcl 脚本：`analyze.tcl`

同时将选择结果保存为：`answer.json`

格式如下：
```json
{
  "target_net": "",
  "target_sinks": []
}
```

## 验证方式

验证器会检查目标网是否为 `done`，并检查所选 sinks 是否为本场景注入的 25 个 `BUF_X2` 负载 pin。
