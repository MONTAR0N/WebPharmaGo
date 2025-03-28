import os
import sqlite3
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import Qdrant
from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA
from qdrant_client import QdrantClient
from datetime import datetime

# Cargar variables de entorno (si usas OpenAI)
load_dotenv()

# Función para inicializar la base de datos de historial
def inicializar_bd_historial():
    """Inicializa la base de datos para el historial de consultas"""
    try:
        # Obtener la ruta a la base de datos
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.join(current_dir, 'Base')
        
        # Crear directorio Base si no existe
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
            
        db_path = os.path.join(base_dir, 'historial_consultas.db')
        
        # Conectar a la base de datos
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Crear tabla de historial si no existe
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id TEXT NOT NULL,
            consulta TEXT NOT NULL,
            respuesta TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        conn.close()
        
        return db_path
    except Exception as e:
        print(f"Error al inicializar la base de datos de historial: {e}")
        return None
def guardar_info_usuario(usuario_id, nombre=None):
    """
    Guarda o actualiza la información de un usuario
    
    Args:
        usuario_id (str): ID único del usuario
        nombre (str, opcional): Nombre del usuario
    """
    try:
        conn = sqlite3.connect(DB_HISTORIAL_PATH)
        cursor = conn.cursor()
        
        # Crear tabla de usuarios si no existe
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id TEXT PRIMARY KEY,
            nombre TEXT,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ultima_actividad TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Verificar si el usuario ya existe
        cursor.execute("SELECT id FROM usuarios WHERE id = ?", (usuario_id,))
        resultado = cursor.fetchone()
        
        current_time = datetime.now().isoformat()
        
        # Si no existe, lo registramos
        if not resultado:
            cursor.execute(
                "INSERT INTO usuarios (id, nombre, fecha_creacion, ultima_actividad) VALUES (?, ?, ?, ?)",
                (usuario_id, nombre, current_time, current_time)
            )
        else:
            # Si existe y se proporciona un nombre, lo actualizamos
            if nombre:
                cursor.execute(
                    "UPDATE usuarios SET nombre = ?, ultima_actividad = ? WHERE id = ?",
                    (nombre, current_time, usuario_id)
                )
            else:
                # Solo actualizamos la última actividad
                cursor.execute(
                    "UPDATE usuarios SET ultima_actividad = ? WHERE id = ?",
                    (current_time, usuario_id)
                )
        
        conn.commit()
        conn.close()
        print(f"Información del usuario {usuario_id} guardada/actualizada")
    except Exception as e:
        print(f"Error al guardar información de usuario: {e}")

def obtener_info_usuario(usuario_id):
    """
    Obtiene la información de un usuario
    
    Args:
        usuario_id (str): ID del usuario
        
    Returns:
        dict: Información del usuario (nombre, fecha de creación, última actividad)
              o None si el usuario no existe
    """
    try:
        conn = sqlite3.connect(DB_HISTORIAL_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT nombre, fecha_creacion, ultima_actividad FROM usuarios WHERE id = ?",
            (usuario_id,)
        )
        
        resultado = cursor.fetchone()
        conn.close()
        
        if resultado:
            nombre, fecha_creacion, ultima_actividad = resultado
            return {
                'nombre': nombre,
                'fecha_creacion': fecha_creacion,
                'ultima_actividad': ultima_actividad
            }
        else:
            return None
    except Exception as e:
        print(f"Error al obtener información de usuario: {e}")
        return None

