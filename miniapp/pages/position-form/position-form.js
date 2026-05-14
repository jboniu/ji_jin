const { getCurrentUserId, isLoggedIn, request } = require("../../utils/api");
const { markPagesDirty } = require("../../utils/page-refresh");

Page({
  data: {
    userId: "",
    isEdit: false,
    originalFundCode: "",
    saving: false,
    form: {
      fundCode: "",
      fundName: "",
      category: "",
      holdingAmount: "",
      note: "",
    },
  },

  onLoad(options) {
    if (!isLoggedIn()) {
      wx.navigateTo({
        url: "/pages/login/login",
      });
      return;
    }

    const userId = getCurrentUserId();
    const originalFundCode = (options.fundCode || "").trim();
    this.setData({
      userId,
      isEdit: Boolean(originalFundCode),
      originalFundCode,
      form: {
        fundCode: originalFundCode,
        fundName: decodeURIComponent(options.fundName || ""),
        category: decodeURIComponent(options.category || ""),
        holdingAmount: options.holdingAmount || "",
        note: decodeURIComponent(options.note || ""),
      },
    });
  },

  handleInput(event) {
    const field = event.currentTarget.dataset.field;
    if (!field) {
      return;
    }
    this.setData({
      [`form.${field}`]: event.detail.value,
    });
  },

  buildPayload() {
    return {
      fund_code: (this.data.form.fundCode || "").trim(),
      fund_name: (this.data.form.fundName || "").trim(),
      category: (this.data.form.category || "").trim(),
      holding_amount: Number(this.data.form.holdingAmount || 0),
      note: (this.data.form.note || "").trim(),
    };
  },

  validatePayload(payload) {
    if (!payload.fund_code) {
      return "请输入基金代码";
    }
    if (!payload.fund_name) {
      return "请输入基金名称";
    }
    if (Number.isNaN(payload.holding_amount) || payload.holding_amount < 0) {
      return "持仓金额必须是大于等于 0 的数字";
    }
    return "";
  },

  async handleSave() {
    if (this.data.saving) {
      return;
    }

    const payload = this.buildPayload();
    const validationMessage = this.validatePayload(payload);
    if (validationMessage) {
      wx.showModal({
        title: "保存失败",
        content: validationMessage,
        showCancel: false,
      });
      return;
    }

    this.setData({ saving: true });
    wx.showLoading({ title: "保存中", mask: true });

    try {
      const path = this.data.isEdit
        ? `/users/${this.data.userId}/positions/${this.data.originalFundCode}`
        : `/users/${this.data.userId}/positions`;
      const method = this.data.isEdit ? "PUT" : "POST";
      await request(path, {
        method,
        header: {
          "content-type": "application/json",
        },
        data: payload,
      });

      wx.hideLoading();
      wx.showToast({
        title: "保存成功",
        icon: "success",
        duration: 1200,
      });
      markPagesDirty(["portfolio", "home"]);
      setTimeout(() => {
        wx.navigateBack({
          delta: 1,
        });
      }, 1200);
    } catch (error) {
      wx.hideLoading();
      wx.showModal({
        title: "保存失败",
        content: error.message || "请检查后端服务",
        showCancel: false,
      });
    } finally {
      this.setData({ saving: false });
    }
  },

  handleDelete() {
    if (!this.data.isEdit || this.data.saving) {
      return;
    }

    wx.showModal({
      title: "删除持仓",
      content: "确认删除这条持仓吗？",
      success: async (result) => {
        if (!result.confirm) {
          return;
        }

        this.setData({ saving: true });
        wx.showLoading({ title: "删除中", mask: true });
        try {
          await request(`/users/${this.data.userId}/positions/${this.data.originalFundCode}`, {
            method: "DELETE",
          });
          wx.hideLoading();
          wx.showToast({
            title: "删除成功",
            icon: "success",
            duration: 1200,
          });
          markPagesDirty(["portfolio", "home"]);
          setTimeout(() => {
            wx.navigateBack({
              delta: 1,
            });
          }, 1200);
        } catch (error) {
          wx.hideLoading();
          wx.showModal({
            title: "删除失败",
            content: error.message || "请检查后端服务",
            showCancel: false,
          });
        } finally {
          this.setData({ saving: false });
        }
      },
    });
  },
});
