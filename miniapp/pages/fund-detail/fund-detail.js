const { request } = require("../../utils/api");

function formatRate(value) {
  return value != null ? `${value}%` : "--";
}

function formatNav(value) {
  return value != null ? `${value}` : "--";
}

function formatSignedRate(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return "--";
  }
  const number = Number(value);
  return `${number >= 0 ? "+" : ""}${number.toFixed(2)}%`;
}

function resolveIntradayChangeText(result) {
  if (result && result.intraday_change_text) {
    return result.intraday_change_text;
  }
  return formatSignedRate(result ? result.daily_change_rate : null);
}

function resolveIntradayChangeLabel(result) {
  return (result && result.intraday_change_label) || "当前涨幅";
}

function resolveTodayChangeText(result) {
  if (result && result.today_change_text) {
    return result.today_change_text;
  }
  return resolveIntradayChangeText(result);
}

function resolveTodayChangeLabel(result) {
  return (result && result.today_change_label) || resolveIntradayChangeLabel(result) || "当前涨幅";
}

function resolveUpdateMeta(result) {
  return {
    label: (result && result.today_change_time_label) || "更新时间",
    text: (result && result.today_change_time_text) || "暂无时间",
  };
}

function resolveMarketHint(result) {
  return (result && result.market_hint) || "";
}

