import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

// Self-hosted (not next/font/google) - see src/fonts/README.md for why.
const geistSans = localFont({
  src: "../fonts/inconsolata-latin-wght-normal.woff2",
  weight: "300 600",
  style: "normal",
  variable: "--font-geist-sans",
});

const masthead = localFont({
  src: "../fonts/eagle-lake-latin-400-normal.woff2",
  weight: "400",
  style: "normal",
  variable: "--font-masthead",
  display: "swap",
});

const headline = localFont({
  src: [
    {
      path: "../fonts/playfair-display-latin-wght-normal.woff2",
      weight: "400 800",
      style: "normal",
    },
    {
      path: "../fonts/playfair-display-latin-wght-italic.woff2",
      weight: "400 800",
      style: "italic",
    },
  ],
  variable: "--font-headline",
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
