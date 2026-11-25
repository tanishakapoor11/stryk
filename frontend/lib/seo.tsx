import type { Metadata } from "next";

/**
 * The site's own origin. Needed for canonical links and social cards, which
 * must be absolute: a relative og:image is simply dropped by every crawler.
 *
 * Set NEXT_PUBLIC_SITE_URL in production. On Vercel preview builds VERCEL_URL
 * stands in, so a preview links to itself rather than to production.
 */
export const SITE_URL = (
  process.env.NEXT_PUBLIC_SITE_URL ??
  (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "http://localhost:3000")
).replace(/\/$/, "");

export const SITE_NAME = "Stryk";

/**
 * Page metadata with a canonical URL and social cards filled in.
 *
 * `path` is the canonical path with no query string. Every analytical page
 * here takes filters as search params - competition, season, phase, venue -
 * so the same content is reachable at dozens of URLs. Pointing them all at
 * one canonical is what stops them competing with each other in search.
 */
export function pageMeta({
  title,
  description,
  path,
  image,
}: {
  title: string;
  description: string;
  path: string;
  image?: string;
}): Metadata {
  const url = `${SITE_URL}${path}`;
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: {
      title: `${title} · ${SITE_NAME}`,
      description,
      url,
      siteName: SITE_NAME,
      type: "website",
      ...(image ? { images: [{ url: image }] } : {}),
    },
    twitter: {
      card: "summary_large_image",
      title: `${title} · ${SITE_NAME}`,
      description,
    },
  };
}

/**
 * The readable name for the competitions a profile is scoped to.
 *
 * A scope carries slugs ("ipl"), which is what a search snippet would
 * otherwise print. The entity's own competition options carry the real names,
 * so they are used where available and the slug is the last resort.
 */
export function scopeName(
  slugs: string[] | undefined,
  options: { slug: string; name: string; short_name: string | null }[] | undefined,
): string | null {
  if (!slugs?.length) return null;
  const bySlug = new Map((options ?? []).map((o) => [o.slug, o.short_name || o.name]));
  return slugs.map((s) => bySlug.get(s) ?? s).join(", ");
}

/** Renders JSON-LD. Structured data is data, so it is never interpolated raw. */
export function JsonLd({ data }: { data: Record<string, unknown> }) {
  return (
    <script
      type="application/ld+json"
      // The payload is built from our own API values, and JSON.stringify
      // escapes them; the </script> guard covers a name containing one.
      dangerouslySetInnerHTML={{
        __html: JSON.stringify(data).replace(/</g, "\\u003c"),
      }}
    />
  );
}
