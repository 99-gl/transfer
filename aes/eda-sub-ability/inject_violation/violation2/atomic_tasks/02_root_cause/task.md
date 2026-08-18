# Task 002_2：违例根因诊断

## 任务目标

结合最大扇出报告和提供的 Innovus checkpoint，判断当前违例的主要根因。

## 输入数据

01 任务输出的最差 Hold 路径信息位于：

`inputs/worst_hold_path.json`

当前违例事实位于：

`inputs/fanout_violation.json`

初始设计位于：

`initial_state/design.enc`

## 任务要求

从以下类型中选择一个主要根因：

- `cell_delay`
- `net_delay`
- `fanout`
- `transition`
- `congestion`

结合驱动 pin、最大允许扇出、实际负载数量和报告中的扇出裕量，简要解释判断依据。只需完成根因诊断，不得修改设计。

## 结果要求

将诊断结果保存为：`answer.json`

格式如下：
```json
{
  "root_cause": "",
  "evidence": ""
}
```

## 验证方式

验证器会检查根因类型是否为 `fanout`，并检查是否提供了非空证据。
