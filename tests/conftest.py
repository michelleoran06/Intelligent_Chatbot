"""Configuración común: base de datos temporal y vector store falso.

Las variables de entorno se definen ANTES de importar los módulos del proyecto.
"""
import os
import tempfile

_TMP_DIR = tempfile.mkdtemp(prefix="chatbot_tests_")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DIR}/test_chatbot.db"
os.environ["CHROMA_PATH"] = os.path.join(_TMP_DIR, "chroma")
os.environ["ADMIN_TOKEN"] = "token-de-prueba"

import pytest  # noqa: E402

import vector_store  # noqa: E402
from tests.fakes import FakeVectorStore  # noqa: E402

FAKE_STORE = FakeVectorStore()
vector_store.set_store(FAKE_STORE)

ADMIN_HEADERS = {"X-Admin-Token": "token-de-prueba"}


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
    main.nlp_engine.clear_cache()
    yield
