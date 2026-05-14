const { getCurrentUserId, isLoggedIn, request } = require("../../utils/api");
const { markPagesDirty, shouldRefreshPage } = require("../../utils/page-refresh");
const { showQueuedToast, showSyncFailedToast } = require("../../utils/optimistic-feedback");

Page({
  data: {
    taskId: "",
    message: "正在读取识别结果",
    items: [],
    loading: true,
    confirming: false,
    loadError: "",
  },

  onLoad(options) {
    const taskId = options.taskId || "";
    this.setData({ taskId });
  },

  onShow() {
    if (!isLoggedIn()) {
      wx.navigateTo({
        url: "/pages/login/login",
      });
      return;
    }
    if (this.data.taskId && shouldRefreshPage(`import-confirm:${this.data.taskId}`)) {
      this.loadTask();
    }
  },

  async loadTask() {
    const userId = getCurrentUserId();
    this.setData({
      loading: true,
      loadError: "",
    });
    try {
      const result = await request(`/users/${userId}/positions/import-tasks/${this.data.taskId}`);
      this.setData({
        message: result.message || "请确认以下识别结果",
        items: result.recognized_positions || [],
        loading: false,
      });
    } catch (error) {
      this.setData({
        loading: false,
        loadError: error.message || "识别结果加载失败",
      });
    }
  },

  getPortfolioPage() {
    const pages = getCurrentPages();
    for (let index = pages.length - 1; index >= 0; index -= 1) {
      const page = pages[index];
      if (page && page.route === "pages/portfolio/portfolio") {
        return page;
      }
    }
    return null;
  },

  syncPortfolioPreview() {
    const portfolioPage = this.getPortfolioPage();
    if (!portfolioPage || typeof portfolioPage.upsertLocalPosition !== "function") {
      return false;
    }

    (this.data.items || []).forEach((item) => {
      portfolioPage.upsertLocalPosition({
        fund_code: item.fund_code || "",
        fund_name: item.fund_name || "",
        category: item.category || "",
        holding_amount: Number(item.holding_amount || 0),
        note: item.note || "",
      });
    });
    return true;
  },

  navigateBackSoon() {
    setTimeout(() => {
      wx.navigateBack({
        delta: 2,
      });
    }, 40);
  },

  async handleConfirmImport() {
    if (this.data.confirming) {
      return;
    }

    const userId = getCurrentUserId();
    this.setData({
      confirming: true,
    });

    const syncedPortfolio = this.syncPortfolioPreview();
    markPagesDirty(syncedPortfolio ? ["home"] : ["portfolio", "home"]);
    showQueuedToast("已导入，后台同步中");
    this.navigateBackSoon();

    try {
      await request(`/users/${userId}/positions/import-tasks/${this.data.taskId}/confirm`, {
        method: "POST",
      });
    } catch (error) {
      markPagesDirty(["portfolio", "home"]);
      showSyncFailedToast(error.message || "导入同步失败，请下拉刷新");
    } finally {
      this.setData({
        confirming: false,
      });
    }
  },
});
