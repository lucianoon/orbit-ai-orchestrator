"""Autenticação: hash PBKDF2, tokens com expiração e usuários em SQLite."""
import pytest

import auth


@pytest.fixture(autouse=True)
def _auth_db(tmp_path, monkeypatch):
    """Redireciona o SQLite de auth para tmp e reinicializa o schema."""
    monkeypatch.setattr(auth, "AUTH_DB_PATH", str(tmp_path / "auth.db"))
    auth.init_auth_db()


def test_hash_e_verificacao_senha():
    h = auth.hash_password("secreta123")
    assert ":" in h and h != "secreta123"
    assert auth.verify_password("secreta123", h) is True
    assert auth.verify_password("errada", h) is False


def test_verify_password_com_hash_malformado_retorna_false():
    assert auth.verify_password("x", "sem-separador") is False


def test_criar_usuario_e_duplicado():
    uid = auth.create_user("ana", "secreta123", "ana@ex.com")
    assert isinstance(uid, int)
    assert auth.create_user("ana", "outra456") is None


def test_autenticar_usuario_sucesso_e_falhas():
    auth.create_user("bruno", "senha987")
    user = auth.authenticate_user("bruno", "senha987")
    assert user["username"] == "bruno"
    assert auth.authenticate_user("bruno", "errada") is None
    assert auth.authenticate_user("inexistente", "qualquer") is None


def test_token_criar_validar_deletar():
    uid = auth.create_user("carla", "senha321")
    token, expires_at = auth.create_token(uid)
    assert auth.validate_token(token) == uid
    auth.delete_token(token)
    assert auth.validate_token(token) is None


def test_token_inexistente_retorna_none():
    assert auth.validate_token("nao-existe") is None


def test_token_expirado_invalida_e_remove():
    from datetime import datetime, timedelta

    uid = auth.create_user("diego", "senha555")
    conn = auth.get_auth_db()
    cursor = conn.cursor()
    passado = (datetime.now() - timedelta(hours=1)).isoformat()
    cursor.execute(
        "INSERT INTO tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
        (uid, "token-velho", passado),
    )
    conn.commit()
    conn.close()

    assert auth.validate_token("token-velho") is None
    # validação remove tokens expirados
    assert auth.validate_token("token-velho") is None


def test_get_user_by_id():
    uid = auth.create_user("elisa", "senha777")
    user = auth.get_user_by_id(uid)
    assert user["username"] == "elisa"
    assert "password_hash" not in user  # nunca vazar hash em consultas públicas
    assert auth.get_user_by_id(99999) is None
