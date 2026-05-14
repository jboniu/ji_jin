const STORAGE_KEY = "pending_report_task";

function savePendingReportTask(task) {
  if (!task || !task.taskId || !task.userId) {
    return;
  }
  wx.setStorageSync(STORAGE_KEY, {
    taskId: task.taskId,
    userId: task.userId,
    createdAt: task.createdAt || Date.now(),
  });
}

function getPendingReportTask() {
  return wx.getStorageSync(STORAGE_KEY) || null;
}

function hasPendingReportTask() {
  const task = getPendingReportTask();
  return !!(task && task.taskId && task.userId);
}

function clearPendingReportTask() {
  wx.removeStorageSync(STORAGE_KEY);
}

module.exports = {
  savePendingReportTask,
  getPendingReportTask,
  hasPendingReportTask,
  clearPendingReportTask,
};
