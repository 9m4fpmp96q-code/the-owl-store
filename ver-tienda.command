#!/bin/bash
# Abre OWL Store en el navegador. Doble clic y ya.
#
# Si el servidor ya está en marcha lo reutiliza; si no, lo arranca y espera
# a que responda antes de abrir el navegador, para no enseñar una pestaña
# de error durante dos segundos.

cd "$(dirname "$0")" || exit 1
PUERTO=5003
URL="http://localhost:$PUERTO"

responde() { curl -s -o /dev/null --max-time 1 "$URL/"; }

if responde; then
  echo "La tienda ya estaba abierta."
else
  echo "Arrancando la tienda..."
  python3 server.py > /tmp/owl-store.log 2>&1 &
  for _ in $(seq 1 25); do
    sleep 0.4
    responde && break
  done
fi

if responde; then
  open "$URL"
  echo "Abierta en $URL"
  echo "Para pararla, cierra esta ventana."
else
  echo "No ha arrancado. Mira el error:"
  tail -20 /tmp/owl-store.log
  read -r -p "Pulsa Intro para cerrar."
fi