# Modifica la función procesar_consulta para manejar el nombre del usuario
def procesar_consulta(usuario_id, query, nombre_usuario=None, guardar_historia=True):
    """
    Función principal para procesar consultas de un usuario específico.
    
    Args:
        usuario_id (str): ID único del usuario
        query (str): La consulta del usuario
        nombre_usuario (str, opcional): Nombre del usuario
        guardar_historia (bool, opcional): Si se debe guardar la consulta en el historial
        
    Returns:
        str: La respuesta generada
    """
    try:
        # Guardar o actualizar información del usuario
        guardar_info_usuario(usuario_id, nombre_usuario)
        
        # Obtener información del usuario
        info_usuario = obtener_info_usuario(usuario_id)
        nombre = info_usuario['nombre'] if info_usuario and info_usuario['nombre'] else None
        
        # El resto de la función es igual...
        # Detectar si es sobre farmacias o medicamentos
        if es_consulta_farmacia(query):
            # Es una consulta sobre farmacias
            comuna = detectar_comuna(query)
            if not comuna:
                saludo = f"Hola {nombre}, " if nombre else ""
                respuesta = f"{saludo}para buscar farmacias necesito que me indiques la comuna específica. Por ejemplo: 'Farmacias en Providencia'."
                
                # Guardar en historial si está habilitado
                if guardar_historia:
                    guardar_historial(usuario_id, query, respuesta)
                    
                return respuesta
            
            # Detectar si es de turno
            es_turno = "turno" in query.lower()
            
            # Consultar farmacias
            farmacias = consultar_farmacias(comuna, solo_turno=es_turno)
            
            # Formatear resultados
            respuesta_base = formatear_resultados_farmacias(farmacias, comuna, solo_turno=es_turno)
            
            # Añadir saludo personalizado si tenemos el nombre
            if nombre:
                saludo = f"Hola {nombre}, "
                respuesta = f"{saludo}{respuesta_base}"
            else:
                respuesta = respuesta_base
            
            # Guardar en historial si está habilitado
            if guardar_historia:
                guardar_historial(usuario_id, query, respuesta)
                
            return respuesta
            
        elif es_consulta_medicamento(query):
            # Es una consulta sobre medicamentos - usar el RAG original
            llm = obtener_llm()
            qdrant = obtener_qdrant()
            
            # Crear la cadena RAG
            retriever = qdrant.as_retriever(search_type="similarity", search_kwargs={"k": 3})
            qa_chain = crear_rag(llm, retriever)
            
            # Realizar la consulta y obtener la respuesta
            respuesta_raw = realizar_consulta(query, qa_chain)
            
            # Verificar la respuesta (pasando también la consulta original)
            respuesta_base = verificar_respuesta_con_llm(respuesta_raw, query)
            
            # Añadir saludo personalizado si tenemos el nombre
            if nombre:
                saludo = f"Hola {nombre}, "
                respuesta = f"{saludo}{respuesta_base}"
            else:
                respuesta = respuesta_base
            
            # Guardar en historial si está habilitado
            if guardar_historia:
                guardar_historial(usuario_id, query, respuesta)
                
            return respuesta
            
        else:
            # No es ni de farmacias ni de medicamentos
            saludo = f"Hola {nombre}, " if nombre else ""
            respuesta = f"{saludo}solo puedo responder consultas relacionadas con farmacias y medicamentos. ¿En qué puedo ayudarte con información sobre medicamentos o farmacias cercanas?"
            
            # Guardar en historial si está habilitado
            if guardar_historia:
                guardar_historial(usuario_id, query, respuesta)
                
            return respuesta
            
    except Exception as e:
        respuesta = f"Lo siento, ocurrió un error al procesar tu consulta: {str(e)}"
        
        # Intentar guardar el error en el historial
        if guardar_historia:
            try:
                guardar_historial(usuario_id, query, respuesta)
            except:
                pass
                
        return respuesta
# Inicializar la base de datos al cargar el módulo
DB_HISTORIAL_PATH = inicializar_bd_historial()

def guardar_historial(usuario_id, consulta, respuesta):
    """
    Guarda la consulta y respuesta en el historial
    
    Args:
        usuario_id (str): ID del usuario que realiza la consulta
        consulta (str): Texto de la consulta
        respuesta (str): Texto de la respuesta
    """
    try:
        conn = sqlite3.connect(DB_HISTORIAL_PATH)
        cursor = conn.cursor()
        
        # Insertar la consulta y respuesta
        cursor.execute(
            "INSERT INTO historial (usuario_id, consulta, respuesta) VALUES (?, ?, ?)",
            (usuario_id, consulta, respuesta)
        )
        
        conn.commit()
        conn.close()
        print(f"Historial guardado para usuario {usuario_id}")
    except Exception as e:
        print(f"Error al guardar historial: {e}")

def obtener_historial(usuario_id, limite=10):
    """
    Obtiene el historial de consultas de un usuario
    
    Args:
        usuario_id (str): ID del usuario
        limite (int): Número máximo de consultas a obtener
        
    Returns:
        list: Lista de tuplas (consulta, respuesta, timestamp)
    """
    try:
        conn = sqlite3.connect(DB_HISTORIAL_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT consulta, respuesta, timestamp FROM historial WHERE usuario_id = ? ORDER BY timestamp DESC LIMIT ?",
            (usuario_id, limite)
        )
        
        resultados = cursor.fetchall()
        conn.close()
        
        return resultados
    except Exception as e:
        print(f"Error al obtener historial: {e}")
        return []

