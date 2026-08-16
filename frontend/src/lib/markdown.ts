export function escapeHtml(text: string): string {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export function renderMarkdown(src: string): string {
  const escaped = escapeHtml(src || "");
  const parts = escaped.split(/```([\s\S]*?)```/g);
  let html = "";
  parts.forEach((part, index) => {
    if (index % 2 === 1) {
      const nl = part.indexOf("\n");
      const code = nl === -1 ? part : part.slice(nl + 1);
      html += `<pre class="mt-3 overflow-auto rounded-lg bg-slate-950 p-3 text-sm font-mono"><code>${code}</code></pre>`;
      return;
    }
    html += part
      .replace(/^### (.+)$/gm, '<h3 class="mt-3 text-lg font-semibold">$1</h3>')
      .replace(/^## (.+)$/gm, '<h2 class="mt-4 text-xl font-semibold">$1</h2>')
      .replace(/^# (.+)$/gm, '<h1 class="mt-4 text-2xl font-bold">$1</h1>')
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, '<code class="rounded bg-slate-950 px-1 font-mono text-sm">$1</code>')
      .replace(/^\- (.+)$/gm, "<li>$1</li>")
      .replace(/(<li>.*<\/li>)/gs, '<ul class="list-disc pl-5">$1</ul>')
      .replace(/\n{2,}/g, "</p><p>")
      .replace(/^(?!<[uhl]|<p|<pre)/, "<p>")
      .replace(/(?!>)$/, "</p>");
  });
  return html;
}
