# -*- coding: utf-8 -*-
"""Genera ligero.html: un tablero autonomo, de un solo archivo, con SOLO la
contratacion que ya esta dada por relacionada con el sismo del 10-ago-2026.

Por que existe aparte del tablero grande:
  - Va incrustado en otra pagina web (estebanoliveros.com), donde no se puede
    contar con que se sirvan cuatro archivos desde el mismo sitio. Aqui todo
    -datos, estilos, guion y contornos del mapa- viaja dentro del HTML: cero
    peticiones de red despues de la primera, y ninguna dependencia externa. Ni
    siquiera las tipografias de Google: la pila del sistema carga al instante y
    una fuente que no llega deja el texto saltando.
  - Lleva la piel del sitio que lo aloja y no la del tablero grande. Ver la nota
    del <style>.
  - Muestra UNA sola clase de registro, 'Alta'. El tablero grande existe para
    dudar en voz alta -'Por revisar', 'Otra emergencia', 'Ordinaria'-; este es
    para publicar hacia afuera, y ahi lo que no esta confirmado no se muestra.
    Incluye lo que una persona marco como relacionado en revisiones.csv, porque
    el colector ya lo sube a 'Alta' antes de llegar aqui.

Lo escribe colector.py al final de cada corrida, asi que se actualiza solo cada
doce horas junto con el resto. No se edita a mano: lo que se edita es este
archivo.
"""

import io
import json
import os

# Los seis grupos que pidio el usuario, en el orden en que se muestran. La llave
# es la que viaja en el dato; el rotulo es lo que se lee en pantalla.
#
# Ojo con el ultimo: 'Otras entidades del Valle' del colector NO es lo mismo que
# "municipios y alcaldias del Valle". Ahi caben tambien hospitales, instituciones
# educativas, camaras de comercio y personerias. Se separan por el nombre de la
# entidad, que es lo unico que lo dice, y lo que no es alcaldia ni municipio se
# va a 'Otros' -igual que se hizo en el Excel de agosto, a peticion del usuario.
GRUPOS = [
    ("cali", "Alcaldía de Cali y sus dependencias"),
    ("gobernacion", "Gobernación del Valle y sus dependencias"),
    ("desc_cali", "Descentralizadas de Cali"),
    ("desc_gob", "Descentralizadas de la Gobernación"),
    ("municipios", "Municipios y alcaldías del Valle"),
    ("otros", "Otras entidades y otras regiones"),
]

# Palabras con las que una entidad del Valle se declara alcaldia o municipio. Se
# mira el nombre porque la fuente no trae ningun campo que distinga una alcaldia
# de un hospital: 'orden' y 'entidad_centralizada' son autodeclarados y marcan
# "Descentralizada" a la Gobernacion.
MARCAS_MUNICIPIO = ("ALCALDIA", "ALCALDÍA", "MUNICIPIO DE", "MUNICIPIO ",
                    "DISTRITO ESPECIAL", "CONCEJO MUNICIPAL", "PERSONERIA MUNICIPAL",
                    "PERSONERÍA MUNICIPAL")

# Tope duro de la fuente. Comprobado contra la API el 12-sep-2026 sobre toda la
# ventana: en SECOP II 'objeto_del_contrato' y 'descripci_n_del_procedimiento'
# miden como maximo 500 caracteres exactos y 'descripcion_del_proceso' 300. No es
# un recorte nuestro y no hay campo mas largo que pedir; SECOP I no tiene tope
# (el objeto mas largo de la ventana mide 1.417). Cuando un objeto llega justo en
# el tope, la pagina lo dice en vez de hacerlo pasar por completo: un texto
# cortado a mitad de palabra que se presenta como entero desinforma.
TOPE_FUENTE = 500


def _grupo_ligero(reg):
    """Traduce el grupo del colector a uno de los seis del tablero ligero."""
    g = reg.get("grupo") or ""
    if g == "Alcaldía de Cali":
        return "cali"
    if g == "Gobernación del Valle":
        return "gobernacion"
    if g == "Descentralizadas de Cali":
        # La UAESP se cuenta como la Alcaldia, no como descentralizada: decision
        # del usuario del 28-ago-2026, tomada para el Excel de los municipios y
        # conservada aqui para que las dos salidas digan lo mismo.
        nombre = (reg.get("entidad") or "").upper()
        if "UAESP" in nombre or ("SERVICIOS PUBLICOS" in nombre and "SANTIAGO DE CALI" in nombre):
            return "cali"
        return "desc_cali"
    if g == "Descentralizadas de la Gobernación":
        return "desc_gob"
    if g == "Otras entidades del Valle":
        nombre = (reg.get("entidad") or "").upper()
        if any(m in nombre for m in MARCAS_MUNICIPIO):
            return "municipios"
        return "otros"
    return "otros"


def _operaciones(registros):
    """Junta proceso y contrato en una sola operacion, como el tablero grande.

    Un proceso y el contrato que salio de el son el mismo hecho en dos momentos.
    La llave ya viene puesta por emparejar_operaciones(); aqui solo se agrupa.
    """
    por_clave = {}
    for r in registros:
        clave = r.get("operacion") or r.get("id")
        por_clave.setdefault(clave, []).append(r)

    ops = []
    for clave, regs in por_clave.items():
        contrato = next((r for r in regs if r.get("tipo") == "Contrato"), None)
        proceso = next((r for r in regs if r.get("tipo") == "Proceso"), None)
        principal = contrato or proceso or regs[0]
        # Nunca se suma precio base con valor firmado: son la misma plata en dos
        # momentos. Manda el contrato si existe; si no, el precio base del proceso.
        valor = float(principal.get("valor") or 0)
        # El objeto mas largo de los dos, porque cada dataset tiene su propio tope
        # y el del proceso a veces trae mas texto que el del contrato.
        objeto = max((r.get("objeto") or "" for r in regs), key=len)
        ops.append({
            "e": principal.get("entidad") or "",
            "g": _grupo_ligero(principal),
            "o": objeto,
            # Si el objeto llego justo en el tope de la fuente, viene cortado.
            "ot": 1 if len(objeto) >= TOPE_FUENTE else 0,
            "v": valor,
            "f": bool(contrato),                       # firmado
            "d": principal.get("fecha") or "",
            "di": principal.get("fecha_inicio") or "",
            "df": principal.get("fecha_fin") or "",
            "p": (contrato or principal).get("proveedor") or "",
            "m": principal.get("modalidad") or "",
            "tc": principal.get("tipo_contrato") or "Otro",
            "mu": principal.get("municipio") or "",
            "mn": principal.get("municipio_nombre") or "",
            "dp": principal.get("dep_codigo") or "",
            "rc": (contrato or {}).get("referencia") or "",
            "rp": (proceso or {}).get("referencia") or "",
            "uc": (contrato or {}).get("url") or "",
            "up": (proceso or {}).get("url") or "",
        })
    # De mayor a menor valor, como el tablero grande.
    ops.sort(key=lambda o: -o["v"])
    return ops


def _mapa(base):
    """Contornos del mapa, solo lo que el tablero ligero dibuja.

    mapa.json es CODIGO, no dato: lo genera preparar_mapa.py a mano con los
    contornos del DANE. Si falta, la seccion del mapa se omite y el resto del
    tablero funciona igual: es preferible una pagina sin mapa a una pagina rota.
    """
    ruta = os.path.join(base, "mapa.json")
    if not os.path.exists(ruta):
        return None
    with io.open(ruta, encoding="utf-8") as fh:
        m = json.load(fh)
    # Solo los dos lienzos. Lo demas son notas para quien lea el archivo, y aqui
    # cada byte viaja dentro del HTML.
    return {"pais": m.get("pais"), "valle": m.get("valle")}


def escribir(payload, base, destino=None):
    """Escribe ligero.html junto al index. Devuelve la ruta, o None si no pudo."""
    registros = [r for r in payload.get("registros", []) if r.get("nivel") == "Alta"]
    ops = _operaciones(registros)
    mapa = _mapa(base)

    datos = {
        "generado": payload.get("generado", ""),
        "evento": payload.get("fecha_evento", ""),
        "desde": payload.get("fecha_inicio", ""),
        "grupos": [{"k": k, "n": n} for k, n in GRUPOS],
        "ops": ops,
        "mapa": mapa or {},
    }
    # separators sin espacios: son cientos de operaciones y cada byte viaja en el
    # HTML.
    crudo = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    # </script> dentro de una cadena JSON cerraria la etiqueta antes de tiempo y
    # el navegador se comeria el resto de la pagina. Pasa de verdad: hay objetos
    # contractuales pegados desde un PDF con marcado dentro.
    crudo = crudo.replace("</", "<\\/")

    html = PLANTILLA.replace("__DATOS__", crudo)
    destino = destino or os.path.join(base, "ligero.html")
    with io.open(destino, "w", encoding="utf-8", newline="") as fh:
        fh.write(html)
    return destino


PLANTILLA = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Contratación pública · Sismo 10 de agosto de 2026</title>
<style>
/* La piel NO es la del tablero grande: es la de estebanoliveros.com, que es donde
   esto se incrusta. Un tablero verde azulado sobre una pagina blanca y verde
   hierba se ve como lo que seria, un cuerpo extrano metido con calzador.
   Medido sobre el sitio: fondo blanco, verde de marca rgb(86,168,0), gris claro
   #E8E6E6, texto negro y cuerpo en Helvetica/Arial.
   La tipografia de titulares del sitio es Cocosharp, con licencia de Wix, que no
   se puede incrustar aqui; el cuerpo si coincide exacto, porque el propio sitio
   cae en Helvetica. Se mantiene la pila del sistema y la identidad la llevan el
   color y la geometria: cero peticiones a terceros. */
:root{
  color-scheme:light;
  --fondo:#FFFFFF; --panel:#FFFFFF; --panel-2:#F3F5F0; --borde:#E0E0E0;
  --texto:#1A1A1A; --texto-2:#444444; --suave:#767676;
  --acento:#56A800;          /* el verde de marca, para rellenos */
  --acento-tinta:#3E7C00;    /* el mismo, oscurecido, para TEXTO sobre blanco:
                                #56A800 sobre blanco se queda en 3,3:1 */
  --alta:#56A800; --abierta:#B8791A;
  --m0:#ECECEC; --m1:#DDEFCA; --m2:#AEDA8B; --m3:#74BA3B; --m4:#3E7C00;
  --mp:#D9A441; --m-borde:#FFFFFF;
}
/* Sin modo oscuro, a proposito. La pagina que lo aloja es blanca y solo blanca:
   un recuadro oscuro en mitad de ella no se leeria como parte del sitio sino
   como un fallo. Por eso tambien el color-scheme:light de arriba, o el navegador
   pinta los <select> en oscuro por su cuenta. */
