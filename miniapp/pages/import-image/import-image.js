const { getBaseUrl, getCurrentUserId, isLoggedIn } = require("../../utils/api");

Page({
  data: {
    localImagePath: "",
    uploading: false,
    resultText: "请选择一张持仓截图开始导入",
    uploadTaskId: "",
    uploadedFileName: "",
  },

  onShow() {
    if (!isLoggedIn()) {
      wx.navigateTo({
        url: "/pages/login/login",
      });
    }
  },

  handleChooseImage() {
    wx.chooseMedia({
      count: 1,
      mediaType: ["image"],
      sourceType: ["album"],
      success: (res) => {
        const file = (res.tempFiles || [])[0];
        if (!file || !file.tempFilePath) {
          return;
        }
        this.setData({
          localImagePath: file.tempFilePath,
          resultText: "图片已选择，点击下方按钮开始导入",
          uploadTaskId: "",
          uploadedFileName: "",
        });
      },
      fail: () => {
        this.setData({
          resultText: "图片选择失败，请重试",
        });
      },
    });
  },

  handleUploadImage() {
    const filePath = this.data.localImagePath;
    const userId = getCurrentUserId();
    if (!filePath) {
      this.setData({
        resultText: "请先选择一张截图",
      });
      return;
    }

    this.setData({
      uploading: true,
      resultText: "截图上传并识别中，请稍候",
    });

    wx.uploadFile({
      url: `${getBaseUrl()}/users/${userId}/positions/import-image`,
      filePath,
      name: "file",
      success: (res) => {
        try {
          const data = JSON.parse(res.data || "{}");
          if (res.statusCode >= 200 && res.statusCode < 300) {
            const taskId = data.task_id || "";
            this.setData({
              resultText: data.message || "识别成功，请确认后导入",
              uploadTaskId: taskId,
              uploadedFileName: data.stored_file_name || "",
            });
            wx.navigateTo({
              url: `/pages/import-confirm/import-confirm?taskId=${taskId}`,
            });
            return;
          }
          this.setData({
            resultText: data.detail || "截图上传失败",
          });
        } catch (error) {
          this.setData({
            resultText: "上传结果解析失败",
          });
        }
      },
      fail: (error) => {
        this.setData({
          resultText: error.errMsg || "截图导入失败",
        });
      },
      complete: () => {
        this.setData({
          uploading: false,
        });
      },
    });
  },
});
