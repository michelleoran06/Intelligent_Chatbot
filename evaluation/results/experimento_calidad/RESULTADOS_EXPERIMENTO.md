# Experimento de calidad del componente de IA

Conjunto: `evaluation\test_set.csv` | Precisión objetivo: 0.90

## Con la configuración vigente (umbral 0.70, divisor 2.5)

| Config. | Modelo | Rechazo | TP | FP | FN | TN | Exactitud | Precisión | Recall | F1 | Escalamiento | Hit@1 | Hit@3 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | default | no | 74 | 24 | 4 | 18 | 0.767 | 0.755 | 0.949 | 0.841 | 0.183 | 0.885 | 0.954 |
| B | paraphrase-multilingual-MiniLM-L12-v2 | no | 79 | 41 | 0 | 0 | 0.658 | 0.658 | 1.000 | 0.794 | 0.000 | 0.908 | 0.943 |
| C | default | sí | 74 | 21 | 4 | 21 | 0.792 | 0.779 | 0.949 | 0.856 | 0.208 | 0.885 | 0.954 |
| D | paraphrase-multilingual-MiniLM-L12-v2 | sí | 79 | 23 | 0 | 18 | 0.808 | 0.774 | 1.000 | 0.873 | 0.150 | 0.908 | 0.943 |

## Mejor combinación con precisión ≥ 0.90 (optimista: ajustada sobre el mismo conjunto)

| Config. | Umbral | Divisor | Precisión | Recall | F1 | Escalamiento |
|---|---|---|---|---|---|---|
| A | 0.75 | 2.0 | 0.900 | 0.847 | 0.873 | 0.333 |
| B | 0.85 | 1.5 | 0.942 | 0.756 | 0.839 | 0.425 |
| C | 0.75 | 2.0 | 0.911 | 0.847 | 0.878 | 0.342 |
| D | 0.85 | 1.5 | 0.942 | 0.756 | 0.839 | 0.425 |

## Recursos

| Config. | Documentos | Construcción del índice (s) | RSS final (MB) | Latencia media (ms) | Latencia p95 (ms) | ¿Cabe en Render? |
|---|---|---|---|---|---|---|
| A | 101 | 16.9 | 160.3 | 538.8 | 1369.5 | sí |
| B | 101 | 87.7 | 1321.0 | 16.0 | 18.7 | no |
| C | 141 | 4.6 | 137.5 | 267.3 | 322.4 | sí |
| D | 141 | 19.1 | 1308.9 | 15.9 | 17.4 | no |

## Recomendación automática

Configuración **C** con umbral 0.75 y divisor 2.0: precisión 0.911, recall 0.847, F1 0.878, RSS 137.5 MB. Debe confirmarse con el conjunto de validación independiente.

## Casos fallidos con la configuración vigente

### Configuración A (28 fallos)

