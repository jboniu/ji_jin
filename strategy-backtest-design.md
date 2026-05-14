# 策略回测设计概要

## 核心功能
1. 在基金详情页增加 `策略回测` 入口
2. 支持一个最小策略：`固定每周定投`
3. 输出累计投入、当前市值、策略收益率
4. 在历史走势上标出定投买点

## 主要文件
- `fund_quote.py` - 提供历史净值数据
- `api_server.py` - 新增策略回测接口
- `miniapp/pages/fund-detail/fund-detail.js` - 接入策略回测数据
- `miniapp/pages/fund-detail/fund-detail.wxml` - 展示回测结果入口与卡片

## 技术选型
- 后端按历史净值逐点模拟每周定投
- 前端先展示回测摘要，再逐步补买点可视化
