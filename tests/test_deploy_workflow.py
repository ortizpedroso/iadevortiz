"""Validação estrutural do workflow de deploy GitHub Actions."""

from pathlib import Path


def test_deploy_workflow_exists_and_parses():
    path = Path(".github/workflows/deploy.yml")
    assert path.is_file(), "deploy.yml ausente"
    text = path.read_text(encoding="utf-8")
    for needle in (
        '"on":',
        "branches:",
        "main",
        "appleboy/ssh-action@v1.2.0",
        "secrets.VPS_HOST",
        "secrets.VPS_USER",
        "secrets.VPS_SSH_KEY",
        "timeout-minutes: 10",
        "deploy/hostinger/update.sh",
        "VPS_HEALTHCHECK_URL",
    ):
        assert needle in text, f"Trecho ausente no workflow: {needle}"
    try:
        import yaml
    except ImportError:
        return
    doc = yaml.safe_load(text)
    assert doc["on"]["push"]["branches"] == ["main"]
    assert "deploy" in doc["jobs"]
    assert doc["jobs"]["deploy"]["timeout-minutes"] == 10
