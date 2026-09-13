# -*- coding: utf-8 -*-
"""Avisa por correo de lo que aparecio en la ultima recoleccion.

Manda dos correos distintos porque son dos decisiones distintas:

  1. RELACIONADO ('Alta'): contratacion que ya esta dada por atencion del sismo.
     Va al equipo. Trae lo que hace falta para verificarla sin abrir el tablero:
     entidad, numero de contrato o de proceso, proveedor, valor, objeto completo,
     fecha de firma, fechas de inicio y fin, y el enlace a SECOP.

  2. POR REVISAR ('Media'): contratacion que el clasificador no puede juzgar solo
     y que puede o no tener que ver con el sismo. Va unicamente a quien revisa.
     Mezclar las dos en un mismo correo seria el peor resultado posible: lo dudoso
     acabaria leyendose como confirmado.

No se avisa dos veces del mismo registro. La bitacora es datos/avisados.csv y se
escribe ANTES del paso que publica, de modo que viaja en el mismo commit que los
datos: si se escribiera despues, una segunda corrida del mismo dia la encontraria
vacia y repetiria todos los avisos. Y en la primera corrida no se manda nada: se
siembra la bitacora con lo que ya existe, porque si no el estreno serian
quinientos correos de contratacion de hace un mes.

Uso:
    py -3 correo.py            # manda lo que haya
    py -3 correo.py --probar   # no manda nada; escribe los correos en disco
"""

import argparse
import csv
import json
import os
import smtplib
import ssl
import sys
from datetime import datetime
from email.message import EmailMessage

BASE = os.path.dirname(os.path.abspath(__file__))
DIR_DATOS = os.path.join(BASE, "datos")
RUTA_AVISADOS = os.path.join(DIR_DATOS, "avisados.csv")
TABLERO = "https://jlzmontenegro.github.io/contratacion-urgencia-manifiesta-valle/"

# Cuantas fichas completas caben en un correo. Por encima, el correo se vuelve
# ilegible y algunos clientes lo recortan sin avisar (Gmail lo hace pasados los
# 102 KB, y el recorte se lleva justo el final). El resto se resume y se remite
# al tablero.
TOPE_FICHAS = 25

AVISOS = {
    "relacionado": {
        "nivel": "Alta",
        "para": "para_relacionados",
        "uno": "contratación nueva relacionada con el sismo",
        "varias": "contrataciones nuevas relacionadas con el sismo",
        "entrada": ("Esto es contratación que ya está dada por atención del sismo del "
                    "10 de agosto de 2026."),
    },
    "revision": {
        "nivel": "Media",
        "para": "para_revision",
        "uno": "contratación nueva por revisar",
        "varias": "contrataciones nuevas por revisar",
        "entrada": ("Esto <b>no</b> está confirmado como del sismo. Son contrataciones "
                    "que el clasificador no puede juzgar solo y que hay que leer para "
                    "decidir si tienen que ver con la emergencia."),
    },
}


def rotulo(clave, n, nuevas=True):
    """Titular del correo. `nuevas=False` en el envio de prueba: decir "8
    contrataciones NUEVAS" encima de un aviso que explica que no lo son es
    contradecirse dentro del mismo correo."""
    c = AVISOS[clave]
    s = c["uno"] if n == 1 else c["varias"]
    if not nuevas:
        s = s.replace("nuevas ", "").replace("nueva ", "")
    return "%d %s" % (n, s)


# --------------------------------------------------------------------------
# Bitacora de lo ya avisado
# --------------------------------------------------------------------------

def leer_avisados():
    """Pares (identificador, aviso) de los que ya salio un correo."""
    if not os.path.exists(RUTA_AVISADOS):
        return None                      # None = nunca se ha avisado nada
    vistos = set()
    with open(RUTA_AVISADOS, encoding="utf-8", newline="") as fh:
        for fila in csv.DictReader(fh):
            vistos.add((fila.get("identificador", ""), fila.get("aviso", "")))
    return vistos


