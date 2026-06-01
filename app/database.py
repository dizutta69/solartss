import sqlite3
import json

DB_NAME = "borradores_survey.db"

def inicializar_bd():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS borradores (
            id_visita TEXT PRIMARY KEY,
            datos TEXT,
            fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def guardar_progreso_local(id_visita: str, datos_dict: dict):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT datos FROM borradores WHERE id_visita = ?", (id_visita,))
    fila = cursor.fetchone()
    
    if fila:
        datos_existentes = json.loads(fila[0])
        datos_existentes.update(datos_dict)
        datos_finales = datos_existentes
    else:
        datos_finales = datos_dict

    cursor.execute('''
        INSERT INTO borradores (id_visita, datos, fecha_actualizacion)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(id_visita) DO UPDATE SET datos = ?, fecha_actualizacion = CURRENT_TIMESTAMP
    ''', (id_visita, json.dumps(datos_finales), json.dumps(datos_finales)))
    
    conn.commit()
    conn.close()

def obtener_progreso_local(id_visita: str) -> dict:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT datos FROM borradores WHERE id_visita = ?", (id_visita,))
    fila = cursor.fetchone()
    conn.close()
    return json.loads(fila[0]) if fila else {}

def eliminar_borrador(id_visita: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM borradores WHERE id_visita = ?", (id_visita,))
    conn.commit()
    conn.close()