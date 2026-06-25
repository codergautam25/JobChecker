import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";
import { GlobalProgress } from "@/components/GlobalProgress";
import { Chatbot } from "@/components/Chatbot";
import { QueryProvider } from "@/components/QueryProvider";
import { ParticleBackground } from "@/components/ParticleBackground";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Career Tracker",
  description: "AI Job Application Assistant",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body suppressHydrationWarning className={`${inter.variable} font-sans antialiased bg-[#0b1120] text-slate-200 flex h-screen overflow-hidden`}>
        <QueryProvider>
          <ParticleBackground />
          <GlobalProgress />
          <Sidebar />
          
          <div className="flex-1 flex flex-col h-screen overflow-y-auto">
            <header className="h-16 border-b border-slate-800 flex items-center px-8 shrink-0 bg-[#0b1120]/80 backdrop-blur-md sticky top-0 z-40">
              {/* Empty space reserved for future features */}
            </header>
            
            <main className="flex-1 p-8 max-w-7xl mx-auto w-full">
              {children}
            </main>
          </div>

          <Chatbot />
        </QueryProvider>
      </body>
    </html>
  );
}
