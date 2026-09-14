# -*- coding: utf-8 -*-
"""Vigila la contratacion del GOBIERNO NACIONAL para el Valle por el sismo.

Y hoy, a un mes del evento, lo que vigila es un CERO. Ese es el punto: el cero
solo vale si se puede probar que se busco bien y se dice donde se busco.

POR QUE UNA PAGINA APARTE Y NO UNA SECCION DE LA LIGERA. Son dos preguntas
distintas: la ligera responde "que se contrato para el Valle", y esta responde
"que puso la Nacion". Mezclarlas obligaria a que el mismo cero conviviera en la
misma pantalla con 375 operaciones, y se leeria como que falta un dato en vez de
como un hallazgo. El usuario pidio que fuera aparte (14-sep-2026).

CUATRO CANALES, medidos en cada corrida contra la API:
  presidencia   Presidencia de la Republica y DAPRE
  ministerios   los diecisiete ministerios
  fngrd         UNGRD y el Fondo Nacional de Gestion del Riesgo
  otras         cualquier otra entidad, cuando su objeto nombra el sismo

De cada uno se cuenta lo mismo: contratos firmados desde el sismo, cuantos
mencionan el evento y cuantos nombran el Valle. Las tres cifras juntas son lo
que impide leer mal el cero: "cero de cero" es no haber mirado, y "cero de 98"
es haber mirado.

EL CAMPO 'orden' DE SECOP NO SIRVE para esto. Es autodeclarado: marca "Nacional"
a la Alcaldia de Ciudad Bolivar y a la de Roldanillo. Por eso los canales se
definen por el NOMBRE de la entidad, que es lo unico que lo dice.

LO QUE ESTA PAGINA NO PUEDE VER, y lo dice en pantalla: el FNGRD es un
patrimonio autonomo administrado por fiduciaria y parte de su ejecucion no
aparece como contrato propio del Fondo; y la plata nacional llega muchas veces
como transferencia al municipio, que luego contrata en su nombre y aparece en el
tablero como contratacion municipal. Una pagina que promete "todo lo que puso la
Nacion" sin decir esto miente.
"""

import io
import json
import os
import re
import unicodedata

DATASET_CONTRATOS = "jbjy-vk9h"

# Nombres de entidad por canal. Se comparan en mayusculas y sin tildes contra el
# nombre que publica SECOP.
CANALES = [
    ("presidencia", "Presidencia y DAPRE",
     ["%PRESIDENCIA DE LA REPUBLICA%", "%DEPARTAMENTO ADMINISTRATIVO DE LA PRESIDENCIA%"],
     "La Presidencia de la República y su departamento administrativo."),
    ("ministerios", "Ministerios",
     ["%MINISTERIO%"],
     "Los ministerios del despacho, incluidos Educación, Vivienda, Transporte y Salud."),
    ("fngrd", "UNGRD y FNGRD",
     ["%GESTION DEL RIESGO DE DESASTRES%"],
     "La Unidad Nacional para la Gestión del Riesgo y el Fondo Nacional, "
     "donde vive la Subcuenta SISMO 2026 que creó el Decreto 1171."),
]

# Palabras que nombran el evento. Las mismas del clasificador, en corto.
SISMO = ("SISMO", "SISMIC", "TERREMOTO", "10 DE AGOSTO DE 2026")

# Nombres largos e inequivocos: SoQL compara subcadenas, no palabras, y '%CALI%'
# encuentra CALIDAD, CALIFICACION y CALIBRACION. Es la misma trampa que ya se
# pago en el colector.
VALLE = ("VALLE DEL CAUCA", "SANTIAGO DE CALI", "BUENAVENTURA", "PALMIRA",
         "TULUA", "BUGA", "CARTAGO", "JAMUNDI", "YUMBO", "ROLDANILLO",
         "CALIMA EL DARIEN", "ZARZAL", "SEVILLA VALLE", "BUGALAGRANDE")

