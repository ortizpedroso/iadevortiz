import type { Message } from "../types";
import { renderMarkdown } from "../lib/markdown";

export function MessageList({
  messages,
  thinking,
}: {
  messages: Message[];
  thinking: boolean;
}) {
  if (!messages.length && !thinking) {
    return (
      <div className="mx-auto max-w-3xl px-4 pt-[10vh] text-center">
        <h1 className="text-3xl font-bold tracking-tight md:text-4xl">O que vamos construir?</h1>
        <p className="mt-3 text-slate-400">Descreva seu app, site ou funcionalidade. A PKF cuida do resto.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5 px-4 pb-8">
      {messages.map((msg, i) => (
        <article key={i} className="space-y-2" aria-label={msg.role === "user" ? "Sua mensagem" : "Resposta PKF"}>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            {msg.role === "user" ? "Você" : "PKF"}
          </div>
          <div
            className={`rounded-xl border px-4 py-3 text-sm leading-relaxed ${
              msg.role === "user"
                ? "border-slate-700 bg-slate-800"
                : msg.role === "error"
                  ? "border-red-500/50 text-red-200"
                  : "border-slate-700 bg-[#111827]"
            }`}
            {...(msg.role !== "user"
              ? { dangerouslySetInnerHTML: { __html: renderMarkdown(msg.content) } }
              : {})}
          >
            {msg.role === "user" ? <p>{msg.content}</p> : null}
          </div>
        </article>
      ))}
      {thinking ? (
        <div className="flex items-center gap-2 text-sm text-slate-400" aria-live="polite">
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
          PKF está trabalhando…
        </div>
      ) : null}
    </div>
  );
}
