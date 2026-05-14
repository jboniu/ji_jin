const ENVIRONMENTS = {
  local: {
    name: "local",
    apiBaseUrl: "http://127.0.0.1:8000/api",
  },
  production: {
    name: "production",
    apiBaseUrl: "https://ji-jin.onrender.com/api",
  },
};

const ACTIVE_ENV = "production";
const CURRENT_ENV = ENVIRONMENTS[ACTIVE_ENV];

module.exports = {
  ACTIVE_ENV,
  CURRENT_ENV,
  ENVIRONMENTS,
};
