from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import stats as stats_module
from app.database import get_session
from app.stats import PeriodoPalabras

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/resumen")
def resumen(db: Session = Depends(get_session)):
    datos = stats_module.resumen_general(db)
    datos["racha_dias"] = stats_module.racha_dias_lectura(db)
    return datos


@router.get("/top-fandoms")
def top_fandoms(limite: int = 10, anio: int | None = None, db: Session = Depends(get_session)):
    return [{"nombre": n, "total": t} for n, t in stats_module.top_fandoms(db, limite, anio=anio)]


@router.get("/top-ships")
def top_ships(
    limite: int = 10, tipo: str | None = None, anio: int | None = None, db: Session = Depends(get_session)
):
    return [
        {"nombre": n, "total": t} for n, t in stats_module.top_ships(db, limite, tipo=tipo, anio=anio)
    ]


@router.get("/palabras-por-mes", response_model=list[PeriodoPalabras])
def palabras_por_mes(anio: int | None = None, db: Session = Depends(get_session)):
    return stats_module.palabras_leidas_por_mes(db, anio)


@router.get("/palabras-por-anio", response_model=list[PeriodoPalabras])
def palabras_por_anio(db: Session = Depends(get_session)):
    return stats_module.palabras_leidas_por_anio(db)


@router.get("/distribucion-longitud")
def distribucion_longitud(db: Session = Depends(get_session)):
    return [{"bucket": b, "total": t} for b, t in stats_module.distribucion_longitud(db)]


@router.get("/ratio-wip-completos")
def ratio_wip_completos(db: Session = Depends(get_session)):
    return stats_module.ratio_wip_vs_completos(db)


@router.get("/estado-lectura")
def estado_lectura(db: Session = Depends(get_session)):
    return stats_module.conteo_por_estado_lectura(db)


@router.get("/relecturas")
def relecturas(limite: int = 10, db: Session = Depends(get_session)):
    return {
        "total": stats_module.total_relecturas(db),
        "top_fics": [
            {"titulo": t, "relecturas": r} for t, r in stats_module.relecturas_por_fic(db, limite)
        ],
    }


@router.get("/rating-por-fandom")
def rating_por_fandom(minimo_resenas: int = 1, db: Session = Depends(get_session)):
    return [
        {"fandom": f, "promedio": round(p, 2), "total_resenas": tr}
        for f, p, tr in stats_module.promedio_rating_por_fandom(db, minimo_resenas)
    ]
