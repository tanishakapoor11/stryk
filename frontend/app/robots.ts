import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/seo";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        // /api is the Next route that proxies search; it has nothing to index,
        // and /compare only exists as a query-string permutation of players
        // already indexed on their own pages.
        disallow: ["/api/", "/compare?"],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
