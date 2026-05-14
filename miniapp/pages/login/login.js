const { isLoggedIn, request, setAuthSession } = require("../../utils/api");

Page({
  data: {
    username: "",
    password: "",
    loading: false,
    errorText: "",
    tips: "测试账号：user_01 / user_02 / user_03，默认密码 123456",
  },

  onShow() {
    if (isLoggedIn()) {
      wx.switchTab({
        url: "/pages/home/home",
      });
    }
  },

  handleUsernameInput(event) {
    this.setData({
      username: event.detail.value || "",
      errorText: "",
    });
  },

  handlePasswordInput(event) {
    this.setData({
      password: event.detail.value || "",
      errorText: "",
    });
  },

  async handleLogin() {
    const username = String(this.data.username || "").trim();
    const password = String(this.data.password || "");

    if (!username || !password) {
      this.setData({
        errorText: "请输入账号和密码",
      });
      return;
    }

    this.setData({
      loading: true,
      errorText: "",
    });

    try {
      const session = await request("/auth/login", {
        method: "POST",
        data: {
          username,
          password,
        },
      });
      setAuthSession(session);
      wx.showToast({
        title: "登录成功",
        icon: "success",
        duration: 1200,
      });
      setTimeout(() => {
        wx.switchTab({
          url: "/pages/home/home",
        });
      }, 200);
    } catch (error) {
      this.setData({
        errorText: error.message || "登录失败，请稍后重试",
      });
    } finally {
      this.setData({
        loading: false,
      });
    }
  },
});
