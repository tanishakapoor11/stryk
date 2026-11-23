/** @type {import('next').NextConfig} */

/**
 * `distDir` is overridable so a production build can be run without trampling a
 * running dev server.
 *
 * `next dev` and `next build` both write to `.next` by default. Building while
 * a dev server is serving from that directory replaces the dev-mode chunks the
 * running server still expects, and it then fails with
 * "Cannot find module './vendor-chunks/<pkg>.js'" until `.next` is deleted and
 * the server restarted. Use `npm run build:isolated` to build into a separate
 * directory instead.
 */
const nextConfig = {
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
