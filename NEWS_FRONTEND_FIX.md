# 新闻动态前端修复说明

本版本不再让浏览器直接访问 GDELT。

原因：
- 浏览器端直接跨站抓取容易受到 CORS、网络和 GDELT 临时状态影响；
- 项目已经有 GitHub Actions 自动抓取机制，前端应只读取本站的 `data/news.json`。

现在逻辑：
- GitHub Actions 自动更新 `data/news.json`
- dashboard 前端读取 `data/news.json`
- “刷新新闻数据”按钮只是重新读取本站 JSON，不再访问外部 API
