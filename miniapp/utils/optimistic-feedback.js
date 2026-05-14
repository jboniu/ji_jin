function showQueuedToast(title = "已提交，后台同步中", duration = 1200) {
  wx.showToast({
    title,
    icon: "none",
    duration,
  });
}

function showSyncFailedToast(title = "同步失败，请下拉刷新", duration = 1800) {
  wx.showToast({
    title,
    icon: "none",
    duration,
  });
}

module.exports = {
  showQueuedToast,
  showSyncFailedToast,
};
