"""
validador.py — Motor de validacion (version corregida y estable)
"""

from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import pandas as pd
import urllib.request, io, json, base64, time

CSV_DECISIONES = Path(__file__).parent / "decisiones_back.csv"
CSV_TITULOS    = Path(__file__).parent / "titulos.csv"

def _norm(texto: str) -> str:
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()

SEMESTRE_POR_NIVEL = {
    "doctorado": 8, "maestria": 7, "especializacion": 6,
    "universitario": 5, "tecnologo": 3, "tecnico": 2, "bachillerato": 1,
}

@dataclass
class Resultado:
    aplica: bool
    nivel: Optional[str]
    semestre: Optional[int]
    confianza: float
    requiere_revision: bool
    metodo: str
    match: Optional[str] = None
    razon: str = ""

    @property
    def confianza_pct(self) -> int:
        return round(self.confianza * 100)

def github_read(token: str, repo: str, filename: str) -> pd.DataFrame:
    if token and repo:
        try:
            url = f"https://raw.githubusercontent.com/{repo}/main/{filename}"
            req = urllib.request.Request(url, headers={"Authorization": f"token {token}"})
            with urllib.request.urlopen(req) as r:
                raw = r.read().decode("utf-8", "replace")
            return pd.read_csv(io.StringIO(raw))
        except Exception:
            pass
    if CSV_DECISIONES.exists():
        return pd.read_csv(CSV_DECISIONES)
    return pd.DataFrame()

def github_write(token: str, repo: str, filename: str, df: pd.DataFrame):
    if not (token and repo):
        df.to_csv(CSV_DECISIONES, index=False)
        return
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    content = csv_buffer.getvalue()
    url = f"https://api.github.com/repos/{repo}/contents/{filename}"
    headers = {"Authorization": f"token {token}", "Content-Type": "application/json"}
    try:
        request = urllib.request.Request(url, headers=headers)
        response = urllib.request.urlopen(request)
        sha = json.loads(response.read())["sha"]
    except Exception:
        sha = None
    body = {"message": f"Actualizacion {filename}",
            "content": base64.b64encode(content.encode()).decode()}
    if sha:
        body["sha"] = sha
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="PUT", headers=headers)
    urllib.request.urlopen(request)
    time.sleep(1.5)

class ValidadorCSV:

    def __init__(self, token="", repo=""):
        self.token = token
        self.repo = repo
        self._df = pd.DataFrame()
        self.recargar()

    def recargar(self):
        df = github_read(self.token, self.repo, "decisiones_back.csv")
        if df.empty:
            self._df = pd.DataFrame()
            return
        df["_norm"] = df["nombre_titulo"].astype(str).apply(_norm)
        df["aplica"] = df["decision_aplica"].astype(str).str.lower().isin(["true", "1", "si"])
        self._df = df

    def validar(self, titulo: str) -> Resultado:
        tn = _norm(titulo)
        if self._df.empty:
            return Resultado(False, None, None, 0, True, "vacio", razon="Base vacia")
        fila = self._df[self._df["_norm"] == tn]
        if not fila.empty:
            row = fila.iloc[-1]
            nivel = str(row["nivel_confirmado"])
            motivo_back = str(row.get("motivo", "")).strip()
            revisor_back = str(row.get("revisor", "")).strip()
            razon_final = motivo_back if motivo_back and motivo_back.lower() not in ["nan","none",""] else "Encontrado en decisiones Back"
            if revisor_back and revisor_back.lower() not in ["nan","none",""]:
                razon_final = f"{razon_final} | Revisor: {revisor_back}"
            return Resultado(
                aplica=row["aplica"], nivel=nivel,
                semestre=SEMESTRE_POR_NIVEL.get(nivel),
                confianza=0.99, requiere_revision=False,
                metodo="back_exacto", match=row["nombre_titulo"],
                razon=razon_final)
        return Resultado(False, None, None, 0.0, True, "no_encontrado",
                         razon="No existe registro exacto en Back")

    def guardar_decision(self, titulo, universidad, pais, aplica,
                         nivel, revisor="", motivo="", incorporar=True):
        df = github_read(self.token, self.repo, "decisiones_back.csv")
        nueva_fila = {
            "fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "nombre_titulo": str(titulo).strip().upper(),
            "universidad": str(universidad).strip().upper() if universidad else "",
            "pais": pais, "decision_aplica": str(aplica).lower(),
            "nivel_confirmado": nivel, "semestre": SEMESTRE_POR_NIVEL.get(nivel, ""),
            "revisor": str(revisor).strip(), "motivo": str(motivo).strip(),
        }
        if not df.empty and "nombre_titulo" in df.columns:
            df = df[df["nombre_titulo"].astype(str).str.strip().str.upper()
                    != nueva_fila["nombre_titulo"]]
        df = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)
        df.to_csv(CSV_DECISIONES, index=False)
        github_write(self.token, self.repo, "decisiones_back.csv", df)
        self.recargar()

    def eliminar_decision(self, nombre_titulo: str) -> bool:
        df = github_read(self.token, self.repo, "decisiones_back.csv")
        if df.empty:
            return False
        nombre_up = str(nombre_titulo).strip().upper()
        df_nuevo = df[df["nombre_titulo"].astype(str).str.strip().str.upper()
                      != nombre_up].reset_index(drop=True)
        if len(df_nuevo) == len(df):
            return False
        df_nuevo.to_csv(CSV_DECISIONES, index=False)
        github_write(self.token, self.repo, "decisiones_back.csv", df_nuevo)
        self.recargar()
        return True

    def editar_decision(self, titulo_original: str, nuevos_datos: dict) -> bool:
        df = github_read(self.token, self.repo, "decisiones_back.csv")
        if df.empty:
            return False
        mascara = (df["nombre_titulo"].astype(str).str.strip().str.upper()
                   == str(titulo_original).strip().upper())
        if not mascara.any():
            return False
        ix = df[mascara].index[0]
        for campo, valor in nuevos_datos.items():
            if campo in df.columns:
                df.at[ix, campo] = valor
        df.to_csv(CSV_DECISIONES, index=False)
        github_write(self.token, self.repo, "decisiones_back.csv", df)
        self.recargar()
        return True

    def stats(self):
        return {"total": len(self._df)}
