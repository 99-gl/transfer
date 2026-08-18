# Task 002_1：最大扇出违例报告

## 任务目标

基于 Cadence Innovus 19.10 对当前提供的注入后设计执行最大扇出检查，并识别 `done` 网上的真实 max-fanout 违例。

## 输入数据

从以下路径加载初始设计：

`initial_state/design.enc`

该 checkpoint 是自包含的，其中包括 MMMC 时序配置和物理设计数据。

## 任务要求

基于 Cadence Innovus 19.10 对当前设计执行 `reportFanoutViolation`，并将报告生成到 `reports/`。从报告中提取违例网、驱动 pin、最大允许扇出、实际扇出和扇出裕量。分析过程中不得修改设计或时序约束。

## 结果要求

将分析结果保存为：`answer.json`

格式如下：
```json
{
  "check_type": "max_fanout",
  "net": "",
  "driver": "",
  "max_fanout": 0,
  "actual_fanout": 0,
  "fanout_slack": 0
}
```

## 验证方式

验证器会将所有字段与本场景注入的 `done` 网 max-fanout 违例进行比较。
