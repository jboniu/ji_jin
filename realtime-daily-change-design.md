# 日涨幅分时段设计概要

## 核心功能
1. 盘中时段显示当日估算涨幅，而不是昨日真实涨幅。
2. 当日 `15:00-24:00` 默认继续显示当日估算涨幅；如果当日真实净值已更新，则切换为真实涨幅。
3. 当日 `00:00-09:30` 显示昨日真实涨幅。
4. 持仓页和详情页统一使用同一套 `today_change_*` 字段，避免页面间口径不一致。
5. 自动刷新逻辑只在盘中生效，保证 `14:00-14:30` 这类场景下用户停留页面时也能看到更新。

## 主要文件
- [fund_quote.py](D:/Project/ZJ-MY-PROJECT/ji_jin/fund_quote.py) - 处理时段判断、估算/真实涨幅切换、缓存兼容
- [fund_quote_service.py](D:/Project/ZJ-MY-PROJECT/ji_jin/fund_quote_service.py) - 透传统一后的 `today_change_*` 字段
- [portfolio.js](D:/Project/ZJ-MY-PROJECT/ji_jin/miniapp/pages/portfolio/portfolio.js) - 持仓页显示今日主涨幅并在盘中自动刷新
- [fund-detail.js](D:/Project/ZJ-MY-PROJECT/ji_jin/miniapp/pages/fund-detail/fund-detail.js) - 详情页顶部显示今日主涨幅并在盘中自动刷新

## 技术选型
- 后端继续使用现有 Python 聚合逻辑，不新增独立服务。
- 时段判断继续使用 `Asia/Shanghai` 本地时间。
- 估算涨幅优先使用东财估值接口 `gszzl`，必要时由 `estimated_nav` 和 `official_nav` 反算。
- 真实涨幅继续使用历史正式净值里的 `daily_change_rate`。

## 实施步骤
1. 后端把时段判断细化为：
   - `00:00-09:30` 开盘前规则
   - 工作日 `09:30-15:00` 盘中规则
   - `15:00-24:00` 收盘后当日晚间规则
2. 后端统一输出 `today_change_rate / today_change_text / today_change_label`。
3. 旧缓存命中时，也按新规则补齐或重算 `today_change_*`。
4. 持仓页和详情页主展示统一只认 `today_change_*`。
5. 用户验证 3 个场景：
   - 盘中
   - 当日 `15:00` 后但真实净值未更新
   - `00:00-09:30`

## 说明
- 这一版的重点是不同时间段看到的主涨幅口径正确。
- 节假日和午休的更精细处理可以继续补，但不影响这次主规则落地。
