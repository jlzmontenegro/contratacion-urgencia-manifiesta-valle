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
import ligero

BASE = os.path.dirname(os.path.abspath(__file__))
DIR_DATOS = os.path.join(BASE, "datos")
ANCHO_PNG = 620          # ancho comodo para un correo; el alto sale de la proporcion
TOPE_FICHAS = 6          # fichas del bloque del Valle
TOPE_FICHAS_FUERA = 3    # el de fuera del Valle es contexto, no el asunto del correo

# El reparto Valle / fuera del Valle mira el departamento de la ENTIDAD, que es
# lo mismo que pinta el mapa y lo mismo que usa la version ligera (dp === "76").
# Cali es 76001, asi que "Cali y el Valle" es UN bloque, no dos.
VALLE = "76"

# El correo habla EN LOS MISMOS SEIS GRUPOS que ligero.html, que es la vista que
# se publica hacia afuera (peticion del usuario, 13-sep-2026). No se copian aqui:
# se importan de ligero.py, con su funcion de clasificacion incluida. Copiarlos
# seria una segunda implementacion de las mismas reglas, y ya sabemos como acaba
# eso -las 477 lineas de JavaScript que repetian el colector-.
#
# El ultimo grupo cambia de rotulo, y solo ahi. En ligero se llama "Otras
# entidades y otras regiones" porque alli todo va en una sola tabla; en el correo
# las otras regiones tienen su propia seccion, asi que dentro del bloque del
# Valle solo quedan las otras entidades DEL Valle -hospitales, universidades,
# camaras de comercio- y llamarlo "y otras regiones" seria falso.
ROTULO_GRUPO = dict(ligero.GRUPOS)
ROTULO_GRUPO["otros"] = "Otras entidades del Valle"

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
    """Agrupa proceso y contrato en una operacion, EXACTAMENTE como ligero.html.

    El principal se elige igual que en ligero._operaciones() -contrato, si no
    proceso, si no el primero- y el grupo sale de ligero._grupo_ligero(), que es
    donde vive la decision de contar la UAESP como Alcaldia de Cali y la de
    separar alcaldias de hospitales por el nombre. Si el correo eligiera por su
    cuenta, diria otra cosa que la vista publica sobre los mismos contratos.
    """
    por_clave = {}
    for r in registros:
        por_clave.setdefault(r.get("operacion") or r.get("id"), []).append(r)
    ops = []
    for regs in por_clave.values():
        contrato = next((r for r in regs if r.get("tipo") == "Contrato"), None)
        proceso = next((r for r in regs if r.get("tipo") == "Proceso"), None)
        pr = contrato or proceso or regs[0]
        objeto = max((r.get("objeto") or "" for r in regs), key=len)
        ops.append({
            "entidad": pr.get("entidad", ""), "objeto": objeto,
            "grupo": ligero._grupo_ligero(pr),
            # Tope de la FUENTE, no recorte nuestro: cuando el objeto llega justo
            # en el tope, SECOP lo corto y hay que decirlo. Mismo criterio que la
            # vista ligera.
            "objeto_cortado": len(objeto) >= ligero.TOPE_FUENTE,
            # Estudios previos: el documento donde la entidad explica POR QUE
            # contrata esto. El contrato y su proceso comparten expediente, asi
            # que sirve el primero de los dos que lo traiga. Aqui va la url
            # entera y no el DocumentId como en ligero.html: en un correo no hay
            # guion que la rearme.
            "docs_ep": next((r.get("docs_ep") or "" for r in regs
                             if r.get("docs_ep")), ""),
            "docs_contrato": next((r.get("docs_contrato") or "" for r in regs
                                   if r.get("docs_contrato")), ""),
            "docs_ejecucion": next((r.get("docs_ejecucion") or "" for r in regs
                                    if r.get("docs_ejecucion")), ""),
            # Cuantas veces publico la entidad esta misma contratacion. Lo decide
            # el colector (unificar_publicaciones_repetidas); aqui solo se lee.
            "repetida": max((int(r.get("repetida") or 0) for r in regs), default=0),
            # La otra publicacion es la del OTRO expediente: el proceso y el
            # contrato del mismo comparten 'portafolio', asi que se distingue por
            # ahi y no por la url, que cambia de forma entre proceso y contrato.
            "url_otra": next(
                (r.get("url") or "" for r in regs
                 if r.get("portafolio") and r.get("portafolio") != (pr.get("portafolio") or "")),
                ""),
            "valor": float(pr.get("valor") or 0), "firmado": bool(contrato),
            "fecha": pr.get("fecha", ""), "mun": pr.get("municipio", ""),
            "mun_nombre": pr.get("municipio_nombre", ""),
            "dep": pr.get("dep_codigo", ""),
            "dep_nombre": pr.get("departamento", ""),
            "proveedor": (contrato or pr).get("proveedor", ""),
            # La referencia del contrato si la hay, y si no la del proceso: es el
            # numero por el que pregunta quien llega desde el buscador de SECOP.
            "ref": ((contrato or {}).get("referencia")
                    or (proceso or {}).get("referencia") or pr.get("referencia", "")),
            "url": (contrato or pr).get("url", ""),
            # Los id de TODOS sus registros: una operacion es nueva si lo es
            # cualquiera de los dos, y asi cada bloque cuenta sus propias novedades
            # en vez de repartirse un total global que no cuadraria con ninguno.
            "ids": [r.get("id") for r in regs if r.get("id")],
        })
    return ops


