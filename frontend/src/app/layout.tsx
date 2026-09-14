import type { Metadata } from "next";
import "@/core/styles/globals.css";

export const metadata: Metadata = {
  title: "Buildora - Enterprise Construction Management",
  description: "AI-Powered Construction Takeoff, Receipt OCR & HR Management Platform ($USD)",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased min-h-screen bg-[#FAF7F2] text-stone-900">
        {children}
      </body>
    </html>
  );
}
