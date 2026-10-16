"""Publicador automático de URBIABLE en Instagram.

Cada ficha de cola/*.json describe una publicación:

    {
      "publicar_el": "2026-10-20T09:30:00+02:00",
      "imagenes": ["2026-10-20-lanzamiento-1.jpg", "2026-10-20-lanzamiento-2.jpg"],
      "texto": "Texto de la publicación con #hashtags",
      "primer_comentario": "opcional"
    }

Una imagen = publicación simple; varias (2-10) = carrusel. Las imágenes van en
imagenes/ (JPEG) y GitHub Pages las sirve en una URL pública.

Cuando llega la hora, se publica y la ficha pasa a publicadas/ con el enlace.

Variables de entorno:
    IG_TOKEN      token de larga duración (secreto de GitHub)
    PAGES_BASE    URL pública de la carpeta del repositorio en GitHub Pages
Opciones:
    --prueba      crea los contenedores en Instagram pero NO publica
    --todas       procesa toda la cola sin mirar la fecha (solo con --prueba)
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://graph.instagram.com/v23.0"
RAIZ = Path(__file__).parent
COLA, PUBLICADAS = RAIZ / "cola", RAIZ / "publicadas"
PAGES_BASE = os.environ.get("PAGES_BASE", "https://urbiable.github.io/urbiable-publicaciones").rstrip("/")


class ErrorInstagram(Exception):
    pass


def llamar(metodo: str, ruta: str, **params) -> dict:
    params["access_token"] = os.environ["IG_TOKEN"]
    url = f"{API}/{ruta}"
    datos = urllib.parse.urlencode(params).encode()
    if metodo == "GET":
        url, datos = f"{url}?{datos.decode()}", None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=datos, method=metodo), timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        cuerpo = json.loads(e.read() or b"{}")
        raise ErrorInstagram(cuerpo.get("error", {}).get("message", str(cuerpo))) from None


_ig_id = None


def ig_id() -> str:
    global _ig_id
    if _ig_id is None:
        _ig_id = llamar("GET", "me", fields="user_id")["user_id"]
    return _ig_id


def url_publica(nombre: str) -> str:
    url = f"{PAGES_BASE}/imagenes/{urllib.parse.quote(nombre)}"
    try:
        urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30)
    except urllib.error.URLError as e:
        raise ErrorInstagram(f"La imagen aún no es pública ({url}): {e}") from None
    return url


def esperar_listo(contenedor: str) -> None:
    for _ in range(30):
        estado = llamar("GET", contenedor, fields="status_code").get("status_code")
        if estado == "FINISHED":
            return
        if estado in ("ERROR", "EXPIRED"):
            raise ErrorInstagram(f"Instagram rechazó el contenedor {contenedor}: {estado}")
        time.sleep(5)
    raise ErrorInstagram(f"El contenedor {contenedor} no terminó de procesarse")


def crear_contenedor(ficha: dict) -> str:
    imagenes = ficha["imagenes"]
    if not 1 <= len(imagenes) <= 10:
        raise ErrorInstagram("Cada publicación necesita entre 1 y 10 imágenes")
    if len(imagenes) == 1:
        c = llamar("POST", f"{ig_id()}/media", image_url=url_publica(imagenes[0]), caption=ficha["texto"])["id"]
    else:
        hijos = []
        for nombre in imagenes:
            h = llamar("POST", f"{ig_id()}/media", image_url=url_publica(nombre), is_carousel_item="true")["id"]
            esperar_listo(h)
            hijos.append(h)
        c = llamar("POST", f"{ig_id()}/media", media_type="CAROUSEL", children=",".join(hijos), caption=ficha["texto"])["id"]
    esperar_listo(c)
    return c


def toca(ficha: dict, ahora: datetime) -> bool:
    return datetime.fromisoformat(ficha["publicar_el"]) <= ahora


def main() -> int:
    prueba, todas = "--prueba" in sys.argv, "--todas" in sys.argv
    if todas and not prueba:
        sys.exit("--todas solo se permite junto a --prueba")
    ahora = datetime.now(timezone.utc)
    fallos = 0
    for ruta in sorted(COLA.glob("*.json")):
        ficha = json.loads(ruta.read_text(encoding="utf-8"))
        if not (todas or toca(ficha, ahora)):
            continue
        try:
            contenedor = crear_contenedor(ficha)
            if prueba:
                print(f"[PRUEBA OK] {ruta.name}: contenedor {contenedor} listo, no se publica")
                continue
            media = llamar("POST", f"{ig_id()}/media_publish", creation_id=contenedor)["id"]
            enlace = llamar("GET", media, fields="permalink").get("permalink")
            if ficha.get("primer_comentario"):
                llamar("POST", f"{media}/comments", message=ficha["primer_comentario"])
            ficha.update(estado="publicada", media_id=media, enlace=enlace, publicada_el=ahora.isoformat())
            (PUBLICADAS / ruta.name).write_text(json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8")
            ruta.unlink()
            print(f"[PUBLICADA] {ruta.name}: {enlace}")
        except ErrorInstagram as e:
            fallos += 1
            print(f"[ERROR] {ruta.name}: {e}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
