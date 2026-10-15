import "./footer.css";

// Credits, prior work and the tracks this entry is for
export function Footer() {
  return (
    <footer className="footer">
      <div className="footer-grid">
        <div>
          <h3>TRACE-Graph</h3>
          <p>
            Built for Graph Hacks 2026 by Humble Bullies (Nikunj Kaushik and Tavish Agarwal). Entered in Track 01, with
            Tracks 02 and 03 as bonuses.
          </p>
        </div>
        <div>
          <h4>Prior work</h4>
          <p>
            The scoring is TRACE, from the CIKM 2026 paper "TRACE: Graph-Aware Anomaly Detection for Trust Routing in
            Adversarial Decentralized Marketplaces" (Kaushik and Gupta). The hire, escrow, judge
            and settle loop takes its ideas from{" "}
            <a href="https://github.com/NikunjKaushik20/satsrouter">SatsRouter</a>. Both were rebuilt from scratch on
            FalkorDB for this event.
          </p>
        </div>
        <div>
          <h4>Data</h4>
          <p>
            The market is synthetic: providers, Sybil writers and wallets are generated from fixed seeds. The language
            model is gpt-4o-mini, capped by a spend meter kept in FalkorDB.
          </p>
        </div>
      </div>
      <p className="footer-legal">
        Powered by <a href="https://www.falkordb.com">FalkorDB</a>. Every number on this page is read from the graph
        when the page loads.
      </p>
    </footer>
  );
}
