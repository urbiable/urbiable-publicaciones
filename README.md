# URBIABLE · publicaciones automáticas

Cola de publicaciones de [@urbiable](https://www.instagram.com/urbiable/).

- `imagenes/` — imágenes JPEG, servidas por GitHub Pages.
- `cola/` — una ficha `.json` por publicación programada (fecha, imágenes, texto).
- `publicadas/` — fichas ya publicadas, con su enlace.
- `publicar.py` — el publicador; lo ejecuta cada hora `.github/workflows/publicar.yml`.

El token de Instagram vive en el secreto `IG_TOKEN` del repositorio.
