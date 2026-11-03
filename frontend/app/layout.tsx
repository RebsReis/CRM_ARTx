import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import AuthShell from "../components/AuthShell";
import ThemeProvider from "../components/ThemeProvider";
import { Suspense } from "react";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ART X CRM",
  description: "CRM da agencia ART X",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="pt-BR"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      
<body>
  <Suspense fallback={<p className="p-6">Carregando CRM...</p>}>
    <ThemeProvider><AuthShell>{children}</AuthShell></ThemeProvider>
  </Suspense>
</body>

    </html>
  );
}
