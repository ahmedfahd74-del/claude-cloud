import type { ReactNode } from "react";

export function Badge({ label }: { label: string }) {
  return <span style={{ background: "#eef2ff", color: "#3730a3", borderRadius: 9999, padding: "0.2rem 0.6rem" }}>{label}</span>;
}

export function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 16, marginBottom: 12 }}>
      <h3>{title}</h3>
      {children}
    </section>
  );
}

export function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 12, minWidth: 140 }}>
      <small>{label}</small>
      <div style={{ fontWeight: 700 }}>{value}</div>
    </div>
  );
}

export function LoadingState({ label = "Loading..." }: { label?: string }) {
  return <p aria-busy="true">{label}</p>;
}

export function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <div>
      <h4>{title}</h4>
      <p>{message}</p>
    </div>
  );
}

export function ErrorState({ title = "Error", message }: { title?: string; message: string }) {
  return (
    <div style={{ border: "1px solid #fecaca", background: "#fef2f2", padding: 12, borderRadius: 8 }}>
      <strong>{title}</strong>
      <p>{message}</p>
    </div>
  );
}
