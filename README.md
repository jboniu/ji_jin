# 支付宝基金自动分析系统

当前阶段目标：跑通本地 Python 脚本，抓取新闻、读取持仓，并生成一份 AI Markdown 分析报告。

## 当前文件
- `fetch_news.py`：抓取公开财经新闻
- `analyze_fund.py`：调用兼容 OpenAI 接口的大模型生成基金分析
- `generate_report.py`：生成 Markdown 报告
- `portfolio.json`：单用户持仓配置
- `users.json`：多用户持仓配置
- `portfolio.py`：读取并格式化持仓摘要
- `reports/`：报告输出目录

## 本地准备
1. 创建虚拟环境：`python -m venv .venv`
2. 安装依赖：`.\.venv\Scripts\python.exe -m pip install -r requirements.txt`
3. 复制环境变量模板：将 `.env.example` 另存为 `.env`
4. 在 `.env` 中填写模型和邮件配置
5. 先测试抓新闻：`.\.venv\Scripts\python.exe .\fetch_news.py`
6. 再生成报告：`.\.venv\Scripts\python.exe .\generate_report.py`

## 持仓输入
当前支持通过 `portfolio.json` 或 `users.json` 维护持仓结构。

可先单独测试读取效果：
```powershell
cd D:\Project\ZJ-MY-PROJECT\ji_jin
.\.venv\Scripts\python.exe .\portfolio.py
```

报告会把持仓摘要一并传给 AI，因此输出内容会结合你的组合结构，重点关注：
- 近一周市场回顾
- 今日 15:00 前重点关注
- 加仓观察
- 减仓观察
- 持有观察

## 多用户支持
当前已支持通过 `users.json` 维护多个用户。

每个用户可配置：
- `user_id`：用户标识
- `owner`：用户名称
- `email_to`：该用户的收件邮箱列表
- `positions`：该用户自己的持仓

当前主流程会优先读取 `users.json`：
- 如果配置了多个用户，会逐个生成报告
- 每份报告会按该用户自己的 `email_to` 发送
- 报告文件名中会带上用户名称，便于区分

## 推荐模型配置
当前默认推荐使用智谱兼容接口：

```env
LLM_PROVIDER=zhipu
OPENAI_API_KEY=你的智谱 API Key
OPENAI_MODEL=glm-4.7-flash
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
```

如果后续要切换到 OpenAI，可改成：

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=你的 OpenAI API Key
OPENAI_MODEL=gpt-4.1-mini
```

## 邮件发送配置
如果你希望报告生成后自动发送邮件，可以在 `.env` 中补充：

```env
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USERNAME=你的发件邮箱
SMTP_PASSWORD=你的 SMTP 授权码
SMTP_USE_SSL=true
EMAIL_FROM=你的发件邮箱
EMAIL_TO=你的收件邮箱
```

说明：
- `SMTP_PASSWORD` 一般不是邮箱登录密码，而是 SMTP 授权码
- 常见邮箱如 QQ、163、企业邮箱都支持 SMTP
- 如果没有配置这些字段，脚本会只生成本地报告，不会中断

## 手动运行
当前项目已停用“交易日自动执行日报脚本”。

手动运行单次日报：
```powershell
cd D:\Project\ZJ-MY-PROJECT\ji_jin
.\run_daily_report.bat
```

如果这台电脑之前注册过旧的 Windows 任务计划，可执行：
```powershell
cd D:\Project\ZJ-MY-PROJECT\ji_jin
powershell -ExecutionPolicy Bypass -File .\unregister_daily_task.ps1
```

说明：
- 保留手动执行入口：`run_daily_report.bat`
- `register_daily_task.ps1` 已不再注册自动任务
- `.env` 里的 `TASK_TIME`、`TASK_WEEKDAYS` 仅作为历史配置保留，不再自动生效

## 当前状态
项目已经接入基础新闻抓取、AI 分析、报告生成、邮件发送、数据库用户/持仓、以及微信小程序前端能力。

## 日志与失败重试
- 运行日志会写入 `logs/fund_analysis.log`
- AI 分析失败时会自动重试
- 邮件发送失败时会自动重试
- 即使 AI 或邮件失败，日志里也会保留错误细节，方便排查
