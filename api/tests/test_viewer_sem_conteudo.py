"""Viewer sem conteúdo de conversa e sem telefone (COM-09, SEC-10)."""

from app.models.user import UserRole
from app.routers.runs import masked_user
from app.schemas.user import ROLE_SCOPES


def test_viewer_nao_le_sessoes_nem_traces() -> None:
    viewer = ROLE_SCOPES[UserRole.viewer]
    assert "sessions:read" not in viewer and "traces:read" not in viewer
    assert "configs:read" in viewer


def test_id_de_quem_falou_mascarado() -> None:
    assert masked_user("whatsapp:5511999990000") == "whatsapp:•••0000"
    assert masked_user("ana@cliente.com") == "•••.com"
    assert masked_user(None) is None
