# Task 001_2：违例根因诊断

## 目标

结合已确认的最差 Hold 路径、详细时序报告和 PostRoute DRV 摘要，判断造成该路径 Hold 违例的主要原因。

## 输入数据

当前已确认的最差路径信息：
`inputs/worst_hold_path.json`

详细 Hold 时序报告：
`inputs/hold_timing_report.gz`

PostRoute 时序和 DRV 摘要：
`inputs/postroute_summary.gz`

## 分析要求

结合数据路径中的 cell delay、net delay，以及 max-transition、max-capacitance 和 max-fanout 检查结果，从以下类型中选择造成当前违例得主要根因：

- `cell_delay`
- `net_delay`
- `fanout`
- `transition`
- `congestion`

同时简要解释一下判断依据。

只需完成根因诊断，不需要完成额外操作。

## 提交要求

将诊断结果保存为：
`answer.json`

格式如下：
```json
{
  "root_cause": "",
  "evidence": ""
}
```

## 验证方式

验证器会检查根因类型是否正确，以及证据是否与目标路径的时序分解和 DRV 结果一致。

