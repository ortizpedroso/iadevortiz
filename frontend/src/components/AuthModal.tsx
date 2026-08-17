import { FormEvent, useState } from "react";

type Props = {
  open: boolean;
  onSubmit: (token: string) => void;
};

export function AuthModal({ open, onSubmit }: Props) {
  const [token, setToken] = useState("");

  if (!open) return null;

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const value = token.trim();
    if (value) onSubmit(value);
  }

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="auth-title"
    >
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md rounded-2xl border border-[var(--pkf-border)] bg-[var(--pkf-bg-panel)] p-6 shadow-2xl"
      >
        <h2 id="auth-title" className="font-serif text-2xl font-semibold text-[var(--pkf-text)]">
          Entrar na PKF
        </h2>
        <p className="mt-2 text-sm text-[var(--pkf-muted)]">
          Informe o token de acesso configurado em <code className="font-mono">PKF_AUTH_TOKEN</code>.
        </p>
        <label htmlFor="auth-token" className="mt-5 block text-xs font-medium uppercase tracking-wide text-[var(--pkf-muted)]">
          Token
        </label>
        <input
          id="auth-token"
          type="password"
          autoComplete="current-password"
          autoFocus
          value={token}
          onChange={(e) => setToken(e.target.value)}
          className="pkf-input mt-2 w-full px-4 py-3 text-sm"
          placeholder="Bearer token"
        />
        <button
          type="submit"
          disabled={!token.trim()}
          className="mt-5 w-full rounded-xl bg-[var(--pkf-accent)] py-3 text-sm font-semibold text-[var(--pkf-bg-primary)] transition hover:brightness-110 disabled:opacity-40 pkf-focus-ring"
        >
          Continuar
        </button>
      </form>
    </div>
  );
}
