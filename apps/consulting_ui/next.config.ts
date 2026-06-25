import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export: the app is fully client-rendered (auth + API calls happen in the
  // browser), so it ships as static files to S3 + CloudFront. `next build` emits out/.
  output: "export",
  images: { unoptimized: true },
  // Emit route/index.html per page so S3 website hosting resolves deep links
  // (/structure/ -> /structure/index.html) without a custom rewrite function.
  trailingSlash: true,
};

export default nextConfig;
