"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type TickerItem = {
  symbol: string;
  name: string;
  price: number | null;
  change_pct: number | null;
  date: string | null;
};

const trustItems = [
  { icon: "monitoring", label: "Indian Markets", warning: false },
  { icon: "candlestick_chart", label: "Stocks + Mutual Funds", warning: false },
  { icon: "table_chart", label: "Structured Quant Data", warning: false },
  { icon: "smart_toy", label: "AI-Assisted Research", warning: false },
  { icon: "warning", label: "Research Only", warning: true },
];

const features = [
  {
    icon: "forum",
    title: "AI Research Chat",
    body: "Query market data in natural language. MarketMind interprets financial metrics and keeps numbers tied to structured data.",
    wide: true,
    prompt: "> Analyze Reliance Industries debt-to-equity ratio vs sector average...",
  },
  {
    icon: "compare_arrows",
    title: "Stock Comparison",
    body: "Side-by-side fundamental research for PE, ROE, margins, and sector context.",
  },
  {
    icon: "pie_chart",
    title: "Mutual Fund Analytics",
    body: "Deep dive into AUM, expense ratios, and rolling returns.",
  },
  {
    icon: "feed",
    title: "News Context & Structured Tables",
    body: "Real-time news mapped to asset price action, with dense financial data in clean tables.",
    wide: true,
  },
];

const formatChange = (value: number | null) => {
  if (value === null || value === undefined) return "--";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
};

export default function LandingPage() {
  const [tickerItems, setTickerItems] = useState<TickerItem[]>([]);
  const [tickerStatus, setTickerStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    let cancelled = false;

    fetch("/api/quant/stocks/nifty50/ticker")
      .then((response) => {
        if (!response.ok) throw new Error("Failed to load Nifty 50 ticker");
        return response.json();
      })
      .then((data) => {
        if (cancelled) return;
        setTickerItems(Array.isArray(data.items) ? data.items : []);
        setTickerStatus("ready");
      })
      .catch(() => {
        if (cancelled) return;
        setTickerStatus("error");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const tickerGroup = tickerItems.length > 0 ? tickerItems : [];

  return (
    <div className="landing-page">
      <header className="landing-nav">
        <div className="landing-nav-inner">
          <Link href="/" className="landing-brand">MarketMind</Link>
          <nav className="landing-links" aria-label="Primary">
            <a className="active" href="#features">Features</a>
            <a href="#workflow">How it Works</a>
            <a href="#data">Data</a>
            <a href="#disclaimer">Disclaimer</a>
          </nav>
          <Link href="/dashboard" className="landing-small-cta">Launch App</Link>
        </div>
      </header>

      <main className="landing-main">
        <section className="landing-hero">
          <div className="landing-hero-glow" />
          <h1>Research Indian stocks and mutual funds with AI-assisted market intelligence.</h1>
          <p>
            Merging structured price data, fundamental metrics, and AI-driven insights into a single institutional terminal built for the discerning retail investor.
          </p>

          <div className="landing-actions">
            <Link href="/dashboard" className="landing-primary-action">Start Researching</Link>
            <a href="#features" className="landing-secondary-action">Explore Features</a>
          </div>

          <div className="landing-trust-strip">
            {trustItems.map((item) => (
              <span className="landing-trust-pill" key={item.label}>
                <span className={`material-symbols-outlined ${item.warning ? "warning" : ""}`}>{item.icon}</span>
                {item.label}
              </span>
            ))}
          </div>

        </section>

        <section className="landing-market-strip" aria-label="Nifty 50 stock changes">
          <div className="landing-market-strip-label">
            <span className="material-symbols-outlined">candlestick_chart</span>
            Nifty 50
          </div>
          <div className="landing-market-strip-window">
            {tickerStatus === "loading" ? (
              <div className="landing-market-strip-message">Loading current stock changes...</div>
            ) : tickerStatus === "error" ? (
              <div className="landing-market-strip-message">Current Nifty 50 changes unavailable.</div>
            ) : tickerItems.length === 0 ? (
              <div className="landing-market-strip-message">No Nifty 50 changes available yet.</div>
            ) : (
              <div className="landing-market-strip-track" style={{ whiteSpace: "nowrap" }}>
                {[0, 1].map((groupIndex) => (
                  <div className="landing-market-strip-group" key={groupIndex} aria-hidden={groupIndex === 1}>
                    {tickerGroup.map((item) => {
                      const isPositive = (item.change_pct ?? 0) >= 0;
                      return (
                        <span className="landing-market-tick" key={`${item.symbol}-${groupIndex}`} title={item.name}>
                          <span>{item.symbol}</span>
                          <strong className={isPositive ? "positive" : "negative"}>{formatChange(item.change_pct)}</strong>
                        </span>
                      );
                    })}
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        <section id="workflow" className="landing-problem">
          <h2>Market research is scattered across too many tabs.</h2>
          <p>
            Stop jumping between generic news portals, clunky screeners, and standalone AI chatbots. MarketMind unifies quantitative data with context-aware AI in one canvas for deep analysis.
          </p>
        </section>

        <section id="features" className="landing-features">
          {features.map((feature) => (
            <article className={`landing-feature-card ${feature.wide ? "wide" : ""}`} key={feature.title}>
              <span className="material-symbols-outlined">{feature.icon}</span>
              <h3>{feature.title}</h3>
              <p>{feature.body}</p>
              {feature.prompt ? <code>{feature.prompt}</code> : null}
            </article>
          ))}
        </section>

        <section id="data" className="landing-data-card">
          <span className="material-symbols-outlined">database</span>
          <h2>Data-first, AI-second.</h2>
          <p>
            MarketMind prioritizes structured quantitative data. AI interprets facts instead of inventing them, and the interface separates verified metrics from generated synthesis.
          </p>
        </section>

        <section className="landing-final-cta">
          <h2>Start researching with more structure.</h2>
          <Link href="/dashboard" className="landing-primary-action">Launch MarketMind</Link>
        </section>
      </main>

      <footer id="disclaimer" className="landing-footer">
        <div>
          <strong>MarketMind</strong>
          <p>© 2026 MarketMind Terminal. Information provided is for research only and does not constitute investment advice.</p>
        </div>
        <nav aria-label="Footer">
          <a href="#">Terms of Service</a>
          <a href="#">Privacy Policy</a>
          <a href="#">Regulatory Disclosure</a>
          <a href="#">API Documentation</a>
        </nav>
      </footer>
    </div>
  );
}
