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
        "a que hora abren la cafeteria a que hora cierran horarios servicio almuerzo comida desde que hora estan",
        "cuales son los metodos de pago aceptan tarjeta efectivo transferencia puedo pagar con terminal",
        "donde esta la cafeteria ubicacion como llego en que edificio estan",
        "que venden de comer menu alimentos disponibles que hay de desayunar chilaquiles tortas"
    ]
    
    metadatas = [
        {"respuesta": "La cafetería de la Facultad de Ingeniería abre de lunes a viernes de 7:00 AM a 6:00 PM."},
        {"respuesta": "Aceptamos efectivo, tarjetas de débito/crédito y transferencias."},
        {"respuesta": "Estamos ubicados en la planta baja del edificio principal de la facultad."},
        {"respuesta": "Vendemos chilaquiles, tortas, sándwiches, guisados del día y bebidas. (Menú sujeto a disponibilidad)."}
    ]
    
    ids = ["caf_1", "caf_2", "caf_3", "caf_4"]
    
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )

if __name__ == "__main__":
    seed_knowledge_base()