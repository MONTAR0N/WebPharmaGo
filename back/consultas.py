import os
from dotenv import load_dotenv
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Qdrant
from qdrant_client import QdrantClient

def main():
    # 1. Cargar variables de entorno (por ejemplo, OPENAI_API_KEY)
    load_dotenv()
    
    # 2. Definir el modelo de embeddings (mismo que usaste al indexar)
    embeddings = OpenAIEmbeddings(model="text-embedding-ada-002")
    
    # 3. Conectarte a la colección existente en Qdrant
    client = QdrantClient(url="http://localhost:6333")
    
    # 4. Crear un objeto Qdrant apuntando a la misma colección
    #    sin reindexar, solo para realizar consultas
    qdrant = Qdrant(
        client=client,
        collection_name="remedios_collection",
        embeddings=embeddings
    )
    
    # 5. Realizar la búsqueda semántica
    query = "¿que remedios se usan para tratar la depresión?"
    resultados = qdrant.similarity_search(query, k=3)
    
    # 6. Imprimir resultados
    print(f"\nConsulta: {query}")
    for i, doc in enumerate(resultados, start=1):
        print(f"\n--- Resultado {i} ---")
        print(doc.page_content)

if __name__ == "__main__":
    main()