| Resultado | Categoría | S | Método | Esperado | Predicho | Consulta |
|---|---|---|---|---|---|---|
| FP | direct | 0.768 | semantic | antojitos | desayunos | ¿Qué antojitos tienen? |
| FP | paraphrase | 0.822 | semantic | desayunos | horarios | ¿Qué puedo desayunar en la mañana? |
| FP | paraphrase | 0.769 | semantic | antojitos | desayunos | ¿Tienen molletes o tostadas? |
| FP | informal | 0.733 | semantic | horarios | ubicacion | orario de la cafe |
| FP | informal | 0.755 | semantic | antojitos | pizzas | kesadillas cuanto |
| FN | informal | 0.560 | semantic | chilaquiles | chilaquiles | chilakiles con cesina |
| FN | informal | 0.693 | semantic | bebidas | bebidas | hay agua de sabor |
| FP | out_of_scope | 0.715 | semantic | ESCALATE | pagos | ¿Cuándo son los exámenes finales? |
| FP | out_of_scope | 0.750 | keyword | ESCALATE | horarios | ¿A qué hora abre la biblioteca? |
| FP | out_of_scope | 0.860 | semantic | ESCALATE | pagos | ¿Aceptan tarjeta en la papelería? |
| FP | out_of_scope | 0.831 | semantic | ESCALATE | antojitos | ¿Cuánto cuesta la colegiatura? |
| FP | out_of_scope | 0.711 | semantic | ESCALATE | ubicacion | ¿En qué edificio está la dirección de la facultad? |
| FP | out_of_scope | 0.802 | semantic | ESCALATE | ubicacion | Perdí mi cartera en la cafetería |
| FP | out_of_scope | 0.727 | semantic | ESCALATE | carnitas | ¿Tienen opciones veganas o sin gluten? |
| FP | out_of_scope | 0.790 | semantic | ESCALATE | paquetes | ¿Cuánto cuesta el examen de inglés? |
| FP | out_of_scope | 0.778 | semantic | ESCALATE | carnitas | ¿Venden cigarros? |
| FP | out_of_scope | 0.746 | semantic | ESCALATE | menu_general | ¿Venden café de grano para llevar a casa? |
| FP | out_of_scope | 0.713 | semantic | ESCALATE | menu_del_dia | La comida me cayó mal, ¿a quién le reporto? |
| FP | out_of_scope | 0.767 | semantic | ESCALATE | pizzas | ¿Cuántas calorías tiene la pizza? |
| FP | out_of_scope | 0.802 | semantic | ESCALATE | pagos | ¿Puedo pagar la inscripción con tarjeta? |
| FN | ambiguous | 0.525 | semantic | menu_general | paquetes | precios |
| FP | ambiguous | 0.717 | semantic | menu_general | paquetes | comida |
| FN | ambiguous | 0.669 | semantic | pizzas | pizzas | pizza |
| FP | ambiguous | 0.788 | semantic | horarios | pagos | horario y formas de pago |
| FP | ambiguous | 0.860 | semantic | ESCALATE | antojitos | ¿cuánto cuesta? |
| FP | ambiguous | 0.800 | semantic | menu_general | desayunos | desayuno y comida, ¿qué hay? |
| FP | ambiguous | 0.821 | semantic | horarios | pagos | ¿Abren temprano y aceptan tarjeta? |
| FP | ambiguous | 0.740 | semantic | ESCALATE | desayunos | ¿Tienen algo barato? |

### Configuración B (41 fallos)

