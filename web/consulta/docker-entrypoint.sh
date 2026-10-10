#!/bin/sh
# Escribe la configuración de la instancia a partir de las variables de entorno del servicio y sirve el sitio.
# ARTIFACT_KEY (opcional): clave de artefacto fija; con ella la Consulta no pide la clave. Se lee al arrancar,
# así que cambiarla solo exige reiniciar el servicio, sin volver a compilar. OJO: /config.js es público.
set -e
node -e 'require("fs").writeFileSync("dist/config.js", "window.MIA_CONFIG = " + JSON.stringify({ artifactKey: process.env.ARTIFACT_KEY || "" }) + ";\n")'
exec serve -s dist -l "${PORT:-3000}"