def verificar_respuesta_con_llm(respuesta, query):
    """
    Usa el LLM para revisar la respuesta generada, con un enfoque más matizado.
    Distingue entre solicitudes de recetas y solicitudes de información general.
    """
    # Extraer texto de respuesta si es un diccionario
    if isinstance(respuesta, dict) and 'result' in respuesta:
        texto_respuesta = respuesta['result']
    else:
        texto_respuesta = str(respuesta)
    
    # Prompt para revisar la respuesta generada con contexto de la consulta
    prompt_revision = f"""
    Analiza esta consulta del usuario y la respuesta generada por un sistema sobre medicamentos:
    
    Consulta: "{query}"
    Respuesta: "{texto_respuesta}"
    
    Tu tarea:
    1. Determina si la consulta pide explícitamente una receta o prescripción personalizada.
    2. Evalúa si la respuesta está dando una prescripción médica personalizada.
    
    Importante: Distingue entre información educativa general (permitida) y consejos de prescripción específicos (no permitidos).
    
    - Si el usuario solo pide información general sobre medicamentos y la respuesta proporciona información educativa -> responde "INFORMACIÓN_EDUCATIVA"
    - Si la respuesta recomienda específicamente qué medicamento debe tomar el usuario o receta personalmente -> responde "PRESCRIPCIÓN_MÉDICA"
    
    Responde ÚNICAMENTE con una de estas dos opciones.
    """

    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
    revision_respuesta = llm.invoke(prompt_revision).content.strip()
    
    # Si el LLM considera que es una prescripción médica, la bloqueamos
    if "PRESCRIPCIÓN_MÉDICA" in revision_respuesta:
        return "Lo siento, no estoy autorizado para recetar medicamentos o dar consejos de prescripción específicos. Esta información es educativa general. Para tratamientos personalizados, por favor consulte con un profesional de la salud."
    else:
        # Si es información educativa, la permitimos con un disclaimer
        if "No sé" in texto_respuesta or "no tengo esa información" in texto_respuesta.lower():
            return "No tengo información específica sobre ese tema médico en mi base de datos. Para información precisa sobre tratamientos, por favor consulte con un profesional de la salud."
        else:
            return texto_respuesta + "\n\nNota: Esta información es solo educativa y no constituye consejo médico. Siempre consulte con un profesional de la salud antes de iniciar cualquier tratamiento."

def obtener_llm():
    """
    Inicializa el LLM (Modelo de Lenguaje) usando OpenAI.
    """
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
    return llm

def obtener_qdrant():
    """
    Establece la conexión a Qdrant, usando la colección existente.
    """
    client = QdrantClient(url="http://localhost:6333")
    embeddings = OpenAIEmbeddings(model="text-embedding-ada-002")
    qdrant = Qdrant(client=client, collection_name="remedios_collection", embeddings=embeddings)
    return qdrant

def crear_rag(llm, retriever):
    """
    Crea la cadena de Retrieval Augmented Generation (RAG) con el LLM y el retriever (Qdrant).
    """
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever
    )
    return qa_chain

def realizar_consulta(query, qa_chain):
    """
    Realiza una consulta al sistema RAG (Qdrant + LLM) y obtiene la respuesta.
    """
    # Ejecutar la consulta y manejar tanto si devuelve un string como un dict
    resultado = qa_chain.invoke(query)
    
    # En versiones recientes de LangChain, puede devolver un dict
    if isinstance(resultado, dict):
        # Extraer el resultado según la estructura del diccionario
        if 'result' in resultado:
            return resultado['result']
        elif 'answer' in resultado:
            return resultado['answer']
        # Si tiene otra estructura, convertimos a string
        return str(resultado)
    else:
        # Si es un string, lo devolvemos directamente
        return resultado

def es_consulta_farmacia(query):
    """Determina si la consulta es sobre farmacias"""
    query_lower = query.lower()
    palabras_farmacia = [
        "farmacia", "farmacias", "comprar", "cerca", "cercana", 
        "turno", "dirección", "donde", "dónde", "ubicación"
    ]
    return any(palabra in query_lower for palabra in palabras_farmacia)

