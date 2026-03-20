"""
validador.py - Motor de validacion
"""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import pandas as pd

try:
    from rapidfuzz import fuzz, process as rfprocess
    RAPIDFUZZ_OK = True
except ImportError:
    RAPIDFUZZ_OK = False

CSV_TITULOS    = Path(__file__).parent / "titulos.csv"
CSV_DECISIONES = Path(__file__).parent / "decisiones_back.csv"

UMBRAL_AUTO    = 0.82
UMBRAL_ESCALAR = 0.60

KEYWORDS_NIVEL = {
    "doctorado":       ["doctorado", "phd", "ph.d", "doctor en"],
    "maestria":        ["maestria", "master", "magister", "mba", "m.sc"],
    "especializacion": ["especializacion", "especialista"],
    "universitario":   ["ingenieria", "licenciatura", "medicina", "derecho",
                        "administracion", "contaduria", "arquitectura",
                        "psicologia", "economia", "enfermeria", "odontologia",
                        "comunicacion", "veterinaria"],
    "tecnologo":       ["tecnologo", "tecnologia en", "tecnico superior"],
    "bachillerato":    ["bachiller", "tecnico", "auxiliar"],
}

SEMESTRE_POR_NIVEL = {
    "doctorado":       8,
    "maestria":        7,
    "especializacion": 6,
    "universitario":   5,
    "tecnologo":       3,
    "bachillerato":    1,
}


@dataclass
class Resultado:
    aplica:            bool
    nivel:             Optional[str]
    semestre:          Optional[int]
    confianza:         float
    requiere_revision: bool
    metodo:            str
    match:             Optional[str] = None
    razon:             str = ""

    @property
    def confianza_pct(self) -> int:
        return round(self.confianza * 100)


def _norm(texto: str) -> str:
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _inferir_nivel(titulo_norm: str) -> Optional[str]:
    for nivel, kws in KEYWORDS_NIVEL.items():
        if any(kw in titulo_norm for kw in kws):
            return nivel
    return None


def _es_no_aplica(titulo_norm: str) -> bool:
    patrones = [r"curso\s+de", r"taller\s+de", r"diplomado\s+(?!avanzado)"]
    return any(re.search(p, titulo_norm) for p in patrones)


class ValidadorCSV:

    def __init__(self):
        self._df = pd.DataFrame()
        self.recargar()

    def recargar(self) -> None:
        frames = []
        if CSV_TITULOS.exists():
            frames.append(pd.read_csv(CSV_TITULOS))
        if CSV_DECISIONES.exists():
            dec = pd.read_csv(CSV_DECISIONES)
            dec = dec[dec["incorporar"].astype(str).str.lower() == "true"]
            if not dec.empty:
                dec = dec.rename(columns={"decision_aplica": "aplica", "nivel_confirmado": "nivel"})
                frames.append(dec[["nombre_titulo", "universidad", "pais", "aplica", "nivel", "semestre"]])
        if frames:
            self._df = pd.concat(frames, ignore_index=True)
            self._df["_norm"] = self._df["nombre_titulo"].astype(str).apply(_norm)
            self._df["aplica"] = self._df["aplica"].astype(str).str.lower().isin(["true", "1", "yes"])
        else:
            self._df = pd.DataFrame(columns=["nombre_titulo", "universidad", "pais",
                                              "aplica", "nivel", "semestre", "_norm"])

    def _exacta(self, titulo_norm: str):
        hits = self._df[self._df["_norm"] == titulo_norm]
        return hits.iloc[0] if not hits.empty else None

    def _fuzzy(self, titulo_norm: str):
        if not RAPIDFUZZ_OK or self._df.empty:
            return []
        nombres = self._df["_norm"].tolist()
        hits = rfprocess.extract(titulo_norm, nombres, scorer=fuzz.token_sort_ratio, limit=5)
        return [(self._df.iloc[idx], score / 100) for _, score, idx in hits if score >= 55]

    def validar(self, titulo: str, universidad: str = "", pais: str = "") -> Resultado:
        tn = _norm(titulo)
        if _es_no_aplica(tn):
            return Resultado(aplica=False, nivel=None, semestre=None, confianza=0.92,
                             requiere_revision=False, metodo="exacto",
                             razon="Patron de exclusion")
        fila = self._exacta(tn)
        if fila is not None:
            nivel = str(fila["nivel"])
            return Resultado(
                aplica=bool(fila["aplica"]), nivel=nivel,
                semestre=int(fila["semestre"]) if pd.notna(fila.get("semestre")) else SEMESTRE_POR_NIVEL.get(nivel),
                confianza=0.98, requiere_revision=False, metodo="exacto",
                match=str(fila["nombre_titulo"]), razon="Coincidencia exacta en base historica")
        fuzzy_hits = self._fuzzy(tn)
        nivel_kw = _inferir_nivel(tn)
        if fuzzy_hits:
            mejor_fila, mejor_sim = fuzzy_hits[0]
            bonus = 0.15 if (nivel_kw and nivel_kw == str(mejor_fila["nivel"])) else (0.10 if nivel_kw else 0.0)
            confianza = min(mejor_sim * 0.85 + bonus, 0.94)
            nivel_final = nivel_kw or str(mejor_fila["nivel"])
            return Resultado(
                aplica=bool(mejor_fila["aplica"]), nivel=nivel_final,
                semestre=SEMESTRE_POR_NIVEL.get(nivel_final),
                confianza=round(confianza, 3),
                requiere_revision=confianza < UMBRAL_ESCALAR,
                metodo="fuzzy", match=str(mejor_fila["nombre_titulo"]),
                razon="Similitud con " + str(mejor_fila["nombre_titulo"]))
        if nivel_kw:
            return Resultado(
                aplica=nivel_kw not in ("bachillerato",), nivel=nivel_kw,
                semestre=SEMESTRE_POR_NIVEL.get(nivel_kw),
                confianza=0.50, requiere_revision=True, metodo="keywords",
                razon="Inferido por palabras clave")
        return Resultado(
            aplica=False, nivel=None, semestre=None, confianza=0.0,
            requiere_revision=True, metodo="desconocido",
            razon="Sin informacion suficiente - revisar con equipo Back")

    def guardar_decision(self, titulo, universidad, pais, aplica, nivel,
                         revisor="", motivo="", incorporar=True) -> None:
        nueva_fila = {
            "fecha":            datetime.now(timezone.utc).isoformat(),
            "nombre_titulo":    titulo,
            "universidad":      universidad,
            "pais":             pais,
            "decision_aplica":  str(aplica).lower(),
            "nivel_confirmado": nivel,
            "semestre":         SEMESTRE_POR_NIVEL.get(nivel, ""),
            "revisor":          revisor,
            "motivo":           motivo,
            "incorporar":       str(incorporar).lower(),
        }
        if CSV_DECISIONES.exists():
            df = pd.read_csv(CSV_DECISIONES)
            df = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)
        else:
            df = pd.DataFrame([nueva_fila])
        df.to_csv(CSV_DECISIONES, index=False)
        if incorporar:
            self.recargar()

    def stats(self) -> dict:
        if self._df.empty:
            return {"total": 0, "aplican": 0, "no_aplican": 0}
        return {
            "total":      len(self._df),
            "aplican":    int(self._df["aplica"].sum()),
            "no_aplican": int((~self._df["aplica"]).sum()),
        }
