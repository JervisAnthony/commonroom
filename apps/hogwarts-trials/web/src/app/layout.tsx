import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";
export const metadata: Metadata = {
  title: "Hogwarts Trials",
  description: "A welcoming wizarding study room for public practice quizzes. An unofficial fan project with synthetic demo content.",
};
export default function RootLayout({ children, }: Readonly<{
  children: React.ReactNode;
}>) {
  return (<html lang="en">
    <body>
      <a className="skip-link" href="#main-content">Skip to content</a>
      <header className="site-header">
        <Link className="brand" href="/">
          <span className="brand-mark" aria-hidden="true">✧</span>
          <span>Hogwarts Trials<small>A COMMONROOM PROJECT</small>
          </span>
        </Link>
        <Link className="header-link" href="/#trials">The trial catalog <span aria-hidden="true">↗</span>
        </Link>
      </header>{children}<footer className="site-footer">
        <p>Hogwarts Trials <span aria-hidden="true">✧</span> Stay curious.</p>
        <p>An unofficial fan project. Not affiliated with or endorsed by the franchise owners.<br />Current quizzes are synthetic demonstrations, not curated canon.</p>
      </footer>
    </body>
  </html>);
}