def es_valle(o):
    return (o.get("dep") or "") == VALLE


# --------------------------------------------------------------------------
# El correo
# --------------------------------------------------------------------------

def _cifra(n, t, color="#16211F"):
    esc = correo.esc
    return ('<td style="padding:0 16px 0 0;vertical-align:top">'
            f'<div style="font-size:26px;font-weight:700;color:{color};'
            f'line-height:1.1">{esc(n)}</div>'
            f'<div style="font-size:12px;color:#6B807C;line-height:1.35;'
            f'padding-top:4px">{esc(t)}</div></td>')


def _cifras(ops, nuevos_ids):
    """Las cuatro cifras de un bloque, contadas SOLO sobre sus operaciones."""
    firmadas = [o for o in ops if o["firmado"]]
    abiertas = [o for o in ops if not o["firmado"]]
    nuevas = sum(1 for o in ops if any(i in nuevos_ids for i in o["ids"]))
    return ('<table cellpadding="0" cellspacing="0" style="margin-bottom:22px"><tr>'
            + _cifra(str(len(ops)), "operaciones con fecha\nen la semana")
            + _cifra(correo.pesos(sum(o["valor"] for o in firmadas)),
                     f"firmados en {len(firmadas)} contratos", "#0E5C58")
            + _cifra(str(len(abiertas)), "procesos abiertos\naún sin contratar")
            + _cifra(str(nuevas), "aparecieron por primera vez\nen el monitor")
            + "</tr></table>")


def _rotulo(texto):
    return ('<h2 style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;'
            f'color:#6B807C;margin:0 0 10px">{correo.esc(texto)}</h2>')


def _barras(pares):
    """Ranking con barra proporcional. `pares` es [(nombre, valor), ...] ya ordenado."""
    esc = correo.esc
    tope = pares[0][1] or 1
    filas = ""
    for nombre, val in pares:
        ancho = max(2, int(val / tope * 100))
        filas += (
            '<tr>'
            f'<td style="padding:4px 10px 4px 0;font-size:13px;color:#16211F;'
            f'white-space:nowrap">{esc(nombre)}</td>'
            f'<td style="padding:4px 0;width:100%">'
            f'<table cellpadding="0" cellspacing="0" style="width:{ancho}%">'
            f'<tr><td style="background:#56A800;height:14px;border-radius:2px">'
            f'&nbsp;</td></tr></table></td>'
            f'<td style="padding:4px 0 4px 10px;font-family:Consolas,monospace;'
            f'font-size:12px;color:#3D4F4C;white-space:nowrap">'
            f'{esc(correo.pesos(val))}</td></tr>')
    return ('<table cellpadding="0" cellspacing="0" style="width:100%;'
            f'margin-bottom:24px">{filas}</table>')