function currentDateText() {
  const now = new Date();
  const year = now.getFullYear();
  const month = `${now.getMonth() + 1}`.padStart(2, "0");
  const day = `${now.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function resolvePrimaryNavMeta(result) {
  if (
    result &&
    result.primary_nav_label &&
    result.primary_nav_title &&
    result.primary_nav_time_label
  ) {
    return {
      label: result.primary_nav_label,
      title: result.primary_nav_title,
      value: formatNav(result.primary_nav_value),
      timeLabel: result.primary_nav_time_label,
      timeText: result.primary_nav_time_text || "暂无",
    };
  }

  const marketStatus = (result && result.market_status) || "";
  if (marketStatus === "trading") {
    return {
      label: "当前重点",
      title: "盘中估值",
      value: formatNav(result && result.estimated_nav),
      timeLabel: "估值时间",
      timeText: (result && result.estimated_nav_time) || "暂无",
    };
  }
  if (marketStatus === "closed" && !(result && result.official_nav_date && result.official_nav_date === currentDateText())) {
    return {
      label: "当前重点",
      title: "今日估值",
      value: formatNav(result && result.estimated_nav),
      timeLabel: "估值时间",
      timeText: (result && result.estimated_nav_time) || "暂无",
    };
  }
  return {
    label: "当前重点",
    title: "最近净值",
    value: formatNav((result && result.last_available_nav) || (result && result.official_nav)),
    timeLabel: "净值日期",
    timeText: (result && result.last_available_nav_date) || (result && result.official_nav_date) || "暂无",
  };
}

function formatHistoryNav(value) {
  return value != null ? Number(value).toFixed(4) : "--";
}

function formatChartDate(value, periodKey = "day") {
  if (!value) {
    return "--";
  }
  const text = String(value);
  if (text.length < 10) {
    return text;
  }
  if (periodKey === "day") {
    return text.slice(5);
  }
  if (periodKey === "month") {
    return `${text.slice(5, 7)}-${text.slice(8, 10)}`;
  }
  if (periodKey === "year" || periodKey === "year2" || periodKey === "year3") {
    return text.slice(2, 7);
  }
  return text.slice(5, 10);
}

function normalizeHistoryItems(items) {
  const normalized = (Array.isArray(items) ? items : [])
    .map((item) => ({
      date: item.date || "",
      close: Number(item.close),
    }))
    .filter((item) => item.date && !Number.isNaN(item.close));

  if (!normalized.length) {
    return [];
  }

  const base = normalized[0].close;
  return normalized.map((item) => ({
    ...item,
    changePct: base ? ((item.close - base) / base) * 100 : 0,
  }));
}

function buildTrendSummary(points) {
  if (!Array.isArray(points) || points.length < 2) {
    return {
      label: "趋势未知",
      value: "--",
      className: "",
    };
  }

  const first = points[0].close;
  const last = points[points.length - 1].close;
  if (!first) {
    return {
      label: "趋势未知",
      value: "--",
      className: "",
    };
  }

  const changeRate = ((last - first) / first) * 100;
  if (changeRate > 0.2) {
    return {
      label: "当前周期走强",
      value: `+${changeRate.toFixed(2)}%`,
      className: "trend-up",
    };
  }
  if (changeRate < -0.2) {
    return {
      label: "当前周期走弱",
      value: `${changeRate.toFixed(2)}%`,
      className: "trend-down",
    };
  }
  return {
    label: "当前周期震荡",
    value: `${changeRate >= 0 ? "+" : ""}${changeRate.toFixed(2)}%`,
    className: "trend-flat",
  };
}

function getHistoryQueryConfig(periodKey) {
  const configMap = {
    day: { apiPeriod: "day", count: 20 },
    month: { apiPeriod: "week", count: 8 },
    year: { apiPeriod: "month", count: 12 },
    year2: { apiPeriod: "month", count: 24 },
    year3: { apiPeriod: "month", count: 36 },
  };
  return configMap[periodKey] || configMap.day;
}

function buildTooltipPosition(index, total, chartWidth, chartHeight) {
  const paddingLeft = 12;
  const paddingRight = 12;
  const plotWidth = chartWidth - paddingLeft - paddingRight;
  const x = paddingLeft + (plotWidth * index) / Math.max(total - 1, 1);
  return {
    left: Math.max(24, Math.min(chartWidth - 92, x - 46)),
    top: Math.max(8, Math.min(chartHeight - 44, 14)),
  };
}

Page({
  data: {
    fundCode: "",
    fundName: "",
    historyPeriod: "day",
    historyPeriods: [
      { key: "day", label: "日" },
      { key: "month", label: "月" },
      { key: "year", label: "年" },
      { key: "year2", label: "2年" },
      { key: "year3", label: "3年" },
    ],
    historyItems: [],
    historyLoading: false,
    isRefreshing: false,
    historyEmptyText: "暂无走势数据",
    chartWidth: 320,
    chartHeight: 180,
    chartStats: {
      minText: "--",
      maxText: "--",
      startDate: "--",
      middleDate: "--",
      endDate: "--",
      latestNav: "--",
    },
    trendSummary: {
      label: "趋势未知",
      value: "--",
      className: "",
    },
    selectedHistoryPoint: {
      date: "--",
      nav: "--",
      left: 0,
      top: 0,
    },
    detail: {
      displayNav: "--",
      displayNavLabel: "加载中",
      primaryNavLabel: "当前重点",
      primaryNavTitle: "最近净值",
      primaryNavValue: "--",
      primaryNavTimeLabel: "净值日期",
      primaryNavTimeText: "暂无",
      officialNav: "--",
      officialNavDate: "暂无",
      estimatedNav: "--",
      estimatedNavTime: "暂无",
      lastAvailableNav: "--",
      lastAvailableNavDate: "暂无",
      dailyChangeRate: "--",
      weeklyChangeRate: "--",
      monthlyChangeRate: "--",
      updatedAtLabel: "更新时间",
      updatedAt: "暂无",
      marketHint: "",
      status: "",
      message: "",
    },
  },

  onLoad(options) {
    const fundCode = options.fundCode || "";
    const fundName = decodeURIComponent(options.fundName || "");
    this.setupChartSize();
    this.setData({ fundCode, fundName });
    this.loadFundDetail(fundCode, fundName);
    this.loadFundHistory(fundCode, this.data.historyPeriod);
  },

  async onPullDownRefresh() {
    this.setData({
      isRefreshing: true,
    });
    try {
      await Promise.all([
        this.loadFundDetail(this.data.fundCode, this.data.fundName),
        this.loadFundHistory(this.data.fundCode, this.data.historyPeriod, { silent: true }),
      ]);
    } finally {
      this.setData({
        isRefreshing: false,
      });
      wx.stopPullDownRefresh();
    }
  },

  setupChartSize() {
    const systemInfo = wx.getSystemInfoSync();
    const rpxUnit = systemInfo.windowWidth / 750;
    const horizontalPadding = (24 * 2 + 28 * 2) * rpxUnit;
    const chartWidth = Math.max(240, Math.floor(systemInfo.windowWidth - horizontalPadding));
    const chartHeight = Math.floor(200 * rpxUnit);
    this.setData({
      chartWidth,
      chartHeight,
    });
  },

  async loadFundDetail(fundCode, fundName) {
    try {
      const path = fundCode
        ? `/funds/${fundCode}/quote?fund_name=${encodeURIComponent(fundName)}`
        : `/funds/lookup?fund_name=${encodeURIComponent(fundName)}`;
      const result = await request(path);
      const nextFundCode = result.fund_code || fundCode || "";
      const todayChangeText = resolveTodayChangeText(result);
      const todayChangeLabel = resolveTodayChangeLabel(result);
      const updateMeta = resolveUpdateMeta(result);
      const primaryNavMeta = resolvePrimaryNavMeta(result);
      this.setData({
        fundCode: nextFundCode,
        fundName: result.fund_name || fundName || nextFundCode,
        detail: {
          displayNav: formatSignedRate(result.daily_change_rate),
          displayNavLabel: "当前涨幅",
          primaryNavLabel: primaryNavMeta.label,
          primaryNavTitle: primaryNavMeta.title,
          primaryNavValue: primaryNavMeta.value,
          primaryNavTimeLabel: primaryNavMeta.timeLabel,
          primaryNavTimeText: primaryNavMeta.timeText,
          officialNav: formatNav(result.official_nav),
          officialNavDate: result.official_nav_date || "暂无",
          estimatedNav: formatNav(result.estimated_nav),
          estimatedNavTime: result.estimated_nav_time || "暂无",
          lastAvailableNav: formatNav(result.last_available_nav),
          lastAvailableNavDate: result.last_available_nav_date || "暂无",
          dailyChangeRate: formatRate(result.daily_change_rate),
          weeklyChangeRate: formatRate(result.weekly_change_rate),
          monthlyChangeRate: formatRate(result.monthly_change_rate),
          updatedAtLabel: updateMeta.label,
          updatedAt: updateMeta.text,
          marketHint: resolveMarketHint(result),
          status: result.status || "",
          message: result.message || "",
        },
      });
      this.setData({
        detail: {
          ...this.data.detail,
          displayNav: todayChangeText,
          displayNavLabel: todayChangeLabel,
          dailyChangeRate: todayChangeText,
        },
      });
      if (nextFundCode && nextFundCode !== fundCode) {
        this.loadFundHistory(nextFundCode, this.data.historyPeriod);
      }
    } catch (error) {
      if (this.data.detail && this.data.detail.status) {
        wx.showToast({
          title: error.message || "刷新失败，请稍后重试",
          icon: "none",
        });
        return;
      }
      this.setData({
        fundCode,
        fundName: fundName || fundCode,
        detail: {
          displayNav: "--",
          displayNavLabel: "当前涨幅",
          primaryNavLabel: "当前重点",
          primaryNavTitle: "最近净值",
          primaryNavValue: "--",
          primaryNavTimeLabel: "净值日期",
          primaryNavTimeText: "暂无",
          officialNav: "--",
          officialNavDate: "暂无",
          estimatedNav: "--",
          estimatedNavTime: "暂无",
          lastAvailableNav: "--",
          lastAvailableNavDate: "暂无",
          dailyChangeRate: "--",
          weeklyChangeRate: "--",
          monthlyChangeRate: "--",
          updatedAtLabel: "更新时间",
          updatedAt: "暂无",
          marketHint: "",
          status: "error",
          message: error.message || "基金详情加载失败",
        },
      });
    }
  },

  async loadFundHistory(fundCode, period, options = {}) {
    const { silent = false } = options;
    if (!fundCode) {
      this.setData({
        historyItems: [],
        historyLoading: false,
        historyEmptyText: "缺少基金代码，无法加载走势",
      });
      return;
    }

    if (!silent) {
      this.setData({
        historyLoading: true,
        historyEmptyText: "加载走势中...",
      });
    }

    try {
      const queryConfig = getHistoryQueryConfig(period);
      const result = await request(`/funds/${fundCode}/history?period=${queryConfig.apiPeriod}&count=${queryConfig.count}`);
      const historyItems = normalizeHistoryItems(result.items).slice(-queryConfig.count);
      this.setData(
        {
          historyItems,
          historyLoading: false,
          historyEmptyText: historyItems.length ? "" : "暂无走势数据",
          chartStats: this.buildChartStats(historyItems, period),
          trendSummary: buildTrendSummary(historyItems),
          selectedHistoryPoint: this.buildSelectedHistoryPoint(historyItems, this.data.chartWidth, this.data.chartHeight),
        },
        () => {
          this.drawHistoryChart();
        }
      );
    } catch (error) {
      if ((silent || (this.data.historyItems || []).length) && (this.data.historyItems || []).length) {
        this.setData({
          historyLoading: false,
        });
        wx.showToast({
          title: error.message || "走势刷新失败，请稍后重试",
          icon: "none",
        });
        return;
      }
      this.setData({
        historyItems: [],
        historyLoading: false,
        historyEmptyText: error.message || "走势加载失败",
        chartStats: this.buildChartStats([], period),
        trendSummary: buildTrendSummary([]),
        selectedHistoryPoint: this.buildSelectedHistoryPoint([], this.data.chartWidth, this.data.chartHeight),
      });
      this.drawHistoryChart();
    }
  },

  buildChartStats(historyItems, periodKey = "day") {
    if (!historyItems.length) {
      return {
        minText: "--",
        maxText: "--",
        startDate: "--",
        middleDate: "--",
        endDate: "--",
        latestNav: "--",
      };
    }

    const min = Math.min(...historyItems.map((item) => item.changePct));
    const max = Math.max(...historyItems.map((item) => item.changePct));
    const firstItem = historyItems[0];
    const middleItem = historyItems[Math.floor((historyItems.length - 1) / 2)];
    const lastItem = historyItems[historyItems.length - 1];
    return {
      minText: formatSignedRate(min),
      maxText: formatSignedRate(max),
      startDate: formatChartDate(firstItem.date, periodKey),
      middleDate: formatChartDate(middleItem.date, periodKey),
      endDate: formatChartDate(lastItem.date, periodKey),
      latestNav: formatSignedRate(lastItem.changePct),
    };
  },

  buildSelectedHistoryPoint(historyItems, chartWidth = 320, chartHeight = 180) {
    if (!historyItems.length) {
      return {
        date: "--",
        nav: "--",
        left: 0,
        top: 0,
      };
    }
    const lastItem = historyItems[historyItems.length - 1];
    const tooltipPosition = buildTooltipPosition(
      historyItems.length - 1,
      historyItems.length,
      chartWidth,
      chartHeight
    );
    return {
      date: lastItem.date || "--",
      nav: formatSignedRate(lastItem.changePct),
      left: tooltipPosition.left,
      top: tooltipPosition.top,
    };
  },

  drawHistoryChart() {
    const { historyItems, chartWidth, chartHeight, selectedHistoryPoint } = this.data;
    const ctx = wx.createCanvasContext("historyChart", this);
    ctx.clearRect(0, 0, chartWidth, chartHeight);

    if (!historyItems.length) {
      ctx.draw();
      return;
    }

    const padding = {
      top: 18,
      right: 12,
      bottom: 24,
      left: 12,
    };
    const plotWidth = chartWidth - padding.left - padding.right;
    const plotHeight = chartHeight - padding.top - padding.bottom;
    const values = historyItems.map((item) => item.changePct);
    let min = Math.min(...values);
    let max = Math.max(...values);
    if (min === max) {
      min -= 0.01;
      max += 0.01;
    }

    const points = historyItems.map((item, index) => {
      const x = padding.left + (plotWidth * index) / Math.max(historyItems.length - 1, 1);
      const y = padding.top + ((max - item.changePct) / (max - min)) * plotHeight;
      return { x, y, value: item.changePct, date: item.date };
    });
    const selectedPoint =
      points.find((point) => point.date === selectedHistoryPoint.date) || points[points.length - 1];

    ctx.setStrokeStyle("#e7dcc9");
    ctx.setLineWidth(1);
    for (let index = 0; index < 3; index += 1) {
      const y = padding.top + (plotHeight * index) / 2;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(chartWidth - padding.right, y);
      ctx.stroke();
    }

    ctx.beginPath();
    ctx.moveTo(points[0].x, chartHeight - padding.bottom);
    points.forEach((point) => {
      ctx.lineTo(point.x, point.y);
    });
    ctx.lineTo(points[points.length - 1].x, chartHeight - padding.bottom);
    ctx.closePath();
    ctx.setFillStyle("rgba(31, 107, 82, 0.10)");
    ctx.fill();

    ctx.beginPath();
    points.forEach((point, index) => {
      if (index === 0) {
        ctx.moveTo(point.x, point.y);
      } else {
        ctx.lineTo(point.x, point.y);
      }
    });
    ctx.setStrokeStyle("#1f6b52");
    ctx.setLineWidth(3);
    ctx.setLineJoin("round");
    ctx.setLineCap("round");
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(selectedPoint.x, padding.top);
    ctx.lineTo(selectedPoint.x, chartHeight - padding.bottom);
    ctx.setStrokeStyle("rgba(31, 107, 82, 0.28)");
    ctx.setLineWidth(1);
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(selectedPoint.x, selectedPoint.y, 4, 0, Math.PI * 2);
    ctx.setFillStyle("#1f6b52");
    ctx.fill();

    ctx.beginPath();
    ctx.arc(selectedPoint.x, selectedPoint.y, 7, 0, Math.PI * 2);
    ctx.setStrokeStyle("rgba(31, 107, 82, 0.16)");
    ctx.setLineWidth(4);
    ctx.stroke();

    ctx.draw();
  },

  onHistoryPeriodTap(event) {
    const period = event.currentTarget.dataset.period;
    if (!period || period === this.data.historyPeriod) {
      return;
    }
    this.setData({
      historyPeriod: period,
    });
    this.loadFundHistory(this.data.fundCode, period);
  },

  onHistoryChartTap(event) {
    const { historyItems, chartWidth, chartHeight } = this.data;
    if (!historyItems.length) {
      return;
    }

    const touch = event.detail;
    const x = touch.x || 0;
    const paddingLeft = 12;
    const paddingRight = 12;
    const plotWidth = chartWidth - paddingLeft - paddingRight;
    const ratio = Math.max(0, Math.min(1, (x - paddingLeft) / Math.max(plotWidth, 1)));
    const index = Math.round(ratio * Math.max(historyItems.length - 1, 0));
    const item = historyItems[index];
    const tooltipPosition = buildTooltipPosition(index, historyItems.length, chartWidth, chartHeight);
    this.setData({
      selectedHistoryPoint: {
        date: item.date || "--",
        nav: formatSignedRate(item.changePct),
        left: tooltipPosition.left,
        top: tooltipPosition.top,
      },
    });
    this.drawHistoryChart();
  },
});
