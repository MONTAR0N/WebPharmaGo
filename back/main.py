import os
from dotenv import load_dotenv

from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings, SentenceTransformerEmbeddings
from langchain.vectorstores import Qdrant
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

# 1. Cargar variables de entorno del archivo .env
load_dotenv()  

def load_and_split_pdf(pdf_path, chunk_size=1000, chunk_overlap=100):
    """
    Carga un PDF y lo divide en fragmentos (chunks).
    """
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    docs = text_splitter.split_documents(documents)
    return docs

def create_embeddings_openai():
    """
    Retorna un objeto embeddings usando OpenAI. 
    """
    return OpenAIEmbeddings(model="text-embedding-ada-002")

def create_embeddings_sentence_transformer(model_name="all-MiniLM-L6-v2"):
    """
    Retorna un objeto embeddings usando SentenceTransformers.
    """
    return SentenceTransformerEmbeddings(model_name=model_name)

def get_qdrant_client(host="localhost", port=6333):
    """
    Retorna un cliente para conectarse a Qdrant que corre en localhost.
    """
    return QdrantClient(url=f"http://{host}:{port}")

def create_qdrant_collection(client, collection_name, vector_size, distance=Distance.COSINE):
    """
    Crea o recrea una colección en Qdrant.
    """
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=vector_size,
            distance=distance
        )
    )
    print(f"Creada (o recreada) la colección '{collection_name}'.")

def index_pdf_in_qdrant(pdf_path, collection_name="remedios_collection", embeddings_model="openai"):
    """
    1. Carga y trocea el PDF.
    2. Genera los embeddings.
    3. Crea (o recrea) la colección en Qdrant.
    4. Indexa los documentos (chunks) en Qdrant.
    """

    # 1. Carga y trocea
    docs = load_and_split_pdf(pdf_path)

    # 2. Genera embeddings
    if embeddings_model.lower() == "openai":
        embeddings = create_embeddings_openai()
    else:
        embeddings = create_embeddings_sentence_transformer()

    # 3. Determina el tamaño del vector (dimensión)
    if embeddings_model.lower() == "openai":
        embeddings = create_embeddings_openai()
        vector_size = 1536  # Para text-embedding-ada-002
    else:
        embeddings = create_embeddings_sentence_transformer()
    # Para SentenceTransformers, generamos un vector de prueba y medimos su longitud
        test_vector = embeddings.embed_query("test")
        vector_size = len(test_vector)

    # 4. Conecta a Qdrant
    client = get_qdrant_client()

    # 5. Crea/Recrea colección en Qdrant
    create_qdrant_collection(client, collection_name, vector_size)

    # 6. Indexa los documentos
    qdrant = Qdrant.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name=collection_name,
        url="http://localhost:6333",  # Ajusta si Qdrant no está en localhost
        prefer_grpc=False
    )
    print("Indexación completada.")
    return qdrant

def query_qdrant(qdrant, query, k=3):
    """
    Realiza una búsqueda semántica (similarity_search) en Qdrant 
    y retorna los k documentos más similares.
    """
    similar_docs = qdrant.similarity_search(query, k=k)
    return similar_docs

def main():
    # Ajusta la ruta a tu PDF
    pdf_path = os.path.join(os.path.dirname(__file__), "Vademecum_5ed_Medicamentos.pdf")

    # Indexar el PDF
    print("Indexando PDF...")
    qdrant = index_pdf_in_qdrant(
        pdf_path=pdf_path,
        collection_name="remedios_collection",
        embeddings_model="openai"  # "openai" o "sentence_transformer"
    )
    
    # Hacer una consulta de prueba
    print("Realizando una búsqueda semántica de prueba...")
    pregunta = "¿Cómo se aplica el FORMITEX?"
    resultados = query_qdrant(qdrant, pregunta, k=3)
    
    # Imprimir resultados
    for i, doc in enumerate(resultados, 1):
        print(f"\n--- Resultado {i} ---")
        print(doc.page_content)
        print("-----------")

if __name__ == "__main__":
    main()