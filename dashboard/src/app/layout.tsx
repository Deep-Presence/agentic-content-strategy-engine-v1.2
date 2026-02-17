import type { Metadata } from "next";
import localFont from "next/font/local";
import { IBM_Plex_Mono } from "next/font/google";
import { AppShell } from "@/components/layout/AppShell";
import "./globals.css";

const crimsonText = localFont({
  src: [
    { path: "../../crimson-text/CrimsonText-Regular.ttf", weight: "400", style: "normal" },
    { path: "../../crimson-text/CrimsonText-Italic.ttf", weight: "400", style: "italic" },
    { path: "../../crimson-text/CrimsonText-SemiBold.ttf", weight: "600", style: "normal" },
    { path: "../../crimson-text/CrimsonText-SemiBoldItalic.ttf", weight: "600", style: "italic" },
    { path: "../../crimson-text/CrimsonText-Bold.ttf", weight: "700", style: "normal" },
    { path: "../../crimson-text/CrimsonText-BoldItalic.ttf", weight: "700", style: "italic" },
  ],
  variable: "--font-crimson-text",
  display: "swap",
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-ibm-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Deep Presence — Content Strategy Engine",
  description: "AI-powered content strategy for B2B companies",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${crimsonText.variable} ${ibmPlexMono.variable}`}
      >
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
