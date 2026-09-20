import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Enterprise Knowledge Agent",
  description: "Grounded answers over the enterprise knowledge base.",
};

// Runs before paint: stored choice first, system preference otherwise.
const themeScript = `(function(){try{var s=localStorage.getItem("theme");var t=s==="dark"||s==="light"?s:(window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light");document.documentElement.dataset.theme=t}catch(e){}})();`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        {children}
      </body>
    </html>
  );
}