# Lo que NO es la Nacion. Sin esto, el canal de "otras entidades nacionales"
# traia 55 contratos que son, uno por uno, alcaldias y municipios del Valle: los
# mismos que ya muestra el tablero principal. Una pagina que titula "que puso la
# Nacion" y lista el contrato de Zarzal no se equivoca en un detalle, se
# equivoca en todo.
#
# Se excluye por el TIPO de entidad y no por donde esta. Filtrar por
# departamento seria mas simple pero dejaria fuera a la Rama Judicial Seccional
# Valle, que es una entidad nacional con sede en el territorio arreglando sus
# propios juzgados: exactamente lo que esta pagina debe mostrar.
TERRITORIAL = ("ALCALDIA", "ALCALDÍA", "MUNICIPIO", "DISTRITO ESPECIAL",
               "GOBERNACION", "GOBERNACIÓN", "DEPARTAMENTO DEL VALLE",
               "CONCEJO", "PERSONERIA", "PERSONERÍA", "EMPRESAS MUNICIPALES",
               "AREA METROPOLITANA", "CAMARA DE COMERCIO",
               "INSTITUCION UNIVERSITARIA", "CORPORACION AUTONOMA")


def _norm(s):
    s = unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode()
    return s.upper()


def _menciona(texto, palabras):
    t = _norm(texto)
    return any(p in t for p in palabras)


def _like(campo, patrones):
    return " OR ".join(f"upper({campo}) like '{p}'" for p in patrones)


def consultar(cfg, consultar_api, registrar=print):
    """Mide los cuatro canales. Devuelve el paquete que pinta la pagina."""
    inicio = cfg.get("fecha_inicio", "2026-08-10")
    ventana = f"fecha_de_firma >= '{inicio}T00:00:00'"
    campos = ("nombre_entidad,fecha_de_firma,valor_del_contrato,"
              "objeto_del_contrato,referencia_del_contrato,urlproceso,"
              "proveedor_adjudicado,departamento")

    canales = []
    vistos = set()
    for clave, rotulo, patrones, explica in CANALES:
        filas = consultar_api(DATASET_CONTRATOS,
                              f"{ventana} AND ({_like('nombre_entidad', patrones)})",
                              campos)
        con_sismo = [f for f in filas if _menciona(f.get("objeto_del_contrato"), SISMO)]
        con_valle = [f for f in filas if _menciona(f.get("objeto_del_contrato"), VALLE)]
        # Lo que de verdad se busca: nombra el evento Y el territorio.
        ambos = [f for f in con_sismo if _menciona(f.get("objeto_del_contrato"), VALLE)]
        for f in filas:
            vistos.add(f.get("referencia_del_contrato") or id(f))
        canales.append({
            "k": clave, "n": rotulo, "explica": explica,
            "total": len(filas),
            "sismo": len(con_sismo),
            "valle": len(con_valle),
            "ops": [_ficha(f) for f in ambos],
        })
        registrar(f"    nacional: {rotulo} -> {len(filas)} contratos, "
                  f"{len(con_sismo)} nombran el sismo, {len(con_valle)} el Valle")

    # Cuarto canal: cualquier OTRA entidad cuyo objeto nombre el sismo Y el
    # Valle. Es la red, y por eso no se filtra por nombre de entidad: si manana
    # aparece una agencia nacional que hoy no existe en ninguna lista, entra.
    obj = " OR ".join(f"upper(objeto_del_contrato) like '%{p}%'" for p in SISMO)
    val = " OR ".join(f"upper(objeto_del_contrato) like '%{p}%'" for p in VALLE)
    filas = consultar_api(DATASET_CONTRATOS, f"{ventana} AND ({obj}) AND ({val})", campos)
    conocidos = tuple(_norm(p.strip("%")) for _, _, ps, _ in CANALES for p in ps)
    otras = []
    territoriales = 0
    for f in filas:
        nom = _norm(f.get("nombre_entidad"))
        if any(p in nom for p in conocidos):
            continue                       # ya esta contado en su canal
        if any(_norm(t) in nom for t in TERRITORIAL):
            territoriales += 1             # es del Valle, no de la Nacion
            continue
        otras.append(f)
    canales.append({
        "k": "otras", "n": "Otras entidades nacionales",
        "explica": "Cualquier otra entidad nacional cuyo objeto nombre a la vez el "
                   "sismo y el Valle. Es la red: no depende de ninguna lista, así "
                   "que cubre también a la que aparezca mañana. No se cuentan aquí "
                   "las alcaldías, municipios y demás entidades territoriales, que "
                   "son el asunto del tablero principal.",
        # Las cuentas de este canal son SOLO las nacionales. Poner aqui las 55
        # que devolvio la consulta inflaria el titular -"de 268 contratos
        # revisados"- contando como nacionales 54 que son de alcaldias del
        # Valle. Las territoriales se dicen aparte, que es informacion, no
        # relleno: son las que ya estan en el tablero principal.
        "total": len(otras), "sismo": len(otras),
        "valle": len(otras), "ops": [_ficha(f) for f in otras],
        "territoriales": territoriales,
    })
    registrar(f"    nacional: otras entidades -> {len(otras)} nacionales con sismo "
              f"y Valle ({territoriales} territoriales descartadas)")
    return canales


