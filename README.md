# 2026 本迪布焦病毒病流行动态仪表盘｜数据外置版

这是 GitHub + Netlify 自动部署版本。网页主体在 `index.html`，疫情数据放在 `data/` 目录。

## 文件结构

```text
index.html
netlify.toml
data/
  timeseries.json
  regional.json
  news.json
```

## 如何更新病例时间序列

打开：

```text
data/timeseries.json
```

在数组末尾添加一条新数据，例如：

```json
{
  "date": "2026-06-21",
  "cases": 960,
  "deaths": 250,
  "recovered": 95,
  "type": "official",
  "source": "WHO / Ministry update",
  "url": "https://example.com",
  "note": "新增官方通报数据"
}
```

注意：
- 每条数据之间要用英文逗号分隔。
- 最后一条数据后面不要加逗号。
- `type` 建议使用 `official` 或 `media`。
- 媒体快讯数字建议在 `note` 里标注“待官方确认”。

## 如何更新地区地图

打开：

```text
data/regional.json
```

修改对应地区的 `cases` 数字即可。

当前支持的 `key` 包括：

```text
ituri
northKivu
southKivu
uganda
```

## 如何更新新闻动态

打开：

```text
data/news.json
```

添加新闻条目即可。网页会在“最新新闻动态”板块显示这些内容。

## 自动部署

修改并提交任何文件后，Netlify 会自动从 GitHub 部署最新版本。


## 自动抓取更新

本项目已加入 GitHub Actions 自动更新模块。具体启用方法见 `AUTO_UPDATE.md`。


## 自动脚本防错

本版本采用候选优先策略，默认不自动写入正式时间线。详见 `SAFETY_RULES.md`。


## WHO-only 正式数据模式

本版本将正式趋势图限定为 WHO / WHO AFRO 口径，媒体和其他来源只作为新闻动态和候选线索。详见 `WHO_ONLY_MODE.md`。