def _grupos(ops):
    """Los seis grupos de ligero.html, SIEMPRE los seis, incluidos los que estan
    en cero.

    Que la Gobernacion del Valle no haya contratado es justamente una de las
    cosas que hay que poder ver. Si la fila desapareciera, el correo no diria
    nada y el silencio se leeria como que no se la vigila -es la misma razon por
    la que en ligero.html los seis grupos van siempre en el desplegable-.
    """
    esc = correo.esc
    acum = {k: [0, 0.0] for k, _ in ligero.GRUPOS}
    for o in ops:
        acum.setdefault(o["grupo"], [0, 0.0])
        acum[o["grupo"]][0] += 1
        if o["firmado"]:
            acum[o["grupo"]][1] += o["valor"]
    filas = ""
    for k, _ in ligero.GRUPOS:
        n, val = acum[k]
        gris = "#9AA7A4"
        col = gris if not n else "#16211F"
        col2 = gris if not n else "#3D4F4C"
        cuenta = ("sin contratación esta semana" if not n
                  else f"{n} operación" if n == 1 else f"{n} operaciones")
        filas += (
            '<tr>'
            f'<td style="padding:5px 10px 5px 0;font-size:13px;color:{col}">'
            f'{esc(ROTULO_GRUPO[k])}</td>'
            f'<td style="padding:5px 10px;font-size:12.5px;text-align:right;'
            f'color:{col2};white-space:nowrap">{esc(cuenta)}</td>'
            f'<td style="padding:5px 0 5px 10px;font-family:Consolas,monospace;'
            f'font-size:12px;text-align:right;white-space:nowrap;color:{col2}">'
            f'{"—" if not val else esc(correo.pesos(val))}</td></tr>')
    return ('<table cellpadding="0" cellspacing="0" style="width:100%;'
            f'margin-bottom:24px">{filas}</table>')


