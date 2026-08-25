from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.api.serializers import to_archivo_out
from app.database import get_session
from app.models import Archivo
from app.schemas import ArchivoOut

router = APIRouter(prefix="/archivos", tags=["archivos"])

MEDIA_TYPES = {
    "epub": "application/epub+zip",
    "html": "text/html; charset=utf-8",
}

# El snapshot guardado es el HTML crudo tal como lo mandó AO3, con el skin
# (a veces personalizado) de quien lo bookmarkeó — columnas angostas, texto
# justificado, fondos decorativos, y todo el menú/dashboard/footer de AO3
# arriba del cuento. Esto se inyecta solo al SERVIR la copia (nunca se toca
# el archivo guardado en disco) para que se lea cómodo, sin perder el
# original como respaldo. #header/#footer/#dashboard/.skiplink son ids fijos
# de la plantilla de AO3 (no cambian con el skin de cada usuaria), así que
# esconderlos es seguro independientemente de qué skin tenía puesto quien
# bookmarkeó el fic.
_MODO_LECTURA = """
<style>
  #header, #footer, #dashboard, .skiplink, #outer > .actions,
  .header.module .actions, .navigation.actions {
    display: none !important;
  }
  html, body {
    background: #fdfcf7 !important;
    background-image: none !important;
  }
  body {
    max-width: 680px !important;
    margin: 0 auto !important;
    padding: 32px 24px !important;
    color: #222 !important;
    font-family: Georgia, "Times New Roman", serif !important;
    font-size: 18px !important;
    line-height: 1.75 !important;
  }
  body * {
    max-width: 100% !important;
    background: transparent !important;
    background-image: none !important;
    text-align: left !important;
    box-shadow: none !important;
    border-color: #e3d3b6 !important;
  }
  p { margin: 0 0 1.2em !important; }
</style>
"""


@router.get("", response_model=list[ArchivoOut])
def listar_archivos(db: Session = Depends(get_session)):
    archivos = db.query(Archivo).order_by(Archivo.fecha_descarga.desc()).all()
    return [to_archivo_out(a) for a in archivos]


@router.get("/{archivo_id}/contenido")
def obtener_contenido_archivo(archivo_id: int, db: Session = Depends(get_session)):
    """Sirve el archivo guardado (epub o snapshot html) de vuelta al navegador.

    HTML se sirve sin Content-Disposition -> el navegador lo renderiza
    inline (es la "copia archivada" que se puede ver directo). EPUB se sirve
    como attachment porque los navegadores no lo renderizan solos.
    """
    archivo = db.get(Archivo, archivo_id)
    if archivo is None:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    ruta = Path(archivo.ruta_local)
    if not ruta.is_file():
        raise HTTPException(
            status_code=410,
            detail="El archivo ya no está en el disco (¿se movió o se borró data/archivo/?).",
        )

    media_type = MEDIA_TYPES.get(archivo.formato, "application/octet-stream")
    if archivo.formato == "html":
        html = ruta.read_text(encoding="utf-8", errors="replace")
        if "</body>" in html:
            html = html.replace("</body>", f"{_MODO_LECTURA}</body>", 1)
        else:
            html += _MODO_LECTURA
        return HTMLResponse(html)

    nombre = f"{archivo.fic.titulo}.{archivo.formato}".replace("/", "-")
    return FileResponse(ruta, media_type=media_type, filename=nombre)


@router.delete("/{archivo_id}", status_code=204)
def borrar_archivo(archivo_id: int, db: Session = Depends(get_session)):
    """Borra una copia archivada (html o epub) a pedido: espacio en disco es
    limitado y no todo fic amerita quedar guardado ahí para siempre. Solo
    borra este `Archivo` puntual, nunca el `Fic` ni su historial de lectura."""
    archivo = db.get(Archivo, archivo_id)
    if archivo is None:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    ruta = Path(archivo.ruta_local)
    if ruta.is_file():
        ruta.unlink()

    db.delete(archivo)
    db.commit()
