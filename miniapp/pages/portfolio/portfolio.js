const { getCurrentUserId, isLoggedIn, request } = require("../../utils/api");
const { shouldRefreshPage } = require("../../utils/page-refresh");

const FILTER_OPTIONS = [
  { key: "all", label: "全部" },
  { key: "stock", label: "偏股型" },
  { key: "bond", label: "偏债型" },
  { key: "index", label: "指数型" },
  { key: "gold", label: "黄金" },
  { key: "global", label: "全球" },
];

function normalizeTrendPoints(items) {
  return (Array.isArray(items) ? items : [])
    .map((item) => ({
      date: item.date || "",
      close: Number(item.close),
    }))
    .filter((item) => item.date && !Number.isNaN(item.close));
}

function formatSignedRate(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return "--";
  }
  const number = Number(value);
  return `${number >= 0 ? "+" : ""}${number.toFixed(2)}%`;
}

function resolveIntradayChangeText(item) {
  if (item && item.intraday_change_text) {
    return item.intraday_change_text;
  }
  return formatSignedRate(item ? item.daily_change_rate : null);
}

function resolveIntradayChangeLabel(item) {
  return (item && item.intraday_change_label) || "当前涨幅";
}

function resolveTodayChangeText(item) {
  if (item && item.today_change_text) {
    return item.today_change_text;
  }
  return resolveIntradayChangeText(item);
}

function resolveTodayChangeLabel(item) {
  return (item && item.today_change_label) || resolveIntradayChangeLabel(item);
}

function resolveUpdateMeta(item) {
  return {
    label: (item && item.today_change_time_label) || "更新时间",
    text: (item && item.today_change_time_text) || "暂无时间",
  };
}

function buildTrendSummary(points) {
  if (!Array.isArray(points) || points.length < 2) {
    return {
      trendLabel: "本月走势",
      trendValue: "--",
      trendClassName: "",
    };
  }

  const first = points[0].close;
  const last = points[points.length - 1].close;
  if (!first) {
    return {
      trendLabel: "本月走势",
      trendValue: "--",
      trendClassName: "",
    };
  }

  const changeRate = ((last - first) / first) * 100;
  const trendValue = `${changeRate >= 0 ? "+" : ""}${changeRate.toFixed(2)}%`;

  if (changeRate > 0.2) {
    return {
      trendLabel: "本月主题",
      trendValue,
      trendClassName: "trend-up",
    };
  }
  if (changeRate < -0.2) {
    return {
      trendLabel: "本月主题",
      trendValue,
      trendClassName: "trend-down",
    };
  }
  return {
    trendLabel: "本月主题",
    trendValue,
    trendClassName: "trend-flat",
  };
}

function parsePercent(value) {
  const matched = String(value || "").match(/-?\d+(\.\d+)?/);
  return matched ? Number(matched[0]) : 0;
}

function resolveChangeSortValue(item) {
  const directValue = Number(item && item.changeRateValue);
  if (!Number.isNaN(directValue)) {
    return directValue;
  }
  return parsePercent(item && item.displayNav);
}

function resolveChangeToneClass(changeRateValue, displayText) {
  const numericValue = Number(changeRateValue);
  if (!Number.isNaN(numericValue)) {
    if (numericValue > 0) {
      return "tone-up";
    }
    if (numericValue < 0) {
      return "tone-down";
    }
    return "tone-flat";
  }

  const parsed = parsePercent(displayText);
  if (parsed > 0) {
    return "tone-up";
  }
  if (parsed < 0) {
    return "tone-down";
  }
  return "tone-flat";
}

function getFundBucket(item) {
  const source = `${item.fundName || ""}${item.category || ""}${item.note || ""}`;
  if (/全球|海外|纳斯达克|恒生|标普|qdii/i.test(source)) {
    return "global";
  }
  if (/黄金/i.test(source)) {
    return "gold";
  }
  if (/债/i.test(source)) {
    return "bond";
  }
  if (/指数|ETF|LOF/i.test(source)) {
    return "index";
  }
  return "stock";
}

