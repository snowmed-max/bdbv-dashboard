# 如何减少自动脚本误判

本版本采用“候选优先”策略：

```text
自动抓取 → candidates.json
人工复核 → timeseries.json / regional.json
```

默认不会把自动提取的数字写入正式时间线。

## 已加入的防错规则

1. 拒绝把 1900–2100 之间的数字当作病例数，避免把 2026 当成病例。
2. 如果数字附近出现 suspected、probable、contacts、health zones、samples、percent 等词，拒绝作为确诊/死亡/康复数字。
3. 只有同时出现在 Bundibugyo/Ebola/DRC/Uganda 等上下文附近的数字，才进入候选。
4. WHO DON index、WHO AFRO topic、Africa CDC news 等列表页只进入候选，不允许自动写入正式数据。
5. 媒体标题里的数字只作为 media_candidate，不进入正式时间线。
6. 每个候选数字都有：
   - confidence
   - score
   - warnings
   - source URL

## 人工复核时优先看什么？

打开：

```text
data/candidates.json
```

优先查看：

```json
"confidence": "medium"
```

或：

```json
"confidence": "high"
```

但只要有：

```json
"warnings": [...]
```

就必须打开原文复核。

## 什么时候可以写入 timeseries.json？

只有确认以下问题后：

- 是本次 2026 BDBV 疫情；
- 是 confirmed cases，而不是 suspected / probable / contacts；
- 是累计数据还是新增数据已经明确；
- 是 DRC 单国、Uganda 单国，还是两国合计；
- 日期明确；
- 来源可靠。

## 为什么不建议完全自动？

公开网页不是结构化数据库。页面上可能同时出现年份、历史疫情、疑似病例、接触者人数、卫生区数量和百分比。完全自动更新正式数据，很容易产生看似精确但实际错误的疫情曲线。
