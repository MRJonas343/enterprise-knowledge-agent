import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Enterprise Knowledge Agent",
  description: "Grounded answers over the enterprise knowledge base.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
