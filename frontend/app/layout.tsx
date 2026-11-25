import type { Metadata } from "next";
import { Bricolage_Grotesque, Inter, JetBrains_Mono } from "next/font/google";
import { TooltipProvider } from "@/components/ui/tooltip";
import { TopBar } from "@/components/layout/top-bar";
import { SiteFooter } from "@/components/layout/footer";
import { JsonLd, SITE_NAME, SITE_URL } from "@/lib/seo";
import "./globals.css";

const sans = Inter({ subsets: ["latin"], variable: "--font-sans", display: "swap" });
// Player and team names carry the page, so they get a face with some character
// rather than the same grotesque as the body text.
const display = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap" });

const DESCRIPTION =
  "Ball-by-ball cricket intelligence across franchise leagues, ICC World Cups and women's cricket: look up any player, team or competition and see what the deliveries say.";

export const metadata: Metadata = {
  // Without this, canonical links and og:image render relative and crawlers
  // discard them.
  metadataBase: new URL(SITE_URL),
  title: { default: "Stryk — Cricket Intelligence", template: "%s · Stryk" },
  description: DESCRIPTION,
  applicationName: SITE_NAME,
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: SITE_NAME,
    title: "Stryk — Cricket Intelligence",
    description: DESCRIPTION,
    url: "/",
  },
  twitter: { card: "summary_large_image", title: "Stryk — Cricket Intelligence", description: DESCRIPTION },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large", "max-snippet": -1 },
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${display.variable} ${mono.variable}`}>
      <body className="min-h-screen bg-canvas">
        {/* Lets search engines offer a site search box, and names the site
            consistently across results. */}
        <JsonLd
          data={{
            "@context": "https://schema.org",
            "@type": "WebSite",
            name: SITE_NAME,
            url: SITE_URL,
            description: DESCRIPTION,
            potentialAction: {
              "@type": "SearchAction",
              target: { "@type": "EntryPoint", urlTemplate: `${SITE_URL}/players?q={search_term_string}` },
              "query-input": "required name=search_term_string",
            },
          }}
        />
        <TooltipProvider delayDuration={120}>
          <div className="flex min-h-screen flex-col">
            <TopBar />
            <main className="flex-1">{children}</main>
            <SiteFooter />
          </div>
        </TooltipProvider>
      </body>
    </html>
  );
}
