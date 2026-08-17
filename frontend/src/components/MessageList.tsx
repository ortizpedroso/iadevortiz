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
      <div className="mx-auto max-w-2xl px-4 pt-[12vh] text-center">
        <h1 className="font-serif text-4xl font-semibold tracking-tight text-[var(--pkf-text)] md:text-5xl">
          O que vamos construir?
        </h1>
        <p className="mt-4 text-[var(--pkf-muted)]">
          Descreva seu app ou funcionalidade. A PKF especifica, implementa e revisa por você.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-2 text-xs text-[var(--pkf-text-dim)]">
          <span className="rounded-full border border-[var(--pkf-border)] px-3 py-1">/spec</span>
          <span className="rounded-full border border-[var(--pkf-border)] px-3 py-1">/build</span>
          <span className="rounded-full border border-[var(--pkf-border)] px-3 py-1">/review</span>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-8 px-4 pb-10 pt-6">
      {messages.map((msg, i) => {
        const isUser = msg.role === "user";
        const isError = msg.role === "error";
        return (
          <article key={i} className={isUser ? "flex justify-end" : ""} aria-label={isUser ? "Sua mensagem" : "Resposta PKF"}>
            {!isUser ? (
              <div className="mb-2 flex items-center gap-2">
                <span className="grid h-6 w-6 place-items-center rounded-lg bg-[var(--pkf-accent)]/15 text-xs font-bold text-[var(--pkf-accent)]">
                  P
                </span>
                <span className="text-xs font-medium text-[var(--pkf-muted)]">{msg.agent && msg.agent !== "pkf" ? msg.agent : "PKF"}</span>
              </div>
            ) : null}
            <div
              className={`text-[15px] leading-relaxed ${
                isUser
                  ? "max-w-[85%] rounded-2xl rounded-br-md bg-[var(--pkf-border)] px-4 py-3 text-[var(--pkf-text)]"
                  : isError
                    ? "rounded-xl border border-red-500/40 bg-red-950/20 px-4 py-3 text-red-200"
                    : "pkf-markdown text-[#d4d4d4]"
              }`}
              {...(!isUser && !isError
                ? { dangerouslySetInnerHTML: { __html: renderMarkdown(msg.content) } }
                : {})}
            >
              {isUser || isError ? <p>{msg.content}</p> : null}
            </div>
          </article>
        );
      })}
      {thinking ? (
        <div className="flex items-center gap-2 text-sm text-[var(--pkf-muted)]" aria-live="polite">
          <span className="inline-flex gap-1">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--pkf-accent)]" />
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--pkf-accent)] [animation-delay:150ms]" />
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--pkf-accent)] [animation-delay:300ms]" />
          </span>
          Trabalhando…
        </div>
      ) : null}
    </div>
  );
}
