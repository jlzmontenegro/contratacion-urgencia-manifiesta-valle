# -*- coding: utf-8 -*-
"""Resumen semanal por correo, con el mapa dibujado.

Sale los lunes a las 8:30. Es un INFORME, no un aviso: cuenta lo que paso en la
semana que acaba de terminar, aunque de cada contrato ya se haya avisado el dia
que aparecio. Por eso no toca datos/avisados.csv.

Y SALE SIEMPRE, tambien cuando no hubo nada. Un informe periodico que se calla
cuando no hay novedades es indistinguible de uno que se rompio: quien lo espera
no sabe si la semana estuvo tranquila o si el flujo lleva tres lunes cayendose.
Los avisos diarios son al reves -solo si hay algo- porque ahi el silencio no
promete nada.

EL MAPA SE DIBUJA AQUI, con Pillow, no en el navegador. En el correo no sirve un
SVG: Gmail y Outlook lo descartan, asi que tiene que ser un PNG incrustado. Y
rasterizar el SVG obligaria a cargar cairo o a levantar un navegador en el
runner. No hace falta ninguna de las dos cosas: los trazos de mapa.json solo usan
los comandos M, L y Z -son poligonos, porque Douglas-Peucker no produce curvas-,
asi que se parsean en diez lineas y se pintan con ImageDraw.polygon.

Uso:
    py -3 resumen.py            # manda el resumen de la semana pasada
    py -3 resumen.py --probar   # no manda; escribe el correo y el mapa en reportes/
"""

import argparse
import io
import json
import os
import re
import sys
from datetime import datetime, timedelta

import correo

BASE = os.path.dirname(os.path.abspath(__file__))
DIR_DATOS = os.path.join(BASE, "datos")
ANCHO_PNG = 620          # ancho comodo para un correo; el alto sale de la proporcion
TOPE_FICHAS = 6

# La misma rampa que la version ligera, para que el correo y el tablero se lean
# como lo mismo. En RGB porque Pillow no entiende '#RRGGBB' en todas partes.
RAMPA = [(236, 236, 236), (221, 239, 202), (174, 218, 139), (116, 186, 59), (62, 124, 0)]
AMBAR = (217, 164, 65)   # solo procesos sin firmar
BORDE = (255, 255, 255)
TINTA = (26, 26, 26)


# --------------------------------------------------------------------------
# El mapa
# --------------------------------------------------------------------------

def _subtrazos(d):
    """Convierte el atributo 'd' de un <path> en listas de puntos.

    Solo se admiten M, L y Z. Si algun dia preparar_mapa.py empezara a emitir
    curvas, esto se quedaria corto EN SILENCIO y el mapa saldria deformado; por
    eso se comprueba y se avisa en vez de dibujar cualquier cosa.
    """
    if re.search(r"[CcSsQqTtAaHhVv]", d):
        raise ValueError("el trazo trae curvas y este dibujante solo entiende M/L/Z")
    trozos = []
    for parte in d.split("M"):
        parte = parte.strip().rstrip("Zz ").strip()
        if not parte:
            continue
        puntos = []
        for par in parte.split("L"):
            par = par.strip()
            if not par:
                continue
            try:
                x, y = par.replace(",", " ").split()
                puntos.append((float(x), float(y)))
            except ValueError:
                continue
        if len(puntos) >= 3:
            trozos.append(puntos)
    return trozos


def _tramos(valores):
    """Cortes por cuantiles, como en el tablero: una sola operacion grande
    aplastaria a las demas contra el extremo bajo de cualquier escala lineal."""
    v = sorted(x for x in valores if x > 0)
    if not v:
        return []
    cortes = []
    for i in range(1, 5):
        c = v[min(len(v) - 1, int(len(v) * i / 5))]
        if not cortes or c > cortes[-1]:
            cortes.append(c)
    return cortes


def _color(valor, cortes, solo_abiertas):
    if not valor:
        return AMBAR if solo_abiertas else RAMPA[0]
    for i, c in enumerate(cortes):
        if valor <= c:
            return RAMPA[min(4, i + 1)]
    return RAMPA[min(4, len(cortes) + 1)]


