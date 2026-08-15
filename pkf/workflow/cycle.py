from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from pkf.config import pkf_dir

COMMANDS = ("/spec", "/build", "/review", "/status", "/agents", "/graph", "/help", "/workspace")


def parse_command(user_input: str) -> tuple[str | None, str]:
    text = user_input.strip()
    lower = text.lower()
    for command in COMMANDS:
        if lower == command or lower.startswith(command + " "):
            return command, text[len(command) :].strip()
    return None, text


@dataclass
class DevCycle:
    phase: str = "IDLE"
    active_spec: str | None = None
    last_agent: str | None = None

    @classmethod
    def load(cls, workspace_root: Path) -> "DevCycle":
        path = pkf_dir(workspace_root) / "session.json"
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(
                phase=data.get("phase", "IDLE"),
                active_spec=data.get("active_spec"),
                last_agent=data.get("last_agent"),
            )
        except json.JSONDecodeError:
            return cls()

    def persist(self, workspace_root: Path) -> None:
        path = pkf_dir(workspace_root) / "session.json"
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

    def set_spec(self, name: str | None) -> None:
        if name:
            self.active_spec = slugify(name)

    def apply(self, command: str | None, kind: str, remainder: str) -> tuple[str, str]:
        """Atualiza a fase e devolve um prefixo de instrução para o agente."""
        if command == "/spec":
            self.phase = "SPEC"
            if remainder:
                self.set_spec(remainder.splitlines()[0][:60])
            return self.phase, _spec_instruction(remainder, self.active_spec)
        if command == "/build":
            self.phase = "BUILD"
            if remainder:
                self.set_spec(remainder)
            return self.phase, _build_instruction(self.active_spec)
        if command == "/review":
            self.phase = "REVIEW"
            return self.phase, _review_instruction(self.active_spec)

        if kind == "feature" and self.phase == "IDLE":
            self.phase = "SPEC"
            if remainder:
                self.set_spec(remainder.splitlines()[0][:60])
            return self.phase, _spec_instruction(remainder, self.active_spec)

        if kind == "change" and self.phase in {"BUILD", "REVIEW"}:
            self.phase = "SPEC"
            return self.phase, (
                "O usuário pediu uma mudança após implementação. "
                "Declare que a spec será atualizada, atualize com save_spec e só então descreva o impacto. "
                f"Pedido: {remainder}"
            )
        return self.phase, remainder

    def status_text(self) -> str:
        spec = self.active_spec or "(nenhuma)"
        agent = self.last_agent or "(nenhum)"
        return f"Fase: {self.phase}\nSpec ativa: {spec}\nÚltimo agente: {agent}"


def slugify(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower()).strip("-")
    return cleaned or "spec"


def _spec_instruction(remainder: str, spec_name: str | None) -> str:
    target = spec_name or "recurso"
    extra = f"\nPedido do usuário: {remainder}" if remainder else ""
    return (
        "Inicie ou continue /spec. Entreviste só o que faltar, feche requisitos e salve com save_spec. "
        f"Nome sugerido da spec: {target}.{extra}"
    )


def _build_instruction(spec_name: str | None) -> str:
    name = spec_name or ""
    return (
        "Fase /build. Leia a spec com get_spec"
        + (f" (name={name})" if name else "")
        + ", inspecione o código existente e implemente exatamente o que foi especificado."
    )


def _review_instruction(spec_name: str | None) -> str:
    name = spec_name or ""
    return (
        "Fase /review. Compare o código com a spec"
        + (f" '{name}'" if name else "")
        + ", aponte lacunas concretas e salve o relatório com save_review."
    )
