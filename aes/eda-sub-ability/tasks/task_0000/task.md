# Task 0001：Setup 时序修复

## 任务目标

使用 Cadence Innovus 19.10 修复所提供的 `ibex_top` 布线后设计中的 setup 时序违例。

初始状态如下：

- Setup WNS：-27.1 ps
- Setup TNS：-27.1 ps
- Hold WNS：+0.4 ps
- Hold TNS：0 ps

## 输入数据

从以下路径加载初始设计：

`initial_state/design.enc`

该 checkpoint 是自包含的，其中包括 MMMC 时序配置和物理设计数据。

## 验收要求

执行修复后必须满足：

- Setup WNS 大于或等于 0 ps；
- Setup TNS 等于 0 ps；
- Hold WNS 大于或等于 0 ps；
- Hold TNS 等于 0 ps；
- max-transition 违例数量为 0；
- max-capacitance 违例数量为 0；
- max-fanout 违例数量不得超过 135，且不得比初始状态恶化；
- DRC 违例数量为 0；
- connectivity 违例数量为 0；
- placement 违例数量为 0。

## 允许的修改

可以使用合法的布线后 ECO 操作，包括但不限于：

- 调整标准单元尺寸；
- 插入 repeater 或 buffer；
- placement legalization；
- ECO routing；
- RC extraction。

可以使用单步或多步修复方案。

## 禁止的修改

不得进行以下操作：

- 修改或替换时序约束；
- 修改时钟定义或时序分析模式；
- 添加 false path 或 multicycle path；
- 关闭或绕过 timing、DRC、connectivity 或 placement 检查；
- 通过删除功能逻辑来消除违例；
- 加载其他设计 checkpoint。

## 提交要求

提交一个可重放的 Innovus Tcl 脚本，文件名必须为：

`repair.tcl`

验证器将在 fresh-load `initial_state/design.enc` 后执行该脚本。提交脚本不得依赖任务目录以外的文件，也不得依赖之前 Innovus 会话遗留的状态。

## 验证方式

验证器将在 Cadence Innovus 19.10 中执行提交脚本，并重新进行时序和物理检查。

只有 timing、DRV、DRC、connectivity 和 placement 要求全部满足时，提交结果才会判定为通过。