*{box-sizing:border-box}
body{margin:0;background:var(--fondo);color:var(--texto);
     font:14px/1.55 "Helvetica Neue",Helvetica,Arial,sans-serif;
     -webkit-text-size-adjust:100%}
.env{max-width:1180px;margin:0 auto;padding:18px 16px 48px}
h1{font-size:21px;margin:0 0 6px;font-weight:700;letter-spacing:-.01em;text-wrap:balance}
h2{font-size:12px;margin:0 0 10px;font-weight:700;letter-spacing:.09em;
   text-transform:uppercase;color:var(--acento-tinta)}
a{color:var(--acento-tinta)}
:focus-visible{outline:2px solid var(--acento);outline-offset:2px}
.sub{color:var(--texto-2);font-size:12.5px;line-height:1.45}
header{border-bottom:3px solid var(--acento);padding-bottom:14px;margin-bottom:16px}
.sello{margin-top:8px;font-size:11.5px;color:var(--suave);
       font-family:ui-monospace,Consolas,monospace}
/* position:relative para que el panel de casillas se ancle aqui, al bloque entero,
   y overflow visible para que no lo recorte: las dos trampas que ya se pagaron en
   el tablero grande. */
.panel{background:var(--panel);border:1px solid var(--borde);border-radius:3px;
       padding:14px;margin-bottom:16px;position:relative;overflow:visible}

/* ---- Ayuda desplegable ---- */
.guia{border:1px solid var(--borde);border-radius:3px;margin-bottom:16px;
      background:var(--panel-2)}
.guia summary{cursor:pointer;padding:11px 14px;font-weight:700;font-size:13.5px;
      list-style:none;display:flex;align-items:center;gap:8px}
.guia summary::-webkit-details-marker{display:none}
.guia summary::before{content:"?";flex:0 0 auto;width:18px;height:18px;
      border-radius:50%;background:var(--acento);color:#fff;font-size:12px;
      display:grid;place-items:center;font-weight:700}
.guia[open] summary{border-bottom:1px solid var(--borde)}
.guia .cuerpo{padding:4px 14px 14px;background:var(--panel)}
.guia h3{font-size:12px;margin:14px 0 6px;letter-spacing:.07em;text-transform:uppercase;
      color:var(--suave);font-weight:700}
.guia ol,.guia ul{margin:0;padding-left:20px;font-size:13.5px;line-height:1.6;
      color:var(--texto-2)}
.guia li{margin-bottom:4px}
.guia dl{margin:0;font-size:13.5px;line-height:1.55;display:grid;gap:6px 14px;
      grid-template-columns:1fr}
@media(min-width:620px){.guia dl{grid-template-columns:auto 1fr}}
.guia dt{font-weight:700;color:var(--texto)}
.guia dd{margin:0;color:var(--texto-2)}

/* ---- Filtros ---- */
.filtros{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(190px,1fr))}
.campo{display:flex;flex-direction:column;gap:4px;min-width:0}
label{font-size:10.5px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;
      color:var(--suave)}
.rotulo{display:flex;align-items:center;gap:6px}
/* La (i) abre la explicacion por CLIC y no por hover: en el telefono no hay
   hover, y un tooltip que solo existe con raton no existe para la mitad de los
   lectores. */
.info{flex:0 0 auto;width:16px;height:16px;border-radius:50%;border:1px solid var(--borde);
      background:var(--panel);color:var(--suave);font-size:10.5px;font-weight:700;
      line-height:1;cursor:pointer;padding:0;display:grid;place-items:center;
      font-family:Georgia,serif;font-style:italic}
.info:hover,.info[aria-expanded="true"]{border-color:var(--acento);color:var(--acento-tinta)}
.ayuda{font-size:12px;line-height:1.45;color:var(--texto-2);background:var(--panel-2);
      border-left:2px solid var(--acento);padding:7px 9px;margin:2px 0 0}
select,input[type=search]{font:inherit;font-size:13px;padding:6px 8px;border-radius:3px;
      border:1px solid var(--borde);background:var(--panel);color:var(--texto);
      width:100%;min-width:0}
/* Desplegable de varias casillas. El panel se ancla al BLOQUE de filtros y no a su
   columna: anclado a la columna, de unos 190px, los rotulos largos se parten en
   cuatro renglones. Y el bloque no puede recortar, o el panel se corta en seco. */
.multi{position:static}
.multi summary{font-size:13px;padding:6px 8px;border:1px solid var(--borde);
      border-radius:3px;background:var(--panel);cursor:pointer;list-style:none;
      display:flex;align-items:center;justify-content:space-between;gap:6px}
.multi summary::-webkit-details-marker{display:none}
.multi summary::after{content:"▾";color:var(--suave);font-size:11px;flex:0 0 auto}
.multi[open] summary{border-color:var(--acento)}
.multi-panel{position:absolute;left:14px;right:14px;top:auto;z-index:20;margin-top:4px;
      background:var(--panel);border:1px solid var(--acento);border-radius:3px;
      padding:10px;box-shadow:0 4px 14px rgba(0,0,0,.1);
      display:grid;gap:6px;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));
      max-height:52vh;overflow:auto}
.multi-panel label{display:flex;align-items:center;gap:8px;font-size:13px;font-weight:400;
      letter-spacing:0;text-transform:none;color:var(--texto);cursor:pointer;
      padding:4px 5px;border-radius:3px}
.multi-panel label:hover{background:var(--panel-2)}
.multi-panel input{accent-color:var(--acento);width:15px;height:15px;margin:0;flex:0 0 auto}
.campo.marca{justify-content:flex-start}
.casilla{display:flex;align-items:center;gap:7px;font-size:13px;font-weight:400;
      letter-spacing:0;text-transform:none;color:var(--texto);cursor:pointer;
      padding-top:4px}
.casilla input{accent-color:var(--acento);width:15px;height:15px;margin:0;flex:0 0 auto}
.acciones{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:12px}
button{font:inherit;font-size:12.5px;padding:6px 11px;border-radius:3px;cursor:pointer;
      border:1px solid var(--borde);background:var(--panel-2);color:var(--texto)}