def _fichas(ops, tope):
    esc = correo.esc
    fichas = ""
    for o in sorted(ops, key=lambda x: -x["valor"])[:tope]:
        botones = ""
        if o["url"]:
            botones += ('<a href="' + esc(o["url"]) + '" '
                        'style="display:inline-block;background:#0E5C58;color:#fff;'
                        'text-decoration:none;padding:7px 14px;border-radius:3px;'
                        'font-size:12.5px;font-weight:600;margin-right:8px">'
                        'Ver en SECOP</a>')
        # En hueco y no en relleno, como en el tablero: lleva a un PDF y no a la
        # ficha, y dos botones macizos seguidos compiten entre si. Solo aparece
        # cuando el archivo existe; no se pone un aviso cuando falta, misma
        # decision que en la version ligera.
        def _hueco(url, rotulo):
            return ('<a href="' + esc(url) + '" '
                    'style="display:inline-block;background:#fff;color:#0E5C58;'
                    'text-decoration:none;padding:6px 13px;border-radius:3px;'
                    'font-size:12.5px;font-weight:600;margin-right:8px;'
                    'border:1px solid #0E5C58">' + esc(rotulo) + "</a>")

        if o["docs_contrato"]:
            botones += _hueco(o["docs_contrato"], "Contrato")
        if o["docs_ep"]:
            botones += _hueco(o["docs_ep"], "Estudios previos")
        # El unico que habla de lo ENTREGADO. Va macizo y en ambar porque hoy lo
        # tiene el 2% de los expedientes: cuando sale, es la noticia de la
        # semana, no un enlace mas.
        if o["docs_ejecucion"]:
            botones += ('<a href="' + esc(o["docs_ejecucion"]) + '" '
                        'style="display:inline-block;background:#8A6D1F;color:#fff;'
                        'text-decoration:none;padding:7px 14px;border-radius:3px;'
                        'font-size:12.5px;font-weight:600;margin-right:8px">'
                        'Informe de ejecución</a>')
        # La publicacion repetida se dice, no se esconde: es un hecho sobre como
        # la entidad publica y quien verifique va a encontrarse los dos
        # expedientes. Se enlaza el otro para que pueda comprobarlo.
        if o["repetida"] and o["url_otra"]:
            botones += ('<a href="' + esc(o["url_otra"]) + '" '
                        'style="display:inline-block;background:#fff;color:#8A6D1F;'
                        'text-decoration:none;padding:6px 13px;border-radius:3px;'
                        'font-size:12.5px;margin-left:8px;'
                        'border:1px solid #E0C070">Ver la otra publicación</a>')
        boton = ('<div style="margin-top:10px">' + botones + "</div>") if botones else ""
        repetida = ""
        if o["repetida"]:
            repetida = ('<div style="font-size:11.5px;color:#8A6D1F;margin-top:6px">'
                        f'La entidad publicó esta misma contratación {o["repetida"]} '
                        'veces en SECOP, con expedientes distintos. Cuenta como una.'
                        '</div>')
        # El objeto llego justo en el tope de la fuente: lo corto SECOP, no
        # nosotros, y presentarlo como entero desinforma. Lo mismo que avisa la
        # fila de ligero.html.
        corte = ""
        if o["objeto_cortado"]:
            corte = ('<div style="font-size:11.5px;color:#8A6D1F;margin-top:5px">'
                     'SECOP corta este objeto; el texto completo está en el '
                     'expediente.</div>')
        # Fuera del Valle el municipio no dice nada sin su departamento.
        sitio = o["mun_nombre"].title() if o["mun_nombre"] else ""
        if sitio and not es_valle(o) and o["dep_nombre"]:
            sitio += f" ({o['dep_nombre']})"
        elif not sitio and o["dep_nombre"]:
            sitio = o["dep_nombre"]
        fichas += (
            '<div style="border:1px solid #D6DEDC;border-radius:3px;padding:13px 15px;'
            'margin-bottom:12px;background:#fff">'
            f'<div style="font-size:11px;text-transform:uppercase;letter-spacing:.07em;'
            f'color:#6B807C;margin-bottom:6px">'
            f'{"Contratada" if o["firmado"] else "Abierta"} · {esc(o["fecha"])}'
            f'{" · " + esc(sitio) if sitio else ""}</div>'
            f'<div style="font-size:14.5px;font-weight:700;color:#16211F;'
            f'margin-bottom:4px">{esc(correo.pesos(o["valor"]))} '
            f'<span style="font-weight:400;font-size:12px;color:#6B807C">'
            f'{"valor firmado" if o["firmado"] else "precio base"}</span></div>'
            f'<div style="font-size:13px;color:#3D4F4C;margin-bottom:6px">'
            f'{esc(o["entidad"])}</div>'
            f'<div style="font-size:13px;color:#16211F;line-height:1.5">'
            f'{esc(o["objeto"][:300])}{"…" if len(o["objeto"]) > 300 else ""}</div>'
            + corte +
            f'<div style="font-size:12px;color:#6B807C;margin-top:6px">'
            f'{esc(o["ref"])}{" · " + esc(o["proveedor"]) if o["proveedor"] else ""}</div>'
            + repetida + boton + "</div>")
    if len(ops) > tope:
        fichas += (f'<div style="font-size:13px;color:#3D4F4C;margin-top:4px">Y '
                   f'<b>{len(ops) - tope}</b> más en el tablero.</div>')
    return fichas


def _aviso(texto):
    return ('<div style="border:1px solid #E0C070;background:#FFF9EC;padding:14px 16px;'
            'border-radius:3px;font-size:13.5px;color:#5C4708;line-height:1.55;'
            f'margin-bottom:22px">{texto}</div>')


