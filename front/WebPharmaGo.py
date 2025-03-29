from flask import Flask, render_template, jsonify, request, session
from datetime import timedelta
import uuid
import sqlite3
import json
import logging
from datetime import datetime
import os
import sys

# Agregar el directorio 'back' al path para poder importar consultas_llm
script_dir = os.path.dirname(os.path.abspath(__file__))
back_dir = os.path.join(os.path.dirname(script_dir), 'back')
sys.path.append(back_dir)

# Importar el sistema RAG
try:
    from consultas_llm import procesar_consulta, obtener_historial_usuario
    print("Módulo RAG importado correctamente")
except ImportError as e:
    print(f"Error al importar el módulo RAG: {e}")
    print(f"Asegúrate de que consultas_llm.py está en: {back_dir}")
    print(f"Path actual: {sys.path}")

# Configuración del logging
logging.basicConfig(
    filename='chat_history.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

app = Flask(__name__)
# Configura una clave secreta para las sesiones
app.secret_key = 'Pajaritos3nIaIuna'  # Cambia esto por una clave segura
# Configura el tiempo de vida de la sesión
app.permanent_session_lifetime = timedelta(minutes=60)

def get_db_connection():
    conn = sqlite3.connect('/Base/farmacias_turno.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_regions')
def get_regions():
    conn = get_db_connection()
    regions = conn.execute('''
        SELECT DISTINCT nombre_region 
        FROM farmacias 
        WHERE nombre_region IS NOT NULL 
        ORDER BY nombre_region
    ''').fetchall()
    conn.close()
    return jsonify([region['nombre_region'] for region in regions])

@app.route('/get_comunas/<region>')
def get_comunas(region):
    conn = get_db_connection()
    comunas = conn.execute('''
        SELECT DISTINCT comuna_nombre 
        FROM farmacias 
        WHERE nombre_region = ? 
        AND comuna_nombre IS NOT NULL 
        ORDER BY comuna_nombre
    ''', (region,)).fetchall()
    conn.close()
    return jsonify([comuna['comuna_nombre'] for comuna in comunas])

@app.route('/search_farmacias/<region>/<comuna>')
def search_farmacias(region, comuna):
    conn = get_db_connection()
    farmacias = conn.execute('''
        SELECT local_nombre, localidad_nombre, local_direccion, 
               de_turno, URL_direccion as url_direccion
        FROM farmacias 
        WHERE nombre_region = ? 
        AND comuna_nombre = ?
        ORDER BY de_turno DESC, local_nombre
    ''', (region, comuna)).fetchall()
    conn.close()
    
    return jsonify([dict(farmacia) for farmacia in farmacias])

class ChatSession:
    def __init__(self):
        self.conversation_history = []
        self.created_at = datetime.now()

    def add_message(self, role, content):
        self.conversation_history.append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })

    def get_history(self):
        return self.conversation_history

    def clear_history(self):
        self.conversation_history = []

# Diccionario para almacenar las sesiones activas
chat_sessions = {}

def get_or_create_chat_session(session_id=None):
    """Obtiene o crea una nueva sesión de chat"""
    if session_id is None:
        # Si no se proporciona un ID, usamos el de la sesión Flask
        if 'chat_sid' not in session:
            session['chat_sid'] = str(uuid.uuid4())
            session.permanent = True
        
        session_id = session['chat_sid']
    
    # Crear nueva sesión de chat si no existe
    if session_id not in chat_sessions:
        chat_sessions[session_id] = ChatSession()
    
    return chat_sessions[session_id], session_id

