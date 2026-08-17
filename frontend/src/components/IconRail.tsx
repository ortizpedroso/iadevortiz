type Props = {
  panel: "project" | "spec" | null;
  onPanel: (panel: "project" | "spec" | null) => void;
  hasSpec: boolean;
  previewAvailable: boolean;
  onPreview: () => void;
};

export function IconRail({ panel, onPanel, hasSpec, previewAvailable, onPreview }: Props) {
  const btn =
    "grid h-11 w-11 place-items-center rounded-xl text-[var(--pkf-muted)] transition hover:bg-[var(--pkf-border)] hover:text-[var(--pkf-text)] pkf-focus-ring";
  const active = "bg-[var(--pkf-border)] text-[var(--pkf-text)]";

  return (
    <nav
      aria-label="Navegação principal"
      className="hidden w-14 shrink-0 flex-col items-center gap-2 border-r border-[var(--pkf-border)] bg-[var(--pkf-bg-rail)] py-4 md:flex"
    >
      <div className="mb-2 grid h-9 w-9 place-items-center rounded-lg bg-[var(--pkf-accent)]/15 text-sm font-bold text-[var(--pkf-accent)]">
        P
      </div>
      <button
        type="button"
        aria-label="Projeto e tarefas"
        aria-pressed={panel === "project"}
        className={`${btn} ${panel === "project" ? active : ""}`}
        onClick={() => onPanel(panel === "project" ? null : "project")}
      >
        ☰
      </button>
      {hasSpec ? (
        <button
          type="button"
          aria-label="Especificação"
          aria-pressed={panel === "spec"}
          className={`${btn} ${panel === "spec" ? active : ""}`}
          onClick={() => onPanel(panel === "spec" ? null : "spec")}
        >
          ◫
        </button>
      ) : null}
      {previewAvailable ? (
        <button type="button" aria-label="Preview do projeto" className={btn} onClick={onPreview}>
          ▣
        </button>
      ) : null}
    </nav>
  );
}
