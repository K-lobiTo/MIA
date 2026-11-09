# Videos de la guía de uso

Videos cortos, con subtítulos y sin voz, que recorren la Consulta, el panel y el bot de WhatsApp con datos de ejemplo. Se publican en un solo Artifact («Guía de uso de MIA») que sirve de índice por rol y de reproductor. Decisiones y catálogo: ver el plan en la conversación del 2026-11-09 (memoria `mia_videos_demo_artifact`).

## Cómo funciona

1. **Datos ficticios** (`scripts/demos/servidor_demo.py`): la API y el Microsoft simulado de `scripts/idp_simulado.py`, con programas, dominios, documentos, artefactos con claves conocidas (`mia_demo_computacion`, `mia_demo_analitica`), usuarios de la Consulta (`estudiante.demo` / `ClaveDemo2026`), un bot y 120 consultas de los últimos 30 días. No usa Qdrant ni el modelo de embeddings, y los documentos subidos pasan de en cola a listo por simulación.
2. **Grabación** (`scripts/demos/grabar.py`, `grabador.py`, `guiones/*.py`): Playwright maneja un navegador real contra los sitios en desarrollo, dibuja el cursor y el clic, y graba `docs/demos/clips/<id>.mp4` más `<id>.json` con los subtítulos y sus tiempos (los subtítulos no se queman en la imagen). Las respuestas del modelo las pone el guion (`g.retener_consultas` y `g.responder_consulta`): la interfaz y el resto de la API son reales y no se gasta saldo.
3. **Reproductor** (`docs/demos/player/index.html` y `catalogo.json`): una sola página con el índice, los subtítulos sincronizados, la lista de pasos que salta al momento del video, velocidad y pantalla completa.

## Regenerar un video

```bash
# 1. Entorno de grabación (aparte del de MIA; el servidor de datos sí usa el de MIA)
python3 -m venv .venv-demos && .venv-demos/bin/pip install -r scripts/demos/requirements.txt
.venv-demos/bin/playwright install chromium            # y ffmpeg instalado en el sistema

# 2. Servidores (tres terminales, desde la raíz)
python scripts/demos/servidor_demo.py                  # API :8000 y Microsoft simulado :9000
cd web/consulta && npm run dev                         # :3000
cd web/admin && VITE_ENTRA_CLIENT_ID=cliente-de-prueba \
  VITE_ENTRA_AUTHORITY=https://localhost:9000/1119bb90-88ba-4894-b7f1-de26e129d977 npm run dev   # :3001

# 3. Grabar
.venv-demos/bin/python scripts/demos/grabar.py --lista
.venv-demos/bin/python scripts/demos/grabar.py a3-preguntar
```

Luego se publica el Artifact con el mismo `index.html`, `catalogo.json` y la carpeta `clips/` (mp4 y json). Los mp4 no se versionan en git: se regeneran con el guion. En `catalogo.json` se marca `"listo": true` cuando el video ya está publicado.

## Escribir un guion nuevo

Un guion es `scripts/demos/guiones/<id>.py` con `ID`, `TITULO`, `URL`, `STORAGE` (por ejemplo la clave ya recordada) y `guion(g)`. Cada paso va dentro de `with g.sub("subtítulo"):` y usa `g.clic`, `g.escribir`, `g.tecla`, `g.pausa`. Reglas:

- Cada paso del guion debe existir en la interfaz actual: leer el componente antes de escribirlo (los textos y las condiciones, por ejemplo qué aparece solo con sesión o con más de un modo).
- Subtítulos en tú, sin guion largo, de una o dos líneas, y solo con lo que la pantalla muestra.
- Solo datos de ejemplo: nada de actas ni documentos reales.
- Si una espera no aporta (procesar un documento, una respuesta lenta), se simula con una demora corta y no se espera de verdad.
