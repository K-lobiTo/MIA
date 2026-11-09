"""SOLO DESARROLLO: motor de grabación de los videos de la guía de uso.

Maneja un navegador con Playwright, graba el video de la pantalla, dibuja un cursor y el resaltado del clic (el video de un
navegador sin ventana no los trae) y guarda los subtítulos como pistas con tiempos, sin quemarlos en la imagen: los dibuja el
reproductor de Artifact. Cada guion (`guiones/*.py`) es una función `guion(g)` que usa esta clase.

Cada video produce `<nombre>.mp4` y `<nombre>.json` (título, duración y pistas de subtítulos).
"""

import contextlib
import json
import shutil
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Self

from playwright.sync_api import Locator, Page, Route, sync_playwright

VIEWPORT = {"width": 1280, "height": 720}
CARACTERES_POR_SEGUNDO = 17  # velocidad de lectura de un subtítulo
MINIMO_SUBTITULO = 2.0

# Cursor y resaltado del clic, dibujados en la propia página (sigue el movimiento real del ratón de Playwright).
JS_CURSOR = """
(() => {
  const montar = () => {
    if (document.getElementById('demo-cursor')) return;
    const css = document.createElement('style');
    css.textContent = `
      #demo-cursor{position:fixed;z-index:2147483647;left:0;top:0;width:22px;height:22px;pointer-events:none;
        transform:translate(-3px,-2px);transition:none;filter:drop-shadow(0 1px 2px rgba(0,0,0,.45))}
      .demo-onda{position:fixed;z-index:2147483646;width:14px;height:14px;margin:-7px 0 0 -7px;border-radius:50%;
        border:3px solid #EE6C4D;pointer-events:none;animation:demo-onda .55s ease-out forwards}
      @keyframes demo-onda{to{transform:scale(3.2);opacity:0}}`;
    document.head.appendChild(css);
    const c = document.createElement('div');
    c.id = 'demo-cursor';
    c.innerHTML = '<svg viewBox="0 0 22 22" width="22" height="22"><path d="M3 2 L3 17 L7 13.5 L10 20 L12.6 18.8 L9.7 12.6 L15 12.2 Z" fill="#fff" stroke="#111" stroke-width="1.4" stroke-linejoin="round"/></svg>';
    document.documentElement.appendChild(c);
    addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
    addEventListener('mousedown', e => {
      const o = document.createElement('div');
      o.className = 'demo-onda'; o.style.left = e.clientX + 'px'; o.style.top = e.clientY + 'px';
      document.documentElement.appendChild(o); setTimeout(() => o.remove(), 700);
    }, true);
  };
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', montar); else montar();
})();
"""


