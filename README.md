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
