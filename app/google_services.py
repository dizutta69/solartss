import os
import base64
import requests
from PIL import Image
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
RUTA_CREDS = "credenciales_google.json"

# CONFIGURACIÓN MAESTRA
ID_GOOGLE_SHEET = "1_OCwBc90_zqaUlW0R20OfE6ByYSYk3zg1A81rnoK9T0"
ID_CARPETA_MAESTRA_DRIVE = "1KeEkJYhey5HyDJKFLCCrlJd00Q8i8LG3"
URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbzU0-z7BY3wP1BUXZUS06JzL7gQ-ydpXmK-hZjWiXDQsrKZp8i7v6mv2HbepXTjHTBbqg/exec"

def conectar_sheets():
    creds = service_account.Credentials.from_service_account_file(RUTA_CREDS, scopes=SCOPES)
    return build('sheets', 'v4', credentials=creds)

def optimizar_y_codificar_foto(ruta_origen):
    """Comprime la imagen y la convierte a cadena Base64 para enviarla por red"""
    if not os.path.exists(ruta_origen):
        return None
        
    img = Image.open(ruta_origen)
    if img.mode in ("RGBA", "P"):
        fondo = Image.new("RGB", img.size, (255, 255, 255))
        fondo.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)
        img = fondo
    elif img.mode != "RGB":
        img = img.convert("RGB")
        
    img.thumbnail((1200, 1200)) # Tamaño óptimo para celulares en campo
    ruta_temp = f"comp_{os.path.basename(ruta_origen)}"
    img.save(ruta_temp, "JPEG", quality=70)
    
    with open(ruta_temp, "rb") as archivo_foto:
        b64_string = base64.b64encode(archivo_foto.read()).decode('utf-8')
        
    os.remove(ruta_origen)
    os.remove(ruta_temp)
    return b64_string

def enviar_datos_a_google(datos: dict, fotos_locales: list):
    sheets = conectar_sheets()
    nombre_cliente = datos.get("cliente", "Anonimo")
    id_visita = datos.get("id_visita", "000")
    
    # 1. Preparar el paquete de fotos comprimidas
    fotos_payload = []
    for foto_ruta in fotos_locales:
        b64 = optimizar_y_codificar_foto(foto_ruta)
        if b64:
            fotos_payload.append({
                "nombre": os.path.basename(foto_ruta),
                "bytes": b64
            })
            
    # 2. Despachar fotos al Apps Script (Sube usando tu cuota personal con éxito asegurado)
    payload_script = {
        "id_carpeta_maestra": ID_CARPETA_MAESTRA_DRIVE,
        "nombre_cliente": nombre_cliente,
        "id_visita": id_visita,
        "fotos": fotos_payload
    }
    
    respuesta = requests.post(URL_APPS_SCRIPT, json=payload_script)
    resultado_script = respuesta.json()
    
    if resultado_script.get("status") == "error":
        raise Exception(f"Fallo en Apps Script: {resultado_script.get('message')}")
        
    url_carpeta_cliente = resultado_script.get("folder_url")
    enlaces_fotos = resultado_script.get("enlaces_fotos", [])
    
    while len(enlaces_fotos) < 3:
        enlaces_fotos.append("No cargada")
        
    # 3. Escribir fila definitiva en Google Sheets mediante la cuenta de servicio
    fila = [
        id_visita,
        datos.get("tipo_instalacion", ""),
        nombre_cliente,
        datos.get("direccion", ""),
        datos.get("gps", ""),
        datos.get("tipo_cubierta", ""),
        datos.get("inclinacion", ""),
        datos.get("tipo_red", ""),
        datos.get("breaker_principal", ""),
        url_carpeta_cliente,
        enlaces_fotos[0],
        enlaces_fotos[1],
        enlaces_fotos[2]
    ]
    
    cuerpo = {'values': [fila]}
    sheets.spreadsheets().values().append(
        spreadsheetId=ID_GOOGLE_SHEET,
        range="Hoja 1!A:M",
        valueInputOption="USER_ENTERED",
        body=cuerpo
    ).execute()