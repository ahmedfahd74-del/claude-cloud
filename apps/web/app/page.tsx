import Link from "next/link";

export default function HomePage() {
  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem", display: "grid", gap: "1rem" }}>
      <h1>Zero-Cost AI Multi-Asset Trading Company OS</h1>
      <p>Paper-trading-only operating system. Live execution is disabled.</p>
      <nav style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <Link href="/overview">Overview</Link>
        <Link href="/market-radar">Market Radar</Link>
        <Link href="/governance">Governance</Link>
        <Link href="/opportunities">Opportunities</Link>
        <Link href="/portfolio">Portfolio</Link>
        <Link href="/execution">Execution</Link>
        <Link href="/memory">Memory</Link>
        <Link href="/settings">Settings</Link>
      </nav>
    </main>
  );
}
