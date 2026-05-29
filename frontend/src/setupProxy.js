const { createProxyMiddleware } = require("http-proxy-middleware");

module.exports = function (app) {
  const target = process.env.REACT_APP_API_URL || "http://localhost:5000";

  app.use(
    ["/api", "/upload"],
    createProxyMiddleware({
      target,
      changeOrigin: true,
    })
  );
};
