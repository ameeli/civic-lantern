import type { Metadata } from "next";
import {
  Geist,
  Geist_Mono,
  Eagle_Lake,
  Playfair_Display,
} from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const masthead = Eagle_Lake({
  weight: "400",
  subsets: ["latin"],
  variable: "--font-masthead",
  display: "swap",
});

// The high-contrast Newspaper Headline Font
const headline = Playfair_Display({
  variable: "--font-headline",
  subsets: ["latin"],
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
        ${geistMono.variable} 
        ${masthead.variable} 
        ${headline.variable} 
        h-full antialiased
      `}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
