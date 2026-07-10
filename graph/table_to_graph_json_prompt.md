# 电子设计违例知识图谱：表格数据 → JSON 转换

## 任务

你是一个数据结构化专家。请将下面提供的电子设计违例修复表格数据，严格按照指定的图结构 schema 转换为 JSON 格式输出。

## 原始数据的表格结构

表格共有 4 列（或等价的字段），逻辑关系如下：

| 列号 | 列名 | 说明 |
|------|------|------|
| 1 | 违例概念 | 一种违例的名称（如 "DRC Spacing Violation"） |
| 2 | 现象识别方法 | 判断某个问题是否属于该违例概念的具体方法/步骤 |
| 3 | 根因分析动作 | 针对该现象，排查可能根因时需要执行的分析动作。一个现象可能对应多条根因，每条根因有独立的分析动作 |
| 4 | 修复方法 | 与第 3 列的根因**一一对应**的修复方案 |

关键逻辑：
- 一个**违例概念 (ViolationConcept)** 对应一个**现象 (Phenomenon)**
- 一个**现象 (Phenomenon)** 对应**多个根因 (RootCause)**
- 每个**根因 (RootCause)** 的 `analysis_action` 和 `fix_method` 一一对应（即表格第 3 列和第 4 列同行配对）

## 目标 JSON Schema

输出 JSON 包含 `nodes`（节点列表）和 `edges`（边列表）。

### 节点类型

1. **ViolationConcept** — 违例概念节点
```json
{
  "id": "vc_<序号>",
  "type": "ViolationConcept",
  "properties": {
    "name": "<违例概念名称>"
  }
}
```

2. **Phenomenon** — 现象节点
```json
{
  "id": "ph_<序号>",
  "type": "Phenomenon",
  "properties": {
    "name": "<现象名称，从违例概念派生或直接取自表格>",
    "identification_method": "<现象识别方法，即表格第 2 列内容>"
  }
}
```

3. **RootCause** — 根因节点
```json
{
  "id": "rc_<序号>",
  "type": "RootCause",
  "properties": {
    "scenario_id": "<根因场景编号，格式为 S<违例序号>-<根因序号>，如 S1-1, S1-2>",
    "analysis_action": "<根因分析动作，即表格第 3 列对应行内容>",
    "fix_method": "<修复方法，即表格第 4 列对应行内容>",
    "dependent_tool": "<从 analysis_action 或 fix_method 中提取的依赖工具名称，若无明确工具则填 null>"
  }
}
```

### 边类型

所有边的关系类型均为 `HAS`：

```json
{
  "source": "<源节点 id>",
  "target": "<目标节点 id>",
  "relation": "HAS"
}
```

边的方向规则：
- `ViolationConcept` —HAS→ `Phenomenon`
- `Phenomenon` —HAS→ `RootCause`

### 完整输出结构

```json
{
  "nodes": [ ... ],
  "edges": [ ... ]
}
```

## 转换规则（逐步执行）

1. **识别违例概念**：遍历表格，将第 1 列的每个不重复值创建为一个 `ViolationConcept` 节点，id 从 `vc_1` 开始递增。

2. **创建现象节点**：每个 `ViolationConcept` 对应创建一个 `Phenomenon` 节点：
   - `name`：取该违例概念下的统一现象描述（如果表格中违例概念行有明确的现象名称就用它，否则用 "<违例概念名称>现象"）。
   - `identification_method`：取表格第 2 列的完整内容。如果同一违例概念下第 2 列有多行但内容相同，只保留一份；如果内容不同，用分号 `;` 合并。
   - id 从 `ph_1` 开始递增。
   - 创建一条边：`vc_X` —HAS→ `ph_X`。