def _ficha(f):
    return {
        "e": f.get("nombre_entidad") or "",
        "o": f.get("objeto_del_contrato") or "",
        "v": float(f.get("valor_del_contrato") or 0),
        "d": (f.get("fecha_de_firma") or "")[:10],
        "r": f.get("referencia_del_contrato") or "",
        "p": f.get("proveedor_adjudicado") or "",
        "u": f.get("urlproceso") or "",
        "dep": f.get("departamento") or "",
    }


def escribir(canales, generado, base, destino=None):
    """Escribe nacional.html y datos/nacional.json."""
    datos = {"generado": generado, "canales": canales}
    crudo = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    # </script> dentro de una cadena cerraria la etiqueta antes de tiempo: pasa de
    # verdad, hay objetos pegados desde un PDF con marcado dentro.
    crudo = crudo.replace("</", "<\\/")

    destino = destino or os.path.join(base, "nacional.html")
    with io.open(destino, "w", encoding="utf-8", newline="") as fh:
        fh.write(PLANTILLA.replace("__DATOS__", crudo))

    try:
        ruta = os.path.join(base, "datos", "nacional.json")
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with io.open(ruta, "w", encoding="utf-8", newline="") as fh:
            fh.write(json.dumps(datos, ensure_ascii=False, separators=(",", ":")))
    except OSError as e:
        print(f"  ! no se pudo escribir datos/nacional.json: {e}")
    return destino


PLANTILLA = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Qué ha contratado la Nación para el Valle · Sismo del 10 de agosto de 2026</title>
<style>
/* Misma piel que la version ligera: blanco, verde de marca y la pila del
   sistema. Cero peticiones de red, cero dependencias. */
:root{
  --fondo:#FFFFFF; --texto:#111111; --suave:#5B5B5B; --borde:#E8E6E6;
  --acento:#56A800; --acento-tinta:#3E7C00; --acento-t:#F2F8EA;
  --ambar:#8A6D1F; --ambar-t:#FFF9EC;
}
*{box-sizing:border-box}
body{margin:0;background:var(--fondo);color:var(--texto);
     font:15px/1.55 Helvetica,Arial,system-ui,sans-serif}
.hoja{max-width:860px;margin:0 auto;padding:26px 18px 60px}
h1{font-size:25px;line-height:1.25;margin:0 0 6px;font-weight:700}
h2{font-size:12px;letter-spacing:.09em;text-transform:uppercase;color:var(--suave);
   margin:32px 0 12px;font-weight:700}
p{margin:0 0 12px}
.sub{font-size:15px;color:var(--suave);margin:0 0 4px}
.sello{font-size:12px;color:var(--suave);margin:0 0 24px}
/* El titular: el cero es el mensaje, no un hueco. */
.titular{border:2px solid var(--acento);border-radius:4px;padding:22px 24px;
         margin:0 0 10px;background:var(--acento-t)}
.titular .n{font-size:46px;font-weight:700;line-height:1;color:var(--acento-tinta)}
.titular .q{font-size:17px;margin-top:8px;font-weight:700}
.titular .x{font-size:14px;color:var(--suave);margin-top:6px}
table{width:100%;border-collapse:collapse;margin:0 0 10px}
th,td{text-align:left;padding:10px 8px;border-bottom:1px solid var(--borde);
      vertical-align:top;font-size:14px}
th{font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:var(--suave)}
td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.canal{font-weight:700}
.canal small{display:block;font-weight:400;font-size:12.5px;color:var(--suave);
             margin-top:3px;max-width:52ch}
