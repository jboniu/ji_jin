const { clearAuthSession, getCurrentUserId, isLoggedIn, request } = require("../../utils/api");
const { markPagesDirty, shouldRefreshPage } = require("../../utils/page-refresh");
const { savePendingReportTask, getPendingReportTask, clearPendingReportTask } = require("../../utils/report-task-state");

Page({
  data: {
    userName: "加载中",
    currentUserId: "",
    todayStatus: "正在读取首页数据",
    latestReportText: "暂无报告",
    latestReportId: "",
    reportStatusText: "尚未开始生成",
    generating: false,
    isLoading: true,
    loadError: "",
    stats: [
      { label: "持仓基金", value: "--" },
      { label: "历史报告", value: "--" },
      { label: "当前用户", value: "--" },
    ],
    quickActions: [
      { key: "portfolio", title: "查看持仓", subtitle: "进入持仓与净值页" },
      { key: "generate", title: "生成日报", subtitle: "在首页直接生成最新日报" },
      { key: "reports", title: "历史报告", subtitle: "查看已生成报告列表" },
    ],
  },

  hasLoadedHomeData: false,
  checkingPendingTask: false,

  onShow() {
    if (!isLoggedIn()) {
      wx.reLaunch({
        url: "/pages/login/login",
      });
      return;
    }
    if (shouldRefreshPage("home")) {
      this.loadHomeData(false, this.hasLoadedHomeData);
    }
    this.checkPendingReportTask();
  },

  onPullDownRefresh() {
    this.loadHomeData(true, false);
  },

  async loadHomeData(fromPullDown = false, silent = false) {
    const userId = getCurrentUserId();
    this.setData({
      isLoading: silent ? this.data.isLoading : true,
      loadError: "",
      currentUserId: userId,
    });

    try {
      const [user, reports] = await Promise.all([request(`/users/${userId}`), request(`/users/${userId}/reports`)]);
      const latestReport = reports.items && reports.items.length ? reports.items[0] : null;

      this.setData({
        userName: user.owner || userId,
        todayStatus: `当前登录账号：${user.user_id}，持有 ${user.positions ? user.positions.length : 0} 只基金`,
        latestReportText: latestReport ? latestReport.file_name : "暂无历史报告",
        latestReportId: latestReport ? latestReport.report_id : "",
        reportStatusText: latestReport ? "最近报告已同步" : "还没有生成过报告",
        stats: [
          { label: "持仓基金", value: `${user.positions ? user.positions.length : 0}` },
          { label: "历史报告", value: `${reports.total || 0}` },
          { label: "当前用户", value: user.owner || user.user_id || userId },
        ],
        isLoading: false,
      });
      this.hasLoadedHomeData = true;
    } catch (error) {
      this.setData({
        userName: userId,
        todayStatus: "首页数据加载失败，请检查后端服务",
        latestReportText: error.message || "请求失败",
        latestReportId: "",
        reportStatusText: "无法读取报告状态",
        stats: [
          { label: "持仓基金", value: "--" },
          { label: "历史报告", value: "--" },
          { label: "当前用户", value: userId },
        ],
        isLoading: false,
        loadError: error.message || "首页数据加载失败",
      });
    } finally {
      if (fromPullDown) {
        wx.stopPullDownRefresh();
      }
    }
  },

  async checkPendingReportTask() {
    if (this.checkingPendingTask) {
      return;
    }

    const pendingTask = getPendingReportTask();
    if (!pendingTask || !pendingTask.taskId || !pendingTask.userId) {
      return;
    }

    this.checkingPendingTask = true;
    try {
      const task = await request(`/users/${pendingTask.userId}/reports/tasks/${pendingTask.taskId}`);
      if (task.status === "completed" && task.result) {
        clearPendingReportTask();
        this.setData({
          reportStatusText: "报告已生成",
        });
        markPagesDirty(["home", "reports"]);
        wx.showToast({
          title: "报告已生成",
          icon: "success",
          duration: 1500,
        });
        this.loadHomeData(false, true);
      } else if (task.status === "failed") {
        clearPendingReportTask();
        this.setData({
          reportStatusText: "报告生成失败，请稍后重试",
        });
      }
    } catch (error) {
      // Keep pending task for next app visit or manual refresh.
    } finally {
      this.checkingPendingTask = false;
    }
  },

  handleOpenProfile() {
    wx.navigateTo({
      url: "/pages/profile/profile",
    });
  },

  async handleGenerateReport() {
    if (this.data.generating) {
      return;
    }

    const userId = getCurrentUserId();
    this.setData({
      generating: true,
      reportStatusText: "已提交生成任务，请稍后查看报告页",
    });

    try {
      const task = await request(`/users/${userId}/reports/tasks`, {
        method: "POST",
        data: { send_email: false },
      });
      savePendingReportTask({
        taskId: task.task_id,
        userId,
      });
      markPagesDirty(["home", "reports"]);
      wx.showToast({
        title: "生成耗时较长，请稍后查看报告页",
        icon: "none",
        duration: 3000,
      });
    } catch (error) {
      this.setData({
        reportStatusText: "生成任务创建失败",
      });
      wx.showModal({
        title: "提交失败",
        content: error.message || "请稍后重试",
        showCancel: false,
      });
    } finally {
      this.setData({ generating: false });
    }
  },

  handleQuickAction(event) {
    const key = event.currentTarget.dataset.key;
    if (key === "portfolio") {
      wx.switchTab({
        url: "/pages/portfolio/portfolio",
      });
      return;
    }
    if (key === "reports") {
      wx.switchTab({
        url: "/pages/reports/reports",
      });
      return;
    }
    if (key === "generate") {
      this.handleGenerateReport();
    }
  },

  handleOpenLatestReport() {
    if (!this.data.latestReportId) {
      return;
    }
    wx.navigateTo({
      url: `/pages/report-detail/report-detail?reportId=${this.data.latestReportId}`,
    });
  },

  handleLogout() {
    clearAuthSession();
    clearPendingReportTask();
    getApp().globalData.pageRefreshState = {};
    wx.reLaunch({
      url: "/pages/login/login",
    });
  },
});
