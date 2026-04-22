import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

const ENGINES: Array<{
  icon: string;
  title: string;
  tone: "blue" | "red" | "amber" | "teal";
  body: string;
}> = [
  {
    icon: "📊",
    title: "OI Change Tracking",
    tone: "blue",
    body: "Tracks change in open interest per cycle — not cumulative totals. Spots writer exits in real-time.",
  },
  {
    icon: "⚠",
    title: "Trap Probability Engine",
    tone: "red",
    body: "Detects false breakouts before they reverse. Scores fake-break risk 0–100% every cycle.",
  },
  {
    icon: "⟳",
    title: "Adaptive Regime Detection",
    tone: "amber",
    body: "Range days get range logic. Trend days get trend logic. Switches automatically.",
  },
  {
    icon: "⚖",
    title: "Conflict-Aware Arbitration",
    tone: "teal",
    body: "When engines disagree, you see WAIT instead of a false signal. Disagreement is a state, not a bug.",
  },
];

const PROBLEM_POINTS = [
  "Jumping between NSE option chain tabs during fast moves",
  "Reading PCR in isolation, missing the OI-change story",
  "Chasing Telegram signals with no entry/stop logic",
  "Reacting to structural shifts 15 minutes too late",
];

const TRUST_POINTS: Array<{
  tone: "positive" | "info";
  title: string;
  body: string;
}> = [
  {
    tone: "positive",
    title: "No buy / sell tips",
    body: "We don't tell you to trade. We show you what the structure is doing.",
  },
  {
    tone: "positive",
    title: "Transparent performance",
    body: "Every signal logged. Every outcome tracked. Win rate updates live.",
  },
  {
    tone: "positive",
    title: "No signal pumping",
    body: "The engine says WAIT more than it says GO. That's the point.",
  },
  {
    tone: "info",
    title: "Not SEBI-registered",
    body: "Educational and analytical use only. Make your own trading decisions.",
  },
];

