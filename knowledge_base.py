"""Contenido inicial de la base de conocimiento (versión 2).

Fuente: docs/fuentes/base_de_conocimiento_cafeteria.txt (texto actualizado por el equipo).
Cuando ese texto y informacion_de_cafeteria.docx no coinciden, manda el texto actualizado.
Los métodos de pago y la ubicación no aparecen en ninguno de los dos y se conservan de la
versión anterior (pendientes de confirmar por el equipo).

Al arrancar, el backend compara KB_SEED_VERSION con la versión guardada en la SQL DB. Si cambió,
actualiza las entradas predeterminadas sin tocar las que creó el Administrador desde el panel.
La SQL DB es la fuente de verdad y los cambios se propagan a ChromaDB (Sección 4.4).

Cada entrada tiene:
- id: identificador único (minúsculas, números y guion bajo)
- category: nombre legible para el panel de administrador
- answer: la respuesta que recibe el usuario
- questions: preguntas de ejemplo; cada una se indexa por separado en ChromaDB
- keywords: palabras clave para el respaldo léxico (se necesitan 2 coincidencias)
"""

KB_SEED_VERSION = "2026-10-cafeteria-v2"

DEFAULT_ENTRIES = [
    {
        "id": "horarios",
        "category": "Horarios",
        "answer": (
            "La cafetería abre de lunes a sábado. De lunes a viernes el servicio es de 7:00 a.m. a 5:00 p.m. "
            "y los sábados solo se abre medio día. Las puertas se abren desde las 6:30 a.m., pero la venta "
            "empieza a las 7:00 a.m. Los desayunos se sirven hasta las 12:00 p.m."
        ),
        "questions": [
            "¿A qué hora abren la cafetería?",
            "¿A qué hora cierran la cafetería?",
            "¿Cuál es el horario de la cafetería?",
            "¿Qué días abren?",
            "¿Abren los sábados?",
            "¿Abren los domingos?",
            "¿Desde qué hora puedo desayunar?",
            "¿Hasta qué hora sirven desayunos?",
            "¿Hasta qué hora hay servicio?",
        ],
        "keywords": ["hora", "horario", "abren", "abre", "cierran", "cierra", "abierto", "abierta",
                     "sabado", "domingo", "lunes", "dias", "temprano", "atienden"],
    },
    {
        "id": "pagos",
        "category": "Métodos de pago",
        "answer": "Aceptamos pago en efectivo, con tarjeta de débito o crédito y por transferencia.",
        "questions": [
            "¿Cuáles son los métodos de pago?",
            "¿Aceptan tarjeta?",
            "¿Puedo pagar con transferencia?",
            "¿Solo aceptan efectivo?",
            "¿Tienen terminal para pagar con tarjeta?",
            "¿Cómo puedo pagar?",
        ],
        "keywords": ["pago", "pagar", "tarjeta", "efectivo", "transferencia", "terminal",
                     "debito", "credito", "aceptan", "metodo", "cobran"],
    },
    {
        "id": "ubicacion",
        "category": "Ubicación",
        "answer": "Estamos en la planta baja del edificio principal de la Facultad de Ingeniería.",
        "questions": [
            "¿Dónde está la cafetería?",
            "¿En qué edificio está la cafetería?",
            "¿Cómo llego a la cafetería?",
            "¿Cuál es la ubicación de la cafetería?",
            "¿En qué piso está la cafetería?",
        ],
        "keywords": ["ubicacion", "ubicada", "ubicados", "edificio", "planta", "piso", "llego",
                     "llegar", "cafeteria", "donde"],
    },
    {
        "id": "desayunos",
        "category": "Desayunos",
        "answer": (
            "Los desayunos se sirven hasta las 12:00 p.m. Tenemos huevos (al gusto, a la mexicana, con "
            "salchicha, con tocino, con jamón, rancheros o divorciados), omelette (de verduras o de jamón con "
            "queso), sopes y enchiladas, todos a $55. Los chilaquiles también se sirven en horario de desayuno."
        ),
        "questions": [
            "¿Qué desayunos tienen?",
            "¿Qué desayunos tienen y cuánto cuestan?",
            "¿Qué hay de desayunar?",
            "¿Venden huevos?",
            "¿Tienen omelette?",
            "¿Tienen enchiladas o sopes?",
            "¿Tienen huevos rancheros o divorciados?",
        ],
        "keywords": ["desayuno", "desayunar", "huevo", "omelette", "enchilada", "sope", "rancheros",
                     "divorciados", "mexicana", "salchicha", "tocino", "jamon"],
    },
    {
        "id": "antojitos",
        "category": "Antojitos y molletes",
        "answer": (
            "Antojitos: quesadillas $30, sincronizadas $35, tostadas $35, tacos dorados $45, tacos ahogados $50, "
            "gringa grande $55 y burrito grande $45. Molletes normales $35 y Molletes Xtreme (frijoles, queso "
            "manchego, chilaquiles y milanesa de pollo) $65."
        ),
        "questions": [
            "¿Qué antojitos y comida rápida venden?",
            "¿Venden quesadillas?",
            "¿Cuánto cuestan los molletes?",
            "¿Tienen tacos dorados?",
            "¿Cuánto cuesta la gringa?",
            "¿Tienen burritos?",
            "¿Venden tostadas?",
        ],
        "keywords": ["antojito", "quesadilla", "sincronizada", "mollete", "xtreme", "tostada", "taco",
                     "dorados", "ahogados", "gringa", "burrito"],
    },
    {
        "id": "chilaquiles",
        "category": "Chilaquiles",
        "answer": (
            "Los chilaquiles se sirven hasta las 12:00 p.m.: sencillos $40, con huevo $50, con milanesa de "
            "pollo o pechuga asada $65 y con cecina $75."
        ),
        "questions": [
            "¿Cuánto cuestan los chilaquiles?",
            "¿Qué chilaquiles tienen?",
            "¿Cuánto cuestan los chilaquiles con cecina?",
            "¿Tienen chilaquiles con pollo?",
            "¿Cuánto cuestan los chilaquiles sencillos?",
            "¿Hay chilaquiles con huevo?",
        ],
        "keywords": ["chilaquiles", "cecina", "sencillos", "huevo", "pollo", "pechuga", "milanesa"],
    },
    {
        "id": "sandwiches",
        "category": "Sándwiches",
        "answer": (
            "Sándwiches: de pollo deshebrado o de pechuga asada $30, de pierna sencillo $45 y Club Sándwich $65."
        ),
        "questions": [
            "¿Cuánto cuestan los sándwiches?",
            "¿Venden sándwiches?",
            "¿Cuánto cuesta el sándwich club?",
            "¿Tienen sándwich de pierna?",
            "¿Qué sándwiches tienen?",
        ],
        "keywords": ["sandwich", "sandwiches", "club", "pierna", "deshebrado"],
    },
    {
        "id": "paquetes",
        "category": "Paquetes de comida",
        "answer": (
            "Paquetes de comida: Paquete 1 (milanesa de pollo) $60, Paquete 2 (pechuga asada) $60, Paquete 3 "
            "(pechuga rellena de jamón y queso) $65, Paquete 4 (filete de pescado a la plancha) $70, Paquete 5 "
            "(filete de pescado empanizado) $70, Paquete 8 (cecina natural asada) $80, Paquete 9 (arrachera a la "
            "plancha) $80 y Paquete 10 (chorizo a la plancha) $70."
        ),
        "questions": [
            "¿Qué paquetes de comida tienen?",
            "¿Qué paquetes tienen con carne de res o cerdo?",
            "¿Cuánto cuesta el paquete de arrachera?",
            "¿Tienen comida completa?",
            "¿Venden filete de pescado?",
            "¿Cuánto cuesta la pechuga rellena?",
            "¿Tienen paquete de milanesa?",
        ],
        "keywords": ["paquete", "comida", "arrachera", "filete", "pescado", "cecina", "chorizo",
                     "milanesa", "pechuga", "rellena", "res", "cerdo", "plancha", "empanizado"],
    },
    {
        "id": "pizzas",
        "category": "Pizzas",
        "answer": (
            "La pizza completa cuesta $100; si necesitas caja para llevar son $20 extra. También vendemos "
            "rebanadas de hawaiana, carnes frías o carne molida a $25 cada una."
        ),
        "questions": [
            "¿Cuánto cuesta la pizza?",
            "¿Venden pizza?",
            "¿Qué sabores de pizza tienen?",
            "¿Cuánto cuesta una rebanada de pizza?",
            "¿Tienen pizza hawaiana?",
            "¿Cuánto cuesta la caja para llevar la pizza?",
        ],
        "keywords": ["pizza", "rebanada", "hawaiana", "molida", "frias", "completa", "entera", "caja", "sabores"],
    },
    {
        "id": "carnitas",
        "category": "Carnitas (viernes y sábado)",
        "answer": (
            "Los viernes y sábados hay carnitas: taco $15, torta de carnitas $30 y combo de 3 tacos con un agua "
            "por $50. También se venden por kilo, por medio kilo o desde $100."
        ),
        "questions": [
            "¿Venden carnitas?",
            "¿Qué días hay carnitas?",
            "¿Cuánto cuesta el taco de carnitas?",
            "¿Cuánto cuesta la torta de carnitas?",
            "¿Tienen combo de tacos de carnitas?",
            "¿Venden carnitas por kilo?",
        ],
        "keywords": ["carnitas", "torta", "combo", "kilo", "viernes", "taco"],
    },
    {
        "id": "bebidas",
        "category": "Bebidas",
        "answer": "Bebidas: agua del día $15 y jugos naturales $35.",
        "questions": [
            "¿Qué bebidas tienen?",
            "¿Venden agua?",
            "¿Tienen jugos naturales?",
            "¿Cuánto cuesta el agua del día?",
            "¿Qué hay de tomar?",
        ],
        "keywords": ["bebida", "tomar", "agua", "jugo", "natural", "sed", "beber"],
    },
    {
        "id": "postres",
        "category": "Panadería, dulces y snacks",
        "answer": (
            "Panadería, dulces y snacks: mantecas $27, churritos $25, galletas de avena $25, enjambre $20, "
            "obleas naturales $15, obleas de sabor $30 y amaranto de chocolate $15."
        ),
        "questions": [
            "¿Qué venden de panadería, dulces o snacks?",
            "¿Tienen postres?",
            "¿Venden pan dulce?",
            "¿Tienen galletas?",
            "¿Cuánto cuestan las obleas?",
            "¿Hay algo dulce?",
        ],
        "keywords": ["postre", "dulce", "pan", "panaderia", "snack", "galleta", "oblea", "churrito",
                     "manteca", "enjambre", "amaranto", "avena", "chocolate"],
    },
    {
        "id": "menu_del_dia",
        "category": "Menú del día",
        "answer": (
            "El menú del día cuesta $80 e incluye sopa de pasta, arroz blanco, milanesa de pollo asada y "
            "gelatina. Para llevar se cobran $20 extra por los recipientes (total $100)."
        ),
        "questions": [
            "¿Tienen menú del día o comida corrida?",
            "¿Qué trae el menú del día?",
            "¿Cuánto cuesta la comida corrida?",
            "¿Qué hay de comer hoy?",
            "¿Qué incluye la comida del día?",
            "¿Cuánto cuesta el menú del día para llevar?",
        ],
        "keywords": ["menu", "dia", "corrida", "hoy", "gelatina", "arroz", "sopa", "incluye"],
    },
    {
        "id": "menu_general",
        "category": "Menú general",
        "answer": (
            "Tenemos desayunos (hasta las 12:00 p.m.), chilaquiles, antojitos y molletes, sándwiches, paquetes "
            "de comida, pizzas, bebidas, panadería y dulces, y el menú del día ($80). Los viernes y sábados "
            "también hay carnitas. ¿Quieres los precios de alguna categoría en específico?"
        ),
        "questions": [
            "¿Qué venden en la cafetería?",
            "¿Qué tienen de comer?",
            "¿Me puedes dar el menú?",
            "¿Cuál es el menú completo?",
            "¿Qué comida tienen?",
            "¿Qué opciones de comida hay?",
        ],
        "keywords": ["menu", "carta", "venden", "comer", "hambre", "opciones", "comida"],
    },
]

