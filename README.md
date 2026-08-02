# 采数 Amazon 标题半自动化工作台

面向 Amazon 运营的本地真实数据工作台。它使用电脑上的 Google Chrome 读取商品、
父子体、搜索结果和评论，结合竞品标题结构、ABA 搜索词、否词与已验证产品事实，
生成原标题或“主标题 + Highlight Item”二段标题，并支持多尺寸 Excel 导出。

> 当前版本：V26 / API 1.26.0
> 系统：Windows 10/11（启动脚本使用 PowerShell）

## 功能概览

- 父体批量优化、最多 100 个子体批量优化、单子体优化；
- 新增变体标题和无 ASIN 新品标题研究；
- 先人工确认搜索词、权重和排除项，再抓取真实竞品；
- 同品牌只保留一个竞品，支持搜索页采集及可选详情页复核；
- 分开分析竞品高频词/标题公式与 ABA 流量词；
- 按不同尺寸整理类目词、场景词和标题结构；
- 从负向评论提取痛点，只有本品已确认改进后才能成为标题卖点；
- 语义级去重，避免主标题与 Highlight 重复同一卖点；
- 导出竞品和多尺寸标题 Excel。

## 安装要求

安装以下软件：

1. [Google Chrome](https://www.google.com/chrome/)；
2. [Node.js 22.13 或更高版本](https://nodejs.org/)；
3. [Python 3.10 或更高版本](https://www.python.org/downloads/)；
4. Git（只有克隆或更新项目时需要）。

安装 Python 时请勾选 **Add Python to PATH**。

## Windows 一键安装

克隆项目：

```powershell
git clone https://github.com/Ariupm/Amazon-AI.git
cd Amazon-AI
```

双击根目录中的 `安装项目依赖.bat`。脚本会检查 Node.js、Python 和 Chrome，然后执行：

```powershell
npm ci
python -m pip install -r amazon_scraper/requirements.txt
```

依赖只需要安装一次；更新 `package-lock.json` 或 `requirements.txt` 后再重新运行。

## 启动与使用

1. 双击 `启动真实抓取器.bat`；
2. 保持弹出的服务窗口开启；
3. 页面会自动打开：`http://localhost:3000/titles`；
4. 如果 3000 被其他项目占用，工作台自动使用 `http://localhost:3001/titles`；
5. 第一次访问 Amazon 若出现登录、验证码或验证页面，请在专用 Chrome 中手动完成；
6. Chrome 会在服务运行期间保持打开，多个采集任务共享登录状态；
7. 关闭启动脚本的服务窗口即可停止本地服务和专用 Chrome。

工作流建议：

1. 选择父体、批量子体、单子体、新增变体或新品模式；
2. 读取商品并人工核对类目、材质、风格、用途和真实卖点；
3. 生成搜索方案，调整搜索词权重与排除词；
4. 搜索并勾选真实竞品；
5. 上传 ABA 词库和否词文件；
6. 分析关键词与不同尺寸标题结构；
7. 确认评论痛点对应的本品改进；
8. 生成、人工复核并导出标题。

## 手动启动

分别打开两个 PowerShell 窗口。

窗口一：

```powershell
python -m uvicorn amazon_scraper.app:app --host 127.0.0.1 --port 8765
```

窗口二：

```powershell
npm run dev -- --host localhost --port 3000
```

然后访问 `http://localhost:3000/titles`。

## 测试

```powershell
python -m unittest discover -s tests -p "test_*.py"
npm test -- --runInBand
```

检查本地 API：

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
```

## 数据与隐私

- Amazon 登录状态保存在本地 `amazon_scraper/.chrome-profile/`，该目录已被 Git 忽略；
- `.env*`、日志、缓存、构建产物和历史部署压缩包不会提交到 GitHub；
- 抓取器只监听 `127.0.0.1:8765`，不会直接暴露到局域网或互联网；
- 项目不生成模拟 Amazon 数据；页面读取失败时应处理登录、验证码或网络问题；
- 请遵守 Amazon 条款、当地法规并控制采集频率。

## 在线页面说明

已有网页入口：
[https://caishu-amazon-insights.chumoiii.chatgpt.site/titles](https://caishu-amazon-insights.chumoiii.chatgpt.site/titles)

网页可以公开打开，但真实 Amazon 读取接口指向访问者电脑的 `127.0.0.1:8765`。
因此在另一台电脑使用抓取功能时，也必须在该电脑安装本仓库并运行
`启动真实抓取器.bat`。

## 常见问题

- **提示未连接本机抓取器**：确认启动窗口仍开着，并访问
  `http://127.0.0.1:8765/health`。
- **提示旧版本占用 8765**：关闭旧的抓取器窗口，再双击当前仓库的启动脚本。
- **Amazon 页面空白**：程序会自动重试三次；仍失败时检查网络、代理、登录或验证页。
- **候选不足 100 个**：100 是上限，不是承诺数量；硬性类目过滤、自有商品排除、
  同品牌去重及 Amazon 实际返回量都会减少结果。
- **类目或尺寸不正确**：人工确认类目与单位。无证据时系统不应回退到 Area Rug。

## 主要目录

```text
app/titles/                    标题工作台前端
amazon_scraper/app.py          本地 FastAPI 接口与常驻 Chrome 会话
amazon_scraper/scraper.py      Amazon 商品、父子体和评论抓取
amazon_scraper/competitors.py  竞品搜索、过滤、相似度及去重
amazon_scraper/title_generator.py  ABA、结构、尺寸场景和标题生成
amazon_scraper/excel_export.py Excel 导出
tests/                         Python 与页面测试
PROJECT_MEMORY.md              项目长期业务与技术记忆
```

开发协作规则见 [AGENTS.md](./AGENTS.md)，长期项目现状见
[PROJECT_MEMORY.md](./PROJECT_MEMORY.md)。
