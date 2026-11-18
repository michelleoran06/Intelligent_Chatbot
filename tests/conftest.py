"""Configuración común: base de datos temporal y vector store falso.

Las variables de entorno se definen ANTES de importar los módulos del proyecto.
"""
import os
import tempfile

_TMP_DIR = tempfile.mkdtemp(prefix="chatbot_tests_")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DIR}/test_chatbot.db"
os.environ["CHROMA_PATH"] = os.path.join(_TMP_DIR, "chroma")
# Credenciales SOLO de prueba (no son de ningún entorno real). El hash se calcula aquí mismo.
TEST_PASSWORD = "contrasena-de-prueba-123"
TEST_SECRET_KEY = "clave-de-prueba-para-firmar-tokens-0123456789"
os.environ["AUTH_SECRET_KEY"] = TEST_SECRET_KEY

import bcrypt  # noqa: E402
import pytest  # noqa: E402

os.environ["OPERATOR_PASSWORD_HASH"] = bcrypt.hashpw(TEST_PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()

import vector_store  # noqa: E402
from tests.fakes import FakeVectorStore  # noqa: E402

FAKE_STORE = FakeVectorStore()
vector_store.set_store(FAKE_STORE)


def operator_headers() -> dict:
    """Encabezado Authorization con un token válido del operador."""
    import security

    return {"Authorization": f"Bearer {security.create_token()}"}


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    import main

    with TestClient(main.app) as test_client:  # ejecuta el lifespan (carga la base de conocimiento)
        yield test_client


@pytest.fixture(autouse=True)
def clean_state():
    """Antes de cada prueba: tablas de conversaciones, reseñas y errores vacías y caché limpia."""
    FAKE_STORE.fail = False
    try:
        import database as db
        import main
    except ImportError:  # entorno sin SQLAlchemy/FastAPI: solo corren las pruebas unitarias puras
        yield
        return
    with db.session_scope() as session:
        session.query(db.ConversationLog).delete()
        session.query(db.PlaceReview).delete()
        session.query(db.SystemErrorLog).delete()
        session.query(db.LoginAttempt).delete()
        session.query(db.OperatorAction).delete()
    main.nlp_engine.clear_cache()
    main.limiter.reset()
    yield
