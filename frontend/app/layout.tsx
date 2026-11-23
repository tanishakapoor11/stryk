import type { Metadata } from "next";
import { Bricolage_Grotesque, Inter, JetBrains_Mono } from "next/font/google";
import { TooltipProvider } from "@/components/ui/tooltip";
import { TopBar } from "@/components/layout/top-bar";
import { SiteFooter } from "@/components/layout/footer";
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

export const metadata: Metadata = {
  title: { default: "Stryk — Cricket Intelligence", template: "%s · Stryk" },
  description:
    "Look up any IPL player and see what the ball-by-ball data says about them: how they score, when they score, and who they struggle against.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${display.variable} ${mono.variable}`}>
      <body className="min-h-screen bg-canvas">
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
