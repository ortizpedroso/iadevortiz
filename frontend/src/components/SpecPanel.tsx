import { useState } from "react";
import type { SpecPreview } from "../types";
import { authHeaders } from "../lib/api";

type Props = {
  spec: SpecPreview | null | undefined;
  specName?: string | null;
  onApproved: () => void;
};

export function SpecPanel({ spec, specName, onApproved }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [stack, setStack] = useState<Record<string, string>>(() => ({
    ...(spec?.suggested_stack || {}),
    ...(spec?.confirmed_stack || {}),
  }));

  if (!spec || spec.status === "approved") return null;

  async function approve() {
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/spec/approve", {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({
          name: specName || spec?.name,
          confirmed_stack: stack,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        setError(data.error || "Não foi possível aprovar a spec.");
        return;
      }
      onApproved();
    } catch {
      setError("Erro de rede ao aprovar a spec.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="flex w-full flex-col border-t border-[var(--pkf-border)] bg-[var(--pkf-bg-panel)] lg:w-96 lg:border-l lg:border-t-0">
      <header className="border-b border-[var(--pkf-border)] px-4 py-3">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--pkf-muted)]">Especificação</p>
        <h2 className="font-serif text-lg font-semibold">{spec.title || "Spec do projeto"}</h2>
        <p className="mt-1 text-xs text-[var(--pkf-accent)]">Aguardando aprovação</p>
      </header>
      <div className="min-h-0 flex-1 overflow-auto px-4 py-3 text-sm leading-relaxed text-[#cfcfcf]">
        <pre className="whitespace-pre-wrap font-sans">{spec.body?.slice(0, 4000) || "—"}</pre>
        {Object.keys(stack).length ? (
          <div className="mt-4 space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--pkf-muted)]">Stack</p>
            {Object.entries(stack).map(([key, value]) => (
              <label key={key} className="block text-xs">
                <span className="text-[var(--pkf-muted)]">{key}</span>
                <input
                  value={value}
                  onChange={(e) => setStack((s) => ({ ...s, [key]: e.target.value }))}
                  className="pkf-input mt-1 w-full font-mono text-xs"
                />
              </label>
            ))}
          </div>
        ) : null}
      </div>
      <footer className="border-t border-[var(--pkf-border)] p-4">
        {error ? <p className="mb-2 text-xs text-red-300">{error}</p> : null}
        <button
          type="button"
          disabled={busy}
          onClick={approve}
          className="w-full rounded-xl bg-[var(--pkf-accent)] py-2.5 text-sm font-semibold text-[var(--pkf-bg-primary)] hover:brightness-110 disabled:opacity-50 pkf-focus-ring"
        >
          {busy ? "Aprovando…" : "Aprovar spec"}
        </button>
      </footer>
    </aside>
  );
}