def es_consulta_medicamento(query):
    """Determina si la consulta es sobre medicamentos"""
    query_lower = query.lower()
    palabras_medicamento = [
        "medicamento", "medicina", "remedio", "pastilla", "comprimido", 
        "para qué sirve", "efectos secundarios", "tratamiento", "droga",
        "fármaco", "antibiótico", "analgésico", "tratar", "cura", "curar"
    ]
    return any(palabra in query_lower for palabra in palabras_medicamento)

def detectar_comuna(query):
    """Detecta la comuna mencionada en la consulta"""
    query_lower = query.lower()
    comunas = [
        "limache","tolten","pedro aguirre cerda","cabrero","ancud","antuco",
        "la calera","cunco","peñaflor","maria pinto","castro","yumbel",
        "quillota","gorbea","peñalolen","pencahue","puerto montt","quilleco",
        "la cruz","villarrica","providencia","quemchi","tocopilla","tucapel",
        "quilpue","lautaro","vitacura","caldera","mejillones","andacollo",
        "quintero","pitrufquen","pudahuel","maullin","puerto varas","mafil",
        "viña del mar","collipulli","puente alto","lota","la serena","corral",
        "valparaiso","loncoche","quilicura","san pablo","combarbala","ninhue",
        "casablanca","rancagua","quinta normal","coihueco","salamanca","algarrobo",
        "el tabo","ovalle","recoleta","santa barbara","calbuco","chillan viejo",
        "san antonio","vicuña","renca","mulchen","los muermos","quinchao",
        "cabildo","illapel","san joaquin","cartagena","osorno","purranque",
        "catemu","coquimbo","san miguel","rio negro","llanquihue","quinta de tilcoco",
        "la ligua","los vilos","san ramon","nogales","aysen","punta arenas",
        "los andes","san fernando","talagante","puqueldon","coyhaique","puerto natales",
        "papudo","graneros","arauco","quilaco","pica","arica",
        "putaendo","las cabras","bulnes","padre las casas","fresia","puren",
        "santa maria","peralillo","cañete","victoria","calama","paredones",
        "zapallar","pichidegua","chiguayante","carahue","chonchi","angol",
        "llay llay","chimbarongo","chillan","lonquimay","antofagasta","traiguen",
        "juan fernandez","doñihue","coelemu","frutillar","nueva imperial","curacautin",
        "iquique","litueche","concepcion","calera de tango","lanco","san pedro",
        "puchuncavi","marchigue","tome","tirua","paillaco","teodoro schmidt",
        "concon","nancagua","coronel","renaico","rio bueno","san juan de la costa",
        "alto hospicio","navidad","curanilahue","el quisco","panguipulli","pucon",
        "hijuelas","requinoa","hualpen","vilcun","la union","puerto octay",
        "rinconada","san francisco de mostazal","hualqui","vallenar","valdivia","alto bio bio",
        "panquehue","santa cruz","lebu","tierra amarilla","temuco","hualaihue",
        "san esteban","peumo","los alamos","colbun","quellon","san rosendo",
        "buin","machali","penco","villa alemana","dalcahue","negrete",
        "cerrillos","san vicente","pinto","pozo almonte","lo barnechea","lolol",
        "cerro navia","pichilemu","quillon","huara","lo espejo","licanten",
        "colina","rengo","quirihue","alhue","lo prado","maule",
        "conchali","retiro","san carlos","los sauces","macul","til-til",
        "curacavi","hualañe","san pedro de la paz","galvarino","maipu","taltal",
        "el bosque","teno","talcahuano","puerto saavedra","melipilla","pelluhue",
        "el monte","san clemente","yungay","huasco","ñuñoa","isla de pascua",
        "estacion central","san javier","los angeles","alto del carmen","padre hurtado","longavi",
        "santiago","molina","nacimiento","san nicolas","paine","puyehue",
        "san bernardo","parral","laja","pirque","chañaral","lumaco",
        "huechuraba","cauquenes","florida","chanco","lago ranco","san rafael",
        "independencia","linares","santa juana","romeral","los lagos","yerbas buenas",
        "isla de maipo","constitucion","san felipe","sagrada familia","mariquina","san fabian",
        "la cisterna","curico","copiapo","vichuquen","futrono","freirina",
        "la florida","talca","diego de almagro","perquenco","las condes","rauco",
        "la granja","cochrane","la pintana","el carmen","la reina","san ignacio",
        "lampa","petorca"
    ]
    for comuna in comunas:
        if comuna in query_lower:
            return comuna
    return query_lower