class Grabacion:
    def __init__(self, nombre: str, titulo: str, salida: Path, url: str, *, storage: dict | None = None, tema: str = "light", ignorar_https: bool = False):
        self.nombre, self.titulo, self.salida, self.url = nombre, titulo, Path(salida), url
        self.storage = storage or {}
        self.tema = tema
        self.ignorar_https = ignorar_https
        self.pistas: list[dict] = []
        self._t0 = 0.0
        self._pos = (VIEWPORT["width"] // 2, VIEWPORT["height"] // 2)

    # --- ciclo de vida -------------------------------------------------------------------------------------------
    def __enter__(self) -> Self:
        self._tmp = Path(tempfile.mkdtemp(prefix="demo-video-"))
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True, args=["--force-device-scale-factor=1"])
        self._ctx = self._browser.new_context(
            viewport=VIEWPORT,
            record_video_dir=str(self._tmp),
            record_video_size=VIEWPORT,
            locale="es-CR",
            timezone_id="America/Costa_Rica",
            color_scheme=self.tema,
            ignore_https_errors=self.ignorar_https,
            permissions=["clipboard-read", "clipboard-write"],  # para que el botón de copiar funcione
        )
        # Estado del navegador previo (p. ej. la clave recordada): se escribe una vez, antes de que cargue la página.
        if self.storage:
            self._ctx.add_init_script(
                "(() => { try { if (!sessionStorage.getItem('__demo_init')) { sessionStorage.setItem('__demo_init', '1');"
                + "".join(f" localStorage.setItem({json.dumps(k)}, {json.dumps(v)});" for k, v in self.storage.items())
                + " } } catch (e) {} })();"
            )
        self._ctx.add_init_script(JS_CURSOR)
        self.page: Page = self._ctx.new_page()
        self._t0 = time.monotonic()
        self.page.goto(self.url)
        return self

    def __exit__(self, tipo, valor, traza) -> None:
        duracion = self.ahora()
        if tipo is not None:  # una captura del momento del fallo ayuda a corregir el guion
            with contextlib.suppress(Exception):
                self.page.screenshot(path=str(Path(tempfile.gettempdir()) / f"demo-fallo-{self.nombre}.png"))
        origen = Path(self.page.video.path())
        self._ctx.close()  # cierra y termina de escribir el video
        self._browser.close()
        self._pw.stop()
        if tipo is not None:
            shutil.rmtree(self._tmp, ignore_errors=True)
            return
        self.salida.mkdir(parents=True, exist_ok=True)
        destino = self.salida / f"{self.nombre}.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(origen), "-c:v", "libx264", "-preset", "slow", "-crf", "26",
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(destino)],
            check=True,
        )
        (self.salida / f"{self.nombre}.json").write_text(
            json.dumps({"id": self.nombre, "titulo": self.titulo, "duracion": round(duracion, 2), "pistas": self.pistas}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        shutil.rmtree(self._tmp, ignore_errors=True)
        print(f"{self.nombre}: {duracion:.1f} s, {len(self.pistas)} subtítulos -> {destino}")

    def ahora(self) -> float:
        return time.monotonic() - self._t0

    # --- subtítulos ----------------------------------------------------------------------------------------------
    @contextmanager
    def sub(self, texto: str, minimo: float | None = None):
        """Muestra un subtítulo mientras dura lo que se haga dentro del bloque (y lo suficiente para leerlo)."""
        inicio = self.ahora()
        yield
        leer = max(MINIMO_SUBTITULO, len(texto) / CARACTERES_POR_SEGUNDO) if minimo is None else minimo
        falta = inicio + leer - self.ahora()
        if falta > 0:
            time.sleep(falta)
        self.pistas.append({"inicio": round(inicio, 2), "fin": round(self.ahora(), 2), "texto": texto})

    def pausa(self, segundos: float) -> None:
        time.sleep(segundos)

    # --- acciones con ratón y teclado visibles --------------------------------------------------------------------
    def _centro(self, objetivo: Locator) -> tuple[float, float]:
        objetivo.scroll_into_view_if_needed()
        caja = objetivo.bounding_box()
        if caja is None:
            raise RuntimeError("elemento sin caja visible")
        return caja["x"] + caja["width"] / 2, caja["y"] + caja["height"] / 2

    def mover(self, objetivo: Locator, pasos: int = 28) -> None:
        x, y = self._centro(objetivo)
        self.page.mouse.move(x, y, steps=pasos)
        self._pos = (x, y)
        time.sleep(0.25)

    def clic(self, objetivo: Locator) -> None:
        self.mover(objetivo)
        self.page.mouse.click(*self._pos)
        time.sleep(0.5)

    def escribir(self, objetivo: Locator, texto: str, retardo_ms: int = 42) -> None:
        self.clic(objetivo)
        self.page.keyboard.type(texto, delay=retardo_ms)
        time.sleep(0.4)

    def tecla(self, tecla: str) -> None:
        self.page.keyboard.press(tecla)
        time.sleep(0.4)

    # --- API simulada ---------------------------------------------------------------------------------------------
    def simular(self, patron: str, manejador) -> None:
        """Intercepta las peticiones que coinciden con el patrón (p. ej. `**/api/query`): `manejador(route, request)`."""
        self.page.route(patron, manejador)

    def retener_consultas(self, patron: str) -> None:
        """Retiene las peticiones al patrón hasta que el guion las responda con `responder_consulta` (así el guion
        decide cuánto se ve la pantalla de "Buscando..."). Un manejador que durmiera bloquearía al propio guion."""
        self._pendientes: list = []
        self._contador = 0
        self.page.route(patron, lambda route, request: self._pendientes.append((route, request)))

    def responder_consulta(self, contenido) -> None:
        """Espera la próxima petición retenida y la responde con `contenido(cuerpo, n) -> (demora_s, respuesta)`."""
        while not self._pendientes:
            self.page.wait_for_timeout(50)
        route, request = self._pendientes.pop(0)
        self._contador += 1
        demora, cuerpo = contenido(json.loads(request.post_data or "{}"), self._contador)
        self.page.wait_for_timeout(int(demora * 1000))
        responder_json(route, cuerpo)


def responder_json(route: Route, cuerpo: dict | list, estado: int = 200) -> None:
    route.fulfill(status=estado, content_type="application/json", body=json.dumps(cuerpo, ensure_ascii=False))
