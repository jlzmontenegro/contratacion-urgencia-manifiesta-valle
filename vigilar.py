# -*- coding: utf-8 -*-
"""Avisa cuando el monitor lleva demasiado tiempo sin recolectar.

POR QUE EXISTE. El 14-sep-2026 el usuario dijo que no le llegaban los correos.
El correo estaba bien: no habia nada que avisar. Lo que habia pasado es que
GitHub retraso la recoleccion de las 20:30 cinco horas y se salto la de las 8:30
entera. Y una corrida que NO OCURRE es invisible: no falla nada, no sale nada en
rojo en Actions, simplemente no existe. El tablero seguia en pie mostrando datos
de la noche anterior, que es justo la forma mas silenciosa de estar roto.

POR QUE ES UN FLUJO APARTE. Si el vigilante viviera dentro de actualizar.yml, el
dia que ese flujo no corra tampoco correria el vigilante: no puede avisar de su
propia ausencia quien depende de ella. Van con cadencias distintas para que haga
falta que fallen dos cosas a la vez, no una.

NO RECOLECTA NI PUBLICA NADA. Solo lee la marca de tiempo de datos/tablero.json
y compara. Si el umbral no se pasa, no hace nada y no escribe nada.
"""

import io
import json
import os
import sys
from datetime import datetime, timedelta

import correo

BASE = os.path.dirname(os.path.abspath(__file__))
DIR_DATOS = os.path.join(BASE, "datos")
RUTA_TABLERO = os.path.join(DIR_DATOS, "tablero.json")
RUTA_BITACORA = os.path.join(DIR_DATOS, "vigilancia.csv")

# Con tres recolecciones -6:07, 13:07 y 20:07- el hueco mayor es de diez horas,
# de la noche a la manana. Catorce deja cuatro de margen para un retraso normal
# de GitHub sin gritar por nada, y salta cuando de verdad se salto una corrida.
UMBRAL_HORAS = 14

# Cada cuanto se puede repetir el aviso. Sin esto, una caida de dos dias serian
# dieciseis correos identicos: el primero informa y los quince siguientes solo
# entrenan a ignorarlos.
REPETIR_CADA_HORAS = 12


def leer_generado():
    """Marca de tiempo de la ultima recoleccion, en hora de Colombia.

    El colector la escribe con TZ=America/Bogota, y este flujo corre con la
    misma zona: se comparan dos horas locales, no una local contra una UTC.
    """
    if not os.path.exists(RUTA_TABLERO):
        return None
    with io.open(RUTA_TABLERO, encoding="utf-8") as fh:
        datos = json.load(fh)
    crudo = (datos.get("generado") or "").strip()
    for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(crudo, formato)
        except ValueError:
            continue
    return None


