const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000/api";

function getAppSafe() {
  try {
    return getApp();
  } catch (error) {
    return null;
  }
}

function getBaseUrl() {
  const app = getAppSafe();
  return (app && app.globalData && app.globalData.apiBaseUrl) || DEFAULT_API_BASE_URL;
}

function buildUrl(path) {
  return `${getBaseUrl()}${path}`;
}

function request(path, options = {}) {
  return new Promise((resolve, reject) => {
    const app = getAppSafe();
    const authToken = (app && app.globalData && app.globalData.authToken) || "";
    const header = Object.assign({}, options.header || {});

    if (authToken) {
      header.Authorization = `Bearer ${authToken}`;
    }

    wx.request({
      url: buildUrl(path),
      method: options.method || "GET",
      data: options.data || {},
      header,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
          return;
        }
        reject(new Error((res.data && res.data.detail) || `Request failed: ${res.statusCode}`));
      },
      fail: (error) => {
        reject(new Error(error.errMsg || error.message || "Network request failed"));
      },
    });
  });
}

function getCurrentUserId() {
  const app = getAppSafe();
  return (app && app.globalData && app.globalData.currentUserId) || wx.getStorageSync("currentUserId") || "";
}

function setCurrentUserId(userId) {
  const nextUserId = userId || "";
  const app = getAppSafe();
  if (app && app.globalData) {
    app.globalData.currentUserId = nextUserId;
  }
  wx.setStorageSync("currentUserId", nextUserId);
}

function setAuthSession(session) {
  const token = session.token || "";
  const userId = session.user_id || "";
  const owner = session.owner || "";
  const app = getAppSafe();

  if (app && app.globalData) {
    app.globalData.authToken = token;
    app.globalData.currentUserId = userId;
    app.globalData.currentOwner = owner;
  }

  wx.setStorageSync("authToken", token);
  wx.setStorageSync("currentUserId", userId);
  wx.setStorageSync("currentOwner", owner);
}

function clearAuthSession() {
  const app = getAppSafe();
  if (app && app.globalData) {
    app.globalData.authToken = "";
    app.globalData.currentUserId = "";
    app.globalData.currentOwner = "";
  }

  wx.removeStorageSync("authToken");
  wx.removeStorageSync("currentUserId");
  wx.removeStorageSync("currentOwner");
}

function isLoggedIn() {
  const app = getAppSafe();
  const appHasSession = Boolean(app && app.globalData && app.globalData.authToken && app.globalData.currentUserId);
  if (appHasSession) {
    return true;
  }
  return Boolean(wx.getStorageSync("authToken") && wx.getStorageSync("currentUserId"));
}

module.exports = {
  request,
  getBaseUrl,
  getCurrentUserId,
  setCurrentUserId,
  setAuthSession,
  clearAuthSession,
  isLoggedIn,
};
