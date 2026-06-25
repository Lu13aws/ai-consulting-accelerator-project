import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

import AuthGate from "@/components/AuthGate";
import NavBar from "@/components/NavBar";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "AI Consulting Accelerator",
  description:
    "Framework Q&A and BA/RE/PM artifact structuring, grounded in cited frameworks.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-white text-slate-900">
        <NavBar />
        <AuthGate>{children}</AuthGate>
      </body>
    </html>
  );
}
