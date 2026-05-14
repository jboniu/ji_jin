const { getCurrentUserId, request } = require("../../utils/api");

Page({
  data: {
    userId: "",
    form: {
      oldPassword: "",
      newPassword: "",
      confirmPassword: "",
    },
    saving: false,
    message: "请输入旧密码和新密码",
  },

  onLoad(query) {
    const nextUserId = (query.userId || getCurrentUserId() || "").trim();
    this.setData({
      userId: nextUserId,
      message: nextUserId ? "请输入旧密码和新密码" : "未找到当前用户，请重新登录后再试",
    });
  },

  handleOldPasswordInput(event) {
    this.setData({
      "form.oldPassword": event.detail.value,
    });
  },

  handleNewPasswordInput(event) {
    this.setData({
      "form.newPassword": event.detail.value,
    });
  },

  handleConfirmPasswordInput(event) {
    this.setData({
      "form.confirmPassword": event.detail.value,
    });
  },

  async handleSubmit() {
    if (this.data.saving) {
      return;
    }

    const userId = this.data.userId;
    const oldPassword = this.data.form.oldPassword || "";
    const newPassword = this.data.form.newPassword || "";
    const confirmPassword = this.data.form.confirmPassword || "";

    if (!userId) {
      wx.showModal({
        title: "修改失败",
        content: "未找到当前用户，请重新登录后再试",
        showCancel: false,
      });
      return;
    }

    if (!oldPassword || !newPassword || !confirmPassword) {
      wx.showModal({
        title: "修改失败",
        content: "请完整填写旧密码、新密码和确认密码",
        showCancel: false,
      });
      return;
    }

    if (newPassword !== confirmPassword) {
      wx.showModal({
        title: "修改失败",
        content: "两次输入的新密码不一致",
        showCancel: false,
      });
      return;
    }

    this.setData({ saving: true });
    wx.showLoading({ title: "提交中", mask: true });
    try {
      await request(`/users/${userId}/change-password`, {
        method: "POST",
        header: {
          "content-type": "application/json",
        },
        data: {
          old_password: oldPassword,
          new_password: newPassword,
        },
      });
      wx.hideLoading();
      wx.showToast({
        title: "修改成功",
        icon: "success",
        duration: 1200,
      });
      this.setData({
        message: "密码修改成功，下次登录请使用新密码",
        form: {
          oldPassword: "",
          newPassword: "",
          confirmPassword: "",
        },
      });
      setTimeout(() => {
        wx.navigateBack({
          delta: 1,
        });
      }, 1200);
    } catch (error) {
      wx.hideLoading();
      wx.showModal({
        title: "修改失败",
        content: error.message || "请检查后端服务",
        showCancel: false,
      });
    } finally {
      this.setData({ saving: false });
    }
  },
});
