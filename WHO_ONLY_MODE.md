# WHO-only 正式数据版说明

本版本采用更严格的数据策略：

```text
正式趋势图 / 首页数据卡片 = WHO / WHO AFRO 已确认口径
新闻动态 = GDELT / Reuters / AP / WHO / 其他公开来源
候选线索 = candidates.json
```

## 自动更新

GitHub Actions 每 6 小时自动更新：

```text
data/news.json
data/candidates.json
```

## 手动更新

以下文件需要人工复核后手动更新：

```text
data/timeseries.json
data/regional.json
```

## 原则

不要把 Reuters、AP、GDELT、CDC、ECDC、Africa CDC 的数字直接写入正式趋势曲线。它们只作为新闻动态、候选线索或交叉核验来源。正式曲线只收录 WHO / WHO AFRO 已确认口径。
