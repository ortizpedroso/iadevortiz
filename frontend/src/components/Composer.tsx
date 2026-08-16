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
    <footer className="border-t border-[#2e2e2e] bg-[#191919]/95 px-4 py-4 backdrop-blur">
      <div className="mx-auto max-w-2xl">
        {!busy ? (
          <div className="mb-3 flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => onSend(s)}
                className="rounded-full border border-[#2e2e2e] bg-[#212121] px-3 py-1.5 text-xs text-[#9b9b9b] transition hover:border-[#d97757]/40 hover:text-[#ececec]"
              >
                {s.split(" ").slice(0, 3).join(" ")}…
              </button>
            ))}
          </div>
        ) : null}
        <form
          onSubmit={submit}
          className="flex items-end gap-2 rounded-2xl border border-[#2e2e2e] bg-[#212121] p-2 shadow-lg focus-within:border-[#d97757]/50"
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
            className="max-h-[200px] min-h-11 flex-1 resize-none bg-transparent px-3 py-2.5 text-[15px] outline-none placeholder:text-[#666]"
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
            className="mb-0.5 grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#d97757] text-[#191919] transition hover:brightness-110 disabled:opacity-30"
          >
            ↑
          </button>
        </form>
        <p className="mt-2 text-center text-[11px] text-[#666]">Enter envia · Shift+Enter nova linha</p>
      </div>
    </footer>
  );
}