button:hover{border-color:var(--acento)}
button.principal{background:var(--acento);border-color:var(--acento);color:#fff;font-weight:700}
button.principal:hover{background:var(--acento-tinta);border-color:var(--acento-tinta)}

/* Territorio elegido en el mapa */
.chip{display:inline-flex;align-items:center;gap:7px;font-size:12.5px;
      background:var(--panel-2);border:1px solid var(--acento);border-radius:3px;
      padding:4px 6px 4px 10px;color:var(--texto)}
.chip b{font-weight:700}
.chip button{border:0;background:none;padding:0 3px;font-size:15px;line-height:1;
      color:var(--suave);cursor:pointer}
.chip button:hover{color:var(--acento-tinta)}

/* ---- Resumen ---- */
.cuenta{font-size:13px;color:var(--texto-2);margin:14px 0 8px}
.cuenta b{color:var(--texto);font-weight:700}

/* ---- Tabla ---- */
.marco{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:0;background:var(--panel-2);color:var(--acento-tinta);
   font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;font-weight:700;
   border-bottom:1px solid var(--borde);white-space:nowrap}
th.fijo{padding:8px 10px}
/* El encabezado ordenable es un <button> de verdad dentro del <th>, no un th con
   onclick: asi llega por tabulador y el lector de pantalla lo anuncia como algo
   que se pulsa. */
th .orden{font:inherit;color:inherit;background:none;border:0;border-radius:0;
   padding:8px 10px;width:100%;text-align:inherit;cursor:pointer;
   display:flex;align-items:center;gap:5px;text-transform:inherit;letter-spacing:inherit}
th.num .orden{justify-content:flex-end}
th .orden:hover{background:var(--borde)}
th .orden i{font-style:normal;font-size:9px;color:var(--suave);opacity:.45}
th .orden[data-dir] i{opacity:1;color:var(--acento-tinta)}
th .orden i::before{content:"▲▼"}
th .orden[data-dir="asc"] i::before{content:"▲"}
th .orden[data-dir="desc"] i::before{content:"▼"}
td{padding:10px;border-bottom:1px solid var(--borde);vertical-align:top}
tbody tr:hover{background:var(--panel-2)}
.num{text-align:right;font-family:ui-monospace,Consolas,monospace;
     font-variant-numeric:tabular-nums;white-space:nowrap}
.ent{font-weight:700;margin-bottom:3px}
/* El objeto va COMPLETO, sin truncar por nuestra parte: es el texto por el que se
   juzga si una contratacion tiene que ver con el sismo. */
.obj{color:var(--texto-2);line-height:1.45;margin-bottom:5px}
.cortado{font-size:11.5px;color:var(--abierta);margin:-2px 0 6px}
.pie{font-size:11.5px;color:var(--suave)}
.refs{margin-top:4px;display:flex;flex-wrap:wrap;gap:5px}
.ref{font-family:ui-monospace,Consolas,monospace;font-size:11px;
     background:var(--panel-2);border:1px solid var(--borde);border-radius:2px;
     padding:1px 5px;color:var(--texto-2)}
.est{font-family:ui-monospace,Consolas,monospace;font-size:10.5px;font-weight:500;
     letter-spacing:.04em;text-transform:uppercase;padding:2px 6px;border-radius:2px;
     display:inline-block;white-space:nowrap}
.est-f{background:var(--alta);color:#fff}
.est-a{background:transparent;color:var(--abierta);border:1px solid var(--abierta)}
.menor{font-size:11.5px;color:var(--suave);margin-top:4px}
.enl{display:inline-block;font-size:11.5px;padding:4px 8px;border-radius:3px;
     border:1px solid var(--borde);text-decoration:none;color:var(--texto);
     white-space:nowrap;margin:0 4px 4px 0}
.enl:hover{border-color:var(--acento);color:var(--acento-tinta)}
/* Compartir */
.compartir{display:flex;flex-wrap:wrap;gap:4px;margin-top:7px}
.compartir button{font-size:11px;padding:3px 8px;border-radius:3px;line-height:1.5}
.compartir .rot{font-size:10px;letter-spacing:.08em;text-transform:uppercase;
     color:var(--suave);width:100%;margin-bottom:1px}
.vacio{padding:26px 10px;text-align:center;color:var(--suave);line-height:1.6}
.pag{display:flex;gap:8px;align-items:center;justify-content:center;margin-top:14px;
     font-size:12.5px;color:var(--texto-2)}
/* Banda de grupo. Agrupar es ORDENAR, no pintar distinto. */
tbody tr.banda:hover{background:var(--panel-2)}
td.banda{background:var(--panel-2);border-bottom:1px solid var(--borde);padding:9px 10px}
td.banda .quien{font-weight:700;font-size:13px}
td.banda .cuanto{font-family:ui-monospace,Consolas,monospace;font-size:11.5px;
      color:var(--texto-2);margin-top:2px}
td.banda .sigue{font-size:11.5px;color:var(--suave);font-style:italic}

/* ---- Mapas ---- */
.mapas{display:grid;gap:18px;grid-template-columns:repeat(auto-fit,minmax(290px,1fr))}
.mapas figure{margin:0;min-width:0}
figcaption{font-family:ui-monospace,Consolas,monospace;font-size:10.5px;
     letter-spacing:.09em;text-transform:uppercase;color:var(--suave);margin-bottom:6px}
.lienzo svg{width:100%;height:auto;display:block;max-height:58vh}
/* El filete entre piezas es del color del fondo, no gris: asi las fronteras se
   leen como separacion y no como un dato mas. */
.lienzo path{stroke:var(--m-borde);stroke-width:.8;stroke-linejoin:round;cursor:pointer}
.lienzo path:hover{stroke:var(--texto);stroke-width:1.6}
.lienzo path:focus-visible{stroke:var(--texto);stroke-width:2;outline:none}
.lienzo path.sel{stroke:var(--texto);stroke-width:2.6}
.lienzo .m0{fill:var(--m0)}.lienzo .m1{fill:var(--m1)}.lienzo .m2{fill:var(--m2)}
.lienzo .m3{fill:var(--m3)}.lienzo .m4{fill:var(--m4)}.lienzo .mp{fill:var(--mp)}
/* Halo del color del panel debajo del relleno de la letra -paint-order:stroke
   pinta el borde DEBAJO, que si no se come el trazo-. */
.lienzo .etq{fill:var(--texto-2);text-anchor:middle;dominant-baseline:middle;
     font-family:"Helvetica Neue",Helvetica,Arial,sans-serif;font-weight:600;
     paint-order:stroke;stroke:var(--panel);stroke-width:3.5;stroke-linejoin:round;
     pointer-events:none}
.lienzo .etq .cifra{font-family:ui-monospace,Consolas,monospace;font-weight:600;
     fill:var(--acento-tinta)}
.leyenda{display:flex;flex-wrap:wrap;gap:4px 12px;align-items:center;font-size:11.5px;
     color:var(--texto-2);margin-top:8px}
.leyenda span{display:inline-flex;align-items:center;gap:5px;
     font-family:ui-monospace,Consolas,monospace}
.leyenda i{width:13px;height:13px;border-radius:2px;border:1px solid var(--borde);
     display:inline-block}
.nota{margin-top:10px;font-size:11.5px;color:var(--suave);line-height:1.55;max-width:80ch}

/* ---- Aviso flotante (copiado al portapapeles) ---- */
.aviso{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);
   background:var(--texto);color:#fff;font-size:13px;padding:10px 16px;border-radius:4px;
   z-index:50;max-width:88vw;text-align:center;box-shadow:0 2px 10px rgba(0,0,0,.25)}

/* ---- Informe impreso / PDF ------------------------------------------- */
#impresion{display:none}
@media print{
  .env{display:none!important}
  #impresion{display:block!important;padding:0}
  body{background:#fff;color:#000;font-size:10pt}
  @page{margin:14mm 12mm}
  #impresion h1{font-size:15pt;margin:0 0 4pt}
  #impresion .sub,#impresion .sello{font-size:8pt;color:#444}
  #impresion .aplicados{font-size:8.5pt;border:1pt solid #bbb;padding:6pt 8pt;
      margin:8pt 0 10pt;background:#f6f6f2}
  #impresion table{width:100%;border-collapse:collapse;font-size:8.5pt}
  #impresion th{background:#eee;border-bottom:1pt solid #999;text-align:left;
      padding:4pt 5pt;font-size:7.5pt;text-transform:uppercase;letter-spacing:.06em}
  #impresion td{border-bottom:.5pt solid #ddd;padding:5pt;vertical-align:top}
  #impresion tr{break-inside:avoid}
  #impresion .mapas-papel{display:flex;gap:10mm;margin:6pt 0 12pt;break-inside:avoid}
  #impresion .mapas-papel figure{flex:1;margin:0}
  #impresion .mapas-papel svg{width:100%;height:auto;max-height:95mm}
  /* El informe necesita SUS PROPIAS reglas de relleno: las de pantalla cuelgan de
     .lienzo y dentro de #impresion no hay ningun .lienzo, asi que los mapas
     salian enteros en negro -el relleno por defecto de un <path>-. */
  #impresion .mapas-papel path{stroke:#fff;stroke-width:.8;stroke-linejoin:round}
  #impresion .mapas-papel .m0{fill:#ECECEC}
  #impresion .mapas-papel .m1{fill:#DDEFCA}
  #impresion .mapas-papel .m2{fill:#AEDA8B}
  #impresion .mapas-papel .m3{fill:#74BA3B}
  #impresion .mapas-papel .m4{fill:#3E7C00}
  #impresion .mapas-papel .mp{fill:#D9A441}
  #impresion .mapas-papel .etq{fill:#1a1a1a;text-anchor:middle;dominant-baseline:middle;
      paint-order:stroke;stroke:#fff;stroke-width:3.5;stroke-linejoin:round;
      font-family:Helvetica,Arial,sans-serif;font-weight:600}
  #impresion .mapas-papel .etq .cifra{fill:#2E5C08;font-weight:700}
  #impresion .fechas{color:#333;line-height:1.5}
  /* El enlace tiene que parecer un boton en el papel y seguir siendo pulsable en
     el PDF. Se conserva el subrayado fuera del recuadro para que se note que es
     un enlace incluso impreso en blanco y negro. */
  #impresion .enlaces{margin-top:4pt;display:flex;gap:4pt;flex-wrap:wrap}
  #impresion a.ir{display:inline-block;border:.75pt solid #3E7C00;color:#2E5C08;
      text-decoration:none;padding:2pt 5pt;border-radius:2pt;font-size:7.5pt;
      white-space:nowrap;font-weight:bold}
  #impresion .ley-papel{font-size:7.5pt;color:#444;margin-top:3pt}
  #impresion .ley-papel i{display:inline-block;width:9pt;height:9pt;border:.5pt solid #999;
      vertical-align:-1pt;margin-right:3pt}
  /* Sin esto el navegador descarta los rellenos al imprimir y el mapa sale blanco. */
  *{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}
}

@media (max-width:640px){
  .env{padding:14px 11px 40px}
  h1{font-size:17px}
  /* La tabla se vuelve tarjetas: seis columnas en 360px son ilegibles. */
  thead{display:none}
  tbody tr{display:block;border:1px solid var(--borde);border-radius:3px;
           margin-bottom:10px;background:var(--panel)}
  tbody td{display:block;border:0;padding:8px 10px}
  tbody td:first-child{border-bottom:1px solid var(--borde)}
  td.num{text-align:left}
  td[data-etq]::before{content:attr(data-etq);display:block;font-size:10px;
           letter-spacing:.09em;text-transform:uppercase;color:var(--suave);
           margin-bottom:3px}
  /* La banda de grupo no es una tarjeta mas: tiene que leerse como el encabezado
     de las que vienen debajo, o se confunde con una operacion. */
  tbody tr.banda{border:0;background:none;margin:16px 0 6px}
  tbody tr.banda td.banda{border-bottom:2px solid var(--acento);padding:6px 2px}
}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style>
</head>
<body>
<div class="env">

<header>
  <h1>Contratación pública relacionada con el sismo del 10 de agosto de 2026 · Cali,
      Valle del Cauca y nacional</h1>
  <div class="sub">
    Fuente: datos.gov.co — SECOP II (contratos <code>jbjy-vk9h</code> y procesos
    <code>p6dx-8zbt</code>) y SECOP I (procesos de compra pública <code>f789-7hwg</code>).
  </div>
  <div class="sello" id="sello"></div>
</header>

<details class="guia">
  <summary>Cómo usar este tablero y qué significa cada cosa</summary>
  <div class="cuerpo">
    <h3>En tres pasos</h3>
    <ol>
      <li><b>Elija un territorio en el mapa.</b> Pulse un municipio del Valle o un
      departamento del país y la tabla de abajo se queda solo con lo de ese sitio. Vuelva
      a pulsarlo para quitar la selección.</li>
      <li><b>Afine con los filtros.</b> Se combinan entre sí: entidad, estado y rango de
      monto se aplican a la vez. Cada filtro tiene una <b>(i)</b> que explica qué hace.</li>
      <li><b>Compruebe en la fuente.</b> Cada fila trae el número con que la entidad
      identifica el contrato y un botón que abre el expediente en SECOP. Nada de lo que
      aparece aquí hay que creérselo: está para verificarse.</li>
    </ol>

    <h3>Convenciones</h3>
    <dl>
      <dt>Operación</dt>
      <dd>Un proceso y el contrato que salió de él, contados <b>una sola vez</b>. La fuente
      los publica por separado y sumarlos contaría dos veces la misma plata.</dd>

      <dt>Contratada</dt>
      <dd>Ya hay contrato firmado. La cifra que se muestra es el <b>valor firmado</b>.</dd>

      <dt>Abierta</dt>
      <dd>El proceso está publicado pero todavía no hay contrato. La cifra es el
      <b>precio base</b>, que es un estimado y no lo que se pagará. Precio base y valor
      firmado <b>nunca se suman</b>: son la misma plata en dos momentos.</dd>

      <dt>Objeto</dt>
      <dd>Lo que se contrató, con las palabras de la entidad. SECOP II lo recorta a 500
      caracteres; cuando llega en ese tope la fila lo advierte y el texto entero está en
      el expediente.</dd>

      <dt>Contratista</dt>
      <dd>Quién recibe la plata. En un proceso abierto todavía no hay.</dd>

      <dt>Municipio</dt>
      <dd>El de la <b>entidad que contrata</b>, no el de la obra. El dato que publica SECOP
      es el domicilio de la entidad, y a veces se contrata desde una ciudad para otra.</dd>

      <dt>Entidad contratante</dt>
      <dd>El grupo al que pertenece: Alcaldía de Cali, Gobernación del Valle, sus
      descentralizadas, los municipios del Valle, o el resto del país.</dd>

      <dt>Recolección</dt>
      <dd>Fecha y hora en que se consultó la fuente por última vez. Se actualiza dos veces
      al día.</dd>
    </dl>

    <h3>Qué NO está aquí</h3>
    <ul>
      <li>Solo aparece la contratación <b>ya confirmada</b> como atención de la emergencia.
      Lo que está en duda no se publica hasta que una persona lo revise.</li>
      <li>La contratación ordinaria, la que no tiene que ver con el sismo, queda fuera.</li>
    </ul>
  </div>
</details>

