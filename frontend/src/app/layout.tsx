import type { Metadata } from "next";
import { headers } from "next/headers";
import { Space_Grotesk, JetBrains_Mono } from "next/font/google";
import { AuthProvider } from "@/components/auth/AuthProvider";
import "./globals.css";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-space-grotesk",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-jetbrains-mono",
});

export const metadata: Metadata = {
  title: "Deep Presence",
  description: "Citation intelligence and revenue attribution platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Read CSP nonce from middleware (Next.js applies it to injected scripts)
  const nonce = headers().get('x-nonce') ?? undefined;

  return (
    <html lang="en" className={`${spaceGrotesk.variable} ${jetbrainsMono.variable}`} suppressHydrationWarning>
      <body nonce={nonce}>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