# ------------------------------------------------------------------ ejemplos de rechazo
# Preguntas de otros temas (trámites, servicios de la universidad, temas generales) que el bot
# NO debe responder. Se indexan en ChromaDB con REJECTION_ID: si la consulta queda más cerca de
# ellas que de cualquier entrada real, el sistema escala. Se activan con
# USE_REJECTION_EXAMPLES=true. Se redactaron sin copiar las consultas de evaluation/test_set.csv
# para no contaminar la evaluación.
REJECTION_ID = "__fuera_de_alcance__"

REJECTION_EXAMPLES = [
    "¿Cómo hago mi servicio social?",
    "¿Dónde pido mi constancia de estudios?",
    "¿Cuáles son los requisitos de titulación?",
    "¿Dónde consulto mi kárdex?",
    "¿Cuál es mi horario de clases?",
    "¿Cómo me doy de baja de una materia?",
    "¿Dónde está control escolar?",
    "¿Cuándo publican las calificaciones?",
    "¿Cómo cambio de carrera?",
    "¿Dónde está el laboratorio de cómputo?",
    "¿A qué hora abre el centro de cómputo?",
    "¿A qué hora cierra la universidad?",
    "¿Hay transporte universitario?",
    "¿Dónde está la enfermería?",
    "¿Dónde están los baños?",
    "¿Cómo reporto una falla en el salón?",
    "¿Me pueden prestar un proyector?",
    "¿Prestan computadoras portátiles?",
    "¿Cómo recupero la contraseña de mi correo institucional?",
    "¿Cuál es el teléfono de la facultad?",
    "¿Dónde venden libros de texto?",
    "¿Venden útiles escolares?",
    "¿Dónde dejo mi bicicleta?",
    "¿Cómo tramito mi certificado?",
    "¿Cómo pago los derechos de titulación?",
    "¿Cuánto cuesta el curso de titulación?",
    "¿En la tienda de la facultad se puede pagar con vales?",
    "¿Rentan casilleros?",
    "¿Hay regaderas o vestidores en la facultad?",
    "¿Dónde se juega fútbol en la universidad?",
    "¿Hay cursos de verano?",
    "¿Cómo solicito una carta de recomendación?",
    "¿Dónde encuentro a mi tutor académico?",
    "¿Dónde está la defensoría universitaria?",
    "¿Qué clima hará mañana?",
    "¿Quién ganó el partido de ayer?",
    "¿Me ayudas con mi tarea de cálculo?",
    "¿Cómo programo en Python?",
    "Cuéntame un chiste",
    "¿Cuál es la mejor universidad de México?",
]
