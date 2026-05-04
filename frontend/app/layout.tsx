import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'MarketMind | AI-Orchestrated Financial Research',
  description: 'MarketMind fuses real-time quantitative metrics with AI-driven news sentiment to provide institutional-grade insights for the Indian markets.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet" />
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
      </head>
      <body className="antialiased selection:bg-[#66fcf1] selection:text-[#0b0c10]">{children}</body>
    </html>
  );
}
