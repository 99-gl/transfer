# Task 002_3：ECO 对象选择

## 任务目标

结合已确认的最大扇出违例和根因诊断结果，从当前设计中选择一个适合后续 ECO 分析的 Innovus 对象。

## 输入数据

从以下路径加载初始设计：

`initial_state/design.enc`

01 任务输出的最差 Hold 路径信息：

`inputs/worst_hold_path.json`

当前违例信息：

`inputs/fanout_violation.json`

根因诊断结果：

`inputs/root_cause.json`

## 任务要求

查询目标网、驱动 pin 及其负载连接关系，从目标对象中选择一个 `instance` 或 `net`。本任务只选择 ECO 对象，不执行具体修改，分析过程不得修改设计或时序约束。查询结果保存到 `reports/object_analysis.rpt`。

## 结果要求

提交可重放的 Innovus Tcl 脚本：`analyze.tcl`

同时将选择结果保存为：`answer.json`

格式如下：
```json
{
  "object_type": "net",
  "object_name": ""
}
```

其中 `object_type` 只能填写 `instance` 或 `net`，且只能提交一个对象。

## 验证方式

验证器会检查所选对象是否为真实存在的 `done` 网。