.cero{color:var(--acento-tinta);font-weight:700}
.aviso{border:1px solid #E0C070;background:var(--ambar-t);border-radius:4px;
       padding:16px 18px;margin:0 0 14px;font-size:14px;line-height:1.55;
       color:#5C4708}
.limite{border:1px solid var(--borde);border-radius:4px;padding:16px 18px;
        font-size:14px;line-height:1.6}
.limite b{color:var(--texto)}
.pie{font-size:12px;color:var(--suave);line-height:1.6;margin-top:28px;
     border-top:1px solid var(--borde);padding-top:14px}
.ficha{border:1px solid var(--borde);border-radius:4px;padding:14px 16px;
       margin-bottom:10px}
.ficha .e{font-weight:700}
.ficha .o{font-size:13.5px;margin-top:6px}
.ficha .m{font-size:12px;color:var(--suave);margin-top:6px}
a.enl{display:inline-block;font-size:11.5px;padding:4px 8px;border-radius:3px;
      border:1px solid var(--borde);text-decoration:none;color:var(--texto);
      margin-top:8px}
a.enl:hover{border-color:var(--acento);color:var(--acento-tinta)}
@media (max-width:560px){
  h1{font-size:21px}
  .titular .n{font-size:38px}
  th:nth-child(3),td:nth-child(3){display:none}
}
</style>
</head>
<body>
<div class="hoja">

<h1>Qué ha contratado la Nación para el Valle</h1>
<p class="sub">Contratación del gobierno nacional relacionada con el sismo del 10 de
agosto de 2026 en beneficio del Valle del Cauca.</p>
<div class="sello" id="sello"></div>

<div id="titular"></div>

<h2>Dónde se buscó</h2>
<table>
  <thead><tr>
    <th>Canal</th>
    <th class="n">Contratos firmados</th>
    <th class="n">Nombran el sismo</th>
    <th class="n">Nombran el Valle</th>
    <th class="n">Para el Valle por el sismo</th>
  </tr></thead>
  <tbody id="canales"></tbody>
</table>
<p style="font-size:13px;color:#5B5B5B">Las tres primeras columnas están para que la
última se pueda juzgar: <b>cero de cero sería no haber mirado; cero de varios cientos
es haber mirado</b>.</p>
<p id="territoriales" style="font-size:13px;color:#5B5B5B"></p>

<div id="hallazgos"></div>

<h2>Qué no alcanza a ver esta página</h2>
<div class="limite">
  <p><b>El FNGRD es un patrimonio autónomo administrado por una fiduciaria.</b> Parte
  de su ejecución puede no aparecer como contrato propio del Fondo en el SECOP, y la
  Subcuenta SISMO 2026 que creó el Decreto 1171 es justamente donde estaría la plata
  nacional de este sismo.</p>
  <p><b>La plata nacional llega muchas veces como transferencia al municipio</b>, que
  después contrata en su propio nombre. Ese gasto existe y es nacional en su origen,
  pero aparece en los registros como contratación municipal, no como contratación de
  la Nación.</p>
  <p style="margin-bottom:0">Por eso esta página no dice «la Nación no ha hecho
  nada». Dice <b>qué se buscó, dónde, y qué se encontró</b>, con su fecha. Lo que
  falta se pregunta por derecho de petición, no se deduce de un cero.</p>
</div>

<div class="pie">
  Fuente: datos.gov.co, SECOP II, contratos firmados desde el 10 de agosto de 2026.
  Los canales se definen por el <b>nombre de la entidad</b> y no por el campo
  <i>orden</i> de SECOP, que es autodeclarado y marca «Nacional» a alcaldías
  municipales. Esta página se actualiza sola con cada recolección.
</div>

</div>

<script id="datos" type="application/json">__DATOS__</script>
<script>
var D = JSON.parse(document.getElementById("datos").textContent);

function esc(s){
  return String(s == null ? "" : s).replace(/[&<>"']/g, function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
  });
}
function pesos(v){ return v ? "$ " + Math.round(v).toLocaleString("es-CO") : "$ 0"; }
function selloLargo(s){
  if (!s) return "";
  var p = String(s).split(/[- :]/);
  var meses = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto",
               "septiembre","octubre","noviembre","diciembre"];
  var d = new Date(+p[0], +p[1] - 1, +p[2], +(p[3]||0), +(p[4]||0));
  var h = d.getHours(), ap = h >= 12 ? "p. m." : "a. m.";
  var h12 = h % 12 || 12;
  return (+p[2]) + " de " + meses[+p[1] - 1] + " de " + p[0] + ", " +
         h12 + ":" + String(d.getMinutes()).padStart(2, "0") + " " + ap;
}

var TOTAL = D.canales.reduce(function(s, c){ return s + c.ops.length; }, 0);
var MIRADOS = D.canales.reduce(function(s, c){ return s + c.total; }, 0);

document.getElementById("sello").textContent =
  "Consulta del " + selloLargo(D.generado) + " · ventana desde el 10 de agosto de 2026";

