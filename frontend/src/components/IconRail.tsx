type Props = {
  panel: "project" | "spec" | null;
  onPanel: (panel: "project" | "spec" | null) => void;
  hasSpec: boolean;
  previewAvailable: boolean;
  onPreview: () => void;
};

export function IconRail({ panel, onPanel, hasSpec, previewAvailable, onPreview }: Props) {
  const btn =
    "grid h-11 w-11 place-items-center rounded-xl text-[#9b9b9b] transition hover:bg-[#2e2e2e] hover:text-[#ececec] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#d97757]";
  const active = "bg-[#2e2e2e] text-[#ececec]";

  return (
    <nav
      aria-label="Navegação principal"
      className="hidden w-14 shrink-0 flex-col items-center gap-2 border-r border-[#2e2e2e] bg-[#141414] py-4 md:flex"
    >
      <div className="mb-2 grid h-9 w-9 place-items-center rounded-lg bg-[#d97757]/15 text-sm font-bold text-[#d97757]">
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