def cleanup_old_sessions():
    """Limpia las sesiones antiguas"""
    current_time = datetime.now()
    for sid in list(chat_sessions.keys()):
        session_age = current_time - chat_sessions[sid].created_at
        if session_age > timedelta(minutes=60):
            del chat_sessions[sid]

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        print("Received data:", data)
        
        # Logging a archivo
        logging.info(f"=== New chat message received ===")
        
        if not data or 'message' not in data:
            print("No message in request")
            logging.warning("No message in request")
            return jsonify({'error': 'No message provided'}), 400

        user_message = data['message'].strip()
        if not user_message:
            print("Empty message")
            logging.warning("Empty message received")
            return jsonify({'error': 'Empty message'}), 400
        
        # Obtener el user_id del request o generar uno nuevo
        user_id = data.get('user_id')
        if not user_id:
            user_id = str(uuid.uuid4())
            print(f"No user_id provided, generated: {user_id}")
        
        print(f"Processing request for user_id: {user_id}")

        # Obtener la sesión de chat
        chat_session, session_id = get_or_create_chat_session(user_id)
        
        # Aquí llamamos al sistema RAG para procesar la consulta
        try:
            # Procesar la consulta con el sistema RAG usando el ID proporcionado
            rag_response = procesar_consulta(user_id, user_message)
            print(f"RAG response for user {user_id}: {rag_response[:100]}...")  # Para debug
        except Exception as rag_error:
            error_msg = f"Error en el sistema RAG: {str(rag_error)}"
            print(error_msg)
            logging.error(f"User {user_id}: {error_msg}")
            rag_response = f"Lo siento, ocurrió un error al procesar tu consulta: {str(rag_error)}"
        
        # Agregar mensajes al historial de la sesión de Flask
        chat_session.add_message('user', user_message)
        chat_session.add_message('assistant', rag_response)
        
        # Guardar el historial de chat en la base de datos de Flask
        save_chat_history(user_id, chat_session.get_history())
        
        logging.info(f"User {user_id} - Message: {user_message}")
        logging.info(f"User {user_id} - Response: {rag_response[:100]}...")

        return jsonify({
            'response': rag_response,
            'user_id': user_id  # Devolvemos el ID para que el cliente lo almacene si fue generado
        })

    except Exception as e:
        error_msg = f"Error in chat endpoint: {str(e)}"
        print(error_msg)
        logging.error(error_msg)
        return jsonify({'error': str(e)}), 500

def save_chat_history(session_id, history):
    """Guarda el historial del chat en la base de datos"""
    try:
        conn = get_db_connection()
        
        # Crear tabla si no existe
        conn.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                history TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Actualizar o insertar el historial
        conn.execute('''
            INSERT OR REPLACE INTO chat_history (session_id, history, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (session_id, json.dumps(history)))
        
        conn.commit()
        conn.close()
        
        logging.info(f"Chat history saved for session {session_id}")
    except Exception as e:
        error_msg = f"Error saving chat history: {str(e)}"
        logging.error(f"Session {session_id}: {error_msg}")
        print(error_msg)

@app.route('/chat/history', methods=['GET'])
def get_chat_history():
    """Endpoint para obtener el historial del chat"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': 'Se requiere user_id'}), 400
            
        # Intentar obtener historial de la sesión activa
        if user_id in chat_sessions:
            local_history = chat_sessions[user_id].get_history()
        else:
            local_history = []
            
        # Obtener historial desde la base de datos RAG
        try:
            rag_history = obtener_historial_usuario(user_id)
            
            # Usar un enfoque normal con bucle for para crear el historial formateado
            rag_history_formatted = []
            for consulta, respuesta, timestamp in rag_history:
                rag_history_formatted.append({
                    'role': 'user',
                    'content': consulta,
                    'timestamp': timestamp
                })
                rag_history_formatted.append({
                    'role': 'assistant',
                    'content': respuesta,
                    'timestamp': timestamp
                })
        except Exception as e:
            print(f"Error obteniendo historial RAG: {e}")
            rag_history_formatted = []
        
        # Combinar historiales (preferimos el local porque incluye la sesión actual)
        if local_history:
            history = local_history
        else:
            history = rag_history_formatted
            
        return jsonify({
            'user_id': user_id,
            'history': history
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/chat/clear', methods=['POST'])
def clear_chat_history():
    """Endpoint para limpiar el historial del chat"""
    try:
        data = request.get_json()
        if not data or 'user_id' not in data:
            return jsonify({'error': 'Se requiere user_id'}), 400
            
        user_id = data['user_id']
        
        # Limpiar sesión si existe
        if user_id in chat_sessions:
            chat_sessions[user_id].clear_history()
            
        # Eliminar historial de la base de datos
        def get_db_connection():
            base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'front', 'Base', 'farmacias_turno.db')
            conn = sqlite3.connect(base_path)
            conn.row_factory = sqlite3.Row
            return conn
        
        return jsonify({'message': 'Chat history cleared', 'user_id': user_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Endpoint para verificar la salud del sistema"""
    try:
        # Verificar conexión a la base de datos
        conn = get_db_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        
        # Verificar que el módulo RAG está cargado correctamente
        try:
            from consultas_llm import procesar_consulta
            rag_status = "loaded"
        except ImportError:
            rag_status = "not loaded"
        
        return jsonify({
            'status': 'ok',
            'timestamp': datetime.now().isoformat(),
            'database': 'connected',
            'rag_system': rag_status
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    # Código existente
    
    print("Iniciando servidor Flask...")
    app.run(host='0.0.0.0', port=5000, debug=False)