from pkf.workflow.compose import verify_ok


def test_verify_ok_positive():
    assert verify_ok("ok: 3 arquivos gerados")


def test_verify_ok_negative():
    assert not verify_ok("nenhum arquivo encontrado")
