import chromadb

client = chromadb.PersistentClient(path="./chroma_data")
collection = client.get_or_create_collection(name="knowledge_base_cafe")

def seed_knowledge_base():
    try:
        existing_data = collection.get()
        if existing_data and existing_data['ids']:
            collection.delete(ids=existing_data['ids'])
    except Exception:
        pass

    documents = [
        "a que hora abren la cafeteria a que hora cierran horarios servicio desde que hora estan que dias abren sabado temprano",
        "cuales son los metodos de pago aceptan tarjeta efectivo transferencia puedo pagar con terminal",
        "donde esta la cafeteria ubicacion como llego en que edificio estan",
        "que desayunos venden menu de la mañana huevos chilaquiles omelette enchiladas sopes comida alimentos",
        "tienen antojitos quesadillas molletes tostadas tacos ahogados dorados gringa burrito comida alimentos menu",
        "que tipos de chilaquiles tienen con que vienen cecina pollo huevo sencillos comida alimentos menu",
        "venden sandwiches o hamburguesas pechuga pierna club comida alimentos menu",
        "que paquetes de comida tienen comidas completas filete cecina arrachera pechuga milanesa alimentos menu",
        "venden pizza que sabores de pizza hawaiana carnes frias molida entera rebanada menu",
        "que bebidas tienen para tomar jugos aguas licuados sed",
        "tienen postres dulces galletas obleas churritos amaranto enjambre",
        "tienen menu del dia comida corrida que incluye precio comida alimentos que hay de comer hoy menu general que venden de comer"
    ]
    
    metadatas = [
        {"respuesta": "La cafetería está abierta de lunes a sábado de 7:00 AM a 5:00 PM. (Abrimos puertas 6:30 AM, pero el servicio empieza a las 7:00 AM)."},
        {"respuesta": "Aceptamos pagos en efectivo, tarjetas de débito/crédito y transferencias."},
        {"respuesta": "Estamos ubicados en la planta baja del edificio principal de la Facultad de Ingeniería."},
        {"respuesta": "De desayuno tenemos: Huevos al gusto, a la mexicana, con salchicha/tocino/jamón, rancheros, divorciados ($55). Chilaquiles, Enchiladas, Sopes ($55). Omelette de verduras o jamón con queso ($55)."},
        {"respuesta": "Antojitos: Quesadillas ($30-$35), Molletes sencillos ($35), Molletes Xtreme ($65), Tostadas ($35), Tacos dorados ($45), Tacos ahogados ($50), Gringa ($55), Burrito ($45)."},
        {"respuesta": "Tenemos chilaquiles con cecina ($75), con milanesa o pechuga asada ($65), con huevo ($50) o sencillos ($40)."},
        {"respuesta": "Sándwiches de pollo o pechuga asada ($30), club ($65), pierna ($45). También tenemos hamburguesa doble y hawaiana."},
        {"respuesta": "Paquetes (comidas): Milanesa ($60), Pechuga asada ($60), Pechuga rellena ($65), Filete de pescado ($70), Arrachera ($80), Cecina natural/adobada ($80), Chorizo ($70)."},
        {"respuesta": "Vendemos pizzas por rebanada ($25) o completas ($100). Sabores: Hawaiana, Carnes frías, Carne molida, Pastor, Queso, Champiñón. (Caja para llevar $20)."},
        {"respuesta": "Para beber tenemos Agua del día ($15), Jugo natural ($35) y Licuados."},
        {"respuesta": "Postres y panadería: Mantecas ($27), Churritos ($25), Enjambre ($20), Galletas de avena ($25), Obleas ($15-$30), Amaranto de chocolate ($15)."},
        {"respuesta": "El menú del día cuesta $80 e incluye: Sopa de pasta, Arroz blanco, Guisado (ej. milanesa de pollo asada) y Gelatina. (Para llevar +$20)."}
    ]
    
    ids = [f"caf_{i}" for i in range(1, 13)]
    
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )

if __name__ == "__main__":
    seed_knowledge_base()