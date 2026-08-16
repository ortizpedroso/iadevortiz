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
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [text]);

  function submit(e?: FormEvent) {
    e?.preventDefault();
    const v = text.trim();
    if (!v || busy) return;
    onSend(v);
    setText("");
  }

  return (
    <footer className="border-t border-slate-800 bg-[#0f172a]/90 p-4 backdrop-blur">
      <div className="mx-auto max-w-3xl">
        {!busy ? (
          <div className="mb-3 flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => onSend(s)}
                className="min-h-10 rounded-full border border-slate-700 bg-slate-900/60 px-3 text-xs transition hover:border-slate-500"
              >
                {s.split(" ")[0]}…
              </button>
            ))}
          </div>
        ) : null}
        <form
          onSubmit={submit}
          className="flex items-end gap-2 rounded-2xl border border-slate-700 bg-[#111827] p-2 shadow-xl"
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
            placeholder="Descreva o que você quer construir…"
            aria-busy={busy}
            className="max-h-[180px] min-h-11 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none placeholder:text-slate-500 focus-visible:ring-2 focus-visible:ring-emerald-500/50 rounded-lg"
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
            className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-emerald-500 text-emerald-950 transition hover:brightness-110 disabled:opacity-40"
          >
            →
          </button>
        </form>
        <p className="mt-2 text-center text-xs text-slate-500">Enter envia · Shift+Enter quebra linha</p>
      </div>
    </footer>
  );
}
