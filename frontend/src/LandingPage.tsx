import { Link } from "react-router-dom";

export default function LandingPage() {
  return (
    <div className="lp-page">
      <section className="lp-hero">
        <div className="lp-container lp-hero-grid">
          <div>
            <div className="lp-kicker">OptionLens for Intraday Structure</div>
            <h1>Stop Guessing. Start Reading Structure.</h1>
            <p>
              OptionLens combines OI change, volume expansion, trap detection, and regime logic into one clean
              intraday decision layer.
            </p>
            <div className="lp-cta-row">
              <Link to="/app" className="lp-btn lp-btn-primary">
                View Live Dashboard
              </Link>
              <a href="#how-it-works" className="lp-btn lp-btn-secondary">
                Learn How It Works
              </a>
            </div>
          </div>
          <div className="lp-hero-preview">
            <div className="lp-preview-title">Decision Snapshot</div>
            <div className="lp-preview-bias">Bias: Bearish</div>
            <div className="lp-preview-metric">Confidence 72%</div>
            <div className="lp-preview-track">
              <span style={{ width: "72%" }} />
            </div>
            <div className="lp-preview-metric">Trap Risk 41%</div>
            <div className="lp-preview-track lp-preview-trap">
              <span style={{ width: "41%" }} />
            </div>
          </div>
        </div>
      </section>

      <section className="lp-section">
        <div className="lp-container">
          <h2>Most Traders Monitor the Market the Wrong Way</h2>
          <ul className="lp-bullets">
            <li>Jump between NSE option chain</li>
            <li>Rely on random PCR values</li>
            <li>Follow Telegram signals</li>
            <li>React late to structural shifts</li>
          </ul>
          <p className="lp-closing">The problem isn&apos;t lack of data. It&apos;s fragmented interpretation.</p>
        </div>
      </section>

      <section className="lp-section">
        <div className="lp-container">
          <h2>What OptionLens Does Differently</h2>
          <div className="lp-grid-4">
            <article className="lp-card">
              <h3>OI Change Tracking</h3>
              <p>We track change in open interest, not just totals.</p>
            </article>
            <article className="lp-card">
              <h3>Trap Probability Engine</h3>
              <p>Detects exhaustion and fake breakouts early.</p>
            </article>
            <article className="lp-card">
              <h3>Adaptive Regime Detection</h3>
              <p>Switches logic between trend and range days.</p>
            </article>
            <article className="lp-card">
              <h3>Conflict-Aware Arbitration</h3>
              <p>Resolves contradictory signals before you see them.</p>
            </article>
          </div>
        </div>
      </section>

      <section className="lp-section" id="how-it-works">
        <div className="lp-container">
          <h2>How It Works</h2>
          <div className="lp-steps">
            <div className="lp-step">
              <span>1</span>
              <p>Live OI + Volume Aggregation</p>
            </div>
            <div className="lp-step-arrow">→</div>
            <div className="lp-step">
              <span>2</span>
              <p>Multi-Engine Intelligence Layer</p>
            </div>
            <div className="lp-step-arrow">→</div>
            <div className="lp-step">
              <span>3</span>
              <p>Clear Decision + Trade Plan Output</p>
            </div>
          </div>
        </div>
      </section>

      <section className="lp-section">
        <div className="lp-container">
          <h2>Live Dashboard Preview</h2>
          <div className="lp-preview-block">
            <div className="lp-overlay-tag">Live Example – Not a Recommendation</div>
            <div className="lp-preview-grid">
              <div className="lp-mini">Bias: Bullish</div>
              <div className="lp-mini">Confidence: 64%</div>
              <div className="lp-mini">Trap: Moderate</div>
              <div className="lp-mini">Levels: S 24,700 / R 24,900</div>
            </div>
          </div>
          <div className="lp-cta-row lp-cta-row-center">
            <Link to="/app" className="lp-btn lp-btn-primary">
              View Live Dashboard
            </Link>
          </div>
        </div>
      </section>

      <section className="lp-section">
        <div className="lp-container">
          <h2>Built for Analytical Use</h2>
          <ul className="lp-bullets">
            <li>No buy/sell tips</li>
            <li>No signal pumping</li>
            <li>Transparent performance tracking</li>
            <li>Not SEBI registered</li>
          </ul>
        </div>
      </section>

      <section className="lp-section lp-final-cta">
        <div className="lp-container">
          <h2>Ready to Monitor Structure Properly?</h2>
          <Link to="/app" className="lp-btn lp-btn-primary">
            Open Live Dashboard
          </Link>
          <p>No signup required. Educational use only.</p>
        </div>
      </section>

      <footer className="lp-footer">
        <div className="lp-container">
          <div className="lp-footer-links">
            <span>This dashboard is for educational and analytical purposes only.</span>
            <a href="mailto:contact@optionlense.com">contact@optionlense.com</a>
            <a href="#">Privacy Policy</a>
            <a href="#">Terms</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