| Resultado | Categoría | S | Método | Esperado | Predicho | Consulta |
|---|---|---|---|---|---|---|
| FP | direct | 0.897 | semantic | antojitos | bebidas | ¿Qué antojitos tienen? |
| FP | paraphrase | 0.812 | semantic | horarios | antojitos | ¿Desde qué hora puedo ir a comprar algo? |
| FP | informal | 0.897 | semantic | antojitos | carnitas | kesadillas cuanto |
| FP | out_of_scope | 0.772 | semantic | ESCALATE | bebidas | ¿Cómo califico a un maestro? |
| FP | out_of_scope | 0.735 | semantic | ESCALATE | horarios | ¿Cuándo son los exámenes finales? |
| FP | out_of_scope | 0.816 | semantic | ESCALATE | pagos | ¿Dónde tramito mi credencial? |
| FP | out_of_scope | 0.813 | semantic | ESCALATE | paquetes | ¿Cuál es la capital de Francia? |
| FP | out_of_scope | 0.770 | semantic | ESCALATE | ubicacion | ¿Dónde está la biblioteca? |
| FP | out_of_scope | 0.852 | semantic | ESCALATE | horarios | ¿A qué hora abre la biblioteca? |
| FP | out_of_scope | 0.864 | semantic | ESCALATE | bebidas | ¿Cómo solicito una beca para posgrado? |
| FP | out_of_scope | 0.755 | semantic | ESCALATE | pagos | Tuve un problema con un empleado y quiero poner una queja |
| FP | out_of_scope | 0.723 | semantic | ESCALATE | menu_general | ¿Venden refacciones para arreglar la pantalla de una laptop? |
| FP | out_of_scope | 0.805 | semantic | ESCALATE | pagos | La API de pagos no me responde |
| FP | out_of_scope | 0.940 | semantic | ESCALATE | pagos | ¿Aceptan tarjeta en la papelería? |
| FP | out_of_scope | 0.844 | semantic | ESCALATE | antojitos | ¿Cuánto cuesta la colegiatura? |
| FP | out_of_scope | 0.889 | semantic | ESCALATE | ubicacion | ¿En qué edificio está la dirección de la facultad? |
| FP | out_of_scope | 0.898 | semantic | ESCALATE | pagos | Me cobraron de más y quiero un reembolso |
| FP | out_of_scope | 0.843 | semantic | ESCALATE | ubicacion | Perdí mi cartera en la cafetería |
| FP | out_of_scope | 0.781 | semantic | ESCALATE | menu_general | ¿Puedo reservar mesas para un evento? |
| FP | out_of_scope | 0.789 | semantic | ESCALATE | menu_general | ¿Hacen pedidos a domicilio? |
| FP | out_of_scope | 0.830 | semantic | ESCALATE | menu_general | ¿Tienen opciones veganas o sin gluten? |
| FP | out_of_scope | 0.732 | semantic | ESCALATE | ubicacion | ¿Cuál es la contraseña del wifi de la facultad? |
| FP | out_of_scope | 0.792 | semantic | ESCALATE | bebidas | ¿Dónde imprimo mis tareas? |
| FP | out_of_scope | 0.792 | semantic | ESCALATE | horarios | ¿Cuándo inicia el semestre? |
| FP | out_of_scope | 0.784 | semantic | ESCALATE | ubicacion | ¿Quién es el director de la facultad? |
| FP | out_of_scope | 0.761 | semantic | ESCALATE | ubicacion | ¿Hay estacionamiento para alumnos? |
| FP | out_of_scope | 0.736 | semantic | ESCALATE | ubicacion | ¿Contratan estudiantes para trabajar? |
| FP | out_of_scope | 0.832 | semantic | ESCALATE | paquetes | ¿Cuánto cuesta el examen de inglés? |
| FP | out_of_scope | 0.805 | semantic | ESCALATE | antojitos | ¿Venden cigarros? |
| FP | out_of_scope | 0.900 | semantic | ESCALATE | menu_general | ¿Venden café de grano para llevar a casa? |
| FP | out_of_scope | 0.895 | semantic | ESCALATE | menu_general | La comida me cayó mal, ¿a quién le reporto? |
| FP | out_of_scope | 0.931 | semantic | ESCALATE | pizzas | ¿Cuántas calorías tiene la pizza? |
| FP | out_of_scope | 0.893 | semantic | ESCALATE | pagos | ¿Puedo pagar la inscripción con tarjeta? |
| FP | ambiguous | 0.884 | semantic | menu_general | antojitos | precios |
| FP | ambiguous | 0.877 | semantic | horarios | pagos | horario y formas de pago |
| FP | ambiguous | 0.938 | semantic | ESCALATE | antojitos | ¿cuánto cuesta? |
| FP | ambiguous | 0.880 | semantic | menu_general | bebidas | ¿qué tienen? |
| FP | ambiguous | 0.976 | semantic | menu_general | desayunos | desayuno y comida, ¿qué hay? |
| FP | ambiguous | 0.895 | semantic | horarios | pagos | ¿Abren temprano y aceptan tarjeta? |
| FP | ambiguous | 0.831 | semantic | ESCALATE | antojitos | ¿Tienen algo barato? |
| FP | ambiguous | 0.851 | semantic | ESCALATE | bebidas | ¿Qué me recomiendas? |

### Configuración C (25 fallos)

| Resultado | Categoría | S | Método | Esperado | Predicho | Consulta |
|---|---|---|---|---|---|---|
| FP | direct | 0.768 | semantic | antojitos | desayunos | ¿Qué antojitos tienen? |
| FP | paraphrase | 0.822 | semantic | desayunos | horarios | ¿Qué puedo desayunar en la mañana? |
| FP | paraphrase | 0.769 | semantic | antojitos | desayunos | ¿Tienen molletes o tostadas? |
| FP | informal | 0.733 | semantic | horarios | ubicacion | orario de la cafe |
| FP | informal | 0.755 | semantic | antojitos | pizzas | kesadillas cuanto |
| FN | informal | 0.560 | semantic | chilaquiles | chilaquiles | chilakiles con cesina |
| FN | informal | 0.693 | semantic | bebidas | bebidas | hay agua de sabor |
| FP | out_of_scope | 0.715 | semantic | ESCALATE | pagos | ¿Cuándo son los exámenes finales? |
| FP | out_of_scope | 0.860 | semantic | ESCALATE | pagos | ¿Aceptan tarjeta en la papelería? |
| FP | out_of_scope | 0.831 | semantic | ESCALATE | antojitos | ¿Cuánto cuesta la colegiatura? |
| FP | out_of_scope | 0.802 | semantic | ESCALATE | ubicacion | Perdí mi cartera en la cafetería |
| FP | out_of_scope | 0.727 | semantic | ESCALATE | carnitas | ¿Tienen opciones veganas o sin gluten? |
| FP | out_of_scope | 0.790 | semantic | ESCALATE | paquetes | ¿Cuánto cuesta el examen de inglés? |
| FP | out_of_scope | 0.778 | semantic | ESCALATE | carnitas | ¿Venden cigarros? |
| FP | out_of_scope | 0.746 | semantic | ESCALATE | menu_general | ¿Venden café de grano para llevar a casa? |
| FP | out_of_scope | 0.767 | semantic | ESCALATE | pizzas | ¿Cuántas calorías tiene la pizza? |
| FP | out_of_scope | 0.802 | semantic | ESCALATE | pagos | ¿Puedo pagar la inscripción con tarjeta? |
| FN | ambiguous | 0.000 | rejected | menu_general | — | precios |
| FP | ambiguous | 0.717 | semantic | menu_general | paquetes | comida |
| FN | ambiguous | 0.669 | semantic | pizzas | pizzas | pizza |
| FP | ambiguous | 0.788 | semantic | horarios | pagos | horario y formas de pago |
| FP | ambiguous | 0.860 | semantic | ESCALATE | antojitos | ¿cuánto cuesta? |
| FP | ambiguous | 0.800 | semantic | menu_general | desayunos | desayuno y comida, ¿qué hay? |
| FP | ambiguous | 0.821 | semantic | horarios | pagos | ¿Abren temprano y aceptan tarjeta? |
| FP | ambiguous | 0.740 | semantic | ESCALATE | desayunos | ¿Tienen algo barato? |

