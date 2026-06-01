from fastapi import FastAPI, Request, Form, UploadFile, File, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import os
import uuid
import secrets
from .database import inicializar_bd, guardar_progreso_local, obtener_progreso_local, eliminar_borrador
from .google_services import enviar_datos_a_google

app = FastAPI()
security = HTTPBasic()

# CREDENCIALES DE ACCESO REQUERIDAS
USUARIO_TECNICO = "tecnico_solar"
PASSWORD_TECNICO = "ZuttaSolar2026*"

def verificar_autenticacion(credentials: HTTPBasicCredentials = Depends(security)):
    usuario_correcto = secrets.compare_digest(credentials.username, USUARIO_TECNICO)
    password_correcto = secrets.compare_digest(credentials.password, PASSWORD_TECNICO)
    if not (usuario_correcto and password_correcto):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales SolarTSS incorrectas",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
os.makedirs("temp_fotos", exist_ok=True)

@app.on_event("startup")
def startup_event():
    inicializar_bd()

@app.get("/solartss", response_class=HTMLResponse)
async def ver_formulario(request: Request, id_visita: str = None, usuario: str = Depends(verificar_autenticacion)):
    """Carga el formulario. Exige login inicial en el navegador"""
    if not id_visita:
        id_visita = str(uuid.uuid4())[:8] # Genera ID corto único de visita
    
    try:
        progreso = obtener_progreso_local(id_visita)
    except Exception:
        progreso = {}
        
    if not progreso:
        progreso = {}
    
    # SOLUCIÓN: Pasar 'request' primero y luego el diccionario de contexto
    return templates.TemplateResponse(
        request=request,
        name="formulario.html", 
        context={
            "id_visita": id_visita,
            "progreso": progreso
        }
    )

@app.post("/api/survey/guardar-parcial")
async def guardar_parcial(request: Request, usuario: str = Depends(verificar_autenticacion)):
    form_data = await request.form()
    id_visita = form_data.get("id_visita")
    if not id_visita:
        return JSONResponse({"error": "ID ausente"}, status_code=400)
    datos = {k: v for k, v in form_data.items() if k != "id_visita"}
    guardar_progreso_local(id_visita, datos)
    return JSONResponse({"status": "Borrador guardado"})

@app.post("/api/survey/subir-foto")
async def subir_foto_temporal(
    id_visita: str = Form(...), 
    tipo_foto: str = Form(...), 
    foto: UploadFile = File(...),
    usuario: str = Depends(verificar_autenticacion)
):
    ruta_local = f"temp_fotos/{id_visita}_{tipo_foto}.jpg"
    with open(ruta_local, "wb") as buffer:
        buffer.write(await foto.read())
    guardar_progreso_local(id_visita, {f"foto_{tipo_foto}": ruta_local})
    return JSONResponse({"status": "Foto guardada temporalmente"})

@app.post("/solartss/finalizar")

@app.post("/solartss/finalizar")
async def finalizar_survey(id_visita: str = Form(...), usuario: str = Depends(verificar_autenticacion)):
    """Recopila el borrador completo y lo sube de forma definitiva a Google Cloud"""
    progreso = obtener_progreso_local(id_visita)
    if not progreso:
        return HTMLResponse(content="<h2>Error: No se encontraron datos para procesar</h2>", status_code=400)
    
    # Recolectar las rutas de las fotos almacenadas temporalmente
    fotos = []
    for tipo in ["recibo", "tablero", "techo"]:
        ruta = progreso.get(f"foto_{tipo}")
        if ruta:
            fotos.append(ruta)
            
    try:
        # Sincronización masiva con Google Drive y Google Sheets
        enviar_datos_a_google(progreso, fotos)
        # Limpieza del borrador en la base de datos local al finalizar con éxito
        eliminar_borrador(id_visita)
        return HTMLResponse(content="<h2>¡Levantamiento Técnico guardado con éxito en Google Drive y Excel! Puedes cerrar esta pestaña.</h2>")
    except Exception as e:
        import traceback
        error_detallado = traceback.format_exc()
        print(error_detallado)  # Esto imprimirá el error real en tu consola de PowerShell
        return HTMLResponse(
            content=f"<h2>Error crítico al sincronizar con Google:</h2><pre>{str(e)}</pre><p>Revisa la consola de PowerShell para ver el reporte detallado.</p>", 
            status_code=500
        )