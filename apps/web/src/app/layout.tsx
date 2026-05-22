import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'aeogenerator',
  description: 'AEO/GEO multi-agent SaaS for digital agencies',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="tr">
      <body className="antialiased">{children}</body>
    </html>
  );
}