function formatHoldingAmount(value) {
  const numericValue = Number(value);
  if (value == null || Number.isNaN(numericValue)) {
    return "--";
  }
  return numericValue.toLocaleString("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
}

function filterPortfolioItems(items, filterKey) {
  if (!filterKey || filterKey === "all") {
    return items.slice();
  }
  return items.filter((item) => item.filterBucket === filterKey);
}

function sortPortfolioItems(items, sortKey, sortDirection) {
  const nextItems = (items || []).slice();
  if (sortKey === "holding") {
    nextItems.sort((left, right) => Number(right.holdingAmountRaw || 0) - Number(left.holdingAmountRaw || 0));
  } else if (sortKey === "change") {
    nextItems.sort((left, right) => resolveChangeSortValue(right) - resolveChangeSortValue(left));
  }

  if (sortDirection === "asc") {
    nextItems.reverse();
  }
  return nextItems;
}

Page({
  data: {
    summary: {
      total: 0,
      totalHoldingAmount: "--",
      estimatedCount: 0,
      officialCount: 0,
    },
    rawItems: [],
    items: [],
    activeFilter: "all",
    filterOptions: FILTER_OPTIONS,
    showFilterOptions: false,
    sortKey: "default",
    amountSortDirection: "desc",
    changeSortDirection: "asc",
    isLoading: true,
    isRefreshing: false,
    loadError: "",
    trendCanvasWidth: 82,
    trendCanvasHeight: 42,
  },

  hasLoadedQuotes: false,

  onShow() {
    if (!isLoggedIn()) {
      wx.navigateTo({
        url: "/pages/login/login",
      });
      return;
    }

    this.setupTrendCanvasSize();
    if (shouldRefreshPage("portfolio")) {
      this.loadQuotes();
      return;
    }
    this.drawTrendCharts();
  },

  onPullDownRefresh() {
    this.loadQuotes(true);
  },

  setupTrendCanvasSize() {
    const systemInfo = wx.getSystemInfoSync();
    const rpxUnit = systemInfo.windowWidth / 750;
    this.setData({
      trendCanvasWidth: Math.floor(120 * rpxUnit),
      trendCanvasHeight: Math.floor(58 * rpxUnit),
    });
  },

  getEffectiveSortState(nextData = {}) {
    const sortKey = nextData.sortKey || this.data.sortKey;
    const amountSortDirection = nextData.amountSortDirection || this.data.amountSortDirection;
    const changeSortDirection = nextData.changeSortDirection || this.data.changeSortDirection;

    if (sortKey === "holding") {
      return {
        sortKey,
        sortDirection: amountSortDirection,
      };
    }
    if (sortKey === "change") {
      return {
        sortKey,
        sortDirection: changeSortDirection,
      };
    }
    return {
      sortKey: "default",
      sortDirection: "desc",
    };
  },

  applyViewState(nextData = {}) {
    const activeFilter = nextData.activeFilter || this.data.activeFilter;
    const filteredItems = filterPortfolioItems(this.data.rawItems, activeFilter);
    const sortState = this.getEffectiveSortState(nextData);
    const sortedItems = sortPortfolioItems(filteredItems, sortState.sortKey, sortState.sortDirection).map(
      (item, index) => ({
        ...item,
        trendCanvasId: `trend-${item.fundCode || "fund"}-${index}`,
      })
    );

    this.setData(
      {
        ...nextData,
        items: sortedItems,
      },
      () => {
        this.drawTrendCharts();
      }
    );
  },

  async loadQuotes(fromPullDown = false) {
    const userId = getCurrentUserId();
    this.setData({
      isLoading: !this.hasLoadedQuotes && !fromPullDown,
      isRefreshing: fromPullDown,
      loadError: "",
    });

    try {
      const [quoteOutcome, trendOutcome] = await Promise.allSettled([
        request(`/users/${userId}/quotes`),
        request(`/users/${userId}/quote-trends?period=week&count=8`),
      ]);

      if (quoteOutcome.status !== "fulfilled") {
        throw quoteOutcome.reason || new Error("持仓行情加载失败");
      }

      const result = quoteOutcome.value || {};
      const trendResult = trendOutcome.status === "fulfilled" ? trendOutcome.value || {} : {};
      const rawItems = result.items || [];
      const trendMap = {};

      (trendResult.items || []).forEach((item) => {
        trendMap[item.fund_code] = normalizeTrendPoints(item.items || []);
      });

      const items = rawItems.map((item) => {
        const trendPoints = trendMap[item.fund_code || ""] || [];
        const trendSummary = buildTrendSummary(trendPoints);
        const updateMeta = resolveUpdateMeta(item);
        const displayNav = resolveTodayChangeText(item);
        const note = item.note || "";

        return {
          fundName: item.fund_name || "未命名基金",
          fundCode: item.fund_code || "",
          holdingAmountRaw: item.holding_amount,
          holdingAmount:
            item.holding_amount == null || Number.isNaN(Number(item.holding_amount))
              ? "--"
              : Number(item.holding_amount).toLocaleString("en-US", {
                  minimumFractionDigits: 0,
                  maximumFractionDigits: 2,
                }),
          category: item.category || "",
          note,
          displayNavLabel: resolveTodayChangeLabel(item),
          displayNav,
          changeRateValue: item && item.today_change_rate,
          changeToneClass: resolveChangeToneClass(item && item.today_change_rate, displayNav),
          updatedAtLabel: updateMeta.label,
          updatedAt: updateMeta.text,
          trendPoints,
          trendLabel: trendSummary.trendLabel,
          trendValue: trendSummary.trendValue,
          trendClassName: trendSummary.trendClassName,
          filterBucket: getFundBucket({
            fundName: item.fund_name || "",
            category: item.category || "",
            note,
          }),
        };
      });

      const totalHoldingAmount = items.reduce((sum, item) => sum + Number(item.holdingAmountRaw || 0), 0);
      const estimatedCount = rawItems.filter((item) => item.display_nav_type === "estimated").length;
      const officialCount = rawItems.filter((item) => item.display_nav_type === "official").length;

      this.setData(
        {
          summary: {
            total: result.total || 0,
            totalHoldingAmount: totalHoldingAmount.toLocaleString("en-US", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            }),
            estimatedCount,
            officialCount,
          },
          rawItems: items,
          isLoading: false,
          isRefreshing: false,
        },
        () => {
          this.hasLoadedQuotes = true;
          this.applyViewState();
        }
      );

      if (trendOutcome.status !== "fulfilled" && fromPullDown) {
        wx.showToast({
          title: "走势预览刷新失败",
          icon: "none",
        });
      }
    } catch (error) {
      if (fromPullDown && this.hasLoadedQuotes) {
        this.setData({
          isLoading: false,
          isRefreshing: false,
        });
        wx.showToast({
          title: error.message || "刷新失败，请稍后重试",
          icon: "none",
        });
        return;
      }

      this.setData({
        summary: {
          total: 0,
          totalHoldingAmount: "--",
          estimatedCount: 0,
          officialCount: 0,
        },
        rawItems: [],
        items: [],
        isLoading: false,
        isRefreshing: false,
        loadError: error.message || "持仓行情加载失败",
      });
    } finally {
      if (fromPullDown) {
        wx.stopPullDownRefresh();
      }
    }
  },

  drawTrendCharts() {
    const { items, trendCanvasWidth, trendCanvasHeight } = this.data;
    items.forEach((item) => {
      this.drawSingleTrendChart(item.trendCanvasId, item.trendPoints, trendCanvasWidth, trendCanvasHeight);
    });
  },

  drawSingleTrendChart(canvasId, points, width, height) {
    const ctx = wx.createCanvasContext(canvasId, this);
    ctx.clearRect(0, 0, width, height);

    if (!Array.isArray(points) || points.length < 2) {
      ctx.draw();
      return;
    }

    const padding = 4;
    const values = points.map((item) => item.close);
    let min = Math.min(...values);
    let max = Math.max(...values);
    if (min === max) {
      min -= 0.01;
      max += 0.01;
    }

    const drawPoints = points.map((item, index) => {
      const x = padding + ((width - padding * 2) * index) / Math.max(points.length - 1, 1);
      const y = padding + ((max - item.close) / (max - min)) * (height - padding * 2);
      return { x, y };
    });

    ctx.beginPath();
    ctx.moveTo(drawPoints[0].x, height - padding);
    drawPoints.forEach((point) => {
      ctx.lineTo(point.x, point.y);
    });
    ctx.lineTo(drawPoints[drawPoints.length - 1].x, height - padding);
    ctx.closePath();
    ctx.setFillStyle("rgba(56, 142, 102, 0.10)");
    ctx.fill();

    ctx.beginPath();
    drawPoints.forEach((point, index) => {
      if (index === 0) {
        ctx.moveTo(point.x, point.y);
      } else {
        ctx.lineTo(point.x, point.y);
      }
    });
    ctx.setStrokeStyle("#3b916d");
    ctx.setLineWidth(2);
    ctx.setLineJoin("round");
    ctx.setLineCap("round");
    ctx.stroke();

    const lastPoint = drawPoints[drawPoints.length - 1];
    ctx.beginPath();
    ctx.arc(lastPoint.x, lastPoint.y, 3, 0, Math.PI * 2);
    ctx.setFillStyle("#2e8a63");
    ctx.fill();

    ctx.draw();
  },

  buildLocalPortfolioItem(position, existingItem = {}) {
    const trendPoints = Array.isArray(existingItem.trendPoints) ? existingItem.trendPoints : [];
    const trendSummary = buildTrendSummary(trendPoints);
    const note = position.note || "";
    const holdingAmountRaw = position.holding_amount;
    const displayNav = existingItem.displayNav || "--";
    const displayNavLabel = existingItem.displayNavLabel || "????";
    const changeRateValue = existingItem.changeRateValue;

    return {
      ...existingItem,
      fundName: position.fund_name || existingItem.fundName || "?????",
      fundCode: position.fund_code || existingItem.fundCode || "",
      holdingAmountRaw,
      holdingAmount: formatHoldingAmount(holdingAmountRaw),
      category: position.category || "",
      note,
      displayNav,
      displayNavLabel,
      changeRateValue,
      changeToneClass: resolveChangeToneClass(changeRateValue, displayNav),
      updatedAtLabel: existingItem.updatedAtLabel || "????",
      updatedAt: existingItem.updatedAt || "???",
      trendPoints,
      trendLabel: trendSummary.trendLabel,
      trendValue: trendSummary.trendValue,
      trendClassName: trendSummary.trendClassName,
      filterBucket: getFundBucket({
        fundName: position.fund_name || existingItem.fundName || "",
        category: position.category || "",
        note,
      }),
    };
  },

  syncLocalPortfolio(rawItems) {
    const estimatedCount = this.data.summary.estimatedCount || 0;
    const officialCount = this.data.summary.officialCount || 0;
    const totalHoldingAmount = rawItems.reduce((sum, item) => sum + Number(item.holdingAmountRaw || 0), 0);

    this.setData(
      {
        summary: {
          total: rawItems.length,
          totalHoldingAmount: totalHoldingAmount.toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          }),
          estimatedCount,
          officialCount,
        },
        rawItems,
      },
      () => {
        this.applyViewState();
      }
    );
  },

  upsertLocalPosition(position, originalFundCode = "") {
    const rawItems = (this.data.rawItems || []).slice();
    const targetCode = (originalFundCode || position.fund_code || "").trim();
    const targetName = (position.fund_name || "").trim();
    const matchIndex = rawItems.findIndex(
      (item) =>
        (targetCode && item.fundCode === targetCode) ||
        (!targetCode && targetName && item.fundName === targetName)
    );
    const existingItem = matchIndex >= 0 ? rawItems[matchIndex] : null;
    const nextItem = this.buildLocalPortfolioItem(position, existingItem || {});

    if (matchIndex >= 0) {
      rawItems.splice(matchIndex, 1, nextItem);
    } else {
      rawItems.unshift(nextItem);
    }
    this.syncLocalPortfolio(rawItems);
  },

  removeLocalPosition(fundCode = "") {
    const nextItems = (this.data.rawItems || []).filter((item) => item.fundCode !== fundCode);
    this.syncLocalPortfolio(nextItems);
  },

  handleOpenImportImage() {
    wx.navigateTo({
      url: "/pages/import-image/import-image",
    });
  },

  handleCreatePosition() {
    wx.navigateTo({
      url: "/pages/position-form/position-form",
    });
  },

  handleOpenFundDetail(event) {
    const fundCode = event.currentTarget.dataset.fundCode;
    const fundName = event.currentTarget.dataset.fundName || "";
    wx.navigateTo({
      url: `/pages/fund-detail/fund-detail?fundCode=${fundCode}&fundName=${fundName}`,
    });
  },

  handleEditPosition(event) {
    const fundCode = event.currentTarget.dataset.fundCode;
    const fundName = event.currentTarget.dataset.fundName || "";
    const category = event.currentTarget.dataset.category || "";
    const holdingAmount = event.currentTarget.dataset.holdingAmount || "";
    const note = event.currentTarget.dataset.note || "";

    wx.navigateTo({
      url:
        `/pages/position-form/position-form?fundCode=${fundCode}` +
        `&fundName=${encodeURIComponent(fundName)}` +
        `&category=${encodeURIComponent(category)}` +
        `&holdingAmount=${holdingAmount}` +
        `&note=${encodeURIComponent(note)}`,
    });
  },

  handleResetSort() {
    this.applyViewState({
      sortKey: "default",
    });
  },

  handleHoldingSort() {
    const nextDirection =
      this.data.sortKey === "holding" && this.data.amountSortDirection === "desc" ? "asc" : "desc";
    this.applyViewState({
      sortKey: "holding",
      amountSortDirection: nextDirection,
    });
  },

  handleChangeSort() {
    const nextDirection =
      this.data.sortKey === "change" && this.data.changeSortDirection === "desc" ? "asc" : "desc";
    this.applyViewState({
      sortKey: "change",
      changeSortDirection: nextDirection,
    });
  },

  handleToggleFilterPanel() {
    this.setData({
      showFilterOptions: !this.data.showFilterOptions,
    });
  },

  handleFilterChange(event) {
    const nextFilter = event.currentTarget.dataset.filterKey;
    if (!nextFilter) {
      return;
    }
    this.applyViewState({
      activeFilter: nextFilter,
      showFilterOptions: false,
    });
  },
});