<section class="panel" id="sec-mapas">
  <div class="rotulo" style="margin-bottom:8px">
    <h2 style="margin:0">Dónde se está contratando</h2>
    <button class="info" type="button" data-para="ay-mapa" aria-expanded="false"
            aria-controls="ay-mapa" aria-label="Cómo funciona el mapa">i</button>
  </div>
  <p class="ayuda" id="ay-mapa" hidden>Pulse cualquier municipio del Valle o cualquier
  departamento del país y la tabla de abajo se queda solo con la contratación de ese
  territorio. El mapa sigue mostrando las cifras de todos los demás, para poder comparar y
  cambiar de selección; el que está elegido va con borde grueso. Pulse otra vez para
  quitarlo.</p>
  <div class="mapas">
    <figure>
      <figcaption>Valle del Cauca · por municipio</figcaption>
      <div class="lienzo" id="mapa-valle"></div>
      <div class="leyenda" id="ley-valle"></div>
    </figure>
    <figure>
      <figcaption>Colombia · por departamento</figcaption>
      <div class="lienzo" id="mapa-pais"></div>
      <div class="leyenda" id="ley-pais"></div>
    </figure>
  </div>
  <p class="nota">
    Los mapas pintan el municipio de la <b>entidad que contrata</b>, no dónde se ejecuta:
    el campo de SECOP es el domicilio de la entidad. El color va por el valor ya
    contratado; el ámbar marca los territorios donde solo hay procesos sin firmar.
    <span id="nota-sitio"></span>
  </p>
</section>

<section class="panel">
  <h2>Filtros</h2>
  <div class="filtros">
    <div class="campo">
      <div class="rotulo"><label for="f-buscar">Buscar</label>
        <button class="info" type="button" data-para="ay-buscar" aria-expanded="false"
                aria-controls="ay-buscar" aria-label="Qué hace este filtro">i</button></div>
      <input type="search" id="f-buscar" placeholder="objeto, entidad, contratista, número…">
      <p class="ayuda" id="ay-buscar" hidden>Busca dentro del objeto, el nombre de la
      entidad, el del contratista, el municipio y los dos números de SECOP. No distingue
      tildes ni mayúsculas.</p>
    </div>
    <div class="campo">
      <div class="rotulo"><label for="res-nivel">Nivel de gobierno</label>
        <button class="info" type="button" data-para="ay-grupo" aria-expanded="false"
                aria-controls="ay-grupo" aria-label="Qué hace este filtro">i</button></div>
      <!-- Casillas dentro de un <details>, no un <select multiple>: el nativo obliga a
           Ctrl+clic y en el teléfono es inmanejable. Misma decisión que el tablero grande. -->
      <details class="multi" id="f-nivel">
        <summary id="res-nivel">Todos</summary>
        <div class="multi-panel" id="lista-nivel"></div>
      </details>
      <p class="ayuda" id="ay-grupo" hidden>Se pueden marcar <b>varios a la vez</b>: sin
      ninguno marcado se ven todos. El número entre paréntesis es cuántas operaciones tiene
      cada nivel; si dice (0), está vigilado y no ha contratado nada del sismo, que es un
      hallazgo y no un dato que falte.</p>
    </div>
    <div class="campo">
      <div class="rotulo"><label for="f-entidad">Entidad</label>
        <button class="info" type="button" data-para="ay-entidad" aria-expanded="false"
                aria-controls="ay-entidad" aria-label="Qué hace este filtro">i</button></div>
      <select id="f-entidad"><option value="">Todas</option></select>
      <p class="ayuda" id="ay-entidad" hidden>Una entidad concreta, con el nombre exacto con
      que publica en SECOP. Solo aparecen las que tienen contratación confirmada del
      sismo.</p>
    </div>
    <div class="campo">
      <div class="rotulo"><label for="f-mun">Municipio</label>
        <button class="info" type="button" data-para="ay-mun" aria-expanded="false"
                aria-controls="ay-mun" aria-label="Qué hace este filtro">i</button></div>
      <select id="f-mun"><option value="">Todos</option></select>
      <p class="ayuda" id="ay-mun" hidden>El municipio donde tiene su sede la entidad que
      contrata, no necesariamente donde se ejecuta la obra. Es lo mismo que se elige
      pulsando el mapa.</p>
    </div>
    <div class="campo">
      <div class="rotulo"><label for="f-estado">Estado</label>
        <button class="info" type="button" data-para="ay-estado" aria-expanded="false"
                aria-controls="ay-estado" aria-label="Qué hace este filtro">i</button></div>
      <select id="f-estado">
        <option value="">Contratadas y abiertas</option>
        <option value="f">Solo ya contratadas</option>
        <option value="a">Solo aún sin contratar</option>
      </select>
      <p class="ayuda" id="ay-estado" hidden><b>Contratada</b>: ya hay contrato firmado y la
      cifra es el valor firmado. <b>Abierta</b>: el proceso está publicado y la cifra es el
      precio base, un estimado que puede cambiar.</p>
    </div>
    <div class="campo">
      <div class="rotulo"><label for="f-monto">Rango de monto</label>
        <button class="info" type="button" data-para="ay-monto" aria-expanded="false"
                aria-controls="ay-monto" aria-label="Qué hace este filtro">i</button></div>
      <select id="f-monto">
        <option value="">Cualquier monto</option>
        <option value="0-10">Menos de $10 millones</option>
        <option value="10-50">$10 a $50 millones</option>
        <option value="50-200">$50 a $200 millones</option>
        <option value="200-500">$200 a $500 millones</option>
        <option value="500-1000">$500 millones a $1.000 millones</option>
        <option value="1000-">Más de $1.000 millones</option>
      </select>
      <p class="ayuda" id="ay-monto" hidden>Filtra por el valor de la operación: el valor
      firmado si ya hay contrato, el precio base si sigue abierta. Los topes son
      inclusivos por abajo y exclusivos por arriba.</p>
    </div>
    <div class="campo">
      <div class="rotulo"><label for="f-tipo">Tipo de contrato</label>
        <button class="info" type="button" data-para="ay-tipo" aria-expanded="false"
                aria-controls="ay-tipo" aria-label="Qué hace este filtro">i</button></div>
      <select id="f-tipo">
        <option value="">Todos los tipos</option>
        <option value="!ps">Sin prestación de servicios</option>
      </select>
      <p class="ayuda" id="ay-tipo" hidden>La <b>prestación de servicios</b> es el tipo más
      numeroso y a veces se quiere ver el resto por aparte. <b>Aquí solo se oculta, no se
      descarta</b>: todo contrato cuyo objeto se relacione con el sismo está en el tablero
      salvo que una persona lo haya revisado y descartado.</p>
    </div>
    <div class="campo">
      <div class="rotulo"><label for="f-orden">Ordenar por</label>
        <button class="info" type="button" data-para="ay-orden" aria-expanded="false"
                aria-controls="ay-orden" aria-label="Qué hace este control">i</button></div>
      <select id="f-orden">
        <option value="valor-desc">Valor, de mayor a menor</option>
        <option value="valor-asc">Valor, de menor a mayor</option>
        <option value="fecha-desc">Fecha, de la más reciente</option>
        <option value="fecha-asc">Fecha, de la más antigua</option>
        <option value="entidad-asc">Entidad, A–Z</option>
        <option value="contratista-asc">Contratista, A–Z</option>
      </select>
      <p class="ayuda" id="ay-orden" hidden>Es lo mismo que pulsar el encabezado de una
      columna en el computador; en el teléfono los encabezados no se ven, y por eso está
      aquí. Con <b>agrupar por entidad</b> marcado, el orden manda igual: las entidades
      quedan donde caiga su primera operación, así que «valor de mayor a menor» pone
      arriba a la del contrato más grande.</p>
    </div>
    <div class="campo marca">
      <div class="rotulo"><label for="f-agrupar">Presentación</label>
        <button class="info" type="button" data-para="ay-agrupar" aria-expanded="false"
                aria-controls="ay-agrupar" aria-label="Qué hace esta opción">i</button></div>
      <label class="casilla"><input type="checkbox" id="f-agrupar" checked>
        Agrupar por entidad</label>
      <p class="ayuda" id="ay-agrupar" hidden>Pone juntas las operaciones de cada entidad,
      con una banda que dice cuántas son y cuánto suman, y ordena las entidades de mayor a
      menor. Sin marcar, la tabla va de mayor a menor valor sin agrupar.</p>
    </div>
  </div>
  <div class="acciones">
    <span id="chip-territorio"></span>
    <button id="btn-limpiar">Quitar todos los filtros</button>
    <button id="btn-csv">Descargar CSV</button>
    <button id="btn-pdf" class="principal">Descargar PDF con el mapa</button>
  </div>
</section>

<div class="cuenta" id="cuenta"></div>

<section class="marco">
  <table>
    <thead><tr>
      <th><button type="button" class="orden" data-col="fecha">Estado<i></i></button></th>
      <th><button type="button" class="orden" data-col="entidad">Qué y quién<i></i></button></th>
      <th class="num"><button type="button" class="orden" data-col="valor">Valor<i></i></button></th>
      <th><button type="button" class="orden" data-col="contratista">Contratista<i></i></button></th>
      <th class="fijo">SECOP y compartir</th>
    </tr></thead>
    <tbody id="cuerpo"></tbody>
  </table>
</section>
<div class="pag" id="pag"></div>

<p class="nota">
  Una operación es un proceso y el contrato que salió de él, contados una sola vez.
  Nunca se suma precio base con valor firmado: la operación muestra el valor firmado
  si hay contrato y el precio base si todavía no, siempre rotulado.
</p>

</div>

<div id="impresion"></div>

<script type="application/json" id="datos">__DATOS__</script>
<script>
"use strict";
var D = JSON.parse(document.getElementById("datos").textContent);
var OPS = D.ops || [];
/* 20 por pagina, como el tablero grande, y ordenadas de mayor a menor valor. En
   el telefono cada fila es una tarjeta con el objeto completo y sube de los 500
   pixeles: veinte ya son catorce mil de recorrido. */
var POR_PAGINA = 20, pagina = 1;

function esc(s){
  return String(s == null ? "" : s).replace(/[&<>"']/g, function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
  });
}
function pesos(v){
  if (!v) return "$ 0";
  return "$ " + Math.round(v).toLocaleString("es-CO");
}
/* Cifras redondas para los titulos del mapa y el resumen: "$ 1.321,9 M" se lee
   de un vistazo y "$ 1.321.917.014" no. */
function corto(v){
  if (v >= 1e9) return "$ " + (v / 1e9).toFixed(1).replace(".", ",") + " mm";
  if (v >= 1e6) return "$ " + Math.round(v / 1e6) + " M";
  return pesos(v);
}
/* El rango va escrito con escapes \u y no con los caracteres combinantes
   literales: literales son bytes invisibles que cualquier copia entre archivos
   puede comerse sin dejar rastro, y entonces la busqueda deja de ignorar tildes
   sin que nada falle. */
function sinTildes(s){
  return String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase();
}
var MESES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto",
             "septiembre","octubre","noviembre","diciembre"];
