# Amazon 真实数据采集器

本项目使用本机 Google Chrome 实际访问 Amazon 页面，不使用演示数据。

## 安装和启动

```powershell
python -m pip install -r amazon_scraper/requirements.txt
.\run_scraper.ps1
```

浏览器打开 `http://127.0.0.1:8765`。程序直接使用电脑已有的 Chrome，无需下载 Playwright 浏览器。

也可以直接双击项目根目录中的 `启动真实抓取器.bat`，页面会自动打开。

## 命令行

```powershell
python -m amazon_scraper.cli B012345678 --marketplace US --review-pages 2 --output product.scrape.json
```

- 首次出现验证码或登录时，在程序打开的 Chrome 中手动完成。
- 输入父体 ASIN 时会逐个打开并采集全部可识别子体；输入子体 ASIN 时只采集该子体。
- 输入框支持每行一个或逗号分隔的批量 ASIN。
- 子体表格包含图片、标题、现价、Typical price/划线价、颜色、尺寸、评分、库存和月销量信号；页面未展示的字段保持为空。
- 完成后可以导出 CSV 表格或完整 JSON。
- 评论优点来自 4–5 星真实评论，痛点来自 1–3 星真实评论，并保留原文证据。
- Amazon 页面结构会变化，选择器需要定期维护。
- 请控制采集频率，并确保使用方式符合适用的平台条款和当地法律。
