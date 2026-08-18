# Task 001_5：buffer 插入位置选择

## 任务目标

已确定通过插入 buffer 修复当前 Hold 违例。请结合目标路径和所选 net 的连接关系，确定 buffer 的插入位置，以及需要连接到新 net 的 sinks。

## 输入数据

从以下路径加载初始设计：

`initial_state/design.enc`

该 checkpoint 是自包含的，其中包括 MMMC 时序配置和物理设计数据。

最差 Hold 路径信息：
`inputs/worst_hold_path.json`

需要进行 ECO 的对象：
`inputs/selected_object.json`

针对该对象采用的 ECO 动作：
`inputs/eco_action.json`

## 任务要求

编写 Innovus Tcl 脚本，查询目标 net 的 driver、sinks 及其连接关系，并将结果保存到：
`reports/location_analysis.rpt`

根据查询结果，确定 buffer 应插入到目标 net 的哪条连接分支，以及哪些 sinks 应改由新 buffer 驱动。选择插入位置时，应优先改善目标 Hold slack，并避免引入新的 transition 或 capacitance 违例。

在 `answer.json` 中使用目标 net 和 sinks 表示插入位置，不需要提交物理坐标。本次只确定插入位置，不执行具体修改。

## 提交要求

提交可重放的 Innovus Tcl 脚本：
`analyze.tcl`

同时将选择结果保存为：
`answer.json`

格式如下：

```json
{
  "target_net": "",
  "target_sinks": []
}
```

## 验证方式

验证器会检查目标 net 和 sinks 是否真实存在、连接关系是否正确，并根据增量 STA 和 DRV 结果判断该位置是否能够获得最佳改善。