/* La fecha y hora de la recoleccion, escrita como se lee. Viene como
   "2026-09-13 08:31:04" en hora de Colombia; se parte a mano y no con Date(),
   que sin zona horaria la interpretaria como UTC y la correria cinco horas. */
function selloLargo(s){
  var m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(String(s || ""));
  if (!m) return String(s || "");
  var h = +m[4], ampm = h < 12 ? "a. m." : "p. m.", h12 = h % 12 === 0 ? 12 : h % 12;
  return (+m[3]) + " de " + MESES[(+m[2]) - 1] + " de " + m[1] + ", " +
         h12 + ":" + m[5] + " " + ampm;
}

/* ---- Rangos de monto, en millones ------------------------------------- */
var RANGOS = {
  "0-10":    [0, 10e6],
  "10-50":   [10e6, 50e6],
  "50-200":  [50e6, 200e6],
  "200-500": [200e6, 500e6],
  "500-1000":[500e6, 1000e6],
  "1000-":   [1000e6, Infinity]
};

/* Los niveles de gobierno elegidos. Conjunto vacío = todos, igual que en el
   tablero grande: es la única forma de que "no he tocado nada" y "los he marcado
   todos" no acaben significando cosas distintas. */
var NIVELES = Object.create(null);
function nivelesElegidos(){ return Object.keys(NIVELES); }

var F = {
  buscar: "", entidad: "", mun: "", dep: "", estado: "", monto: "", tipo: "",
  agrupar: true, orden: "valor-desc"
};
var PS = "Prestación de servicios";

function pasa(o){
  var ns = nivelesElegidos();
  if (ns.length && !NIVELES[o.g]) return false;
  if (F.entidad && o.e !== F.entidad) return false;
  if (F.mun && o.mu !== F.mun) return false;
  if (F.dep && o.dp !== F.dep) return false;
  /* "!ps" es "todo menos prestacion de servicios". Cualquier otro valor es un
     tipo concreto. Ocultar no es descartar: lo que se relaciona con el sismo
     sigue en el archivo y en las descargas cuando el filtro esta quitado. */
  if (F.tipo === "!ps"){ if (o.tc === PS) return false; }
  else if (F.tipo && o.tc !== F.tipo) return false;
  if (F.estado === "f" && !o.f) return false;
  if (F.estado === "a" && o.f) return false;
  if (F.monto){
    var r = RANGOS[F.monto];
    if (r && (o.v < r[0] || o.v >= r[1])) return false;
  }
  if (F.buscar){
    var t = sinTildes(o.e + " " + o.o + " " + o.p + " " + o.rc + " " + o.rp + " " + o.mn);
    if (t.indexOf(F.buscar) < 0) return false;
  }
  return true;
}

/* Agrupar por entidad es ORDENAR, no pintar distinto: aqui se devuelven las
   operaciones de cada entidad contiguas y las entidades por lo que suman. Hecho
   asi, la paginacion, el recuento de cabecera, el CSV y el PDF heredan el mismo
   orden sin tocar nada mas; la tabla se limita a intercalar una banda cuando
   cambia el nombre. */
/* Agrupa RESPETANDO el orden que ya trae la lista: cada entidad aparece donde
   aparece su primera operación bajo ese orden, y las suyas quedan contiguas.
   Se probó antes ordenando las entidades por lo que suman y ordenando solo
   dentro de cada bloque, y no servía: casi toda entidad tiene una sola
   operación, así que ordenar por valor no movía nada y el encabezado parecía
   roto. Con esta regla, "valor de mayor a menor" pone arriba a la entidad del
   contrato más grande, que es lo que espera quien pulsa esa columna. La banda
   sigue diciendo el total real de la entidad, así que nada miente. */
function agrupar(ops){
  var bloques = [], indice = Object.create(null);
  ops.forEach(function(o){
    var i = indice[o.e];
    if (i === undefined){ indice[o.e] = bloques.length; bloques.push([o]); }
    else bloques[i].push(o);
  });
  return [].concat.apply([], bloques);
}

/* El orden que pide el lector. Cuando hay agrupacion se aplica DENTRO de cada
   entidad: el orden de las entidades sigue siendo por lo que suman, porque si no,
   pedir "valor de mayor a menor" con agrupar puesto rompería los grupos y la
   banda diria una cosa y las filas otra. La ayuda del control lo dice. */
function comparador(){
  var p = F.orden.split("-"), col = p[0], dir = p[1] === "asc" ? 1 : -1;
  if (col === "valor")   return function(a, b){ return (a.v - b.v) * dir; };
  if (col === "fecha")   return function(a, b){ return String(a.d).localeCompare(String(b.d)) * dir; };
  if (col === "entidad") return function(a, b){ return a.e.localeCompare(b.e) * dir; };
  return function(a, b){
    /* Las que no tienen contratista al final siempre, se ordene como se ordene:
       una lista alfabetica que empieza con doce huecos no informa de nada. */
    if (!a.p && !b.p) return 0;
    if (!a.p) return 1;
    if (!b.p) return -1;
    return a.p.localeCompare(b.p) * dir;
  };
}

function vista(){
  /* Se ordena SIEMPRE primero y se agrupa después. Al revés, la agrupación
     mandaría sobre el orden y pulsar una columna no se notaría. */
  var v = OPS.filter(pasa).sort(comparador());
  return F.agrupar ? agrupar(v) : v;
}
/* Los mapas respetan todos los filtros MENOS el territorio que ellos mismos
   ponen. Si respetaran tambien ese, al elegir un municipio los demas quedarian
   en cero y no habria como cambiar de seleccion: el mapa dejaria de ser un
   control. La pieza elegida muestra la misma cifra que la tabla; las demas
   muestran la suya, y el texto de ayuda del mapa lo dice con esas palabras. */
function vistaMapa(){
  var guardaM = F.mun, guardaD = F.dep;
  F.mun = ""; F.dep = "";
  var v = OPS.filter(pasa);
  F.mun = guardaM; F.dep = guardaD;
  return v;
}

/* ---- Compartir en redes ----------------------------------------------- */
function fechasDe(o){
  var p = [];
  if (o.d) p.push((o.f ? "Firma: " : "Publicado: ") + o.d);
  if (o.di) p.push("Inicio: " + o.di);
  if (o.df) p.push("Termina: " + o.df);
  return p.join(" | ");
}
function recortar(s, n){
  s = String(s || "");
  return s.length <= n ? s : s.slice(0, n - 1).trim() + "…";
}
function mensaje(o){
  var url = o.uc || o.up || location.href;
  var l = ["Nuevo contrato relacionado con la emergencia del sismo del 10 de agosto de 2026.",
           "", "Entidad contratante: " + o.e, "Objeto: " + o.o,
           "Valor: " + pesos(o.v) + (o.f ? " (valor firmado)" : " (precio base)"),
           "Contratista: " + (o.p || "aún sin contratista")];
  var fe = fechasDe(o);
  if (fe) l.push(fe);
  l.push("", "Verifíquelo en SECOP: " + url);
  return l.join("\n");
}
/* X corta en 280 caracteres y cuenta cualquier enlace como 23, pase lo que pase
   con su longitud real. El mensaje largo mide 768: mandarlo sin ajustar deja al
   usuario con la ventana de X llena de texto que no puede publicar. Aqui se
   arma lo fijo primero, se mide, y lo que sobra del presupuesto se le da al
   objeto, que es lo unico elastico. Si ni asi cabe, se recorta el nombre de la
   entidad: el enlace nunca se toca, porque es lo que hace verificable el dato. */
function mensajeX(o){
  var url = o.uc || o.up || location.href;
  var TOPE = 280, ENLACE = 23;
  var ent = recortar(o.e, 70);
  var plata = pesos(o.v) + (o.f ? " (firmado)" : " (precio base)");
  var quien = o.p ? " · " + recortar(o.p, 40) : "";
  var cabeza = "Sismo 10-ago-2026 · " + ent + "\n";
  var cola = "\n" + plata + quien + "\n";
  var libre = TOPE - ENLACE - cabeza.length - cola.length;
  if (libre < 30){                       /* entidad larguisima: se cede ahi */
    ent = recortar(o.e, Math.max(20, 70 - (30 - libre)));
    cabeza = "Sismo 10-ago-2026 · " + ent + "\n";
    libre = TOPE - ENLACE - cabeza.length - cola.length;
  }
  return cabeza + recortar(o.o, Math.max(20, libre)) + cola + url;
}
function abrir(u){ window.open(u, "_blank", "noopener,noreferrer"); }

function compartir(i, red){
  var o = ULTIMA_VISTA[i];
  if (!o) return;
  var url = o.uc || o.up || location.href;
  if (red === "wa") abrir("https://wa.me/?text=" + encodeURIComponent(mensaje(o)));
  else if (red === "x") abrir("https://twitter.com/intent/tweet?text=" +
      encodeURIComponent(mensajeX(o)));
  else if (red === "fb") abrir("https://www.facebook.com/sharer/sharer.php?u=" +
      encodeURIComponent(url) + "&quote=" + encodeURIComponent(mensaje(o)));
  else if (red === "ig") copiar(mensaje(o),
      "Texto copiado. Instagram no permite publicar desde otra página: abra la app, cree la " +
      "historia y pegue el texto.");
}
/* Instagram no tiene forma de recibir una publicacion desde otra pagina -no
   existe una URL de compartir a Stories-, asi que lo honesto es copiar el texto
   y decirlo, en vez de abrir algo que no va a funcionar. */
function copiar(texto, aviso){
  function listo(){ decir(aviso); }
  function falla(){ decir("No se pudo copiar. Seleccione el texto de la fila a mano."); }
  if (navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(texto).then(listo, falla);
  } else {
    var a = document.createElement("textarea");
    a.value = texto; a.style.position = "fixed"; a.style.opacity = "0";
    document.body.appendChild(a); a.select();
    try { document.execCommand("copy"); listo(); } catch (e) { falla(); }
    document.body.removeChild(a);
  }
}
var tempAviso;
function decir(t){
  var v = document.getElementById("aviso");
  if (!v){ v = document.createElement("div"); v.id = "aviso"; v.className = "aviso";
           v.setAttribute("role", "status"); document.body.appendChild(v); }
  v.textContent = t;
  clearTimeout(tempAviso);
  tempAviso = setTimeout(function(){ if (v.parentNode) v.parentNode.removeChild(v); }, 5200);
}

/* ---- Tabla ------------------------------------------------------------ */
var ULTIMA_VISTA = [];

