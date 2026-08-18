# Task 001_3：ECO 对象选择

## 任务目标

结合已确认的最差 Hold 路径和根因诊断结果，从该路径中选择一个最适合后续局部 ECO 的 instance 或 net。

## 输入数据

从以下路径加载初始设计：
`initial_state/design.enc`

该 checkpoint 是自包含的，其中包括 MMMC 时序配置和物理设计数据。

已确认的最差 Hold 目标路径：
`inputs/worst_hold_path.json`

已确认的根因诊断结果：
`inputs/root_cause.json`

## 任务要求

编写 Innovus Tcl 脚本，查询目标路径上的 instance、net、pin 及其连接关系，并将结果保存到：
`reports/object_analysis.rpt`

根据查询结果，从目标路径中选择一个最优的进行 ECO 的对象，使后续修改能够最大幅度改善最差 Hold slack，并尽量减少对其他路径的影响。

本次只选择 ECO 对象，不执行具体修改。分析过程中不得修改设计或时序约束。

## 提交要求

提交可重放的 Innovus Tcl 脚本：
`analyze.tcl`

同时将最终选择结果保存为：
`answer.json`

格式如下：

```json
{
  "object_type": "",
  "object_name": ""
}
```

其中 `object_type` 只能填写 `instance` 或 `net`，只提交一个对象。

## 验证方式

验证器会检查所选对象是否真实存在、是否位于目标 Hold 数据路径，并判断选择结果是否正确。