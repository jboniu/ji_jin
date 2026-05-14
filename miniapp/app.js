const { ACTIVE_ENV, CURRENT_ENV } = require("./config/env");

App({
  globalData: {
    currentUserId: "",
    currentOwner: "",
    authToken: "",
    apiBaseUrl: CURRENT_ENV.apiBaseUrl,
    runtimeEnv: ACTIVE_ENV,
    pageRefreshState: {},
  },

  onLaunch() {
    const savedUserId = wx.getStorageSync("currentUserId");
    const savedOwner = wx.getStorageSync("currentOwner");
    const savedToken = wx.getStorageSync("authToken");

    if (savedUserId) {
      this.globalData.currentUserId = savedUserId;
    }
    if (savedOwner) {
      this.globalData.currentOwner = savedOwner;
    }
    if (savedToken) {
      this.globalData.authToken = savedToken;
    }
  },
});
