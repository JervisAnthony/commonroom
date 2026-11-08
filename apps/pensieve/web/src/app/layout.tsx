import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Pensieve | Commonroom",
  description: "Pensieve's web foundation and current service availability.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">Skip to content</a>
        <header className="masthead"><span className="wordmark">Commonroom</span><span>Pensieve / Web foundation</span></header>
        {children}
        <footer>Commonroom is an unofficial fan project. It is not affiliated with or endorsed by the franchise creators, publishers, or rights holders. All franchise trademarks belong to their respective owners.</footer>
      </body>
    </html>
  );
}