def _compacto(v):
    """Cifra corta para el mapa. '$ 2.381.278.400' no cabe dentro de un municipio
    y se derrama sobre los vecinos; '$2.381 M' se lee de un vistazo y es lo mismo."""
    if v >= 1e9:
        return "$" + f"{v / 1e9:.1f}".replace(".", ",") + " mm"
    if v >= 1e6:
        return f"${round(v / 1e6):,.0f} M".replace(",", ".")
    return correo.pesos(v).replace("$ ", "$")


def _fuente(tam):
    from PIL import ImageFont
    for ruta in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(ruta):
            try:
                return ImageFont.truetype(ruta, tam)
            except OSError:
                pass
    return ImageFont.load_default()


def dibujar_mapa(definicion, por_pieza, ancho_px=ANCHO_PNG):
    """PNG del mapa, en bytes. Devuelve None si Pillow no esta o el trazo falla:
    el correo tiene que salir igual, con sus cifras, aunque no haya dibujo."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("  ! Pillow no esta instalado: el resumen sale sin mapa")
        return None
    try:
        ancho = float(definicion["ancho"])
        alto = float(definicion["alto"])
        k = ancho_px / ancho
        # x2 y luego reducir: el suavizado de los bordes se nota mucho en poligonos
        # con muchos vertices, y un mapa dentado parece un error de impresion.
        esc = k * 2
        img = Image.new("RGB", (int(ancho * esc), int(alto * esc)), (255, 255, 255))
        dib = ImageDraw.Draw(img)

        cortes = _tramos([(por_pieza.get(p["codigo"]) or {}).get("v", 0)
                          for p in definicion["piezas"]])
        etiquetas = []
        for p in definicion["piezas"]:
            d = por_pieza.get(p["codigo"]) or {"v": 0, "n": 0}
            solo_abiertas = d["n"] > 0 and d["v"] == 0
            relleno = _color(d["v"], cortes, solo_abiertas)
            for puntos in _subtrazos(p["d"]):
                dib.polygon([(x * esc, y * esc) for x, y in puntos],
                            fill=relleno, outline=BORDE)
            if d["n"]:
                etiquetas.append((p, d, solo_abiertas))

        # Se rotulan SOLO las ocho de mayor valor, no las 20 que pueden tener algo.
        # En el tablero cabe rotularlo todo porque el mapa mide 560px y ademas hay
        # raton con que descubrir lo demas; en un correo no hay ninguna de las dos
        # cosas, y veinte rotulos a este tamano son manchas. El reparto completo
        # va en la lista de barras de abajo, que es donde se lee bien.
        etiquetas.sort(key=lambda e: -(e[1]["v"] or e[1]["n"]))
        W, A = img.size
        puestas = []
        for p, d, solo_abiertas in etiquetas[:8]:
            # El cuerpo va en unidades del viewBox y luego se escala: con 11
            # unidades el rotulo salia a siete pixeles y no se leia.
            unidades = max(18.0, min(34.0, (float(p["a"]) ** 0.5) / 4.5))
            cuerpo = int(unidades * esc)
            f, fc = _fuente(cuerpo), _fuente(int(cuerpo * 0.82))
            cifra = (f"{d['n']} sin firmar" if solo_abiertas else _compacto(d["v"]))
            nombre = p.get("rotulo") or p["nombre"]

            an = dib.textlength(nombre, font=f)
            ac = dib.textlength(cifra, font=fc)
            ancho_e = max(an, ac)
            alto_e = cuerpo * 2.1
            x = float(p["cx"]) * esc
            y = float(p["cy"]) * esc

            # Desempate: la que llega despues -la de menor valor- se aparta de la
            # que ya esta puesta. Sin esto, Tulua y San Pedro salian escritas una
            # encima de la otra y la cifra de Cali se montaba sobre Candelaria.
            for _ in range(14):
                caja = (x - ancho_e / 2, y - alto_e / 2,
                        x + ancho_e / 2, y + alto_e / 2)
                choque = next((c for c in puestas
                               if caja[0] < c[2] and c[0] < caja[2]
                               and caja[1] < c[3] and c[1] < caja[3]), None)
                if not choque:
                    break
                centro_c = (choque[1] + choque[3]) / 2
                y += alto_e * 0.62 if y >= centro_c else -alto_e * 0.62
            # Y hacia dentro por los cuatro lados, o el rotulo se sale del PNG y
            # se corta a media palabra.
            x = min(max(x, ancho_e / 2 + 4), W - ancho_e / 2 - 4)
            y = min(max(y, alto_e / 2 + 4), A - alto_e / 2 - 4)
            puestas.append((x - ancho_e / 2, y - alto_e / 2,
                            x + ancho_e / 2, y + alto_e / 2))

            g = max(2, int(cuerpo * 0.18))
            for texto, fuente, dy in ((nombre, f, -cuerpo * 0.55),
                                      (cifra, fc, cuerpo * 0.55)):
                yy = y + dy
                # Halo: el nombre sobre el verde oscuro de la rampa no se lee.
                for ox in (-g, 0, g):
                    for oy in (-g, 0, g):
                        if ox or oy:
                            dib.text((x + ox, yy + oy), texto, font=fuente,
                                     fill=(255, 255, 255), anchor="mm")
                dib.text((x, yy), texto, font=fuente, fill=TINTA, anchor="mm")

        img = img.resize((ancho_px, int(alto * k)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    except Exception as e:
        print(f"  ! no se pudo dibujar el mapa ({e}); el resumen sale sin el")
        return None


# --------------------------------------------------------------------------
# La semana
# --------------------------------------------------------------------------

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def dia_largo(d):
    return f"{d.day} de {MESES[d.month - 1]}"


def ventana(hoy):
    """La semana que acaba de terminar: del lunes anterior al domingo.

    Se cuenta hacia atras desde ayer y no desde hoy, porque el informe sale el
    lunes por la manana y lo de hoy todavia no ha pasado."""
    fin = hoy.date() - timedelta(days=1)
    return fin - timedelta(days=6), fin


def operaciones(registros):
    """Agrupa proceso y contrato en una operacion, como el resto del sistema."""
    por_clave = {}
    for r in registros:
        por_clave.setdefault(r.get("operacion") or r.get("id"), []).append(r)
    ops = []
    for regs in por_clave.values():
        contrato = next((r for r in regs if r.get("tipo") == "Contrato"), None)
        pr = contrato or regs[0]
        ops.append({
            "entidad": pr.get("entidad", ""), "objeto": max(
                (r.get("objeto") or "" for r in regs), key=len),
            "valor": float(pr.get("valor") or 0), "firmado": bool(contrato),
            "fecha": pr.get("fecha", ""), "mun": pr.get("municipio", ""),
            "mun_nombre": pr.get("municipio_nombre", ""),
            "dep": pr.get("dep_codigo", ""),
            "proveedor": pr.get("proveedor", ""),
            "ref": (contrato or {}).get("referencia") or regs[0].get("referencia", ""),
            "url": (contrato or regs[0]).get("url", ""),
        })
    return ops


# --------------------------------------------------------------------------
# El correo
# --------------------------------------------------------------------------

def cuerpo(ops_semana, nuevas, ini, fin, generado, hay_mapa):
    esc = correo.esc
    firmadas = [o for o in ops_semana if o["firmado"]]
    plata = sum(o["valor"] for o in firmadas)
    abiertas = [o for o in ops_semana if not o["firmado"]]

    por_mun = {}
    for o in firmadas:
        if o["mun_nombre"]:
            por_mun.setdefault(o["mun_nombre"], [0, 0])
            por_mun[o["mun_nombre"]][0] += o["valor"]
            por_mun[o["mun_nombre"]][1] += 1
    orden = sorted(por_mun.items(), key=lambda kv: -kv[1][0])

    def cifra(n, t, color="#16211F"):
        return ('<td style="padding:0 16px 0 0;vertical-align:top">'
                f'<div style="font-size:26px;font-weight:700;color:{color};'
                f'line-height:1.1">{esc(n)}</div>'
                f'<div style="font-size:12px;color:#6B807C;line-height:1.35;'
                f'padding-top:4px">{esc(t)}</div></td>')

    cabeza = (
        f'<h1 style="font-size:19px;margin:0 0 4px;color:#16211F">Resumen de la semana</h1>'
        f'<div style="font-size:13.5px;color:#3D4F4C;margin-bottom:4px">'
        f'Del {esc(dia_largo(ini))} al {esc(dia_largo(fin))} de {fin.year}</div>'
        f'<div style="font-family:Consolas,monospace;font-size:11px;color:#6B807C;'
        f'margin-bottom:20px">Contratación pública relacionada con el sismo del '
        f'10 de agosto de 2026</div>')

    if not ops_semana:
        return (cabeza +
                '<div style="border:1px solid #E0C070;background:#FFF9EC;padding:16px 18px;'
                'border-radius:3px;font-size:14px;color:#5C4708;line-height:1.55">'
                '<b>Esta semana no apareció contratación nueva relacionada con el sismo.</b>'
                '<br>No es un fallo del monitor: las dos recolecciones diarias corrieron y '
                'no encontraron nada con fecha en este rango. El acumulado sigue completo '
                f'en el tablero.</div>{pie(generado)}')

    tabla = ('<table cellpadding="0" cellspacing="0" style="margin-bottom:22px">'
             '<tr>' +
             cifra(str(len(ops_semana)), "operaciones con fecha\nen la semana") +
             cifra(correo.pesos(plata), f"firmados en {len(firmadas)} contratos", "#0E5C58") +
             cifra(str(len(abiertas)), "procesos abiertos\naún sin contratar") +
             cifra(str(nuevas), "aparecieron por primera vez\nen el monitor") +
             "</tr></table>")

    mapa = ""
    if hay_mapa:
        mapa = ('<div style="margin:0 0 8px"><img src="cid:mapa" width="620" '
                'style="width:100%;max-width:620px;height:auto;display:block;'
                'border:1px solid #D6DEDC;border-radius:3px" '
                'alt="Mapa del Valle del Cauca con la contratación de la semana"></div>'
                '<div style="font-size:11.5px;color:#6B807C;margin-bottom:22px;'
                'line-height:1.5">Valle del Cauca. Se pinta el municipio de la '
                '<b>entidad que contrata</b>, no dónde se ejecuta. Solo se rotulan los '
                'que se movieron esta semana; el ámbar marca donde hay procesos abiertos '
                'sin firmar.</div>')

    munis = ""
    if orden:
        tope = orden[0][1][0] or 1
        filas = ""
        for nombre, (val, n) in orden[:10]:
            ancho = max(2, int(val / tope * 100))
            filas += (
                '<tr>'
                f'<td style="padding:4px 10px 4px 0;font-size:13px;color:#16211F;'
                f'white-space:nowrap">{esc(nombre.title())}</td>'
                f'<td style="padding:4px 0;width:100%">'
                f'<table cellpadding="0" cellspacing="0" style="width:{ancho}%">'
                f'<tr><td style="background:#56A800;height:14px;border-radius:2px">'
                f'&nbsp;</td></tr></table></td>'
                f'<td style="padding:4px 0 4px 10px;font-family:Consolas,monospace;'
                f'font-size:12px;color:#3D4F4C;white-space:nowrap">'
                f'{esc(correo.pesos(val))}</td></tr>')
        munis = ('<h2 style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;'
                 'color:#6B807C;margin:0 0 10px">Dónde se movió la plata</h2>'
                 '<table cellpadding="0" cellspacing="0" style="width:100%;'
                 f'margin-bottom:24px">{filas}</table>')

    grandes = sorted(ops_semana, key=lambda o: -o["valor"])[:TOPE_FICHAS]
    fichas = ""
    for o in grandes:
        boton = ""
        if o["url"]:
            boton = ('<div style="margin-top:10px"><a href="' + esc(o["url"]) + '" '
                     'style="display:inline-block;background:#0E5C58;color:#fff;'
                     'text-decoration:none;padding:7px 14px;border-radius:3px;'
                     'font-size:12.5px;font-weight:600">Ver en SECOP</a></div>')
        fichas += (
            '<div style="border:1px solid #D6DEDC;border-radius:3px;padding:13px 15px;'
            'margin-bottom:12px;background:#fff">'
            f'<div style="font-size:11px;text-transform:uppercase;letter-spacing:.07em;'
            f'color:#6B807C;margin-bottom:6px">'
            f'{"Contratada" if o["firmado"] else "Abierta"} · {esc(o["fecha"])}'
            f'{" · " + esc(o["mun_nombre"].title()) if o["mun_nombre"] else ""}</div>'
            f'<div style="font-size:14.5px;font-weight:700;color:#16211F;'
            f'margin-bottom:4px">{esc(correo.pesos(o["valor"]))} '
            f'<span style="font-weight:400;font-size:12px;color:#6B807C">'
            f'{"valor firmado" if o["firmado"] else "precio base"}</span></div>'
            f'<div style="font-size:13px;color:#3D4F4C;margin-bottom:6px">'
            f'{esc(o["entidad"])}</div>'
            f'<div style="font-size:13px;color:#16211F;line-height:1.5">'
            f'{esc(o["objeto"][:300])}{"…" if len(o["objeto"]) > 300 else ""}</div>'
            f'<div style="font-size:12px;color:#6B807C;margin-top:6px">'
            f'{esc(o["ref"])}{" · " + esc(o["proveedor"]) if o["proveedor"] else ""}</div>'
            + boton + "</div>")

    mas = ""
    if len(ops_semana) > TOPE_FICHAS:
        mas = (f'<div style="font-size:13px;color:#3D4F4C;margin-top:4px">Y '
               f'<b>{len(ops_semana) - TOPE_FICHAS}</b> más en el tablero.</div>')

    return (cabeza + tabla + mapa + munis +
            '<h2 style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;'
            'color:#6B807C;margin:0 0 10px">Lo más grande de la semana</h2>'
            + fichas + mas + pie(generado))


def pie(generado):
    return ('<div style="font-size:11.5px;color:#6B807C;line-height:1.55;margin-top:24px;'
            'border-top:1px solid #D6DEDC;padding-top:12px">'
            f'Recolección del {correo.esc(generado)}. Fuente: datos.gov.co — SECOP I y '
            'SECOP II. Solo se cuenta la contratación ya confirmada como atención de la '
            'emergencia; lo que está en duda no entra hasta que una persona lo revise. '
            f'<a href="{correo.TABLERO}" style="color:#0E5C58">Ver el tablero</a>.</div>')


def envoltura(interior):
    return ('<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Resumen de la semana</title></head>'
            '<body style="margin:0"><div style="font-family:system-ui,-apple-system,'
            'Segoe UI,sans-serif;background:#F5F7F6;padding:22px;color:#16211F">'
            f'<div style="max-width:680px;margin:0 auto">{interior}</div></div>'
            "</body></html>")


def texto_plano(ops_semana, ini, fin, generado):
    l = [f"Resumen de la semana · del {dia_largo(ini)} al {dia_largo(fin)} de {fin.year}",
         f"Recoleccion del {generado}", ""]
    if not ops_semana:
        l.append("Esta semana no aparecio contratacion nueva relacionada con el sismo.")
        return "\n".join(l)
    firmadas = [o for o in ops_semana if o["firmado"]]
    l.append(f"{len(ops_semana)} operaciones con fecha en la semana; "
             f"{correo.pesos(sum(o['valor'] for o in firmadas))} firmados en "
             f"{len(firmadas)} contratos.")
    l.append("")
    for o in sorted(ops_semana, key=lambda x: -x["valor"])[:TOPE_FICHAS]:
        l += ["-" * 66,
              f"{correo.pesos(o['valor'])} | {o['entidad']}",
              f"{o['ref']} | {o['fecha']} | {o['mun_nombre']}",
              o["objeto"][:300], o["url"] or "", ""]
    return "\n".join(l)


# --------------------------------------------------------------------------
# Principal
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probar", action="store_true",
                    help="no envia; escribe el correo y el mapa en reportes/")
    args = ap.parse_args()

    ruta = os.path.join(DIR_DATOS, "tablero.json")
    if not os.path.exists(ruta):
        print("  ! no hay datos/tablero.json; el colector no ha corrido.")
        return 0
    with io.open(ruta, encoding="utf-8") as fh:
        datos = json.load(fh)
    with io.open(os.path.join(BASE, "config.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)

    hoy = datetime.now()
    ini, fin = ventana(hoy)
    registros = [r for r in datos.get("registros", []) if r.get("nivel") == "Alta"]
    ops = operaciones(registros)
    en_semana = [o for o in ops
                 if o["fecha"] and ini.isoformat() <= o["fecha"][:10] <= fin.isoformat()]

    # Cuantas aparecieron por primera vez esta semana. Es distinto de la fecha del
    # contrato: SECOP publica con rezago, asi que una firma de hace quince dias
    # puede ser noticia de esta.
    nov = datos.get("novedades", {}) or {}
    ids = {r["id"] for r in registros}
    nuevas = sum(1 for k, v in nov.items()
                 if k in ids and ini.isoformat() <= str(v)[:10] <= fin.isoformat())

    por_mun = {}
    for o in en_semana:
        if not o["mun"]:
            continue
        por_mun.setdefault(o["mun"], {"v": 0, "n": 0})
        por_mun[o["mun"]]["n"] += 1
        if o["firmado"]:
            por_mun[o["mun"]]["v"] += o["valor"]

    png = None
    ruta_mapa = os.path.join(BASE, "mapa.json")
    if os.path.exists(ruta_mapa) and por_mun:
        with io.open(ruta_mapa, encoding="utf-8") as fh:
            png = dibujar_mapa(json.load(fh)["valle"], por_mun)

    html = envoltura(cuerpo(en_semana, nuevas, ini, fin,
                            datos.get("generado", ""), bool(png)))
    texto = texto_plano(en_semana, ini, fin, datos.get("generado", ""))
    asunto = (f"Sismo 10-ago · resumen del {dia_largo(ini)} al {dia_largo(fin)}"
              + (f" · {correo.pesos(sum(o['valor'] for o in en_semana if o['firmado']))}"
                 if en_semana else " · sin contratación nueva"))

    if args.probar:
        os.makedirs(os.path.join(BASE, "reportes"), exist_ok=True)
        with io.open(os.path.join(BASE, "reportes", "resumen_semanal.html"),
                     "w", encoding="utf-8") as fh:
            fh.write(html.replace('src="cid:mapa"', 'src="mapa_semana.png"'))
        if png:
            with open(os.path.join(BASE, "reportes", "mapa_semana.png"), "wb") as fh:
                fh.write(png)
        print(f"  {asunto}")
        print(f"  prueba escrita en reportes/resumen_semanal.html "
              f"({len(en_semana)} operaciones, mapa: {'sí' if png else 'no'})")
        return 0

    para = [d for d in (cfg.get("correo", {}).get("para_resumen") or []) if d and "@" in d]
    if not para:
        print("  ! no hay destinatarios en config.json > correo > para_resumen.")
        return 0
    try:
        if correo.enviar(asunto, para, html, texto,
                         imagenes={"mapa": png} if png else None):
            print(f"  resumen enviado a {', '.join(para)} "
                  f"({len(en_semana)} operaciones de la semana)")
    except Exception as e:
        print(f"  ! fallo el envio del resumen: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
