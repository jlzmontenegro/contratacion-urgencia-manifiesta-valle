# -*- coding: utf-8 -*-
"""Genera ligero.html: un tablero autonomo, de un solo archivo, con SOLO la
contratacion que ya esta dada por relacionada con el sismo del 10-ago-2026.

Por que existe aparte del tablero grande:
  - Va incrustado en otra pagina web (un iframe, una instancia ajena), donde no
    se puede contar con que se sirvan cuatro archivos desde el mismo sitio. Aqui
    todo -datos, estilos, guion y contornos del mapa- viaja dentro del HTML: cero
    peticiones de red despues de la primera, y ninguna dependencia externa. Ni
    siquiera las tipografias de Google: la pila del sistema carga al instante y
    una fuente que no llega deja el texto saltando.
  - Lleva la piel de estebanoliveros.com, que es donde se incrusta, y no la del
    tablero grande. Ver la nota del <style>.
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
        if "UAESP" in nombre or "SERVICIOS PUBLICOS" in nombre and "SANTIAGO DE CALI" in nombre:
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
        # El objeto mas largo de los dos: SECOP recorta descripcion_del_proceso
        # cerca de los 300 caracteres y el del contrato suele venir completo.
        objeto = max((r.get("objeto") or "" for r in regs), key=len)
        ops.append({
            "e": principal.get("entidad") or "",
            "g": _grupo_ligero(principal),
            "o": objeto,
            "v": valor,
            "f": bool(contrato),                       # firmado
            "d": principal.get("fecha") or "",
            "di": principal.get("fecha_inicio") or "",
            "df": principal.get("fecha_fin") or "",
            "p": (contrato or principal).get("proveedor") or "",
            "m": principal.get("modalidad") or "",
            "mu": principal.get("municipio") or "",
            "mn": principal.get("municipio_nombre") or "",
            "dp": principal.get("dep_codigo") or "",
            "rc": (contrato or {}).get("referencia") or "",
            "rp": (proceso or {}).get("referencia") or "",
            "uc": (contrato or {}).get("url") or "",
            "up": (proceso or {}).get("url") or "",
            "pl": principal.get("plataforma") or "",
            "rv": bool(principal.get("revisada")),
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
    # Solo los dos lienzos y la procedencia. Lo demas son notas para quien lea el
    # archivo, y aqui cada byte viaja dentro del HTML.
    return {"pais": m.get("pais"), "valle": m.get("valle"), "_fuente": m.get("_fuente", "")}


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
    # separators sin espacios: son 374 operaciones y cada byte viaja en el HTML.
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
<title>Contratación del sismo · Cali y Valle del Cauca</title>
<style>
/* La piel NO es la del tablero grande: es la de estebanoliveros.com, que es donde
   esto se incrusta. Un tablero verde azulado sobre una pagina blanca y verde
   hierba se ve como lo que seria, un cuerpo extrano metido con calzador.
   Medido sobre el sitio: fondo blanco, verde de marca rgb(86,168,0), gris claro
   #E8E6E6, texto negro y cuerpo en Helvetica/Arial.
   La tipografia de titulares del sitio es Cocosharp, una fuente con licencia de
   Wix que no se puede incrustar aqui; el cuerpo si coincide exacto, porque el
   propio sitio cae en Helvetica. Se mantiene la pila del sistema y la identidad
   la llevan el color y la geometria: cero peticiones a terceros. */
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
   pinta los <select> y la barra de monto en oscuro por su cuenta. */
*{box-sizing:border-box}
body{margin:0;background:var(--fondo);color:var(--texto);
     font:14px/1.55 "Helvetica Neue",Helvetica,Arial,sans-serif;
     -webkit-text-size-adjust:100%}
.env{max-width:1180px;margin:0 auto;padding:18px 16px 48px}
h1{font-size:21px;margin:0 0 4px;font-weight:700;letter-spacing:-.01em;text-wrap:balance}
h2{font-size:12px;margin:0 0 10px;font-weight:700;letter-spacing:.09em;
   text-transform:uppercase;color:var(--acento-tinta)}
a{color:var(--acento-tinta)}
.sub{color:var(--texto-2);font-size:12.5px;line-height:1.45}
header{border-bottom:3px solid var(--acento);padding-bottom:14px;margin-bottom:16px}
.sello{margin-top:8px;font-size:11.5px;color:var(--suave);
       font-family:ui-monospace,Consolas,monospace}
.panel{background:var(--panel);border:1px solid var(--borde);border-radius:3px;
       padding:14px;margin-bottom:16px}

/* ---- Filtros ---- */
.filtros{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(190px,1fr))}
.campo{display:flex;flex-direction:column;gap:4px;min-width:0}
label{font-size:10.5px;font-weight:600;letter-spacing:.09em;text-transform:uppercase;
      color:var(--suave)}
select,input[type=search]{font:inherit;font-size:13px;padding:6px 8px;border-radius:3px;
      border:1px solid var(--borde);background:var(--panel);color:var(--texto);
      width:100%;min-width:0}
.rango{padding-top:2px}
.rango .lectura{font-family:ui-monospace,Consolas,monospace;font-size:12px;
      color:var(--texto-2);margin-bottom:2px}
/* Dos <input type=range> superpuestos: no existe control nativo de rango doble.
   El truco esta en pointer-events: el control entero no recibe el raton y solo
   lo reciben los pulgares. Sin eso el de arriba tapa al de abajo y uno de los
   dos topes queda muerto. */
.doble{position:relative;height:24px}
.doble input{position:absolute;left:0;top:0;width:100%;margin:0;height:24px;
      -webkit-appearance:none;appearance:none;background:none;pointer-events:none}
.doble input::-webkit-slider-thumb{-webkit-appearance:none;pointer-events:auto;
      width:15px;height:15px;border-radius:50%;background:var(--acento);
      border:2px solid var(--panel);cursor:pointer}
.doble input::-moz-range-thumb{pointer-events:auto;width:15px;height:15px;
      border-radius:50%;background:var(--acento);border:2px solid var(--panel);
      cursor:pointer}
.doble .riel{position:absolute;left:0;right:0;top:10px;height:4px;border-radius:2px;
      background:var(--panel-2);border:1px solid var(--borde)}
.campo.marca{justify-content:flex-start}
.casilla{display:flex;align-items:center;gap:7px;font-size:13px;font-weight:400;
      letter-spacing:0;text-transform:none;color:var(--texto);cursor:pointer;
      padding-top:4px}
.casilla input{accent-color:var(--acento);width:15px;height:15px;margin:0;flex:0 0 auto}
.acciones{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:12px}
button{font:inherit;font-size:12.5px;padding:6px 11px;border-radius:3px;cursor:pointer;
      border:1px solid var(--borde);background:var(--panel-2);color:var(--texto)}
button:hover{border-color:var(--acento)}

/* ---- Resumen de lo que se esta viendo ---- */
.cuenta{font-size:13px;color:var(--texto-2);margin:14px 0 8px}
.cuenta b{color:var(--texto);font-weight:600}

/* ---- Tabla ---- */
.marco{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:8px 10px;background:var(--panel-2);color:var(--acento-tinta);
   font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;font-weight:600;
   border-bottom:1px solid var(--borde);white-space:nowrap}
td{padding:10px;border-bottom:1px solid var(--borde);vertical-align:top}
tbody tr:hover{background:var(--panel-2)}
.num{text-align:right;font-family:ui-monospace,Consolas,monospace;
     font-variant-numeric:tabular-nums;white-space:nowrap}
.ent{font-weight:600;margin-bottom:3px}
/* El objeto va COMPLETO, sin truncar: es el texto por el que se juzga si una
   contratacion tiene que ver con el sismo. Recortarlo obliga a abrir SECOP. */
.obj{color:var(--texto-2);line-height:1.45;margin-bottom:5px}
.pie{font-size:11.5px;color:var(--suave)}
.refs{margin-top:4px;display:flex;flex-wrap:wrap;gap:5px}
.ref{font-family:ui-monospace,Consolas,monospace;font-size:11px;
     background:var(--panel-2);border:1px solid var(--borde);border-radius:2px;
     padding:1px 5px;color:var(--texto-2)}
.est{font-family:ui-monospace,Consolas,monospace;font-size:10.5px;font-weight:500;
     letter-spacing:.04em;text-transform:uppercase;padding:2px 6px;border-radius:2px;
     display:inline-block;white-space:nowrap}
.est-f{background:var(--alta);color:var(--panel)}
.est-a{background:transparent;color:var(--abierta);border:1px solid var(--abierta)}
.menor{font-size:11.5px;color:var(--suave);margin-top:4px}
/* Banda de grupo. Agrupar es ORDENAR, no pintar distinto: la tabla solo intercala
   esta fila cuando cambia el nombre de la entidad. */
tbody tr.banda:hover{background:var(--panel-2)}
td.banda{background:var(--panel-2);border-bottom:1px solid var(--borde);padding:9px 10px}
td.banda .quien{font-weight:600;font-size:13px}
td.banda .cuanto{font-family:ui-monospace,Consolas,monospace;font-size:11.5px;
      color:var(--texto-2);margin-top:2px}
td.banda .sigue{font-size:11.5px;color:var(--suave);font-style:italic}
.rev{font-size:11px;color:var(--acento-tinta);font-weight:700;margin-top:4px}
.enl{display:inline-block;font-size:11.5px;padding:4px 8px;border-radius:3px;
     border:1px solid var(--borde);text-decoration:none;color:var(--texto);
     white-space:nowrap;margin:0 4px 4px 0}
.enl:hover{border-color:var(--acento);color:var(--acento-tinta)}
.vacio{padding:26px 10px;text-align:center;color:var(--suave);line-height:1.6}
.pag{display:flex;gap:8px;align-items:center;justify-content:center;margin-top:14px;
     font-size:12.5px;color:var(--texto-2)}

/* ---- Mapas ---- */
.mapas{display:grid;gap:18px;grid-template-columns:repeat(auto-fit,minmax(290px,1fr))}
.mapas figure{margin:0;min-width:0}
figcaption{font-family:ui-monospace,Consolas,monospace;font-size:10.5px;
     letter-spacing:.09em;text-transform:uppercase;color:var(--suave);margin-bottom:6px}
.lienzo svg{width:100%;height:auto;display:block;max-height:58vh}
/* El filete entre piezas es del color del fondo, no gris: asi las fronteras se
   leen como separacion y no como un dato mas. */
.lienzo path{stroke:var(--m-borde);stroke-width:.8;stroke-linejoin:round}
.lienzo .m0{fill:var(--m0)}.lienzo .m1{fill:var(--m1)}.lienzo .m2{fill:var(--m2)}
.lienzo .m3{fill:var(--m3)}.lienzo .m4{fill:var(--m4)}.lienzo .mp{fill:var(--mp)}
/* Halo del color del panel debajo del relleno de la letra -paint-order:stroke
   pinta el borde DEBAJO, que si no se come el trazo-, o el nombre no se lee
   sobre el tono oscuro de la rampa. */
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
  /* La banda de grupo no es una tarjeta más: en el teléfono tiene que leerse como
     el encabezado de las que vienen debajo, o se confunde con una operación. */
  tbody tr.banda{border:0;background:none;margin:16px 0 6px}
  tbody tr.banda td.banda{border-bottom:2px solid var(--acento);padding:6px 2px}
}
</style>
</head>
<body>
<div class="env">

<header>
  <h1>Contratación relacionada con el sismo del 10 de agosto de 2026</h1>
  <div class="sub">
    Cali y Valle del Cauca. Solo lo que está confirmado como atención de la emergencia.
    Fuente: datos.gov.co — SECOP II (contratos <code>jbjy-vk9h</code> y procesos
    <code>p6dx-8zbt</code>), SECOP I (<code>f789-7hwg</code>) y la contratación de la
    UNGRD y el FNGRD.
  </div>
  <div class="sello" id="sello"></div>
</header>

<section class="panel">
  <h2>Filtros</h2>
  <div class="filtros">
    <div class="campo">
      <label for="f-buscar">Buscar</label>
      <input type="search" id="f-buscar" placeholder="objeto, entidad, contratista, número…">
    </div>
    <div class="campo">
      <label for="f-grupo">Entidad contratante</label>
      <select id="f-grupo"><option value="">Todas</option></select>
    </div>
    <div class="campo">
      <label for="f-entidad">Entidad</label>
      <select id="f-entidad"><option value="">Todas</option></select>
    </div>
    <div class="campo">
      <label for="f-mun">Municipio</label>
      <select id="f-mun"><option value="">Todos</option></select>
    </div>
    <div class="campo">
      <label for="f-estado">Estado</label>
      <select id="f-estado">
        <option value="">Contratadas y abiertas</option>
        <option value="f">Solo ya contratadas</option>
        <option value="a">Solo aún sin contratar</option>
      </select>
    </div>
    <div class="campo marca">
      <label for="f-agrupar">Presentación</label>
      <label class="casilla"><input type="checkbox" id="f-agrupar"> Agrupar por entidad</label>
    </div>
    <div class="campo rango">
      <label>Monto</label>
      <div class="lectura" id="lec-monto">sin límite</div>
      <div class="doble">
        <div class="riel"></div>
        <input type="range" id="f-min" min="0" max="100" value="0">
        <input type="range" id="f-max" min="0" max="100" value="100">
      </div>
    </div>
  </div>
  <div class="acciones">
    <button id="btn-limpiar">Quitar todos los filtros</button>
    <button id="btn-csv">Descargar CSV de lo que se ve</button>
  </div>
</section>

<div class="cuenta" id="cuenta"></div>

<section class="marco">
  <table>
    <thead><tr>
      <th>Estado</th><th>Qué y quién</th><th class="num">Valor</th>
      <th>Contratista</th><th>SECOP</th>
    </tr></thead>
    <tbody id="cuerpo"></tbody>
  </table>
</section>
<div class="pag" id="pag"></div>

<section class="panel" id="sec-mapas">
  <h2>Dónde se está contratando</h2>
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
    el campo de SECOP es el domicilio de la entidad. Respetan todos los filtros activos.
    <span id="nota-sitio"></span>
  </p>
</section>

<p class="nota">
  Una operación es un proceso y el contrato que salió de él contados una sola vez.
  Nunca se suma precio base con valor firmado: la operación muestra el valor firmado
  si hay contrato y el precio base si todavía no, siempre rotulado.
  Tablero completo, con lo que está por revisar y la contratación ordinaria:
  <a href="https://jlzmontenegro.github.io/contratacion-urgencia-manifiesta-valle/"
     target="_blank" rel="noopener">ver el monitor completo</a>.
</p>

</div>

<script type="application/json" id="datos">__DATOS__</script>
<script>
"use strict";
var D = JSON.parse(document.getElementById("datos").textContent);
var OPS = D.ops || [];
/* 20 por página, como el tablero grande, y ordenadas de mayor a menor valor. En
   el teléfono cada fila es una tarjeta con el objeto completo y sube de los 500
   píxeles: veinte ya son catorce mil de recorrido. */
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
  if (v >= 1e6) return "$ " + (v / 1e6).toFixed(0) + " M";
  return pesos(v);
}
function sinTildes(s){
  return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase();
}

/* ---- Escala del monto, por CUANTILES ---------------------------------- *
 * No puede ser lineal: casi todo se apelotona en el primer centimetro. Se
 * calcula UNA vez por carga; si se recalculara con cada filtro, el tramo
 * elegido pasaria a significar otra cosa sin que nadie lo tocara.            */
var VALORES = OPS.map(function(o){ return o.v; }).sort(function(a,b){ return a-b; });
var TOPE = 100;
function posAValor(p){
  if (p <= 0) return -Infinity;          /* extremo abierto: entran los de valor cero */
  if (p >= TOPE) return Infinity;        /* y arriba no se puede caer nada por redondeo */
  if (!VALORES.length) return Infinity;
  var i = Math.floor((p / TOPE) * (VALORES.length - 1));
  return VALORES[i];
}

var F = {
  buscar: "", grupo: "", entidad: "", mun: "", estado: "",
  min: 0, max: TOPE, agrupar: false
};

function pasa(o){
  if (F.grupo && o.g !== F.grupo) return false;
  if (F.entidad && o.e !== F.entidad) return false;
  if (F.mun && o.mu !== F.mun) return false;
  if (F.estado === "f" && !o.f) return false;
  if (F.estado === "a" && o.f) return false;
  if (F.min > 0 && o.v < posAValor(F.min)) return false;
  if (F.max < TOPE && o.v > posAValor(F.max)) return false;
  if (F.buscar){
    var t = sinTildes(o.e + " " + o.o + " " + o.p + " " + o.rc + " " + o.rp + " " + o.mn);
    if (t.indexOf(F.buscar) < 0) return false;
  }
  return true;
}
/* Agrupar por entidad es ORDENAR, no pintar distinto: aquí se devuelven las
   operaciones de cada entidad contiguas y las entidades por lo que suman. Hecho
   así, la paginación, el recuento de cabecera y la descarga en CSV heredan el
   mismo orden sin tocar nada más; la tabla se limita a intercalar una banda
   cuando cambia el nombre. */
function agrupar(ops){
  var suma = {};
  ops.forEach(function(o){ suma[o.e] = (suma[o.e] || 0) + (o.f ? o.v : 0); });
  /* Desempate por nombre: dos entidades que suman cero -todo sin firmar- no
     pueden quedar en un orden que cambie de una carga a otra. */
  var orden = Object.keys(suma).sort(function(a, b){
    return (suma[b] - suma[a]) || a.localeCompare(b);
  });
  var puesto = {};
  orden.forEach(function(e, i){ puesto[e] = i; });
  return ops.slice().sort(function(a, b){
    return (puesto[a.e] - puesto[b.e]) || (b.v - a.v);
  });
}

function vista(){
  var v = OPS.filter(pasa);
  return F.agrupar ? agrupar(v) : v;
}

/* ---- Tabla ------------------------------------------------------------ */
function fila(o){
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
  return '<tr>' +
    '<td data-etq="Estado">' +
      (o.f ? '<span class="est est-f">Contratada</span>'
           : '<span class="est est-a">Abierta</span>') +
      '<div class="menor">' + esc(o.d) + "</div>" + fechas + "</td>" +
    '<td data-etq="Qué y quién"><div class="ent">' + esc(o.e) + "</div>" +
      '<div class="obj">' + esc(o.o) + "</div>" +
      '<div class="pie">' + esc(NOMBRE_GRUPO[o.g] || "") +
        (o.mn ? " · " + esc(o.mn) : "") + (o.m ? " · " + esc(o.m) : "") + "</div>" +
      '<div class="refs">' + refs.join("") + "</div>" +
      (o.rv ? '<div class="rev">✓ confirmado por una persona</div>' : "") + "</td>" +
    '<td class="num" data-etq="Valor">' + esc(pesos(o.v)) +
      '<div class="menor">' + (o.f ? "valor firmado" : "precio base") + "</div></td>" +
    '<td data-etq="Contratista">' +
      (o.p ? esc(o.p) : '<span class="menor">aún sin contratista</span>') + "</td>" +
    '<td data-etq="SECOP">' + (enl || '<span class="menor">sin enlace</span>') + "</td></tr>";
}

/* Un cero tiene que decir POR QUE. En este tablero un cero se lee como "no hay
   contratación del sismo", que es una afirmación fuerte: el mensaje se redacta
   según el filtro que este puesto. */
function mensajeVacio(){
  if (F.buscar) return "Ninguna operación del sismo coincide con «" + esc(F.buscar.toLowerCase()) +
    "». La búsqueda mira objeto, entidad, contratista, municipio y los dos números de SECOP.";
  if (F.entidad) return "Esa entidad no tiene contratación confirmada del sismo con los demás " +
    "filtros puestos. Puede tener contratación en revisión: eso se ve en el monitor completo.";
  if (F.estado === "a") return "No hay procesos abiertos sin contratar con estos filtros: " +
    "todo lo que coincide ya está firmado.";
  if (F.estado === "f") return "No hay nada firmado con estos filtros; lo que coincide sigue " +
    "como proceso abierto.";
  if (F.min > 0 || F.max < TOPE) return "Ninguna operación cae en ese rango de monto.";
  if (F.grupo) return "<b>" + esc(NOMBRE_GRUPO[F.grupo] || "Ese grupo") + "</b> no tiene " +
    "contratación confirmada del sismo en la ventana de seguimiento. Está vigilado y su " +
    "contratación se revisa en cada recolección: el cero es un hallazgo, no un dato que falte.";
  if (F.mun) return "Ese municipio no tiene contratación confirmada del sismo.";
  return "No hay contratación confirmada del sismo para mostrar.";
}

function pintarTabla(){
  var v = vista();
  var total = v.reduce(function(s,o){ return s + o.v; }, 0);
  var firmado = v.filter(function(o){ return o.f; });
  var sumaF = firmado.reduce(function(s,o){ return s + o.v; }, 0);
  /* El desglose Valle / fuera del Valle no es un adorno. El título dice "Cali y
     Valle del Cauca" y en la vista sin filtros más de la mitad de lo firmado es
     de Antioquia, Risaralda y Chocó, que entran por "Otras entidades y otras
     regiones". Una sola cifra grande debajo de ese título se leería como si toda
     fuera del Valle. Se separa por el departamento de la entidad, que es lo mismo
     que pinta el mapa. */
  var valle = firmado.filter(function(o){ return o.dp === "76"; });
  var sumaValle = valle.reduce(function(s,o){ return s + o.v; }, 0);
  var reparto = (sumaValle && sumaValle !== sumaF)
    ? " — de eso, <b>" + esc(corto(sumaValle)) + "</b> de entidades del Valle del Cauca y " +
      esc(corto(sumaF - sumaValle)) + " de otras regiones"
    : "";
  document.getElementById("cuenta").innerHTML =
    "<b>" + v.length + "</b> operacion" + (v.length === 1 ? "" : "es") +
    " · <b>" + esc(corto(sumaF)) + "</b> ya contratado en " + firmado.length +
    " · " + (v.length - firmado.length) + " aún sin contratar" +
    (v.length - firmado.length ? " por " + esc(corto(total - sumaF)) + " de precio base" : "") +
    reparto;

  var paginas = Math.max(1, Math.ceil(v.length / POR_PAGINA));
  if (pagina > paginas) pagina = paginas;
  var desde = (pagina - 1) * POR_PAGINA;
  var trozo = v.slice(desde, pagina * POR_PAGINA);
  var filas = "";
  if (F.agrupar){
    var anterior = null;
    trozo.forEach(function(o, i){
      if (o.e !== anterior){
        /* Si el grupo empieza antes de esta página, la banda lo dice. Sin eso,
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
      filas += fila(o);
    });
  } else {
    filas = trozo.map(fila).join("");
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

/* Tramos por cuantiles, no lineales: una sola operación grande aplastaría a
   todas las demás contra el extremo bajo de cualquier escala lineal. Y el cero
   tiene color propio, fuera de la rampa: "no ha contratado" no es "ha
   contratado poco". */
function tramos(valores){
  var v = valores.filter(function(x){ return x > 0; }).sort(function(a,b){ return a-b; });
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

/* El cuerpo de letra sale del tamaño de la pieza: con uno solo, el nombre de un
   municipio pequeño se derrama sobre tres vecinos. La raíz del área porque lo
   que importa es cuánto mide de ancho, no cuánta superficie tiene. */
function letraPieza(a){
  return Math.max(11, Math.min(21, Math.round(Math.sqrt(Number(a) || 0) / 7)));
}

/* Separa las etiquetas que se pisan, y luego mete hacia dentro las que se salgan
   por cualquiera de los cuatro lados: San Andrés es la esquina noroeste del país
   y su rótulo centrado se salía por la izquierda y por arriba a la vez.
   Se mide con getBBox() sobre el SVG ya puesto en la página, que es lo único que
   sabe cuánto ocupa de verdad un texto; estimar el ancho por el número de letras
   deja solapes. Tres pasadas y se corta: un ajuste de etiquetas no puede colgar
   la página. */
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
        /* La pequeña se aparta hacia el lado contrario a la grande. */
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

function pintarMapa(idSvg, idLey, def, porPieza){
  var caja = document.getElementById(idSvg);
  if (!caja || !def || !def.piezas || !def.piezas.length) return;
  var ancho = Number(def.ancho), alto = Number(def.alto);
  var cortes = tramos(def.piezas.map(function(p){
    var d = porPieza[p.codigo]; return d ? d.v : 0;
  }));
  var trazos = "", letras = "";
  def.piezas.forEach(function(p){
    var d = porPieza[p.codigo] || {v: 0, n: 0};
    var soloAbiertas = d.n > 0 && d.v === 0;
    var titulo = p.nombre + " — " + (d.n
      ? d.n + " operación" + (d.n === 1 ? "" : "es") + " · " +
        (soloAbiertas ? d.n + (d.n === 1 ? " sin firmar" : " sin firmar") : corto(d.v))
      : "sin contratación del sismo");
    trazos += '<path class="' + clase(d.v, cortes, soloAbiertas) + '" d="' + p.d +
              '"><title>' + esc(titulo) + "</title></path>";
    var cuerpo = letraPieza(p.a);
    var nombre = p.rotulo || p.nombre;
    /* "$ 0" no es una cifra, es un cero sin explicación: pasa en los municipios
       que solo tienen procesos sin firmar, que ya van en su propio color. Se
       escribe lo que de verdad hay. */
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
     escala, y con una sola la del Valle describía los colores del país. */
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
  var v = vista();
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
  pintarMapa("mapa-valle", "ley-valle", m.valle, porMun);
  pintarMapa("mapa-pais", "ley-pais", m.pais, porDep);
  /* Un mapa que se come operaciones en silencio se lee como un censo. */
  document.getElementById("nota-sitio").textContent = sinSituar
    ? "De lo que se está viendo, " + sinSituar + " operación" + (sinSituar === 1 ? "" : "es") +
      " no se pudo situar en el mapa porque la fuente no dice el municipio."
    : "";
}

/* ---- Filtros: llenado y eventos --------------------------------------- */
function llenar(){
  /* Los seis grupos van SIEMPRE, incluso los que están en cero, y con su cuenta
     al lado. La Gobernación del Valle no tiene contratación confirmada del sismo,
     y esa es justamente una de las cosas que hay que poder ver: si la opción
     desapareciera del desplegable, la página no diría nada y el lector supondría
     que no se la vigila. */
  var selG = document.getElementById("f-grupo");
  (D.grupos || []).forEach(function(g){
    var n = OPS.filter(function(o){ return o.g === g.k; }).length;
    var op = document.createElement("option");
    op.value = g.k; op.textContent = g.n + " (" + n + ")";
    selG.appendChild(op);
  });
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
  var selM = document.getElementById("f-mun");
  Object.keys(muns).sort(function(a,b){ return muns[a].localeCompare(muns[b]); })
    .forEach(function(c){
      var op = document.createElement("option");
      op.value = c; op.textContent = muns[c]; selM.appendChild(op);
    });
  document.getElementById("sello").textContent =
    "Recolección del " + D.generado + " (hora de Colombia) · ventana desde el " + D.desde +
    " · " + OPS.length + " operaciones confirmadas";
}

function leerMonto(){
  var a = posAValor(F.min), b = posAValor(F.max);
  document.getElementById("lec-monto").textContent =
    (F.min <= 0 ? "sin límite" : "desde " + corto(a)) + " — " +
    (F.max >= TOPE ? "sin límite" : "hasta " + corto(b));
}

function repintar(){ pagina = 1; pintarTabla(); pintarMapas(); }

function conectar(){
  var b = document.getElementById("f-buscar");
  var t;
  b.addEventListener("input", function(){
    clearTimeout(t);
    t = setTimeout(function(){ F.buscar = sinTildes(b.value.trim()); repintar(); }, 180);
  });
  ["grupo", "entidad", "mun", "estado"].forEach(function(k){
    document.getElementById("f-" + k).addEventListener("change", function(e){
      F[k] = e.target.value; repintar();
    });
  });
  document.getElementById("f-agrupar").addEventListener("change", function(e){
    F.agrupar = e.target.checked; repintar();
  });
  var mi = document.getElementById("f-min"), ma = document.getElementById("f-max");
  function mover(){
    F.min = Math.min(+mi.value, +ma.value);
    F.max = Math.max(+mi.value, +ma.value);
    leerMonto(); repintar();
  }
  mi.addEventListener("input", mover);
  ma.addEventListener("input", mover);

  document.getElementById("btn-limpiar").onclick = function(){
    /* Agrupar no es un filtro: no esconde nada, solo cambia el orden. Quitar los
       filtros no tiene por qué deshacer cómo el lector prefiere ver la tabla. */
    F = {buscar: "", grupo: "", entidad: "", mun: "", estado: "", min: 0, max: TOPE,
         agrupar: F.agrupar};
    b.value = ""; mi.value = 0; ma.value = TOPE;
    ["grupo", "entidad", "mun", "estado"].forEach(function(k){
      document.getElementById("f-" + k).value = "";
    });
    leerMonto(); repintar();
  };

  /* El CSV sale de lo que la tabla está mostrando, no de todo: un archivo que
     sale del tablero y no cuadra con la pantalla es peor que no tenerlo. */
  document.getElementById("btn-csv").onclick = function(){
    var cols = ["Grupo", "Entidad contratante", "Estado", "Fecha", "Numero de proceso",
                "Numero de contrato", "Valor", "Tipo de valor", "Contratista", "Municipio",
                "Modalidad", "Objeto", "Enlace contrato", "Enlace proceso"];
    var filas = vista().map(function(o){
      return [NOMBRE_GRUPO[o.g] || "", o.e, o.f ? "Contratada" : "Abierta", o.d, o.rp, o.rc,
              o.v, o.f ? "valor firmado" : "precio base", o.p, o.mn, o.m, o.o, o.uc, o.up];
    });
    var txt = [cols].concat(filas).map(function(f){
      return f.map(function(c){ return '"' + String(c == null ? "" : c).replace(/"/g, '""') + '"'; })
              .join(";");
    }).join("\r\n");
    /* BOM: sin el, Excel en Windows abre el archivo en la codificacion del
       sistema y los objetos con tildes salen rotos. */
    var url = URL.createObjectURL(new Blob(["﻿" + txt], {type: "text/csv;charset=utf-8"}));
    var a = document.createElement("a");
    a.href = url; a.download = "contratacion_sismo_" + (D.generado || "").slice(0, 10) + ".csv";
    a.click(); setTimeout(function(){ URL.revokeObjectURL(url); }, 2000);
  };
}

llenar(); conectar(); leerMonto(); pintarTabla(); pintarMapas();
</script>
</body>
</html>
"""
