function getRefreshStore() {
  const app = getApp();
  if (!app.globalData.pageRefreshState) {
    app.globalData.pageRefreshState = {};
  }
  return app.globalData.pageRefreshState;
}

function ensurePageState(pageKey) {
  const store = getRefreshStore();
  if (!store[pageKey]) {
    store[pageKey] = {
      hasEntered: false,
      shouldRefresh: false,
    };
  }
  return store[pageKey];
}

function shouldRefreshPage(pageKey) {
  const state = ensurePageState(pageKey);
  if (!state.hasEntered) {
    state.hasEntered = true;
    return true;
  }
  if (state.shouldRefresh) {
    state.shouldRefresh = false;
    return true;
  }
  return false;
}

function markPagesDirty(pageKeys = []) {
  pageKeys.forEach((pageKey) => {
    if (!pageKey) {
      return;
    }
    const state = ensurePageState(pageKey);
    state.shouldRefresh = true;
  });
}

module.exports = {
  markPagesDirty,
  shouldRefreshPage,
};
