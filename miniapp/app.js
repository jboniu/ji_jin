App({
  globalData: {
    currentUserId: "",
    currentOwner: "",
    authToken: "",
    apiBaseUrl: "http://127.0.0.1:8000/api",
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
