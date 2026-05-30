const { createProxyMiddleware } = require("http-proxy-middleware");

module.exports = function (app) {
  const backendTarget = process.env.REACT_APP_API_URL || "http://localhost:5000";
  const dashTarget =
    process.env.REACT_APP_DASH_APP_INTERNAL_URL || "http://dash-service:3001";

  app.use(
    ["/api", "/upload"],
    createProxyMiddleware({
      target: backendTarget,
      changeOrigin: true,
    })
  );

  app.use(
    "/visualize",
    createProxyMiddleware({
      target: dashTarget,
      changeOrigin: true,
    })
  );
};