function fila(o, i){
  var refs = [];
  if (o.rp) refs.push('<span class="ref" title="Número del proceso en SECOP">' + esc(o.rp) + "</span>");
  if (o.rc) refs.push('<span class="ref" title="Número del contrato en SECOP">' + esc(o.rc) + "</span>");
  var enl = "";
  if (o.uc) enl += '<a class="enl" href="' + esc(o.uc) + '" target="_blank" rel="noopener">Contrato</a>';
  if (o.up) enl += '<a class="enl" href="' + esc(o.up) + '" target="_blank" rel="noopener">Proceso</a>';
  var fechas = "";
  if (o.di || o.df) fechas = '<div class="menor">' +
      (o.di ? "inicia " + esc(o.di) : "") + (o.di && o.df ? " · " : "") +
      (o.df ? "termina " + esc(o.df) : "") + "</div>";
  var comp = '<div class="compartir"><span class="rot">Compartir</span>' +
    '<button type="button" data-comp="wa" data-i="' + i + '">WhatsApp</button>' +
    '<button type="button" data-comp="x"  data-i="' + i + '">X</button>' +
    '<button type="button" data-comp="fb" data-i="' + i + '">Facebook</button>' +
    '<button type="button" data-comp="ig" data-i="' + i + '">Instagram</button></div>';
  return '<tr>' +
    '<td data-etq="Estado">' +
      (o.f ? '<span class="est est-f">Contratada</span>'
           : '<span class="est est-a">Abierta</span>') +
      '<div class="menor">' + esc(o.d) + "</div>" + fechas + "</td>" +
    '<td data-etq="Qué y quién"><div class="ent">' + esc(o.e) + "</div>" +
      '<div class="obj">' + esc(o.o) + "</div>" +
      (o.ot ? '<div class="cortado">SECOP corta el objeto en 500 caracteres: ' +
              'el texto completo está en el expediente.</div>' : "") +
      '<div class="pie">' + esc(NOMBRE_GRUPO[o.g] || "") +
        (o.mn ? " · " + esc(o.mn) : "") + (o.tc ? " · " + esc(o.tc) : "") +
        (o.m ? " · " + esc(o.m) : "") + "</div>" +
      '<div class="refs">' + refs.join("") + "</div></td>" +
    '<td class="num" data-etq="Valor">' + esc(pesos(o.v)) +
      '<div class="menor">' + (o.f ? "valor firmado" : "precio base") + "</div></td>" +
    '<td data-etq="Contratista">' +
      (o.p ? esc(o.p) : '<span class="menor">aún sin contratista</span>') + "</td>" +
    '<td data-etq="SECOP y compartir">' + (enl || '<span class="menor">sin enlace</span>') +
      comp + "</td></tr>";
}

/* Un cero tiene que decir POR QUE. En este tablero un cero se lee como "no hay
   contratacion del sismo", que es una afirmacion fuerte: el mensaje se redacta
   segun el filtro que este puesto. */
function mensajeVacio(){
  if (F.buscar) return "Ninguna operación coincide con «" + esc(F.buscar.toLowerCase()) +
    "». La búsqueda mira objeto, entidad, contratista, municipio y los dos números de SECOP.";
  if (F.entidad) return "Esa entidad no tiene contratación confirmada del sismo con los demás " +
    "filtros puestos.";
  if (F.estado === "a") return "No hay procesos abiertos sin contratar con estos filtros: " +
    "todo lo que coincide ya está firmado.";
  if (F.estado === "f") return "No hay nada firmado con estos filtros; lo que coincide sigue " +
    "como proceso abierto.";
  if (F.monto) return "Ninguna operación cae en ese rango de monto.";
  if (F.tipo === "!ps") return "Con estos filtros, toda la contratación que queda es de " +
    "prestación de servicios. Quite «Sin prestación de servicios» para verla.";
  if (F.tipo) return "No hay contratación de tipo «" + esc(F.tipo.toLowerCase()) +
    "» con los filtros puestos.";
  if (F.mun || F.dep) return "Ese territorio no tiene contratación confirmada del sismo con " +
    "los filtros puestos.";
  var ns = nivelesElegidos();
  if (ns.length === 1) return "<b>" + esc(NOMBRE_GRUPO[ns[0]] || "Ese nivel") + "</b> no tiene " +
    "contratación confirmada del sismo en la ventana de seguimiento. Está vigilado y su " +
    "contratación se revisa en cada recolección: el cero es un hallazgo, no un dato que falte.";
  if (ns.length) return "Ninguno de los " + ns.length + " niveles de gobierno elegidos tiene " +
    "contratación confirmada del sismo con los demás filtros puestos.";
  return "No hay contratación confirmada del sismo para mostrar.";
}

function resumen(v){
  var total = v.reduce(function(s, o){ return s + o.v; }, 0);
  var firmado = v.filter(function(o){ return o.f; });
  var sumaF = firmado.reduce(function(s, o){ return s + o.v; }, 0);
  /* El desglose Valle / fuera del Valle no es un adorno: sin filtros, mas de la
     mitad de lo firmado es de otros departamentos, y una sola cifra grande se
     leeria como si toda fuera del Valle.
     Pero SOLO sin territorio elegido. El reparto mira el departamento de la
     ENTIDAD y el filtro del mapa mira el MUNICIPIO asignado, y los dos no
     siempre coinciden: la Escuela Nacional del Deporte esta en Cali y SECOP la
     publica en Bogota. Con "municipio: CALI" puesto, la frase salia diciendo
     "$36 M de otras regiones" y se leia como un error del tablero. */
  var reparto = "";
  if (!F.mun && !F.dep){
    var valle = firmado.filter(function(o){ return o.dp === "76"; });
    var sumaValle = valle.reduce(function(s, o){ return s + o.v; }, 0);
    if (sumaValle && sumaValle !== sumaF)
      reparto = " — de eso, <b>" + esc(corto(sumaValle)) +
        "</b> de entidades del Valle del Cauca y " +
        esc(corto(sumaF - sumaValle)) + " de otras regiones";
  }
  return "<b>" + v.length + "</b> operacion" + (v.length === 1 ? "" : "es") +
    " · <b>" + esc(corto(sumaF)) + "</b> ya contratado en " + firmado.length +
    " · " + (v.length - firmado.length) + " aún sin contratar" +
    (v.length - firmado.length ? " por " + esc(corto(total - sumaF)) + " de precio base" : "") +
    reparto;
}

function pintarTabla(){
  var v = vista();
  ULTIMA_VISTA = v;
  document.getElementById("cuenta").innerHTML = resumen(v);

  var paginas = Math.max(1, Math.ceil(v.length / POR_PAGINA));
  if (pagina > paginas) pagina = paginas;
  var desde = (pagina - 1) * POR_PAGINA;
  var trozo = v.slice(desde, pagina * POR_PAGINA);
  var filas = "";
  if (F.agrupar){
    var anterior = null;
    trozo.forEach(function(o, i){
      if (o.e !== anterior){
        /* Si el grupo empieza antes de esta pagina, la banda lo dice. Sin eso,
           media docena de filas quedan bajo un encabezado cuya cuenta no cuadra
           con lo que se ve. */
        var viene = (i === 0 && desde > 0 && v[desde - 1].e === o.e);
        var suyas = v.filter(function(x){ return x.e === o.e; });
        var firm = suyas.filter(function(x){ return x.f; });
        filas += '<tr class="banda"><td class="banda" colspan="5">' +
          '<div class="quien">' + esc(o.e) + "</div>" +
          '<div class="cuanto">' + suyas.length + " operacion" +
            (suyas.length === 1 ? "" : "es") + " · " +
            esc(corto(firm.reduce(function(s, x){ return s + x.v; }, 0))) +
            " ya contratado" +
            (suyas.length - firm.length
              ? " · " + (suyas.length - firm.length) + " sin contratar" : "") +
          "</div>" +
          (viene ? '<div class="sigue">viene de la página anterior</div>' : "") +
          "</td></tr>";
        anterior = o.e;
      }
      filas += fila(o, desde + i);
    });
  } else {
    filas = trozo.map(function(o, i){ return fila(o, desde + i); }).join("");
  }
  document.getElementById("cuerpo").innerHTML = trozo.length
    ? filas
    : '<tr><td colspan="5" class="vacio">' + mensajeVacio() + "</td></tr>";

  document.getElementById("pag").innerHTML = v.length > POR_PAGINA
    ? '<button id="ant"' + (pagina === 1 ? " disabled" : "") + ">Anterior</button>" +
      "<span>página " + pagina + " de " + paginas + "</span>" +
      '<button id="sig"' + (pagina === paginas ? " disabled" : "") + ">Siguiente</button>"
    : "";
  var a = document.getElementById("ant"), s = document.getElementById("sig");
  if (a) a.onclick = function(){ pagina--; pintarTabla(); window.scrollTo(0, 0); };
  if (s) s.onclick = function(){ pagina++; pintarTabla(); window.scrollTo(0, 0); };
}

/* ---- Mapas ------------------------------------------------------------ */
var NOMBRE_GRUPO = {};
(D.grupos || []).forEach(function(g){ NOMBRE_GRUPO[g.k] = g.n; });
var NOMBRE_PIEZA = {};

/* Tramos por cuantiles, no lineales: una sola operacion grande aplastaria a
   todas las demas contra el extremo bajo de cualquier escala lineal. Y el cero
   tiene color propio, fuera de la rampa: "no ha contratado" no es "ha contratado
   poco". */
function tramos(valores){
  var v = valores.filter(function(x){ return x > 0; }).sort(function(a, b){ return a - b; });
  if (!v.length) return [];
  var cortes = [];
  for (var i = 1; i <= 4; i++){
    var c = v[Math.min(v.length - 1, Math.floor(v.length * i / 5))];
    if (!cortes.length || c > cortes[cortes.length - 1]) cortes.push(c);
  }
  return cortes;
}
function clase(valor, cortes, soloAbiertas){
  if (!valor) return soloAbiertas ? "mp" : "m0";
  for (var i = 0; i < cortes.length; i++) if (valor <= cortes[i]) return "m" + (i + 1);
  return "m" + Math.min(4, cortes.length + 1);
}

/* El cuerpo de letra sale del tamano de la pieza: con uno solo, el nombre de un
   municipio pequeno se derrama sobre tres vecinos. La raiz del area porque lo
   que importa es cuanto mide de ancho, no cuanta superficie tiene. */
function letraPieza(a){
  return Math.max(11, Math.min(21, Math.round(Math.sqrt(Number(a) || 0) / 7)));
}

/* Separa las etiquetas que se pisan y luego mete hacia dentro las que se salgan
   por cualquiera de los cuatro lados: San Andres es la esquina noroeste del pais
   y su rotulo centrado se salia por la izquierda y por arriba a la vez.
   Se mide con getBBox() sobre el SVG ya puesto en la pagina, que es lo unico que
   sabe cuanto ocupa de verdad un texto; estimar el ancho por el numero de letras
   deja solapes. Tres pasadas y se corta: un ajuste de etiquetas no puede colgar
   la pagina. */
