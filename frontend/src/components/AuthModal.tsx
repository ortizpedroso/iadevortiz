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
        className="w-full max-w-md rounded-2xl border border-[#2e2e2e] bg-[#212121] p-6 shadow-2xl"
      >
        <h2 id="auth-title" className="font-serif text-2xl font-semibold text-[#ececec]">
          Entrar na PKF
        </h2>
        <p className="mt-2 text-sm text-[#9b9b9b]">
          Informe o token de acesso configurado em <code className="font-mono">PKF_AUTH_TOKEN</code>.
        </p>
        <label htmlFor="auth-token" className="mt-5 block text-xs font-medium uppercase tracking-wide text-[#9b9b9b]">
          Token
        </label>
        <input
          id="auth-token"
          type="password"
          autoComplete="current-password"
          autoFocus
          value={token}
          onChange={(e) => setToken(e.target.value)}
          className="mt-2 w-full rounded-xl border border-[#2e2e2e] bg-[#191919] px-4 py-3 text-sm outline-none focus:border-[#d97757] focus:ring-2 focus:ring-[#d97757]/30"
          placeholder="Bearer token"
        />
        <button
          type="submit"
          disabled={!token.trim()}
          className="mt-5 w-full rounded-xl bg-[#d97757] py-3 text-sm font-semibold text-[#191919] transition hover:brightness-110 disabled:opacity-40"
        >
          Continuar
        </button>
      </form>
    </div>
  );
}
