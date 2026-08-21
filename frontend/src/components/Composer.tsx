import { FormEvent, useEffect, useRef, useState } from "react";

const SUGGESTIONS = [
  "Cardápio digital whitelabel para restaurantes",
  "Landing page para startup de IA",
  "Painel admin com login e dashboard",
];

type Props = {
  busy: boolean;
  onSend: (text: string) => void;
};

export function Composer({ busy, onSend }: Props) {
  const [text, setText] = useState("");
  const ta = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ta.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);

  function submit(e?: FormEvent) {
    e?.preventDefault();
    const v = text.trim();
    if (!v || busy) return;
    onSend(v);
    setText("");
  }

  return (
    <footer className="border-t border-[var(--pkf-border-soft)] bg-[var(--pkf-bg-primary)]/95 px-4 py-5 backdrop-blur">
      <div className="mx-auto w-full max-w-4xl">
        {!busy ? (
          <div className="mb-3 flex flex-wrap justify-center gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => onSend(s)}
                className="rounded-full border border-[var(--pkf-border-soft)] bg-[var(--pkf-bg-panel)] px-3 py-1.5 text-xs text-[var(--pkf-muted)] transition hover:border-[var(--pkf-accent)]/40 hover:text-[var(--pkf-text)] pkf-focus-ring"
              >
                {s.split(" ").slice(0, 3).join(" ")}…
              </button>
            ))}
          </div>
        ) : null}
        <form
          onSubmit={submit}
          className="flex items-end gap-2 rounded-[1.75rem] border border-[var(--pkf-border-soft)] bg-white p-2 shadow-[0_4px_24px_rgba(31,30,28,0.08)] focus-within:border-[var(--pkf-accent)]/50"
        >
          <label htmlFor="prompt" className="sr-only">
            Mensagem para a PKF
          </label>
          <textarea
            id="prompt"
            ref={ta}
            rows={1}
            value={text}
            disabled={busy}
            placeholder="Descreva o que você quer construir… (/spec, /build, /review)"
            aria-busy={busy}
            className="max-h-[200px] min-h-11 flex-1 resize-none bg-transparent px-3 py-2.5 text-[15px] outline-none placeholder:text-[var(--pkf-text-dim)]"
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
          />
          <button
            type="submit"
            disabled={busy || !text.trim()}
            aria-label="Enviar"
            className="mb-0.5 grid h-10 w-10 shrink-0 place-items-center rounded-full bg-[var(--pkf-accent)] text-[#1a1917] transition hover:bg-[var(--pkf-accent-hover)] disabled:opacity-30 pkf-focus-ring"
          >
            ↑
          </button>
        </form>
        <p className="mt-2 text-center text-[11px] text-[var(--pkf-text-dim)]">Enter envia · Shift+Enter nova linha</p>
      </div>
    </footer>
  );
}