def cuerpo(ops_semana, nuevos_ids, ini, fin, generado, hay_mapa):
    esc = correo.esc

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

    # El orden lo pidio el usuario (13-sep-2026): PRIMERO Cali y el Valle, que es
    # el asunto del monitor, y lo de fuera en su propia seccion mas abajo. Antes
    # iba todo mezclado y la ficha mas grande de la semana podia ser de Caldas
    # bajo un titulo que nombra el Valle -la misma trampa de los $14,0 mm-.
    valle = [o for o in ops_semana if es_valle(o)]
    fuera = [o for o in ops_semana if not es_valle(o)]

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

    # ---------------- Cali y el Valle del Cauca ----------------
    bloque1 = _rotulo("Cali y el Valle del Cauca")
    if valle:
        por_mun = {}
        for o in valle:
            if o["firmado"] and o["mun_nombre"]:
                por_mun[o["mun_nombre"]] = por_mun.get(o["mun_nombre"], 0) + o["valor"]
        orden = sorted(por_mun.items(), key=lambda kv: -kv[1])[:10]
        bloque1 += _cifras(valle, nuevos_ids) + mapa
        bloque1 += _rotulo("Quién contrató, por grupo") + _grupos(valle)
        if orden:
            bloque1 += (_rotulo("Dónde se movió la plata")
                        + _barras([(n.title(), v) for n, v in orden]))
        bloque1 += _rotulo("Lo más grande de la semana") + _fichas(valle, TOPE_FICHAS)
    else:
        # Un cero aqui es un hallazgo, no un hueco: hay que decir por que.
        bloque1 += _aviso(
            "<b>Ninguna entidad del Valle del Cauca contrató esta semana.</b><br>"
            "Las dos recolecciones diarias corrieron y no encontraron nada con fecha "
            "en este rango para el departamento. Lo de abajo es de otras regiones.")

    # ---------------- Fuera del Valle ----------------
    regla = ('<div style="border-top:1px solid #D6DEDC;margin:30px 0 18px"></div>')
    bloque2 = regla + _rotulo("Otras entidades, fuera del Valle")
    if fuera:
        por_dep = {}
        for o in fuera:
            if o["firmado"]:
                # "No Definido" es literalmente lo que publica SECOP cuando la
                # entidad no diligencia el departamento. Sacarlo tal cual a una
                # barra se lee como un fallo del informe; hay que decir de quien
                # es el hueco.
                clave = o["dep_nombre"]
                if not clave or clave.lower().startswith("no definido"):
                    clave = "Sin departamento en la fuente"
                por_dep[clave] = por_dep.get(clave, 0) + o["valor"]
        orden_dep = sorted(por_dep.items(), key=lambda kv: -kv[1])[:8]
        bloque2 += (
            '<div style="font-size:13px;color:#3D4F4C;line-height:1.55;'
            'margin:-2px 0 16px">Contratación que nombra el sismo en los otros '
            'departamentos declarados en desastre por el Decreto 1171. '
            '<b>No suma en las cifras de arriba.</b></div>'
            + _cifras(fuera, nuevos_ids))
        if orden_dep:
            bloque2 += _rotulo("Por departamento") + _barras(orden_dep)
        bloque2 += (_rotulo("Lo más grande, fuera del Valle")
                    + _fichas(fuera, TOPE_FICHAS_FUERA))
    else:
        bloque2 += ('<div style="font-size:13px;color:#3D4F4C;line-height:1.55">'
                    'Esta semana no apareció contratación del sismo fuera del Valle '
                    'del Cauca.</div>')

    return cabeza + bloque1 + bloque2 + pie(generado)