def consultar_farmacias(comuna, solo_turno=False):
    """Consulta la base de datos de farmacias"""
    try:
        # Obtener la ruta a la base de datos
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, 'Base', 'farmacias_turno.db')
        
        # Conectar a la base de datos
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Construir consulta SQL
        if solo_turno:
            sql = """
            SELECT 
                local_nombre, 
                local_direccion, 
                funcionamiento_hora_apertura, 
                funcionamiento_hora_cierre, 
                local_telefono, 
                URL_direccion
            FROM farmacias
            WHERE comuna_nombre LIKE ? AND de_turno = 1
            """
        else:
            sql = """
            SELECT 
                local_nombre, 
                local_direccion, 
                funcionamiento_hora_apertura, 
                funcionamiento_hora_cierre, 
                local_telefono, 
                URL_direccion,
                de_turno
            FROM farmacias
            WHERE comuna_nombre LIKE ?
            """
        
        # Ejecutar consulta
        cursor.execute(sql, (f"%{comuna}%",))
        farmacias = cursor.fetchall()
        
        conn.close()
        return farmacias
    except Exception as e:
        print(f"Error al consultar farmacias: {e}")
        return []

def formatear_resultados_farmacias(farmacias, comuna, solo_turno=False):
    """Formatea los resultados de farmacias para presentación"""
    if not farmacias:
        tipo = "de turno " if solo_turno else ""
        return f"No se encontraron farmacias {tipo}en {comuna}."
    
    tipo = "de turno " if solo_turno else ""
    resultado = f"Encontré {len(farmacias)} farmacias {tipo}en {comuna}:\n\n"
    
    # Limitar a 10 farmacias para evitar respuestas muy largas
    farmacias_mostradas = farmacias[:10]
    
    for i, farmacia in enumerate(farmacias_mostradas, 1):
        if solo_turno:
            nombre, direccion, hora_apertura, hora_cierre, telefono, url = farmacia
            es_turno = True
        else:
            nombre, direccion, hora_apertura, hora_cierre, telefono, url, es_turno = farmacia
        
        resultado += f"{i}. {nombre}"
        if es_turno:
            resultado += " (DE TURNO)"
        resultado += "\n"
        
        if direccion:
            resultado += f"   Dirección: {direccion}\n"
        
        if hora_apertura and hora_cierre:
            resultado += f"   Horario: {hora_apertura} - {hora_cierre}\n"
        
        if telefono:
            resultado += f"   Teléfono: {telefono}\n"
        
        if url:
            resultado += f"   Mapa: {url}\n"
        
        resultado += "\n"
    
    if len(farmacias) > 10:
        resultado += f"...y {len(farmacias) - 10} farmacias más.\n"
    
    return resultado

def obtener_historial_usuario(usuario_id, limite=10):
    """
    Obtiene el historial de consultas para un usuario específico
    
    Args:
        usuario_id (str): ID del usuario
        limite (int): Número máximo de conversaciones a obtener
        
    Returns:
        list: Lista de tuplas (consulta, respuesta, timestamp)
    """
    return obtener_historial(usuario_id, limite)

# Ejemplo de uso del módulo
if __name__ == "__main__":
    # Esta parte solo se ejecuta cuando corres el script directamente para pruebas
    
    # ID de usuario de prueba (esto vendría del front-end)
    usuario_id = "usuario_123"
    
    # Ejemplo de consulta
    ejemplo_consulta = "remedios utilizados para tratar la depresión"
    
    # Procesar la consulta
    resultado = procesar_consulta(usuario_id, ejemplo_consulta)
    
    print(f"Usuario: {usuario_id}")
    print(f"Consulta: {ejemplo_consulta}")
    print(resultado)
    
    # Obtener historial del usuario
    print("\nHistorial del usuario:")
    historial = obtener_historial_usuario(usuario_id)
    
    for i, (consulta, respuesta, timestamp) in enumerate(historial, 1):
        print(f"\n--- Consulta {i} ({timestamp}) ---")
        print(f"Consulta: {consulta}")
        print(f"Respuesta: {respuesta[:100]}...")  # Mostrar solo las primeras 100 letras