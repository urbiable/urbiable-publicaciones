"""Renueva el token de Instagram (Instagram API with Instagram Login) para que no caduque nunca.

El token de larga duración dura 60 días y se puede renovar mientras siga vigente
(y tenga más de 24 horas). Este script lo renueva cada semana desde GitHub Actions:
así siempre le quedan unos 60 días y, en la práctica, es permanente.

- Nunca imprime el token: solo los días de vigencia y si ha cambiado.
- Si Instagram devuelve un token distinto, lo guarda en GITHUB_OUTPUT para que el
  workflow actualice el secreto IG_TOKEN (necesita el secreto GH_PAT).
- Si la renovación falla, sale con error: GitHub avisa por email.
"""
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

URL = "https://graph.instagram.com/refresh_access_token"


def main() -> int:
    viejo = os.environ.get("IG_TOKEN", "").strip()
    if not viejo:
        print("ERROR: falta el secreto IG_TOKEN.")
        return 1
    url = URL + "?" + urllib.parse.urlencode({"grant_type": "ig_refresh_token", "access_token": viejo})
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            datos = json.load(r)
    except urllib.error.HTTPError as e:
        cuerpo = json.loads(e.read() or b"{}")
        print("ERROR al renovar:", cuerpo.get("error", {}).get("message", cuerpo))
        return 1
    nuevo = datos.get("access_token", "")
    dias = round(int(datos.get("expires_in", 0)) / 86400)
    if not nuevo:
        print("ERROR: Instagram no ha devuelto token.")
        return 1
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::add-mask::{nuevo}")  # GitHub oculta este valor en todos los registros
    cambia = hashlib.sha256(nuevo.encode()).hexdigest() != hashlib.sha256(viejo.encode()).hexdigest()
    print(f"Token renovado: vigente {dias} días más. ¿Token distinto?: {'sí' if cambia else 'no'}")
    salida = os.environ.get("GITHUB_OUTPUT")
    if salida:
        with open(salida, "a", encoding="utf-8") as f:
            f.write(f"cambia={'si' if cambia else 'no'}\n")
            if cambia:
                f.write(f"nuevo={nuevo}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
