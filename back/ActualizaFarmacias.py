import requests
import json
import sqlite3
from datetime import datetime
import logging
import os  # Agregar esta importación al inicio del archivo

# Configuración de logging
logging.basicConfig(
    filename='actualizacion_farmacias.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# https://midas.minsal.cl/farmacia_v2/WS/getLocales.php
# https://midas.minsal.cl/farmacia_v2/WS/getLocalesTurnos.php


class ActualizadorFarmacias:
    def __init__(self):
        # Obtener el directorio donde se encuentra el archivo actual
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Crear la carpeta Base en el mismo directorio que el archivo
        base_dir = os.path.join(current_dir, 'Base')
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
            
        # Definir la ruta de la base de datos dentro de la carpeta Base
        self.db_path = os.path.join(base_dir, 'farmacias_turno.db')
        # URLs de las farmacias
        self.url_farmacias_normal = "https://midas.minsal.cl/farmacia_v2/WS/getLocales.php"
        self.url_farmacias_turno = "https://midas.minsal.cl/farmacia_v2/WS/getLocalesTurnos.php"
        try:
            # Conectar a la base de datos SQLite
            self.connection = sqlite3.connect(self.db_path)
            self.cursor = self.connection.cursor()
            
            # Crear la tabla si no existe
            self.crear_tabla()
            
            print("Conexión y estructura de base de datos inicializada correctamente")
            
        except sqlite3.Error as err:
            print(f"Error al inicializar la base de datos: {err}")
            raise

    def crear_tabla(self):
        """Crea la tabla farmacias si no existe"""
        try:
            crear_tabla_sql = """
            CREATE TABLE IF NOT EXISTS farmacias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                local_id INTEGER NOT NULL,
                local_nombre TEXT,
                comuna_nombre TEXT,
                localidad_nombre TEXT,
                local_direccion TEXT,
                URL_direccion TEXT,
                funcionamiento_hora_apertura TEXT,
                funcionamiento_hora_cierre TEXT,
                local_telefono TEXT,
                local_lat REAL,
                local_lng REAL,
                funcionamiento_dia TEXT,
                fecha TEXT,
                de_turno INTEGER DEFAULT 0,
                fk_region INTEGER,
                fk_comuna INTEGER,
                fk_localidad INTEGER,
                nombre_region TEXT,
                fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            self.cursor.execute(crear_tabla_sql)
            self.connection.commit()
            print("Tabla farmacias creada o verificada correctamente")
            
        except sqlite3.Error as err:
            print(f"Error al crear la tabla farmacias: {err}")
            raise

    def obtener_datos_api(self, url):
        """Obtiene datos de la API especificada"""
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error obteniendo datos de {url}: {str(e)}")
            return None

    def limpiar_tabla(self):
        """Limpia todos los registros de la tabla farmacias"""
        try:
            self.cursor.execute("DELETE FROM farmacias")
            self.connection.commit()
            print("Tabla farmacias limpiada correctamente")
        except sqlite3.Error as err:
            print(f"Error al limpiar la tabla: {err}")
            raise

    def cerrar_conexion(self):
        """Cierra la conexión a la base de datos"""
        if hasattr(self, 'connection') and self.connection:
            self.connection.close()
            print("Conexión a la base de datos cerrada")

    def validar_farmacia(self, farmacia: dict) -> tuple[bool, str]:
        """Valida los datos críticos de una farmacia antes de insertarla"""
        try:
            print("Iniciando validación de farmacia:", farmacia)  # Debug log
            
            # Mapeo de regiones
            regiones = {
                1: 'Arica y Parinacota',
                2: 'Tarapacá',
                3: 'Antofagasta',
                4: 'Atacama',
                5: 'Coquimbo',
                6: 'Valparaíso',
                7: 'Metropolitana de Santiago',
                8: 'Libertador General Bernardo O\'Higgins',
                9: 'Maule',
                10: 'Biobío',
                11: 'La Araucanía',
                12: 'Los Ríos',
                13: 'Los Lagos',
                14: 'Aysén del General Carlos Ibáñez del Campo',
                15: 'Magallanes y de la Antártica Chilena',
                16: 'Ñuble'
            }

            # Validaciones de campos obligatorios
            campos_obligatorios = ['local_id', 'local_nombre', 'comuna_nombre', 'local_direccion']
            for campo in campos_obligatorios:
                if not farmacia.get(campo):
                    print(f"Error: Campo obligatorio '{campo}' está vacío")  # Debug log
                    return False, f"Campo obligatorio '{campo}' está vacío"

            # Limpiar y validar todos los campos string
            campos_string = [
                'local_nombre', 'comuna_nombre', 'localidad_nombre', 'local_direccion',
                'funcionamiento_hora_apertura', 'funcionamiento_hora_cierre',
                'local_telefono', 'funcionamiento_dia'
            ]
            for campo in campos_string:
                if campo in farmacia and farmacia[campo]:
                    farmacia[campo] = str(farmacia[campo]).strip()
                    print(f"Campo {campo} limpiado: {farmacia[campo]}")  # Debug log

            # Validación y conversión de campos numéricos
            campos_numericos = ['local_id', 'fk_region', 'fk_comuna', 'fk_localidad']
            for campo in campos_numericos:
                if campo in farmacia and farmacia[campo]:
                    try:
                        valor_original = farmacia[campo]
                        farmacia[campo] = int(str(farmacia[campo]).strip())
                        print(f"Campo {campo} convertido: {valor_original} -> {farmacia[campo]}")  # Debug log
                        if campo == 'local_id' and farmacia[campo] <= 0:
                            print(f"Error: local_id inválido: {farmacia[campo]}")  # Debug log
                            return False, f"local_id debe ser mayor que 0: {farmacia[campo]}"
                    except (ValueError, TypeError) as e:
                        print(f"Error al convertir {campo}: {e}")  # Debug log
                        return False, f"{campo} no es un número válido: {farmacia[campo]}"

            # Agregar nombre_region basado en fk_region
            if 'fk_region' in farmacia and farmacia['fk_region']:
                farmacia['nombre_region'] = regiones.get(farmacia['fk_region'], 'Región no encontrada')
                print(f"Nombre región asignado: {farmacia['nombre_region']}")  # Debug log

            print("Validación exitosa")  # Debug log
            return True, "Validación exitosa"
            
        except Exception as e:
            print(f"Error en validación: {str(e)}")  # Debug log
            return False, f"Error en validación: {str(e)}"

    def insertar_farmacias(self, farmacias, de_turno) -> bool:
        """Inserta las farmacias en la base de datos"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            farmacias_validas = 0
            farmacias_invalidas = 0

            sql = """
            INSERT INTO farmacias (
                local_id, local_nombre, comuna_nombre, localidad_nombre,
                local_direccion, URL_direccion, funcionamiento_hora_apertura,
                funcionamiento_hora_cierre, local_telefono, local_lat, local_lng,
                funcionamiento_dia, fecha, de_turno, fk_region, fk_comuna,
                fk_localidad, nombre_region
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """
            
            for farmacia in farmacias:
                # Validar la farmacia antes de insertarla
                es_valida, mensaje = self.validar_farmacia(farmacia)
                if es_valida:
                    valores = (
                        farmacia.get('local_id'),
                        farmacia.get('local_nombre'),
                        farmacia.get('comuna_nombre'),
                        farmacia.get('localidad_nombre'),
                        farmacia.get('local_direccion'),
                        farmacia.get('URL_direccion'),
                        farmacia.get('funcionamiento_hora_apertura'),
                        farmacia.get('funcionamiento_hora_cierre'),
                        farmacia.get('local_telefono'),
                        farmacia.get('local_lat'),
                        farmacia.get('local_lng'),
                        farmacia.get('funcionamiento_dia'),
                        farmacia.get('fecha'),
                        de_turno,
                        farmacia.get('fk_region'),
                        farmacia.get('fk_comuna'),
                        farmacia.get('fk_localidad'),
                        farmacia.get('nombre_region')
                    )
                    
                    cursor.execute(sql, valores)
                    farmacias_validas += 1
                else:
                    print(f"Farmacia inválida: {mensaje}")
                    farmacias_invalidas += 1
            
            conn.commit()

            # Registro de resultados
            tipo_farmacia = "de turno" if de_turno else "normales"
            print(f"Farmacias {tipo_farmacia} procesadas:")
            print(f"- Válidas: {farmacias_validas}")
            print(f"- Inválidas: {farmacias_invalidas}")
            print(f"- Total: {farmacias_validas + farmacias_invalidas}")

            # Registro en archivo de log
            logging.info(f"Farmacias {tipo_farmacia} procesadas:")
            logging.info(f"- Válidas: {farmacias_validas}")
            logging.info(f"- Inválidas: {farmacias_invalidas}")
            logging.info(f"- Total: {farmacias_validas + farmacias_invalidas}")
            
            return True
            
        except sqlite3.Error as e:
            print(f"Error al insertar farmacias: {e}")
            logging.error(f"Error al insertar farmacias: {e}")
            farmacias_invalidas += 1
            return False
        finally:
            if conn:
                conn.close()

    def actualizar_farmacias(self):
        """Proceso principal de actualización"""
        try:
            # Crear tabla si no existe
            self.crear_tabla()
            
            # Obtener datos de ambas APIs
            farmacias_normal = self.obtener_datos_api(self.url_farmacias_normal)
            farmacias_turno = self.obtener_datos_api(self.url_farmacias_turno)
            
            if farmacias_normal is None or farmacias_turno is None:
                logging.error("No se pudieron obtener los datos de las APIs")
                return False
            
            # Limpiar tabla antes de insertar nuevos datos
            self.limpiar_tabla()
            
            # Insertar farmacias normales
            self.insertar_farmacias(farmacias_normal, False)
            
            # Insertar farmacias de turno
            self.insertar_farmacias(farmacias_turno, True)
            
            # Actualizar URLs usando el método combinado
            self.actualizar_url_combinada()
            
            logging.info("Actualización de farmacias completada exitosamente")
            return True
            
        except Exception as e:
            logging.error(f"Error en el proceso de actualización: {str(e)}")
            return False

    def consultar_farmacias(self, limit=10):
        """Consulta los primeros registros de la tabla Farmacias"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Consulta SQL para obtener los primeros registros
            cursor.execute('''
                SELECT * 
                FROM farmacias
                limit 50
            ''')
            
            # Obtener los nombres de las columnas
            columns = [description[0] for description in cursor.description]
            
            # Obtener los resultados
            results = cursor.fetchall()
            
            # Imprimir resultados en formato tabular
            print("-" * 100)
            print("|".join(f"{col:^15}" for col in columns))
            print("-" * 100)
            
            for row in results:
                print("|".join(f"{str(val):^15}" for val in row))
            
            logging.info(f"Consultados {len(results)} registros de farmacias")
            return results
            
        except Exception as e:
            logging.error(f"Error consultando farmacias: {str(e)}")
            raise
        finally:
            conn.close()

    def actualizar_url_direccion(self) -> bool:
        """Actualiza el campo URL_direccion para todas las farmacias"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Obtener todas las farmacias que necesitan URL
            cursor.execute("""
                SELECT id, local_direccion, comuna_nombre, nombre_region 
                FROM farmacias
            """)
            farmacias = cursor.fetchall()
            
            actualizadas = 0
            con_error = 0
            
            for farmacia in farmacias:
                try:
                    id_farmacia, direccion, comuna, region = farmacia
                    
                    # Construir la URL reemplazando espacios por +
                    url_base = "https://www.google.com/maps/place/"
                    direccion_formateada = direccion.replace(" ", "+") if direccion else ""
                    comuna_formateada = comuna.replace(" ", "+") if comuna else ""
                    region_formateada = region.replace(" ", "+") if region else ""
                    
                    url_completa = f"{url_base}{direccion_formateada},+{comuna_formateada},+{region_formateada}"
                    
                    # Actualizar el registro
                    cursor.execute("""
                        UPDATE farmacias 
                        SET URL_direccion = ? 
                        WHERE id = ?
                    """, (url_completa, id_farmacia))
                    
                    actualizadas += 1
                    
                except Exception as e:
                    logging.error(f"Error procesando farmacia {id_farmacia}: {str(e)}")
                    con_error += 1
                    continue
            
            conn.commit()
            
            # Registrar resultados
            logging.info("Actualización de URLs completada:")
            logging.info(f"- Farmacias actualizadas: {actualizadas}")
            logging.info(f"- Farmacias con error: {con_error}")
            logging.info(f"- Total procesadas: {actualizadas + con_error}")
            
            return True
            
        except sqlite3.Error as e:
            logging.error(f"Error en la base de datos: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def actualizar_url_coordenadas(self) -> bool:
        """Actualiza el campo URL_direccion usando las coordenadas geográficas"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Obtener todas las farmacias con coordenadas
            cursor.execute("""
                SELECT id, local_lat, local_lng 
                FROM farmacias
                WHERE local_lat IS NOT NULL AND local_lng IS NOT NULL
            """)
            farmacias = cursor.fetchall()
            
            actualizadas = 0
            con_error = 0
            
            for farmacia in farmacias:
                try:
                    id_farmacia, lat, lng = farmacia
                    
                    # Construir la URL con coordenadas
                    url_base = "https://www.google.com/maps/@"
                    lat_formateada = str(lat)[:11] if lat else ""
                    lng_formateada = str(lng)[:10] if lng else ""
                    
                    url_completa = f"{url_base}{lat_formateada},{lng_formateada},18z"
                    
                    # Actualizar el registro
                    cursor.execute("""
                        UPDATE farmacias 
                        SET URL_direccion = ? 
                        WHERE id = ?
                    """, (url_completa, id_farmacia))
                    
                    actualizadas += 1
                    
                except Exception as e:
                    logging.error(f"Error procesando coordenadas de farmacia {id_farmacia}: {str(e)}")
                    con_error += 1
                    continue
            
            conn.commit()
            
            # Registrar resultados
            logging.info("Actualización de URLs por coordenadas completada:")
            logging.info(f"- Farmacias actualizadas: {actualizadas}")
            logging.info(f"- Farmacias con error: {con_error}")
            logging.info(f"- Total procesadas: {actualizadas + con_error}")
            
            return True
            
        except sqlite3.Error as e:
            logging.error(f"Error en la base de datos: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def actualizar_url_combinada(self) -> bool:
        """Actualiza el campo URL_direccion combinando dirección y coordenadas"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Obtener todas las farmacias con sus datos
            cursor.execute("""
                SELECT id, local_direccion, comuna_nombre, nombre_region, local_lat, local_lng 
                FROM farmacias
                WHERE local_lat IS NOT NULL AND local_lng IS NOT NULL
            """)
            farmacias = cursor.fetchall()
            
            actualizadas = 0
            con_error = 0
            
            for farmacia in farmacias:
                try:
                    id_farmacia, direccion, comuna, region, lat, lng = farmacia
                    
                    # Construir la primera parte de la URL (dirección)
                    url_base = "https://www.google.com/maps/place/"
                    direccion_formateada = direccion.replace(" ", "+") if direccion else ""
                    comuna_formateada = comuna.replace(" ", "+") if comuna else ""
                    region_formateada = region.replace(" ", "+") if region else ""
                    
                    # Construir la segunda parte (coordenadas)
                    lat_formateada = str(lat)[:11] if lat else ""
                    lng_formateada = str(lng)[:10] if lng else ""
                    
                    # Combinar ambas partes
                    url_completa = f"{url_base}{direccion_formateada},+{comuna_formateada},+{region_formateada}/@{lat_formateada},{lng_formateada}"
                    
                    # Actualizar el registro
                    cursor.execute("""
                        UPDATE farmacias 
                        SET URL_direccion = ? 
                        WHERE id = ?
                    """, (url_completa, id_farmacia))
                    
                    actualizadas += 1
                    
                except Exception as e:
                    logging.error(f"Error procesando farmacia {id_farmacia}: {str(e)}")
                    con_error += 1
                    continue
            
            conn.commit()
            
            # Registrar resultados
            logging.info("Actualización de URLs combinadas completada:")
            logging.info(f"- Farmacias actualizadas: {actualizadas}")
            logging.info(f"- Farmacias con error: {con_error}")
            logging.info(f"- Total procesadas: {actualizadas + con_error}")
            
            return True
            
        except sqlite3.Error as e:
            logging.error(f"Error en la base de datos: {e}")
            return False
        finally:
            if conn:
                conn.close()

# Agregar código para ejecutar el proceso
if __name__ == "__main__":
    actualizador = ActualizadorFarmacias()
    if actualizador.actualizar_farmacias():
        print("\nConsultando resultados...")
        actualizador.consultar_farmacias()