def anotar_avisados(nuevos):
    """Agrega al final; nunca reescribe. La bitacora es historia, no estado."""
    existe = os.path.exists(RUTA_AVISADOS)
    os.makedirs(DIR_DATOS, exist_ok=True)
    sello = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(RUTA_AVISADOS, "a", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        if not existe:
            w.writerow(["identificador", "aviso", "fecha_envio", "entidad", "valor"])
        for ident, aviso, entidad, valor in nuevos:
            w.writerow([ident, aviso, sello, entidad, valor])


# --------------------------------------------------------------------------
# Redaccion
# --------------------------------------------------------------------------

def pesos(v):
    try:
        return "$ {:,.0f}".format(float(v or 0)).replace(",", ".")
    except (TypeError, ValueError):
        return "$ 0"


def esc(s):
    return (str(s if s is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def ficha(r):
    """Una contratacion, en HTML. Tabla y estilos en linea: los clientes de correo
    no leen hojas de estilo externas y la mitad ignora incluso el <style> del
    documento."""
    campos = []

    def linea(etiqueta, valor, mono=False):
        if not valor:
            return
        estilo = ("font-family:Consolas,monospace;" if mono else "")
        campos.append(
            '<tr><td style="padding:3px 10px 3px 0;color:#6B807C;font-size:12px;'
            'white-space:nowrap;vertical-align:top">' + esc(etiqueta) + "</td>"
            '<td style="padding:3px 0;font-size:13px;color:#16211F;' + estilo + '">'
            + esc(valor) + "</td></tr>")

    linea("Entidad", r.get("entidad"))
    linea("N.º " + ("contrato" if r.get("tipo") == "Contrato" else "proceso"),
          r.get("referencia"), mono=True)
    linea("Contratista", r.get("proveedor") or "aún sin contratista")
    linea("Valor", pesos(r.get("valor")) +
          ("  (valor firmado)" if r.get("tipo") == "Contrato" else "  (precio base)"))
    linea(r.get("etiqueta_fecha") or "Fecha", r.get("fecha"))
    linea("Inicio", r.get("fecha_inicio"))
    linea("Terminación", r.get("fecha_fin"))
    linea("Municipio", r.get("municipio_nombre"))
    linea("Modalidad", r.get("modalidad"))
    linea("Por qué entró", r.get("motivo"))

    boton = ""
    if r.get("url"):
        boton = ('<div style="margin-top:12px"><a href="' + esc(r["url"]) + '" '
                 'style="display:inline-block;background:#0E5C58;color:#ffffff;'
                 'text-decoration:none;padding:9px 16px;border-radius:3px;'
                 'font-size:13px;font-weight:600">Ver en '
                 + esc(r.get("plataforma") or "SECOP") + "</a></div>")

    return (
        '<div style="border:1px solid #D6DEDC;border-radius:3px;padding:14px;'
        'margin-bottom:14px;background:#ffffff">'
        '<div style="font-size:11px;letter-spacing:.08em;text-transform:uppercase;'
        'color:#6B807C;margin-bottom:8px">' + esc(r.get("tipo") or "") + " · "
        + esc(r.get("grupo") or "") + "</div>"
        '<div style="font-size:14px;line-height:1.5;color:#16211F;margin-bottom:12px">'
        + esc(r.get("objeto")) + "</div>"
        '<table cellpadding="0" cellspacing="0" style="border-collapse:collapse">'
        + "".join(campos) + "</table>" + boton + "</div>")


def cuerpo_html(clave, regs, generado, nuevas=True):
    cfg = AVISOS[clave]
    n = len(regs)
    total = sum(float(r.get("valor") or 0) for r in regs)
    mostradas = regs[:TOPE_FICHAS]
    resto = n - len(mostradas)

    pie_resto = ""
    if resto > 0:
        pie_resto = ('<p style="font-size:13px;color:#3D4F4C">Y <b>' + str(resto) +
                     "</b> más que no caben en este correo. Están todas en el "
                     '<a href="' + TABLERO + '" style="color:#0E5C58">tablero</a>.</p>')

    # Documento completo y con charset declarado. El MIME ya lo dice, pero hay
    # clientes -y previsualizadores- que abren el HTML por su cuenta y sin esta
    # linea leen el archivo en la codificacion del sistema: "contratación" sale
    # como "contrataciÃ³n" en todas las tildes.
    return (
        '<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>" + esc(rotulo(clave, n, nuevas)) + "</title></head><body style=\"margin:0\">"
        '<div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;'
        'background:#F5F7F6;padding:22px;color:#16211F">'
        '<div style="max-width:680px;margin:0 auto">'
        '<h1 style="font-size:18px;margin:0 0 6px;font-weight:600">'
        + esc(rotulo(clave, n, nuevas)) + "</h1>"
        '<p style="font-size:13px;line-height:1.55;color:#3D4F4C;margin:0 0 4px">'
        + cfg["entrada"] + "</p>"
        '<p style="font-family:Consolas,monospace;font-size:11.5px;color:#6B807C;'
        'margin:0 0 18px">Recolección del ' + esc(generado) + " · suman " + pesos(total)
        + "</p>"
        + "".join(ficha(r) for r in mostradas) + pie_resto +
        '<p style="font-size:12px;color:#6B807C;line-height:1.55;margin-top:22px;'
        'border-top:1px solid #D6DEDC;padding-top:12px">'
        'Monitor de contratación del sismo del 10 de agosto de 2026. '
        'Fuente: datos.gov.co (SECOP I, SECOP II, UNGRD y FNGRD). '
        'Este aviso sale solo cuando hay algo nuevo; de cada contratación se avisa '
        'una sola vez. <a href="' + TABLERO + '" style="color:#0E5C58">Ver el tablero'
        "</a>.</p></div></div></body></html>")


def cuerpo_texto(clave, regs, generado, nuevas=True):
    """Version en texto plano. No es un adorno: si el cliente no pinta HTML, sin
    esto el correo llega en blanco."""
    cfg = AVISOS[clave]
    lineas = [rotulo(clave, len(regs), nuevas),
              "Recoleccion del %s" % generado, ""]
    for r in regs[:TOPE_FICHAS]:
        lineas += [
            "-" * 66,
            "%s | %s" % (r.get("tipo", ""), r.get("grupo", "")),
            "Entidad     : %s" % (r.get("entidad") or ""),
            "Numero      : %s" % (r.get("referencia") or ""),
            "Contratista : %s" % (r.get("proveedor") or "aun sin contratista"),
            "Valor       : %s" % pesos(r.get("valor")),
            "%-12s: %s" % (r.get("etiqueta_fecha") or "Fecha", r.get("fecha") or ""),
            "Inicio      : %s" % (r.get("fecha_inicio") or "-"),
            "Termina     : %s" % (r.get("fecha_fin") or "-"),
            "Objeto      : %s" % (r.get("objeto") or ""),
            "SECOP       : %s" % (r.get("url") or "sin enlace"),
            "",
        ]
    if len(regs) > TOPE_FICHAS:
        lineas.append("Y %d mas en el tablero: %s" % (len(regs) - TOPE_FICHAS, TABLERO))
    return "\n".join(lineas)


# --------------------------------------------------------------------------
# Envio
# --------------------------------------------------------------------------

def enviar(asunto, destinatarios, html, texto):
    # 'or' y no el segundo argumento de get(): GitHub Actions define la variable
    # igual cuando no existe, solo que vacia. Con get(clave, defecto) el defecto
    # nunca se usaria y int("") reventaria la corrida.
    servidor = os.environ.get("CORREO_SERVIDOR") or "smtp.gmail.com"
    puerto = int(os.environ.get("CORREO_PUERTO") or "465")
    usuario = os.environ.get("CORREO_USUARIO") or ""
    clave = os.environ.get("CORREO_CLAVE") or ""
    remitente = os.environ.get("CORREO_REMITENTE") or usuario

    if not usuario or not clave:
        print("  ! faltan CORREO_USUARIO o CORREO_CLAVE: no se envia nada.")
        print("    (se configuran en Settings > Secrets and variables > Actions)")
        return False

    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = remitente
    msg["To"] = ", ".join(destinatarios)
    msg.set_content(texto)
    msg.add_alternative(html, subtype="html")

    contexto = ssl.create_default_context()
    with smtplib.SMTP_SSL(servidor, puerto, context=contexto, timeout=60) as s:
        s.login(usuario, clave)
        s.send_message(msg)
    return True


EN_PRUEBA = 8


def enviar_prueba(registros, destinos, generado):
    """Manda los dos correos una vez, con lo que hoy esta clasificado.

    Sirve para dos cosas a la vez: ver como llega el correo y comprobar que la
    contrasena de aplicacion quedo bien puesta. No escribe en avisados.csv a
    proposito: si lo hiciera, esta prueba se comeria los avisos de verdad de la
    contratacion que todavia no se ha notificado.
    """
    hubo = False
    for clave, c in AVISOS.items():
        muestras = [r for r in registros if r.get("nivel") == c["nivel"]]
        if not muestras:
            print(f"  {clave}: no hay nada en este nivel para mostrar.")
            continue
        muestras.sort(key=lambda r: -float(r.get("valor") or 0))
        total = len(muestras)
        muestras = muestras[:EN_PRUEBA]

        para = [d for d in destinos.get(c["para"], []) if d and "@" in d]
        if not para:
            print(f"  ! {clave}: no hay destinatarios en config.json > correo > {c['para']}.")
            continue

        aviso = (f"PRUEBA. No es un aviso de novedades: son las {len(muestras)} de mayor "
                 f"valor de las {total} que hoy estan en este nivel, para ver como llega "
                 f"el correo. Nada de esto se marca como avisado.")
        html = cuerpo_html(clave, muestras, generado, nuevas=False).replace(
            "<h1 ", '<p style="background:#FFF4D6;border:1px solid #E0C070;padding:10px 12px;'
                    'border-radius:3px;font-size:13px;color:#5C4708;margin:0 0 14px">'
            + esc(aviso) + "</p><h1 ", 1)
        texto = "*** " + aviso + " ***\n\n" + cuerpo_texto(clave, muestras, generado, nuevas=False)
        # Sin la palabra "nuevas": no lo son, y un asunto que promete novedades
        # sobre contratacion de hace semanas es justo lo que no puede hacer un
        # aviso del que se espera que se le crea.
        asunto = "[PRUEBA] Sismo 10-ago · %s · %s" % (
            c["varias"].replace("nuevas ", "").replace("nueva ", ""), generado[:10])

        try:
            if enviar(asunto, para, html, texto):
                print(f"  {clave}: PRUEBA enviada a {', '.join(para)} "
                      f"({len(muestras)} de {total}). La bitacora no se toco.")
                hubo = True
        except Exception as e:
            print(f"  ! {clave}: fallo el envio de prueba: {e}")
            return 1
    if not hubo:
        print("  no se envio ninguna prueba. Revise las credenciales y los destinatarios.")
        return 1
    return 0


# --------------------------------------------------------------------------
# Principal
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probar", action="store_true",
                    help="no envia; escribe los correos en reportes/ para revisarlos")
    ap.add_argument("--prueba", action="store_true",
                    help="envia UNA vez, con lo que hoy esta clasificado, para ver como "
                         "llega. No toca la bitacora: nada se da por avisado.")
    args = ap.parse_args()

    ruta_tablero = os.path.join(DIR_DATOS, "tablero.json")
    if not os.path.exists(ruta_tablero):
        print("  ! no hay datos/tablero.json; el colector no ha corrido.")
        return 0
    with open(ruta_tablero, encoding="utf-8") as fh:
        datos = json.load(fh)

    with open(os.path.join(BASE, "config.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)
    destinos = cfg.get("correo", {})

    generado = datos.get("generado", "")
    registros = datos.get("registros", [])

    # Envio de prueba, a mano. Manda los dos correos con lo que HOY esta
    # clasificado, para ver como llegan, y NO toca la bitacora: nada se da por
    # avisado, asi que la corrida siguiente sigue avisando de lo que de verdad
    # aparezca. Se limita a las mas grandes porque el correo es para ver el
    # formato, no para leerse entero.
    if args.prueba:
        return enviar_prueba(registros, destinos, generado)

    avisados = leer_avisados()

    # Primera vez: se siembra y no se manda nada. Si no, el estreno del aviso
    # serian quinientos correos de contratacion que ya se conocia.
    if avisados is None:
        siembra = [(r["id"], clave, r.get("entidad", ""), r.get("valor", 0))
                   for clave, c in AVISOS.items()
                   for r in registros if r.get("nivel") == c["nivel"]]
        anotar_avisados(siembra)
        print(f"  primera corrida: se sembro la bitacora con {len(siembra)} registros "
              f"ya conocidos. No se envia nada; a partir de la proxima solo sale "
              f"lo que aparezca nuevo.")
        return 0

    envios = 0
    for clave, c in AVISOS.items():
        pendientes = [r for r in registros
                      if r.get("nivel") == c["nivel"] and (r["id"], clave) not in avisados]
        if not pendientes:
            print(f"  {clave}: nada nuevo.")
            continue

        para = [d for d in destinos.get(c["para"], []) if d and "@" in d]
        if not para:
            print(f"  ! {clave}: {len(pendientes)} pendientes pero no hay "
                  f"destinatarios en config.json > correo > {c['para']}. "
                  f"No se anota nada: quedan pendientes para cuando los haya.")
            continue

        # De mayor a menor valor: lo primero que se ve es lo que mas pesa.
        pendientes.sort(key=lambda r: -float(r.get("valor") or 0))
        asunto = "Sismo 10-ago · %s · %s" % (rotulo(clave, len(pendientes)),
                                             generado[:10])
        html = cuerpo_html(clave, pendientes, generado)
        texto = cuerpo_texto(clave, pendientes, generado)

        if args.probar:
            os.makedirs(os.path.join(BASE, "reportes"), exist_ok=True)
            destino = os.path.join(BASE, "reportes", f"correo_{clave}.html")
            with open(destino, "w", encoding="utf-8") as fh:
                fh.write(html)
            print(f"  {clave}: {len(pendientes)} pendientes para {', '.join(para)}")
            print(f"    prueba escrita en {destino}")
            continue

        try:
            if not enviar(asunto, para, html, texto):
                # Sin credenciales no se anota nada: cuando se configuren, sale.
                continue
        except Exception as e:
            print(f"  ! {clave}: fallo el envio: {e}")
            # Tampoco se anota. Un correo que no salio no puede darse por avisado.
            continue

        anotar_avisados([(r["id"], clave, r.get("entidad", ""), r.get("valor", 0))
                         for r in pendientes])
        print(f"  {clave}: enviado a {', '.join(para)} ({len(pendientes)} registros)")
        envios += 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
