import { useCallback, useEffect, useState } from "react";
import { useAgentRun } from "./agent/useAgentRun";
import { NamesProvider } from "./graph/names";
import { useHealth, useSnapshot } from "./hooks/useLive";
import { AgentSection } from "./sections/agent/AgentSection";
import { AskSection } from "./sections/ask/AskSection";
import { Footer } from "./sections/Footer";
import { Hero } from "./sections/Hero";
import { Nav } from "./sections/Nav";
import { ProofSection } from "./sections/proof/ProofSection";
import { ReceiptSection } from "./sections/receipts/ReceiptSection";
import { RingSection } from "./sections/ring/RingSection";
import { UnplugSection } from "./sections/UnplugSection";

// The whole page: one shared graph snapshot and one agent run feed every section
export function App() {
  const live = useHealth();
  const market = useSnapshot();
  const [receiptsVersion, setReceiptsVersion] = useState(0);
  const [openDecision, setOpenDecision] = useState<string | null>(null);

  // A tool result changed the graph: redraw it and let the receipt list catch up
  const onGraphChange = useCallback(() => {
    market.reload();
    setReceiptsVersion((version) => version + 1);
  }, [market]);

  const { run, start } = useAgentRun(onGraphChange);
  const databaseUp = live.health?.falkordb === "up" && !live.health.unplugged;
  const { load: loadMarket } = market;

  // Reads the graph again whenever FalkorDB comes back
  useEffect(() => {
    if (databaseUp) loadMarket();
  }, [databaseUp, loadMarket]);

  // Jumps to the receipts section with one decision open
  const showReceipt = useCallback((decisionId: string) => {
    setOpenDecision(decisionId);
    document.getElementById("receipts")?.scrollIntoView({ behavior: "smooth" });
  }, []);

  return (
    <NamesProvider snapshot={market.snapshot}>
      <Nav health={live.health} reachable={live.reachable} />
      <main>
        <Hero
          snapshot={market.snapshot}
          error={market.error}
          onRetry={market.load}
          health={live.health}
          spend={live.spend}
        />
        <AgentSection snapshot={market.snapshot} run={run} onStart={start} onShowReceipt={showReceipt} />
        <RingSection run={run} snapshot={market.snapshot} />
        <ReceiptSection version={receiptsVersion} openDecision={openDecision} onOpen={setOpenDecision} />
        <ProofSection />
        <AskSection snapshot={market.snapshot} />
        <UnplugSection
          health={live.health}
          reachable={live.reachable}
          onChange={() => {
            live.refresh();
            market.load();
          }}
        />
      </main>
      <Footer />
    </NamesProvider>
  );
}
