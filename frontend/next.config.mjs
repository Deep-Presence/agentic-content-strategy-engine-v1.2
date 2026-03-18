/** @type {import('next').NextConfig} */
const nextConfig = {
  webpack: (config) => {
    config.module.rules.push({
      test: /\.md$/,
      type: 'asset/source',
    });
    return config;
  },
  async rewrites() {
    // Proxy API calls to FastAPI backend in development.
    // In production, set NEXT_PUBLIC_API_URL to the real backend URL.
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return [
      { source: '/api/:path*', destination: `${backendUrl}/api/:path*` },
      { source: '/health', destination: `${backendUrl}/health` },
      { source: '/readiness', destination: `${backendUrl}/readiness` },
    ];
  },
};

export default nextConfig;