function separarEtiquetas(svg, ancho, alto){
  var etqs = Array.prototype.slice.call(svg.querySelectorAll("text"))
    .map(function(t){ return {t: t, tam: Number(t.getAttribute("font-size")) || 12}; })
    .sort(function(a, b){ return b.tam - a.tam; });
  for (var pasada = 0; pasada < 3; pasada++){
    var movio = false;
    var cajas = etqs.map(function(e){ return e.t.getBBox(); });
    for (var i = 0; i < etqs.length; i++){
      for (var j = i + 1; j < etqs.length; j++){
        var a = cajas[i], b = cajas[j];
        var sx = Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x);
        var sy = Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y);
        if (sx <= 0 || sy <= 0) continue;
        var abajo = (b.y + b.height / 2) >= (a.y + a.height / 2);
        var salto = (sy + 1.5) * (abajo ? 1 : -1);
        var margen = etqs[j].tam;
        var y = Math.max(margen, Math.min(alto - margen,
          Number(etqs[j].t.getAttribute("y")) + salto));
        etqs[j].t.setAttribute("y", y.toFixed(1));
        cajas[j] = etqs[j].t.getBBox();
        movio = true;
      }
    }
    if (!movio) break;
  }
  etqs.forEach(function(e){
    var b = e.t.getBBox(), dx = 0, dy = 0;
    if (b.x < 2) dx = 2 - b.x;
    else if (b.x + b.width > ancho - 2) dx = ancho - 2 - (b.x + b.width);
    if (b.y < 2) dy = 2 - b.y;
    else if (b.y + b.height > alto - 2) dy = alto - 2 - (b.y + b.height);
    if (dx || dy) e.t.setAttribute("transform",
      "translate(" + dx.toFixed(1) + "," + dy.toFixed(1) + ")");
  });
}

function pintarMapa(idSvg, idLey, def, porPieza, elegido){
  var caja = document.getElementById(idSvg);
  if (!caja || !def || !def.piezas || !def.piezas.length) return;
  var ancho = Number(def.ancho), alto = Number(def.alto);
  var cortes = tramos(def.piezas.map(function(p){
    var d = porPieza[p.codigo]; return d ? d.v : 0;
  }));
  var trazos = "", letras = "";
  def.piezas.forEach(function(p){
    NOMBRE_PIEZA[p.codigo] = p.nombre;
    var d = porPieza[p.codigo] || {v: 0, n: 0};
    var soloAbiertas = d.n > 0 && d.v === 0;
    var titulo = p.nombre + " — " + (d.n
      ? d.n + " operación" + (d.n === 1 ? "" : "es") + " · " +
        (soloAbiertas ? d.n + " sin firmar" : corto(d.v)) + " · pulse para filtrar"
      : "sin contratación del sismo");
    trazos += '<path class="' + clase(d.v, cortes, soloAbiertas) +
      (elegido === p.codigo ? " sel" : "") + '" d="' + p.d +
      '" data-cod="' + p.codigo + '" tabindex="0" role="button" aria-label="' +
      esc(titulo) + '"><title>' + esc(titulo) + "</title></path>";
    var cuerpo = letraPieza(p.a);
    var nombre = p.rotulo || p.nombre;
    /* "$ 0" no es una cifra, es un cero sin explicacion: pasa en los municipios
       que solo tienen procesos sin firmar, que ya van en su propio color. */
    var cifra = !d.n ? "" : (soloAbiertas ? d.n + " sin firmar" : corto(d.v));
    var y = cifra ? Number(p.cy) - cuerpo * 0.5 : Number(p.cy);
    letras += '<text class="etq" x="' + p.cx + '" y="' + y.toFixed(1) +
      '" font-size="' + cuerpo + '" text-anchor="middle">' +
      '<tspan x="' + p.cx + '" dy="0">' + esc(nombre) + "</tspan>" +
      (cifra ? '<tspan x="' + p.cx + '" dy="' + (cuerpo * 1.05).toFixed(1) +
               '" class="cifra">' + esc(cifra) + "</tspan>" : "") + "</text>";
  });
  caja.innerHTML = '<svg viewBox="0 0 ' + ancho + " " + alto +
    '" xmlns="http://www.w3.org/2000/svg" role="img">' + trazos + letras + "</svg>";
  separarEtiquetas(caja.querySelector("svg"), ancho, alto);

  /* Una leyenda POR MAPA: un municipio y un departamento no juegan en la misma
     escala, y con una sola la del Valle describia los colores del pais. */
  var ley = ["<span><i style='background:var(--m0)'></i>sin contratación</span>"];
  var desde = 0;
  cortes.forEach(function(c, i){
    ley.push("<span><i style='background:var(--m" + (i + 1) + ")'></i>hasta " +
             corto(c) + "</span>");
    desde = c;
  });
  if (cortes.length) ley.push("<span><i style='background:var(--m" +
      Math.min(4, cortes.length + 1) + ")'></i>más de " + corto(desde) + "</span>");
  ley.push("<span><i style='background:var(--mp)'></i>solo procesos sin firmar</span>");
  document.getElementById(idLey).innerHTML = ley.join("");
}

function pintarMapas(){
  var m = D.mapa || {};
  if (!m.pais || !m.valle){
    document.getElementById("sec-mapas").style.display = "none";
    return;
  }
  var v = vistaMapa();
  var porMun = {}, porDep = {}, sinSituar = 0;
  v.forEach(function(o){
    if (!o.mu && !o.dp){ sinSituar++; return; }
    if (o.mu){
      porMun[o.mu] = porMun[o.mu] || {v: 0, n: 0};
      porMun[o.mu].n++; if (o.f) porMun[o.mu].v += o.v;
    }
    if (o.dp){
      porDep[o.dp] = porDep[o.dp] || {v: 0, n: 0};
      porDep[o.dp].n++; if (o.f) porDep[o.dp].v += o.v;
    }
  });
  pintarMapa("mapa-valle", "ley-valle", m.valle, porMun, F.mun);
  pintarMapa("mapa-pais", "ley-pais", m.pais, porDep, F.dep);
  /* Un mapa que se come operaciones en silencio se lee como un censo. */
  document.getElementById("nota-sitio").textContent = sinSituar
    ? "De lo que se está viendo, " + sinSituar + " operación" + (sinSituar === 1 ? "" : "es") +
      " no se pudo situar en el mapa porque la fuente no dice el municipio."
    : "";
}

/* ---- Territorio elegido ------------------------------------------------ */
function pintarChip(){
  var c = document.getElementById("chip-territorio");
  var cod = F.mun || F.dep;
  if (!cod){ c.innerHTML = ""; return; }
  c.innerHTML = '<span class="chip">Territorio: <b>' +
    esc(NOMBRE_PIEZA[cod] || cod) + '</b>' +
    '<button type="button" id="quita-terr" aria-label="Quitar el territorio elegido">&times;</button></span>';
  document.getElementById("quita-terr").onclick = function(){
    F.mun = ""; F.dep = "";
    document.getElementById("f-mun").value = "";
    repintar();
  };
}
function elegirTerritorio(cod, esMunicipio){
  if (esMunicipio){
    F.mun = (F.mun === cod) ? "" : cod;
    document.getElementById("f-mun").value = F.mun;
  } else {
    F.dep = (F.dep === cod) ? "" : cod;
    /* Elegir un departamento entero deja sin sentido un municipio suelto. */
    if (F.dep){ F.mun = ""; document.getElementById("f-mun").value = ""; }
  }
  repintar();
}

/* ---- Descargas -------------------------------------------------------- */
var COLS = ["Grupo", "Entidad contratante", "Estado", "Fecha", "Numero de proceso",
            "Numero de contrato", "Valor", "Tipo de valor", "Contratista", "Municipio",
            "Tipo de contrato", "Modalidad", "Fecha inicio", "Fecha fin", "Objeto",
            "Enlace contrato", "Enlace proceso"];
function filaDatos(o){
  return [NOMBRE_GRUPO[o.g] || "", o.e, o.f ? "Contratada" : "Abierta", o.d, o.rp, o.rc,
          o.v, o.f ? "valor firmado" : "precio base", o.p, o.mn, o.tc, o.m, o.di, o.df,
          o.o, o.uc, o.up];
}
function textoFiltros(){
  var p = [];
  if (F.buscar) p.push("búsqueda: “" + F.buscar.toLowerCase() + "”");
  var ns = nivelesElegidos();
  if (ns.length) p.push("nivel de gobierno: " +
    ns.map(function(k){ return NOMBRE_GRUPO[k] || k; }).join(", "));
  if (F.entidad) p.push("entidad: " + F.entidad);
  if (F.mun) p.push("municipio: " + (NOMBRE_PIEZA[F.mun] || F.mun));
  if (F.dep) p.push("departamento: " + (NOMBRE_PIEZA[F.dep] || F.dep));
  if (F.tipo === "!ps") p.push("sin prestación de servicios");
  else if (F.tipo) p.push("tipo: " + F.tipo.toLowerCase());
  if (F.estado === "f") p.push("solo ya contratadas");
  if (F.estado === "a") p.push("solo aún sin contratar");
  if (F.monto){
    var s = document.getElementById("f-monto");
    p.push("monto: " + s.options[s.selectedIndex].text.toLowerCase());
  }
  return p.length ? p.join(" · ") : "sin filtros: toda la contratación confirmada";
}