def pie(generado):
    return ('<div style="font-size:11.5px;color:#6B807C;line-height:1.55;margin-top:24px;'
            'border-top:1px solid #D6DEDC;padding-top:12px">'
            f'Recolección del {correo.esc(generado)}. Fuente: datos.gov.co — SECOP I y '
            'SECOP II. Solo se cuenta la contratación ya confirmada como atención de la '
            'emergencia; lo que está en duda no entra hasta que una persona lo revise. '
            'Es la misma información y los mismos grupos de la vista pública. '
            f'<a href="{correo.TABLERO}ligero.html" style="color:#0E5C58">Ver la vista '
            f'pública</a> · <a href="{correo.TABLERO}" style="color:#0E5C58">tablero '
            'completo</a>.</div>')


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

    # El mismo orden que el HTML: primero el Valle, luego lo de fuera. Si las dos
    # versiones contaran distinto, quien lea la de texto veria otro correo.
    def seccion(titulo, ops, tope, nota=""):
        if not ops:
            return [titulo.upper(), "", "  (nada esta semana)", ""]
        firmadas = [o for o in ops if o["firmado"]]
        t = [titulo.upper(), ""]
        if nota:
            t += [nota, ""]
        t.append(f"{len(ops)} operaciones con fecha en la semana; "
                 f"{correo.pesos(sum(o['valor'] for o in firmadas))} firmados en "
                 f"{len(firmadas)} contratos.")
        t.append("")
        for o in sorted(ops, key=lambda x: -x["valor"])[:tope]:
            sitio = o["mun_nombre"] or o["dep_nombre"]
            t += ["-" * 66,
                  f"{correo.pesos(o['valor'])} | {o['entidad']}",
                  f"{o['ref']} | {o['fecha']} | {sitio}",
                  o["objeto"][:300], o["url"] or ""]
            if o["docs_ep"]:
                t.append("Estudios previos: " + o["docs_ep"])
            if o["repetida"]:
                t.append(f"La entidad publico esta contratacion {o['repetida']} veces "
                         f"en SECOP; cuenta como una. La otra: {o['url_otra'] or 's/d'}")
            t.append("")
        if len(ops) > tope:
            t += [f"Y {len(ops) - tope} mas en el tablero.", ""]
        return t

    valle = [o for o in ops_semana if es_valle(o)]
    fuera = [o for o in ops_semana if not es_valle(o)]
    l += seccion("Cali y el Valle del Cauca", valle, TOPE_FICHAS)
    l += ["=" * 66, ""]
    l += seccion("Otras entidades, fuera del Valle", fuera, TOPE_FICHAS_FUERA,
                 "No suma en las cifras de arriba.")
    return "\n".join(l)


# --------------------------------------------------------------------------
# Principal
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probar", action="store_true",
                    help="no envia; escribe el correo y el mapa en reportes/")
    # Una prueba no puede salir hacia afuera. Sin esto, lanzar el flujo a mano
    # para ver como quedo un cambio le mandaba el correo a todo el equipo: paso
    # dos veces el 13-sep-2026. Con --solo-a se manda a una direccion y punto.
    ap.add_argument("--solo-a", default="", metavar="CORREO",
                    help="manda solo a esta direccion, en vez de para_resumen")
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
    nuevos_ids = {k for k, v in nov.items()
                  if k in ids and ini.isoformat() <= str(v)[:10] <= fin.isoformat()}

    # El mapa es el del Valle: se alimenta solo de las operaciones del Valle. Con
    # las de fuera daba igual -sus codigos no estan en la definicion y se
    # ignoraban-, pero contarlas aqui y no en el bloque seria una cuenta que no
    # cuadra con ninguna de las dos secciones.
    por_mun = {}
    for o in en_semana:
        if not o["mun"] or not es_valle(o):
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

    html = envoltura(cuerpo(en_semana, nuevos_ids, ini, fin,
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

    if args.solo_a:
        if "@" not in args.solo_a:
            print(f"  ! --solo-a no parece un correo: {args.solo_a}")
            return 1
        para = [args.solo_a]
        # Se dice en el asunto, no solo en el registro: si alguien reenvia el
        # correo, tiene que verse que era una prueba y no el informe del lunes.
        asunto = "[PRUEBA] " + asunto
    else:
        para = [d for d in (cfg.get("correo", {}).get("para_resumen") or [])
                if d and "@" in d]
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
