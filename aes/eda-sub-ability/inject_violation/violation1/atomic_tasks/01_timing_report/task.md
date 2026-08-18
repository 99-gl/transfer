# Task 001_1：最差路径获取

## 任务目标

基于 Cadence Innovus 19.10 对当前提供的初始设计执行 Hold 时序分析，并识别最差 Hold 路径。

## 输入数据

从以下路径加载初始设计：

`initial_state/design.enc`

该 checkpoint 是自包含的，其中包括 MMMC 时序配置和物理设计数据。

## 任务要求

基于 Cadence Innovus 19.10 对当前设计执行 PostRoute Hold 时序分析，并将报告生成到：

`reports/hold`

从生成的报告中提取最差路劲的：

- Beginpoint；
- Endpoint；
- Slack，单位为 ns；
- Path Group。

分析过程中不得修改设计或时序约束。

## 结果要求

将分析结果保存为：`answer.json`

格式如下：
```json
{
  "beginpoint": "",
  "endpoint": "",
  "slack_ns": 0.0,
  "path_group": ""
}
```

## 验证方式

只有当 `answer.json` 中的 Beginpoint、Endpoint、Slack 和 Path Group 是与实际的最差路径一致时才算通过。