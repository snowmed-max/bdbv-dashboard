# 2026 本迪布焦病毒病流行动态仪表盘

这是一个用于展示 2026 年本迪布焦病毒病（Bundibugyo virus disease, BDBV）流行动态的静态网页项目，可部署到 GitHub + Netlify，实现自动部署。

## 文件说明

- `index.html`：网页主文件，Netlify / GitHub Pages / Cloudflare Pages 会默认读取它作为首页。
- `netlify.toml`：Netlify 部署配置文件。
- `.gitignore`：忽略系统临时文件。

## 最简单的部署方式：GitHub + Netlify

1. 在 GitHub 新建一个仓库，例如 `bdbv-dashboard`。
2. 上传本项目中的全部文件。
3. 登录 Netlify。
4. 选择 `Add new site` → `Import an existing project`。
5. 选择 GitHub，并授权 Netlify 访问该仓库。
6. 选择 `bdbv-dashboard` 仓库。
7. Build command 留空。
8. Publish directory 填 `.`，或者保持默认。
9. 点击 Deploy。

之后每次你修改 GitHub 仓库里的 `index.html`，Netlify 会自动重新部署网站。

## 后续动态化建议

当前版本的数据主要写在 `index.html` 内。下一步可以把数据拆成：

```text
data/timeseries.json
data/regional.json
data/news.json
```

再用 GitHub Actions 定时抓取 WHO、CDC、ECDC、GDELT 等来源，自动更新 JSON 数据。

测试 GitHub 自动部署。