function descargarCSV(){
  var filas = ULTIMA_VISTA.map(filaDatos);
  var txt = [COLS].concat(filas).map(function(f){
    return f.map(function(c){ return '"' + String(c == null ? "" : c).replace(/"/g, '""') + '"'; })
            .join(";");
  }).join("\r\n");
  /* BOM: sin el, Excel en Windows abre el archivo en la codificacion del sistema
     y los objetos con tildes salen rotos. */
  var url = URL.createObjectURL(new Blob(["﻿" + txt], {type: "text/csv;charset=utf-8"}));
  var a = document.createElement("a");
  a.href = url; a.download = "contratacion_sismo_" + (D.generado || "").slice(0, 10) + ".csv";
  a.click(); setTimeout(function(){ URL.revokeObjectURL(url); }, 2000);
}

/* El PDF es la impresion del navegador con hoja de estilos, no una libreria: una
   libreria obligaria a recortar el objeto para que la tabla cuadre, y el objeto
   es el texto por el que se juzga si una contratacion tiene que ver con el
   sismo. En papel se imprimen TODAS las filas del filtro, no las 20 de la
   pagina. */
function imprimirInforme(){
  var v = ULTIMA_VISTA;
  var svgV = document.querySelector("#mapa-valle svg");
  var svgP = document.querySelector("#mapa-pais svg");
  var mapas = "";
  if (svgV || svgP){
    mapas = '<div class="mapas-papel">' +
      (svgV ? "<figure><figcaption>Valle del Cauca · por municipio</figcaption>" +
              svgV.outerHTML + '<div class="ley-papel">' +
              document.getElementById("ley-valle").innerHTML + "</div></figure>" : "") +
      (svgP ? "<figure><figcaption>Colombia · por departamento</figcaption>" +
              svgP.outerHTML + '<div class="ley-papel">' +
              document.getElementById("ley-pais").innerHTML + "</div></figure>" : "") +
      "</div>";
  }
  /* Los enlaces van como <a href> de verdad, no como texto: al imprimir a PDF el
     navegador conserva el hipervinculo y el boton queda pulsable dentro del
     archivo. Si fueran texto, el PDF traeria el enlace escrito y habria que
     copiarlo a mano. */
  var cuerpo = v.map(function(o){
    var enl = [];
    if (o.uc) enl.push('<a class="ir" href="' + esc(o.uc) + '">Contrato ↗</a>');
    if (o.up) enl.push('<a class="ir" href="' + esc(o.up) + '">Proceso ↗</a>');
    var fechas = [];
    if (o.d) fechas.push((o.f ? "Firma " : "Publicado ") + esc(o.d));
    if (o.di) fechas.push("Inicia " + esc(o.di));
    if (o.df) fechas.push("Termina " + esc(o.df));
    return "<tr><td>" + esc(o.e) + "<br><small>" + esc(NOMBRE_GRUPO[o.g] || "") +
      (o.mn ? " · " + esc(o.mn) : "") + "</small></td>" +
      "<td>" + esc(o.o) + "<br><small>" + esc(o.rp || "") +
      (o.rp && o.rc ? " · " : "") + esc(o.rc || "") + "</small></td>" +
      "<td>" + esc(o.f ? "Contratada" : "Abierta") +
      '<br><small class="fechas">' + fechas.join("<br>") + "</small></td>" +
      '<td style="text-align:right;white-space:nowrap">' + esc(pesos(o.v)) +
      "<br><small>" + (o.f ? "firmado" : "precio base") + "</small></td>" +
      "<td>" + esc(o.p || "—") +
      (enl.length ? '<div class="enlaces">' + enl.join(" ") + "</div>" : "") + "</td></tr>";
  }).join("");

  document.getElementById("impresion").innerHTML =
    "<h1>Contratación pública relacionada con el sismo del 10 de agosto de 2026</h1>" +
    '<div class="sub">Cali, Valle del Cauca y nacional · datos.gov.co, SECOP I y SECOP II</div>' +
    '<div class="sello">Recolección del ' + esc(selloLargo(D.generado)) + "</div>" +
    '<div class="aplicados"><b>Lo que muestra este informe:</b> ' + esc(textoFiltros()) +
    "<br>" + resumen(v).replace(/<[^>]+>/g, "") + "</div>" + mapas +
    "<table><thead><tr><th>Entidad</th><th>Objeto y números</th><th>Estado</th>" +
    "<th>Valor</th><th>Contratista</th></tr></thead><tbody>" + cuerpo + "</tbody></table>";
  window.print();
}

/* ---- Filtros: llenado y eventos --------------------------------------- */
function llenar(){
  /* Los seis grupos van SIEMPRE, incluso los que estan en cero, y con su cuenta
     al lado. La Gobernacion del Valle no tiene contratacion confirmada del
     sismo, y esa es justamente una de las cosas que hay que poder ver. */
  var lista = document.getElementById("lista-nivel");
  (D.grupos || []).forEach(function(g){
    var n = OPS.filter(function(o){ return o.g === g.k; }).length;
    var l = document.createElement("label");
    l.innerHTML = '<input type="checkbox" value="' + esc(g.k) + '">' +
                  "<span>" + esc(g.n) + " (" + n + ")</span>";
    lista.appendChild(l);
  });
  resumenNivel();
  var ents = {}, muns = {};
  OPS.forEach(function(o){
    ents[o.e] = (ents[o.e] || 0) + 1;
    if (o.mu) muns[o.mu] = o.mn || o.mu;
  });
  var selE = document.getElementById("f-entidad");
  Object.keys(ents).sort().forEach(function(e){
    var op = document.createElement("option");
    op.value = e; op.textContent = e + " (" + ents[e] + ")"; selE.appendChild(op);
  });
  /* Los tipos que de verdad hay, con su cuenta. No se listan los que no aparecen:
     elegirlos daría siempre tabla vacía. */
  var tipos = {};
  OPS.forEach(function(o){ tipos[o.tc] = (tipos[o.tc] || 0) + 1; });
  var selT = document.getElementById("f-tipo");
  Object.keys(tipos).sort(function(a, b){ return tipos[b] - tipos[a] || a.localeCompare(b); })
    .forEach(function(k){
      var op = document.createElement("option");
      op.value = k; op.textContent = "Solo " + k.toLowerCase() + " (" + tipos[k] + ")";
      selT.appendChild(op);
    });

  var selM = document.getElementById("f-mun");
  Object.keys(muns).sort(function(a, b){ return muns[a].localeCompare(muns[b]); })
    .forEach(function(c){
      var op = document.createElement("option");
      op.value = c; op.textContent = muns[c]; selM.appendChild(op);
      NOMBRE_PIEZA[c] = muns[c];
    });
  document.getElementById("sello").textContent =
    "Recolección del " + selloLargo(D.generado) + " · " + OPS.length +
    " operaciones · ventana desde el 10 de agosto de 2026";
}

/* El resumen cerrado dice cuántos hay elegidos: un filtro puesto que no se ve
   miente igual que un tablero filtrado en silencio. */
function resumenNivel(){
  var ns = nivelesElegidos();
  var s = document.getElementById("res-nivel");
  if (!ns.length){ s.textContent = "Todos"; return; }
  if (ns.length === 1){ s.textContent = NOMBRE_GRUPO[ns[0]] || ns[0]; return; }
  s.textContent = ns.length + " niveles elegidos";
}

/* Marca en los encabezados de columna cuál está ordenando y hacia dónde. */
function pintarOrden(){
  var p = F.orden.split("-");
  document.querySelectorAll("th .orden").forEach(function(b){
    if (b.getAttribute("data-col") === p[0]){
      b.setAttribute("data-dir", p[1]);
      b.setAttribute("aria-sort", p[1] === "asc" ? "ascending" : "descending");
    } else {
      b.removeAttribute("data-dir");
      b.removeAttribute("aria-sort");
    }
  });
  document.getElementById("f-orden").value = F.orden;
}

function repintar(){
  pagina = 1; pintarTabla(); pintarMapas(); pintarChip(); pintarOrden();
}

function conectar(){
  var b = document.getElementById("f-buscar");
  var t;
  b.addEventListener("input", function(){
    clearTimeout(t);
    t = setTimeout(function(){ F.buscar = sinTildes(b.value.trim()); repintar(); }, 180);
  });
  ["entidad", "mun", "estado", "monto", "tipo", "orden"].forEach(function(k){
    document.getElementById("f-" + k).addEventListener("change", function(e){
      F[k] = e.target.value;
      /* Elegir municipio a mano manda sobre el departamento del mapa. */
      if (k === "mun" && e.target.value) F.dep = "";
      repintar();
    });
  });
  document.getElementById("f-agrupar").addEventListener("change", function(e){
    F.agrupar = e.target.checked; repintar();
  });

  /* Marcar un nivel NO repinta la lista de casillas, solo el resumen y la tabla:
     si repintara, las casillas saltarían bajo el cursor al elegir la segunda. */
  document.getElementById("lista-nivel").addEventListener("change", function(e){
    var c = e.target;
    if (!c || c.type !== "checkbox") return;
    if (c.checked) NIVELES[c.value] = 1; else delete NIVELES[c.value];
    resumenNivel();
    pagina = 1; pintarTabla(); pintarMapas(); pintarChip();
  });

  /* Encabezados ordenables. Pulsar el que ya ordena invierte el sentido. */
  document.querySelectorAll("th .orden").forEach(function(b){
    b.addEventListener("click", function(){
      var col = b.getAttribute("data-col");
      var p = F.orden.split("-");
      var dir = (p[0] === col && p[1] === "desc") ? "asc"
              : (p[0] === col && p[1] === "asc") ? "desc"
              /* Primer clic: lo útil por defecto. Valor y fecha interesan de
                 mayor a menor; los nombres, alfabéticos. */
              : (col === "valor" || col === "fecha") ? "desc" : "asc";
      F.orden = col + "-" + dir;
      repintar();
    });
  });

  document.getElementById("btn-limpiar").onclick = function(){
    /* Agrupar y el orden no son filtros: no esconden nada, solo cambian como se
       presenta. Quitar los filtros no tiene por que deshacer como el lector
       prefiere ver la tabla. */
    F = {buscar: "", entidad: "", mun: "", dep: "", estado: "", monto: "", tipo: "",
         agrupar: F.agrupar, orden: F.orden};
    b.value = "";
    ["entidad", "mun", "estado", "monto", "tipo"].forEach(function(k){
      document.getElementById("f-" + k).value = "";
    });
    Object.keys(NIVELES).forEach(function(k){ delete NIVELES[k]; });
    document.querySelectorAll("#lista-nivel input").forEach(function(c){ c.checked = false; });
    resumenNivel();
    repintar();
  };
  document.getElementById("btn-csv").onclick = descargarCSV;
  document.getElementById("btn-pdf").onclick = imprimirInforme;

  /* Delegacion: la tabla y los mapas se repintan enteros, asi que enganchar los
     eventos a cada boton obligaria a volver a engancharlos en cada repintado. */
  document.getElementById("cuerpo").addEventListener("click", function(e){
    var bo = e.target.closest("button[data-comp]");
    if (bo) compartir(Number(bo.getAttribute("data-i")), bo.getAttribute("data-comp"));
  });
  [["mapa-valle", true], ["mapa-pais", false]].forEach(function(par){
    var caja = document.getElementById(par[0]);
    if (!caja) return;
    caja.addEventListener("click", function(e){
      var p = e.target.closest("path[data-cod]");
      if (p) elegirTerritorio(p.getAttribute("data-cod"), par[1]);
    });
    caja.addEventListener("keydown", function(e){
      if (e.key !== "Enter" && e.key !== " ") return;
      var p = e.target.closest("path[data-cod]");
      if (p){ e.preventDefault(); elegirTerritorio(p.getAttribute("data-cod"), par[1]); }
    });
  });

  /* La (i) de cada filtro. Por clic y no por hover: en el telefono no hay hover. */
  document.addEventListener("click", function(e){
    var i = e.target.closest(".info[data-para]");
    if (!i) return;
    var caja = document.getElementById(i.getAttribute("data-para"));
    if (!caja) return;
    var abierto = caja.hidden;
    caja.hidden = !caja.hidden;
    i.setAttribute("aria-expanded", abierto ? "true" : "false");
  });
}

llenar(); conectar(); pintarTabla(); pintarMapas(); pintarChip(); pintarOrden();
</script>
</body>
</html>
"""
