# Task 002_4：ECO 动作选择

## 任务目标

根据已确认的最大扇出违例、根因和 ECO 对象，选择能够降低 `done` 网扇出违例的 ECO 动作。

## 输入数据

从以下路径加载初始设计：

`initial_state/design.enc`

01 任务输出的最差 Hold 路径信息：

`inputs/worst_hold_path.json`

当前违例信息：

`inputs/fanout_violation.json`

根因诊断结果：

`inputs/root_cause.json`

已选择的 ECO 对象：

`inputs/eco_object.json`

## 任务要求

查询所选对象的驱动和负载连接关系，从以下动作中选择一种：

- `size_cell`
- `swap_vt`
- `insert_buffer`
- `clone_driver`
- `adjust_placement`

本任务只选择 ECO 动作，不执行具体修改，分析过程不得修改设计或时序约束。查询结果保存到 `reports/action_analysis.rpt`。

## 结果要求

提交可重放的 Innovus Tcl 脚本：`analyze.tcl`

同时将选择结果保存为：`answer.json`

格式如下：
```json
{
  "eco_action": ""
}
```

## 验证方式

验证器会检查提交的动作是否为 `insert_buffer`。
