# 日涨幅与估值展示规则

## 核心目标
1. 盘中优先展示当日估值与当日估涨，而不是上一交易日真实涨幅。
2. 收盘后如果正式净值还没更新，继续展示“今日估值 / 今日估涨”。
3. 开盘前与非交易日统一展示最近一个交易日的真实净值和真实涨幅。
4. 持仓页和详情页统一依赖后端返回的 `today_change_*`、`intraday_change_*`、`display_nav_*` 字段，不在前端二次推导。

## 当前规则
### 时间基准
- 所有交易时段判断统一按 `Asia/Shanghai` 计算。
- 不能使用部署机器本地时区直接判断，否则会把北京时间下午误判成 `pre_open`。

### 交易日 `09:30-15:00`
- `market_status = trading`
- `display_nav_type = estimated`
- `display_nav_label = 盘中估值`
- `primary_nav_title = 盘中估值`
- `intraday_change_label = 实时估涨`
- `today_change_label = 实时估涨`

### 交易日 `15:00-24:00` 且正式净值未更新
- `market_status = closed`
- `display_nav_type = estimated`
- `display_nav_label = 今日估值`
- `primary_nav_title = 今日估值`
- `intraday_change_label = 今日估涨`
- `today_change_label = 今日估涨`
- `intraday_change_rate` 与 `today_change_rate` 保持一致，统一使用估涨值

### 交易日 `15:00-24:00` 且正式净值已更新
- 优先展示正式净值
- `display_nav_type = official`
- `display_nav_label = 正式净值`
- `today_change_label = 真实涨幅`

### 交易日 `00:00-09:30`
- `market_status = pre_open`
- 展示最近一次正式净值
- `today_change_label = 昨日真实涨幅`
- `intraday_change_label = 当前状态`
- `intraday_change_text = 暂未开盘`

### 周末 / 节假日
- `market_status = non_trading_day`
- 展示最近一次正式净值
- `today_change_label = 最后交易日真实涨幅`
- 不展示“今日估值 / 今日估涨”

## 关键字段约定
- `display_nav_*`
  用于主净值展示，决定当前最该展示的是正式净值、盘中估值还是最近净值。
- `primary_nav_*`
  用于前端主卡片标题和时间文案。
- `intraday_change_*`
  用于描述“当前时段最该看的涨幅”。
- `today_change_*`
  用于跨页面统一的“今日主涨幅”展示。
- `market_hint`
  只做辅助说明，不参与前端计算。
- `message`
  用于解释当前为什么展示这类数据。

## 主要文件
- [fund_quote.py](D:/Project/ZJ-MY-PROJECT/ji_jin/fund_quote.py)
  负责交易时段判断、正式净值/估值优先级、接口中文文案和缓存兼容。
- [fund_quote_service.py](D:/Project/ZJ-MY-PROJECT/ji_jin/fund_quote_service.py)
  负责向上层接口透传统一后的行情字段。
- [miniapp/pages/portfolio/portfolio.js](D:/Project/ZJ-MY-PROJECT/ji_jin/miniapp/pages/portfolio/portfolio.js)
  负责持仓页展示。
- [miniapp/pages/fund-detail/fund-detail.js](D:/Project/ZJ-MY-PROJECT/ji_jin/miniapp/pages/fund-detail/fund-detail.js)
  负责详情页展示。

## 已验证场景
1. 北京时间盘中，请求线上 `quotes`，不再误判为 `pre_open`。
2. 盘中基金可返回 `display_nav_type = estimated`、`market_status = trading`。
3. 接口中文文案已恢复正常，不再出现乱码或 `????`。
4. 收盘后正式净值未更新时，`intraday_change_*` 与 `today_change_*` 已统一为“今日估涨”。

## 后续改动约束
1. 如果调整 `market_status` 规则，必须同时检查 `display_nav_*`、`primary_nav_*`、`intraday_change_*`、`today_change_*` 是否仍然一致。
2. 如果修改缓存逻辑，不能让缓存覆盖新的时段判断结果。
3. 如果新增前端展示位，优先复用现有后端字段，不新增页面侧推导。
