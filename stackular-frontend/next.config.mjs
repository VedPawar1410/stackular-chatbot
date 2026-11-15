/** @type {import('next').NextConfig} */
const nextConfig = {
  // The repo root has its own package-lock.json (for `concurrently`); pin the
  // workspace root here so Turbopack stops warning about multiple lockfiles.
  turbopack: { root: import.meta.dirname },
};

export default nextConfig;