### Configuración D (23 fallos)

| Resultado | Categoría | S | Método | Esperado | Predicho | Consulta |
|---|---|---|---|---|---|---|
| FP | direct | 0.897 | semantic | antojitos | bebidas | ¿Qué antojitos tienen? |
| FP | paraphrase | 0.812 | semantic | horarios | antojitos | ¿Desde qué hora puedo ir a comprar algo? |
| FP | informal | 0.897 | semantic | antojitos | carnitas | kesadillas cuanto |
| FP | out_of_scope | 0.813 | semantic | ESCALATE | paquetes | ¿Cuál es la capital de Francia? |
| FP | out_of_scope | 0.864 | semantic | ESCALATE | bebidas | ¿Cómo solicito una beca para posgrado? |
| FP | out_of_scope | 0.940 | semantic | ESCALATE | pagos | ¿Aceptan tarjeta en la papelería? |
| FP | out_of_scope | 0.889 | semantic | ESCALATE | ubicacion | ¿En qué edificio está la dirección de la facultad? |
| FP | out_of_scope | 0.898 | semantic | ESCALATE | pagos | Me cobraron de más y quiero un reembolso |
| FP | out_of_scope | 0.843 | semantic | ESCALATE | ubicacion | Perdí mi cartera en la cafetería |
| FP | out_of_scope | 0.781 | semantic | ESCALATE | menu_general | ¿Puedo reservar mesas para un evento? |
| FP | out_of_scope | 0.830 | semantic | ESCALATE | menu_general | ¿Tienen opciones veganas o sin gluten? |
| FP | out_of_scope | 0.805 | semantic | ESCALATE | antojitos | ¿Venden cigarros? |
| FP | out_of_scope | 0.900 | semantic | ESCALATE | menu_general | ¿Venden café de grano para llevar a casa? |
| FP | out_of_scope | 0.895 | semantic | ESCALATE | menu_general | La comida me cayó mal, ¿a quién le reporto? |
| FP | out_of_scope | 0.931 | semantic | ESCALATE | pizzas | ¿Cuántas calorías tiene la pizza? |
| FP | out_of_scope | 0.893 | semantic | ESCALATE | pagos | ¿Puedo pagar la inscripción con tarjeta? |
| FP | ambiguous | 0.884 | semantic | menu_general | antojitos | precios |
| FP | ambiguous | 0.877 | semantic | horarios | pagos | horario y formas de pago |
| FP | ambiguous | 0.938 | semantic | ESCALATE | antojitos | ¿cuánto cuesta? |
| FP | ambiguous | 0.880 | semantic | menu_general | bebidas | ¿qué tienen? |
| FP | ambiguous | 0.976 | semantic | menu_general | desayunos | desayuno y comida, ¿qué hay? |
| FP | ambiguous | 0.895 | semantic | horarios | pagos | ¿Abren temprano y aceptan tarjeta? |
| FP | ambiguous | 0.831 | semantic | ESCALATE | antojitos | ¿Tienen algo barato? |
