import type { Metadata } from "next";
import { Inconsolata, Eagle_Lake, Playfair_Display } from "next/font/google";
import "./globals.css";

const geistSans = Inconsolata({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600"],
});

const masthead = Eagle_Lake({
  weight: "400",
  subsets: ["latin"],
  variable: "--font-masthead",
  display: "swap",
});

const headline = Playfair_Display({
  variable: "--font-headline",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  style: ["normal", "italic"],
});

export const metadata: Metadata = {
  title: "The Civic Lantern",
  description: "Civic Data Archive",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`
        ${geistSans.variable} 
        ${masthead.variable} 
        ${headline.variable} 
        h-full antialiased
      `}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