export default function LandingPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleNotifySubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!email || !email.includes("@")) return;
    // TODO: wire to backend notify endpoint. For now, optimistic success.
    setSubmitted(true);
  };

  return (
    <div className="lp-page lp-page-v2">
      {/* ═══ NAV ═══ */}
      <nav className="lp-nav">
        <div className="lp-container lp-nav-inner">
          <Link to="/" className="lp-brand">
            <span className="lp-brand-option">Option</span>
            <span className="lp-brand-lens">Lens</span>
          </Link>
          <div className="lp-nav-links">
            <a href="#how-it-works" className="lp-nav-link">
              How it works
            </a>
            <a href="#features" className="lp-nav-link">
              Features
            </a>
            <a href="#trust" className="lp-nav-link">
              Principles
            </a>
            <Link to="/app" className="lp-nav-cta">
              Open dashboard →
            </Link>
          </div>
        </div>
      </nav>

      {/* ═══ HERO ═══ */}
      <section className="lp-hero lp-hero-v2">
        <div className="lp-container lp-hero-grid-v2">
          <div className="lp-hero-left">
            <div className="lp-hero-badge">
              <span className="lp-hero-badge-dot" />
              Intraday structure intelligence
            </div>
            <h1 className="lp-h1">
              Stop guessing.
              <br />
              Start reading structure.
            </h1>
            <p className="lp-hero-sub">
              OI change, volume expansion, trap detection, and regime logic —
              combined into a single intraday decision layer for NIFTY traders.
            </p>
            <div className="lp-cta-row">
              <Link to="/app" className="lp-btn lp-btn-primary-v2">
                Open live dashboard →
              </Link>
              <a href="#how-it-works" className="lp-btn lp-btn-ghost">
                See how it works
              </a>
            </div>
            <div className="lp-trust-inline">
              <span>✓ No signup</span>
              <span>✓ Free during beta</span>
              <span>✓ Not SEBI-registered · analytical use</span>
            </div>
          </div>

          <div className="lp-hero-snapshot">
            <div className="lp-snap-head">
              <span className="lp-snap-eyebrow">Live Snapshot</span>
              <span className="lp-snap-live">
                <span className="lp-snap-live-dot" />
                LIVE
              </span>
            </div>
            <div className="lp-snap-price-row">
              <span className="lp-snap-price">24,577</span>
              <span className="lp-snap-delta">▲ 211.8</span>
              <span className="lp-snap-pct">0.87%</span>
            </div>
            <div className="lp-snap-grid">
              <div className="lp-snap-cell">
                <div className="lp-snap-cell-head">
                  <span className="lp-snap-cell-key">Readiness</span>
                  <span className="lp-snap-cell-val lp-snap-good">65%</span>
                </div>
                <div className="lp-snap-bar">
                  <div className="lp-snap-bar-fill lp-snap-bar-good" style={{ width: "65%" }} />
                </div>
              </div>
              <div className="lp-snap-cell">
                <div className="lp-snap-cell-head">
                  <span className="lp-snap-cell-key">Trap Risk</span>
                  <span className="lp-snap-cell-val lp-snap-warn">41%</span>
                </div>
                <div className="lp-snap-bar">
                  <div className="lp-snap-bar-fill lp-snap-bar-warn" style={{ width: "41%" }} />
                </div>
              </div>
            </div>
            <div className="lp-snap-unlock">
              <div className="lp-snap-unlock-label">Unlock when</div>
              <div className="lp-snap-unlock-body">Spot tags S 24,200 or R 24,900</div>
            </div>
            <div className="lp-snap-foot">
              <span>
                Bias: <span className="lp-snap-bias">Bearish</span>
              </span>
              <span>Range: 24,200 – 24,900</span>
            </div>
          </div>
        </div>
      </section>

      {/* ═══ PROBLEM ═══ */}
      <section className="lp-section lp-section-problem">
        <div className="lp-container lp-problem-grid">
          <div>
            <div className="lp-section-label lp-section-label-red">The problem</div>
            <h2 className="lp-h2">
              The problem isn't lack of data.
              <br />
              It's fragmented interpretation.
            </h2>
            <p className="lp-section-sub">
              Retail traders already have the data. They don't have a framework that integrates it.
            </p>
          </div>
          <div className="lp-problem-list">
            {PROBLEM_POINTS.map((text) => (
              <div key={text} className="lp-problem-item">
                {text}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ SOLUTION (4 engines) ═══ */}
      <section className="lp-section lp-section-solution" id="features">
        <div className="lp-container">
          <div className="lp-section-head">
            <div className="lp-section-label lp-section-label-teal">The solution</div>
            <h2 className="lp-h2 lp-h2-center">Four engines. One decision layer.</h2>
            <p className="lp-section-sub lp-section-sub-center">
              Each component of market microstructure gets its own engine. Conflict between engines is explicitly
              resolved before anything reaches you.
            </p>
          </div>
          <div className="lp-engines-grid">
            {ENGINES.map((eng) => (
              <article key={eng.title} className={`lp-engine lp-engine-${eng.tone}`}>
                <div className="lp-engine-icon" aria-hidden="true">
                  {eng.icon}
                </div>
                <h3 className="lp-engine-title">{eng.title}</h3>
                <p className="lp-engine-body">{eng.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ HOW IT WORKS ═══ */}
      <section className="lp-section lp-section-how" id="how-it-works">
        <div className="lp-container">
          <div className="lp-section-head">
            <div className="lp-section-label">How it works</div>
            <h2 className="lp-h2 lp-h2-center">From raw OI to trade plan — in one screen.</h2>
          </div>

          {/* Step 1: OI ladder */}
          <div className="lp-how-step">
            <div className="lp-how-step-head">
              <span className="lp-how-step-num">1</span>
              <div>
                <div className="lp-how-step-title">You see live OI shifts, not stale totals</div>
                <div className="lp-how-step-sub">
                  Every 15 seconds, the dashboard recomputes writer behavior across the chain
                </div>
              </div>
            </div>
            <div className="lp-how-ladder">
              {[
                { strike: "24,400", pe: 10, ce: 4, tone: "", tag: "" },
                { strike: "24,450", pe: 8, ce: 3, tone: "", tag: "" },
                { strike: "24,500", pe: 6, ce: 6, tone: "magnet", tag: "" },
                { strike: "24,550", pe: 4, ce: 9, tone: "spot", tag: "" },
                { strike: "24,600", pe: 3, ce: 14, tone: "ce", tag: "" },
                { strike: "24,650", pe: 3, ce: 11, tone: "", tag: "" },
                { strike: "24,700", pe: 2, ce: 12, tone: "", tag: "" },
              ].map((s) => (
                <div key={s.strike} className={`lp-how-ladder-cell${s.tone ? ` lp-how-ladder-cell-${s.tone}` : ""}`}>
                  <div className="lp-how-ladder-strike">{s.strike}</div>
                  <div className="lp-how-ladder-bars">
                    <div className="lp-how-bar lp-how-bar-pe" style={{ height: `${s.pe}px` }} />
                    <div className="lp-how-bar lp-how-bar-ce" style={{ height: `${s.ce}px` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Step 2: engine scores */}
          <div className="lp-how-step">
            <div className="lp-how-step-head">
              <span className="lp-how-step-num">2</span>
              <div>
                <div className="lp-how-step-title">Four engines evaluate the structure in parallel</div>
                <div className="lp-how-step-sub">
                  Trap probability, regime, directional force, and structural clarity — scored independently
                </div>
              </div>
            </div>
            <div className="lp-how-scores">
              <div className="lp-how-score">
                <span className="lp-how-score-key">Trap</span>
                <span className="lp-how-score-val lp-score-warn">41%</span>
              </div>
              <div className="lp-how-score">
                <span className="lp-how-score-key">Regime</span>
                <span className="lp-how-score-val lp-score-info">Range play</span>
              </div>
              <div className="lp-how-score">
                <span className="lp-how-score-key">Force</span>
                <span className="lp-how-score-val lp-score-bad">−58%</span>
              </div>
              <div className="lp-how-score">
                <span className="lp-how-score-key">Clarity</span>
                <span className="lp-how-score-val lp-score-good">72%</span>
              </div>
            </div>
          </div>

          {/* Step 3: actionable output */}
          <div className="lp-how-step">
            <div className="lp-how-step-head">
              <span className="lp-how-step-num">3</span>
              <div>
                <div className="lp-how-step-title">You get a single, actionable output</div>
                <div className="lp-how-step-sub">
                  Action, entry zone, stop level, targets, risk/reward — or an explicit WAIT
                </div>
              </div>
            </div>
            <div className="lp-how-output">
              <div className="lp-how-output-badge">
                <span className="lp-how-output-dot" />
                <span className="lp-how-output-label">WAIT</span>
              </div>
              <div className="lp-how-output-body">
                Range conflict · waiting for spot to tag S 24,200 or R 24,900 with trap below 55%
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══ TRUST ═══ */}
      <section className="lp-section lp-section-trust" id="trust">
        <div className="lp-container">
          <div className="lp-section-head">
            <div className="lp-section-label">Built different</div>
            <h2 className="lp-h2 lp-h2-center">Analytics-first. Not another tipping channel.</h2>
          </div>
          <div className="lp-trust-grid">
            {TRUST_POINTS.map((t) => (
              <div key={t.title} className={`lp-trust-item lp-trust-item-${t.tone}`}>
                <span className="lp-trust-mark" aria-hidden="true">
                  {t.tone === "positive" ? "✓" : "ⓘ"}
                </span>
                <div>
                  <div className="lp-trust-title">{t.title}</div>
                  <div className="lp-trust-body">{t.body}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ FINAL CTA + email ═══ */}
      <section className="lp-section lp-final-cta-v2">
        <div className="lp-container lp-final-inner">
          <h2 className="lp-h2 lp-h2-center lp-h2-big">
            No signup. No tips.
            <br />
            Just structure.
          </h2>
          <p className="lp-section-sub lp-section-sub-center">See how OptionLens reads the NIFTY structure right now.</p>
          <Link to="/app" className="lp-btn lp-btn-primary-v2 lp-btn-primary-large">
            Open live dashboard →
          </Link>

          <div className="lp-notify">
            <span className="lp-notify-label">Get notified when Pro launches:</span>
            {submitted ? (
              <span className="lp-notify-ok">✓ We'll let you know</span>
            ) : (
              <form onSubmit={handleNotifySubmit} className="lp-notify-form">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@email.com"
                  className="lp-notify-input"
                  aria-label="Email address"
                />
                <button type="submit" className="lp-notify-btn">
                  Notify me
                </button>
              </form>
            )}
          </div>
        </div>
      </section>

      {/* ═══ FOOTER ═══ */}
      <footer className="lp-footer-v2">
        <div className="lp-container lp-footer-inner">
          <div className="lp-footer-copy">© 2026 OptionLens · Educational and analytical purposes only</div>
          <div className="lp-footer-links">
            <a href="#">Privacy Policy</a>
            <a href="#">Terms</a>
            <a href="mailto:contact@optionlense.com">contact@optionlense.com</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