/* El titular cambia de cara segun haya o no hallazgos. Un cero anunciado con el
   mismo tono que un hallazgo se lee como que el dato falta. */
document.getElementById("titular").innerHTML = TOTAL === 0
  ? '<div class="titular"><div class="n">0</div>' +
    '<div class="q">contratos del gobierno nacional para el Valle por el sismo</div>' +
    '<div class="x">Se revisaron ' + MIRADOS.toLocaleString("es-CO") +
    ' contratos firmados por entidades nacionales desde el 10 de agosto. ' +
    'Ninguno nombra a la vez el sismo y el Valle del Cauca.</div></div>'
  : '<div class="titular"><div class="n">' + TOTAL + '</div>' +
    '<div class="q">contrato' + (TOTAL === 1 ? "" : "s") +
    ' del gobierno nacional para el Valle por el sismo</div>' +
    '<div class="x">De ' + MIRADOS.toLocaleString("es-CO") +
    ' contratos firmados por entidades nacionales desde el 10 de agosto.</div></div>';

document.getElementById("canales").innerHTML = D.canales.map(function(c){
  return "<tr>" +
    '<td class="canal">' + esc(c.n) + "<small>" + esc(c.explica) + "</small></td>" +
    '<td class="n">' + c.total.toLocaleString("es-CO") + "</td>" +
    '<td class="n">' + c.sismo.toLocaleString("es-CO") + "</td>" +
    '<td class="n">' + c.valle.toLocaleString("es-CO") + "</td>" +
    '<td class="n' + (c.ops.length ? '' : ' cero') + '">' + c.ops.length + "</td></tr>";
}).join("");

/* Los territoriales descartados se dicen, no se callan: son 54 contratos que
   nombran el sismo y el Valle y que alguien podria echar en falta aqui. Decir
   donde estan es lo que evita que la cifra de esta pagina parezca incompleta. */
var TERR = D.canales.reduce(function(s, c){ return s + (c.territoriales || 0); }, 0);
document.getElementById("territoriales").innerHTML = TERR
  ? "Además, <b>" + TERR + " contratos</b> nombran el sismo y el Valle pero los firmaron " +
    "alcaldías, municipios y otras entidades territoriales. No son contratación de la " +
    "Nación y no se cuentan aquí: son el asunto del tablero principal."
  : "";

var conOps = D.canales.filter(function(c){ return c.ops.length; });
document.getElementById("hallazgos").innerHTML = conOps.length
  ? "<h2>Lo que se encontró</h2>" + conOps.map(function(c){
      return c.ops.map(function(o){
        return '<div class="ficha"><div class="e">' + esc(o.e) + "</div>" +
          '<div class="o">' + esc(o.o) + "</div>" +
          '<div class="m">' + esc(pesos(o.v)) + " · firmado " + esc(o.d) +
          (o.p ? " · " + esc(o.p) : "") + (o.r ? " · " + esc(o.r) : "") + "</div>" +
          (o.u ? '<a class="enl" href="' + esc(o.u) +
                 '" target="_blank" rel="noopener">Ver en SECOP</a>' : "") +
          "</div>";
      }).join("");
    }).join("")
  : '<div class="aviso" style="margin-top:28px"><b>No hay nada que listar, y eso ' +
    'es el hallazgo.</b> A un mes del sismo, ninguna entidad del gobierno nacional ' +
    'registra en el SECOP un contrato que atienda la emergencia en el Valle del ' +
    'Cauca. El cero está medido, no supuesto: abajo está dónde se buscó.</div>';

/* Alto automatico para cuando va incrustada, igual que la version ligera. */
(function(){
  if (window.parent === window) return;
  var ultimo = 0, pend = null;
  function medir(){
    var a = Math.max(document.documentElement.scrollHeight,
                     document.body ? document.body.scrollHeight : 0);
    if (Math.abs(a - ultimo) < 8) return;
    ultimo = a;
    window.parent.postMessage({ tipo: "tablero-sismo:alto", alto: a }, "*");
  }
  function avisar(){ if (pend) cancelAnimationFrame(pend); pend = requestAnimationFrame(medir); }
  window.addEventListener("load", avisar);
  window.addEventListener("resize", avisar);
  if (window.ResizeObserver && document.body) new ResizeObserver(avisar).observe(document.body);
  setInterval(medir, 1500);
  avisar();
})();
</script>
</body>
</html>
"""
