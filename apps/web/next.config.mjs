/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@trading-os/ui", "@trading-os/contracts", "@trading-os/mock-data"],
};

export default nextConfig;