def ultimo_aviso():
    if not os.path.exists(RUTA_BITACORA):
        return None
    ultima = None
    with io.open(RUTA_BITACORA, encoding="utf-8") as fh:
        for linea in fh:
            partes = linea.strip().split(",")
            if len(partes) >= 2 and partes[0] != "fecha_aviso":
                try:
                    ultima = datetime.strptime(partes[0], "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass
    return ultima


def anotar(ahora, horas):
    existe = os.path.exists(RUTA_BITACORA)
    os.makedirs(DIR_DATOS, exist_ok=True)
    with io.open(RUTA_BITACORA, "a", encoding="utf-8", newline="") as fh:
        if not existe:
            fh.write("fecha_aviso,horas_sin_recoleccion\n")
        fh.write(f"{ahora:%Y-%m-%d %H:%M:%S},{horas:.1f}\n")


def cuerpo(generado, horas):
    esc = correo.esc
    acciones = (
        "https://github.com/jlzmontenegro/contratacion-urgencia-manifiesta-valle"
        "/actions/workflows/actualizar.yml")
    html = (
        '<div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;'
        'background:#F5F7F6;padding:22px;color:#16211F">'
        '<div style="max-width:620px;margin:0 auto">'
        '<div style="border:1px solid #E0C070;background:#FFF9EC;padding:18px 20px;'
        'border-radius:3px">'
        '<h1 style="font-size:18px;margin:0 0 8px;color:#5C4708">'
        f'El monitor lleva {horas:.0f} horas sin recolectar</h1>'
        f'<p style="font-size:14px;line-height:1.55;margin:0 0 10px">La última '
        f'recolección fue el <b>{esc(generado)}</b>. Deberían entrar tres al día, '
        'a las 6:07, 13:07 y 20:07.</p>'
        '<p style="font-size:14px;line-height:1.55;margin:0 0 10px">'
        '<b>El tablero no está caído</b>: sigue en pie mostrando los últimos datos '
        'buenos, con su fecha a la vista. Lo que falta es la actualización, así que '
        'una contratación nueva del sismo podría llevar horas sin aparecer y sin '
        'que salga su aviso.</p>'
        '<p style="font-size:14px;line-height:1.55;margin:0 0 14px">Lo más probable '
        'es que GitHub haya retrasado o saltado la ejecución programada, que es lo '
        'que pasó el 14 de septiembre. Se arregla lanzando el flujo a mano.</p>'
        f'<a href="{acciones}" style="display:inline-block;background:#0E5C58;'
        'color:#fff;text-decoration:none;padding:8px 15px;border-radius:3px;'
        'font-size:13px;font-weight:600">Abrir Actions y lanzar la recolección</a>'
        '</div>'
        '<p style="font-size:11.5px;color:#6B807C;line-height:1.5;margin-top:16px">'
        f'Este aviso se manda como máximo una vez cada {REPETIR_CADA_HORAS} horas '
        'mientras dure la situación. Si la recolección vuelve sola, no se manda '
        'nada más.</p>'
        "</div></div>")
    texto = (
        f"El monitor lleva {horas:.0f} horas sin recolectar.\n\n"
        f"Ultima recoleccion: {generado}\n"
        "Deberian entrar tres al dia: 6:07, 13:07 y 20:07.\n\n"
        "El tablero no esta caido: muestra los ultimos datos buenos con su fecha. "
        "Lo que falta es la actualizacion.\n\n"
        f"Lanzar a mano: {acciones}\n")
    return html, texto


def main():
    ahora = datetime.now()
    generado = leer_generado()
    if generado is None:
        print("  ! no se pudo leer la marca de tiempo de datos/tablero.json")
        return 1

    horas = (ahora - generado).total_seconds() / 3600.0
    print(f"  ultima recoleccion: {generado:%Y-%m-%d %H:%M:%S} "
          f"({horas:.1f} horas)")

    if horas < UMBRAL_HORAS:
        print(f"  al dia (umbral {UMBRAL_HORAS} h). No se hace nada.")
        return 0

    previo = ultimo_aviso()
    if previo and (ahora - previo) < timedelta(hours=REPETIR_CADA_HORAS):
        falta = REPETIR_CADA_HORAS - (ahora - previo).total_seconds() / 3600.0
        print(f"  ya se aviso el {previo:%Y-%m-%d %H:%M}; "
              f"no se repite hasta dentro de {falta:.1f} h.")
        return 0

    with io.open(os.path.join(BASE, "config.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)
    destinos = cfg.get("correo", {})
    # 'para_alertas' si existe; si no, quien revisa. Es un aviso de operacion, no
    # contenido: va a quien puede lanzar el flujo, no a todo el equipo.
    para = [d for d in (destinos.get("para_alertas")
                        or destinos.get("para_revision") or []) if d and "@" in d]
    if not para:
        print("  ! no hay destinatarios para el aviso de vigilancia.")
        return 1

    html, texto = cuerpo(f"{generado:%Y-%m-%d %H:%M:%S}", horas)
    asunto = f"[MONITOR] {horas:.0f} horas sin recolectar · sismo 10-ago"
    try:
        enviado = correo.enviar(asunto, para, html, texto)
    except Exception as e:
        print(f"  ! fallo el envio del aviso: {e}")
        return 1

    # Solo se anota si SALIO. Un aviso que no se mando no puede darse por dado:
    # es la misma regla de correo.py, y aqui importa mas todavia, porque anotarlo
    # en falso dejaria doce horas de silencio justo durante una caida.
    if enviado:
        anotar(ahora, horas)
        print(f"  aviso enviado a {', '.join(para)} ({horas:.1f} horas)")
        # Anotacion de Actions: se ve en la pestana sin abrir el registro, y no
        # pone el flujo en rojo -esto no es un fallo del vigilante-.
        print(f"::warning::El monitor lleva {horas:.0f} horas sin recolectar "
              f"(ultima: {generado:%Y-%m-%d %H:%M})")
    else:
        print("  ! no se pudo enviar; no se anota y se reintenta en la proxima.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
