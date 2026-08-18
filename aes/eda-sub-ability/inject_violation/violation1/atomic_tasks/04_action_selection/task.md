# Task 001_4：ECO 动作选择
## 任务目标

根据已确认的 Hold 违例及其根因，以及已经选定的最优 ECO 对象，选择合适的 ECO 动作修复该违例。

## 输入数据

从以下路径加载初始设计：
`initial_state/design.enc`

该 checkpoint 是自包含的，其中包括 MMMC 时序配置和物理设计数据。

最差 Hold 路径信息：
`inputs/worst_hold_path.json`

根因诊断结果：
`inputs/root_cause.json`

预计的 ECO 对象：
`inputs/eco_object.json`

## 任务要求

编写 Innovus Tcl 脚本，查询所选对象的连接关系、驱动和负载，并将结果保存到：

`reports/action_analysis.rpt`

从以下动作中选择一种：

- `size_cell`
- `swap_vt`
- `insert_buffer`
- `clone_driver`
- `adjust_placement`

本次只选择 ECO 动作，不执行具体修改。分析过程中不得修改设计或时序约束。

## 提交要求

提交可重放的 Innovus Tcl 脚本：
`analyze.tcl`

同时将选择结果保存为：
`answer.json`

格式如下：

```json
{
  "eco_action": ""
}
```

## 验证方式

验证器会将选择结果与候选动作的实际增量 STA 结果进行比较，确认提交的动作是否能够为目标 Hold 路径带来最大收益。