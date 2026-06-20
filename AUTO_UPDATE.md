# 自动抓取与更新说明

本项目已经加入 GitHub Actions 自动更新模块。

## 自动更新做什么？

每 6 小时运行一次：

1. 抓取 GDELT 新闻索引，更新 `data/news.json`。
2. 抓取 WHO、WHO AFRO、CDC、ECDC、Africa CDC 等公开页面。
3. 从官方/准官方页面中尝试提取病例、死亡、康复数字。
4. 把提取到的候选数字写入 `data/candidates.json`。
5. 如果官方/准官方来源出现更高的累计确诊数，自动追加到 `data/timeseries.json`。

## 为什么还要 candidates.json？

疫情数据口径很敏感。网页、新闻、PDF 和官方简报的写法经常变化，自动提取可能误抓到日期、百分比或历史数字。因此：

- `news.json` 可以自动更新；
- `candidates.json` 用于人工复核；
- `timeseries.json` 只在脚本判断为高置信官方/准官方数字时自动追加。

## 如何启用 GitHub Actions？

1. 打开 GitHub 仓库。
2. 点击上方 `Actions`。
3. 如果看到提示，点击 `I understand my workflows, go ahead and enable them`。
4. 点击左侧 `Auto update dashboard data`。
5. 点击右侧 `Run workflow`，手动运行一次测试。

## 如果自动提交失败

进入：

`Settings` → `Actions` → `General`

找到：

`Workflow permissions`

选择：

`Read and write permissions`

然后保存。

## 修改运行频率

打开：

`.github/workflows/update-data.yml`

当前设置为：

```yaml
- cron: "17 */6 * * *"
```

意思是 UTC 时间每 6 小时运行一次。

如果要每天运行一次，可以改成：

```yaml
- cron: "17 0 * * *"
```

## 自动追加媒体数字？

默认不自动把媒体数字写入 `timeseries.json`，因为媒体快讯需要等官方确认。

如果你强行希望媒体数字也进入候选时间序列，可在 workflow 里把：

```yaml
AUTO_APPEND_MEDIA: "false"
```

改成：

```yaml
AUTO_APPEND_MEDIA: "true"
```

但不建议这样做。
