import type { NextConfig } from "next";
import path from "path";

const ngrokDomain = process.env.NGROK_DOMAIN;

const nextConfig: NextConfig = {
  experimental: {

    ...(ngrokDomain
      ? {
        allowedDevOrigins: [`https://${ngrokDomain}`],
      }
      : {}),
  },
};

export default nextConfig;
