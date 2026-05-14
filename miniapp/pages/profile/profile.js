const { getCurrentUserId, request } = require("../../utils/api");
const { markPagesDirty, shouldRefreshPage } = require("../../utils/page-refresh");
const { showQueuedToast, showSyncFailedToast } = require("../../utils/optimistic-feedback");

Page({
  data: {
    userId: "",
    persistedOwner: "",
    persistedEmailTo: [],
    form: {
      owner: "",
      emailText: "",
      subscribeEmailReports: false,
    },
    confirmedSubscribeEmailReports: false,
    pendingSubscribeValue: null,
    savingSubscription: false,
    saving: false,
    message: "正在加载用户资料",
  },

  hasLoadedProfile: false,

  onShow() {
    if (shouldRefreshPage("profile")) {
      this.loadProfile(this.hasLoadedProfile);
    }
  },

  async loadProfile(silent = false) {
    const userId = getCurrentUserId();
    if (!silent) {
      this.setData({
        message: "正在加载用户资料",
      });
    }

    try {
      const user = await request(`/users/${userId}`);
      const subscribed = !!user.subscribe_email_reports;
      this.hasLoadedProfile = true;
      this.setData({
        userId,
        persistedOwner: user.owner || "",
        persistedEmailTo: user.email_to || [],
        confirmedSubscribeEmailReports: subscribed,
        pendingSubscribeValue: null,
        form: {
          owner: user.owner || "",
          emailText: (user.email_to || []).join(", "),
          subscribeEmailReports: subscribed,
        },
        message: "",
      });
    } catch (error) {
      this.setData({
        userId,
        message: error.message || "用户资料加载失败",
      });
    }
  },

  handleOwnerInput(event) {
    this.setData({
      "form.owner": event.detail.value,
    });
  },

  handleEmailInput(event) {
    this.setData({
      "form.emailText": event.detail.value,
    });
  },

  async flushSubscribePreference() {
    if (this.data.savingSubscription) {
      return;
    }

    while (this.data.pendingSubscribeValue !== null) {
      const nextValue = !!this.data.pendingSubscribeValue;
      this.setData({
        savingSubscription: true,
        pendingSubscribeValue: null,
      });

      try {
        await request(`/users/${this.data.userId}`, {
          method: "PUT",
          header: {
            "content-type": "application/json",
          },
          data: {
            owner: this.data.persistedOwner,
            email_to: this.data.persistedEmailTo,
            subscribe_email_reports: nextValue,
          },
        });
        this.setData({
          confirmedSubscribeEmailReports: nextValue,
        });
        markPagesDirty(["home", "reports", "profile"]);
        wx.showToast({
          title: nextValue ? "已开启邮件订阅" : "已关闭邮件订阅",
          icon: "none",
        });
      } catch (error) {
        const confirmedValue = !!this.data.confirmedSubscribeEmailReports;
        this.setData({
          "form.subscribeEmailReports": confirmedValue,
          pendingSubscribeValue: null,
        });
        wx.showModal({
          title: "保存失败",
          content: error.message || "请稍后重试",
          showCancel: false,
        });
        break;
      } finally {
        this.setData({
          savingSubscription: false,
        });
      }
    }
  },

  handleSubscribeChange(event) {
    const nextValue = !!event.detail.value;
    this.setData({
      "form.subscribeEmailReports": nextValue,
      pendingSubscribeValue: nextValue,
    });
    this.flushSubscribePreference();
  },

  handleGoChangePassword() {
    wx.navigateTo({
      url: `/pages/change-password/change-password?userId=${this.data.userId}`,
    });
  },

  async handleSave() {
    if (this.data.saving) {
      return;
    }

    const owner = (this.data.form.owner || "").trim();
    if (!owner) {
      wx.showModal({
        title: "保存失败",
        content: "用户名不能为空",
        showCancel: false,
      });
      return;
    }

    const emailTo = (this.data.form.emailText || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);

    this.setData({
      saving: true,
      message: "资料已更新，正在后台同步",
    });
    markPagesDirty(["home", "reports"]);
    showQueuedToast("已保存，后台同步中");

    setTimeout(() => {
      wx.switchTab({
        url: "/pages/home/home",
      });
    }, 40);

    try {
      await request(`/users/${this.data.userId}`, {
        method: "PUT",
        header: {
          "content-type": "application/json",
        },
        data: {
          owner,
          email_to: emailTo,
          subscribe_email_reports: !!this.data.confirmedSubscribeEmailReports,
        },
      });
      this.setData({
        persistedOwner: owner,
        persistedEmailTo: emailTo,
        message: "资料已保存",
      });
    } catch (error) {
      markPagesDirty(["home", "profile", "reports"]);
      showSyncFailedToast(error.message || "同步失败，请稍后重试", 2000);
    } finally {
      this.setData({ saving: false });
    }
  },
});