3. **创建根因节点**：对于每个现象，遍历其对应的所有表格行（第 3 列和第 4 列的配对）：
   - 每一对（第 3 列, 第 4 列）创建一个 `RootCause` 节点。
   - `scenario_id`：格式为 `S<违例序号>-<该违例下的根因序号>`，如第 1 个违例的第 2 个根因为 `S1-2`。
   - `analysis_action`：第 3 列内容。
   - `fix_method`：第 4 列内容。
   - `dependent_tool`：从第 3 列或第 4 列文本中提取提及的 EDA 工具名称（如 Calibre、ICC2、Innovus、Virtuoso 等）。如果未明确提及工具，填 `null`。
   - id 从 `rc_1` 开始全局递增。
   - 创建一条边：`ph_X` —HAS→ `rc_Y`。

4. **去重检查**：
   - 相同的 `ViolationConcept` name 不重复创建节点。
   - 相同的 `analysis_action` + `fix_method` 组合不重复创建 `RootCause` 节点（复用已有节点并建边）。

5. **输出**：仅输出最终的 JSON，不要输出任何解释性文字。JSON 需要格式化（缩进 2 空格）。

## 示例

### 输入表格

| 违例概念 | 现象识别方法 | 根因分析动作 | 修复方法 |
|---------|------------|------------|---------|
| Metal Spacing Violation | 在 DRC 报告中检查是否存在 metal layer 间距小于最小间距规则的标记 | 检查该区域是否存在手动 route 导致的间距不足 | 删除手动 route，使用 auto-route 重新布线 |
| Metal Spacing Violation | 在 DRC 报告中检查是否存在 metal layer 间距小于最小间距规则的标记 | 使用 Calibre 检查是否因 via 扩展导致相邻 metal 间距被压缩 | 调整 via 位置或更换 via 类型以恢复间距 |
| Via Enclosure Violation | 检查 DRC 报告中 via enclosure 不足的违例标记 | 检查上下层 metal 宽度是否满足 via enclosure 最小要求 | 加宽对应 metal layer 以满足 enclosure 规则 |

### 输出 JSON

```json
{
  "nodes": [
    {
      "id": "vc_1",
      "type": "ViolationConcept",
      "properties": {
        "name": "Metal Spacing Violation"
      }
    },
    {
      "id": "ph_1",
      "type": "Phenomenon",
      "properties": {
        "name": "Metal Spacing Violation 现象",
        "identification_method": "在 DRC 报告中检查是否存在 metal layer 间距小于最小间距规则的标记"
      }
    },
    {
      "id": "rc_1",
      "type": "RootCause",
      "properties": {
        "scenario_id": "S1-1",
        "analysis_action": "检查该区域是否存在手动 route 导致的间距不足",
        "fix_method": "删除手动 route，使用 auto-route 重新布线",
        "dependent_tool": null
      }
    },
    {
      "id": "rc_2",
      "type": "RootCause",
      "properties": {
        "scenario_id": "S1-2",
        "analysis_action": "使用 Calibre 检查是否因 via 扩展导致相邻 metal 间距被压缩",
        "fix_method": "调整 via 位置或更换 via 类型以恢复间距",
        "dependent_tool": "Calibre"
      }
    },
    {
      "id": "vc_2",
      "type": "ViolationConcept",
      "properties": {
        "name": "Via Enclosure Violation"
      }
    },
    {
      "id": "ph_2",
      "type": "Phenomenon",
      "properties": {
        "name": "Via Enclosure Violation 现象",
        "identification_method": "检查 DRC 报告中 via enclosure 不足的违例标记"
      }
    },
    {
      "id": "rc_3",
      "type": "RootCause",
      "properties": {
        "scenario_id": "S2-1",
        "analysis_action": "检查上下层 metal 宽度是否满足 via enclosure 最小要求",
        "fix_method": "加宽对应 metal layer 以满足 enclosure 规则",
        "dependent_tool": null
      }
    }
  ],
  "edges": [
    { "source": "vc_1", "target": "ph_1", "relation": "HAS" },
    { "source": "ph_1", "target": "rc_1", "relation": "HAS" },
    { "source": "ph_1", "target": "rc_2", "relation": "HAS" },
    { "source": "vc_2", "target": "ph_2", "relation": "HAS" },
    { "source": "ph_2", "target": "rc_3", "relation": "HAS" }
  ]
}
```

## 待转换的表格数据

<在此处粘贴你的原始表格数据>
