const { getCurrentUserId, request } = require("../../utils/api");

function extractBodyHtml(content) {
  if (!content) {
    return "";
  }

  const bodyMatch = content.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
  return bodyMatch ? bodyMatch[1] : content;
}

function normalizeDocHtml(content) {
  if (!content) {
    return "";
  }

  return content.replace(/(<h1[^>]*>[\s\S]*?<\/h1>)\s*(<h1[^>]*>[\s\S]*?<\/h1>)/i, "$2");
}

function formatTimestamp(value) {
  if (value === null || value === undefined || value === "") {
    return "暂无时间";
  }

  const seconds = typeof value === "number" ? value : parseFloat(value);
  if (!Number.isFinite(seconds)) {
    return "暂无时间";
  }

  const date = new Date(Math.floor(seconds * 1000));
  if (Number.isNaN(date.getTime())) {
    return "暂无时间";
  }

  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  const hour = `${date.getHours()}`.padStart(2, "0");
  const minute = `${date.getMinutes()}`.padStart(2, "0");
  const second = `${date.getSeconds()}`.padStart(2, "0");
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
}

Page({
  data: {
    reportId: "",
    fileName: "",
    owner: "",
    fileType: "",
    updatedAtText: "暂无时间",
    content: "正在加载报告详情",
    htmlContent: "",
  },

  onLoad(options) {
    const reportId = decodeURIComponent(options.reportId || "");
    this.setData({ reportId });
    if (reportId) {
      this.loadReportDetail(reportId);
    }
  },

  async loadReportDetail(reportId) {
    const userId = getCurrentUserId();
    try {
      const result = await request(`/users/${userId}/reports/${reportId}`);
      const fileType = result.file_type || "";
      const rawContent = result.content || "报告内容为空";
      this.setData({
        fileName: result.file_name || reportId,
        owner: result.owner || userId,
        fileType,
        updatedAtText: result.updated_at_text || formatTimestamp(result.updated_at),
        content: rawContent,
        htmlContent: fileType === "doc" ? normalizeDocHtml(extractBodyHtml(rawContent)) : "",
      });
    } catch (error) {
      this.setData({
        fileName: reportId,
        owner: userId,
        fileType: "",
        updatedAtText: "暂无时间",
        content: error.message || "报告详情加载失败",
        htmlContent: "",
      });
    }
  },
});
