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
      <div className="mx-auto max-w-4xl px-4 pt-[10vh] text-center">
        <div className="mx-auto mb-6 grid h-14 w-14 place-items-center rounded-2xl bg-[var(--pkf-accent)] text-xl font-bold text-[#1a1917]">
          P
        </div>
        <h1 className="font-serif text-4xl font-semibold tracking-tight text-[var(--pkf-text)] md:text-5xl">
          Como posso ajudar?
        </h1>
        <p className="mt-4 text-[var(--pkf-muted)]">
          Descreva o que você quer construir. Eu especifico, implemento e reviso o código.
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
    <div className="mx-auto flex max-w-4xl flex-col gap-8 px-4 pb-10 pt-6">
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
                  ? "max-w-[85%] rounded-3xl rounded-br-md bg-[var(--pkf-user-bubble)] px-4 py-3 text-[var(--pkf-text)] ring-1 ring-[var(--pkf-border-soft)]"
                  : isError
                    ? "rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-red-800"
                    : "pkf-markdown text-[var(--pkf-text)]"
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
