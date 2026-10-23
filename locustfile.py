"""Prueba de carga con Locust (Sección 19.5).

Mezcla de consultas tomada del conjunto de prueba: 4 de cada 5 son respondibles y 1 de cada 5
se escala. Cada consulta escalada crea un ticket, así que conviene correr la prueba contra
los contenedores locales (docker compose) y no contra la base de producción.

Uso básico (interfaz web en http://localhost:8089):
    locust -f locustfile.py --host http://127.0.0.1:8000

Escalones de 10, 50, 100, 250 y 500 usuarios (60 s cada uno), sin interfaz:
    STEP_LOAD=1 locust -f locustfile.py --host http://127.0.0.1:8000 --headless --csv evaluation/results/load
"""
import csv
import os
import random

from locust import HttpUser, LoadTestShape, between, task

_TEST_SET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evaluation", "test_set.csv")
with open(_TEST_SET, newline="", encoding="utf-8") as _handle:
    _ROWS = list(csv.DictReader(_handle))
ANSWERABLE = [r["query"] for r in _ROWS if r["expected"] != "ESCALATE"]
ESCALATE = [r["query"] for r in _ROWS if r["expected"] == "ESCALATE"]
USER_TYPES = ["estudiante", "maestro", "administrativo"]


class ChatbotUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.user_id = f"locust_{random.randint(1, 100000)}"
        self.user_type = random.choice(USER_TYPES)

    def _ask(self, query, name):
        payload = {"user_id": self.user_id, "user_type": self.user_type, "query": query}
        with self.client.post("/api/v1/chat", json=payload, name=name, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(4)
    def ask_answerable_question(self):
        self._ask(random.choice(ANSWERABLE), "chat: pregunta respondible")

    @task(1)
    def ask_escalation_question(self):
        self._ask(random.choice(ESCALATE), "chat: pregunta que se escala")


if os.getenv("STEP_LOAD") == "1":
    class StepLoadShape(LoadTestShape):
        """Escalones de usuarios concurrentes de la Tabla 31."""

        steps = [(10, 60), (50, 60), (100, 60), (250, 60), (500, 60)]
        spawn_rate = 10

        def tick(self):
            run_time = self.get_run_time()
            elapsed = 0
            for users, duration in self.steps:
                elapsed += duration
                if run_time < elapsed:
                    return users, self.spawn_rate
            return None
