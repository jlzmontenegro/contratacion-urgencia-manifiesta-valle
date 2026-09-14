# -*- coding: utf-8 -*-
"""Toda la contratacion de la Secretaria de Infraestructura de la Gobernacion.

Del sismo y ordinaria, DESDE EL 1 DE ENERO DE 2024. Lo pidio el usuario el
14-sep-2026: primero "revisa toda la contratacion que haya de la secretaria de
infraestructura de la Gobernacion del Valle, sismo y no sismo, y saca un html
solo de ello", y enseguida "que consulte desde 1 de enero de 2024".

POR QUE UNA PAGINA APARTE. El tablero principal responde "que se contrato por el
sismo" y por eso deja fuera casi todo lo de esta Secretaria: de sus 148 contratos
posteriores al sismo ninguno nombra el evento. Esta pagina responde otra pregunta
-"que hizo la Secretaria que tendria que reconstruir"- y ahi la contratacion
ordinaria no es ruido: es la respuesta.

POR QUE LA VENTANA ES MAS LARGA QUE LA DEL MONITOR. El monitor arranca el dia del
sismo porque su pregunta es que se contrato por el evento. Aqui la pregunta es si
lo que se ve despues del sismo se sale de lo normal, y eso no se puede contestar
sin lo normal. Medido el 14-sep-2026 sobre los 1.923 contratos de la ventana: hay
5 de obra en dos anos y medio, ninguno posterior al sismo, y concentran mas de la
mitad de todo el dinero. Ese reparto es el que hace legible el cero.

COMO SE IDENTIFICA LA DEPENDENCIA. SECOP II no trae un campo de dependencia: la
Gobernacion publica cada secretaria como un nombre_entidad distinto bajo el mismo
NIT. Medido el 14-sep-2026: 27 nombres para los tres NIT de la Gobernacion, y uno
solo lleva INFRAESTRUCTURA. Por eso el filtro es NIT + nombre, y no una lista de
nombres escrita a mano: el dia que la entidad cambie la redaccion del nombre,
esto la sigue encontrando.

  OJO: filtrar solo por '%INFRAESTRUCTURA%' sin el NIT traeria tambien la
  Secretaria de Infraestructura de Cali y la de Habitat e Infraestructura de
  Tulua. Son otras entidades.

SE ACTUALIZA SOLA, como ligero.html y nacional.html: la llama el colector al
final de cada recoleccion. No se edita el HTML, se edita este archivo.
"""

import io
import json
import os
import re
import unicodedata

DATASET_CONTRATOS = "jbjy-vk9h"
DATASET_PROCESOS = "p6dx-8zbt"

# El nombre con que SECOP publica la dependencia, en el filtro de la consulta.
# Se combina SIEMPRE con el NIT de la Gobernacion.
PATRON_NOMBRE = "%INFRAESTRUCTURA%"

# Desde cuando se mira. El usuario lo pidio asi el 14-sep-2026: "que consulte
# desde 1 de enero de 2024". Es la ventana de esta pagina y NO la del monitor,
# que arranca el dia del sismo: aqui la contratacion anterior no es contexto
# prescindible, es la unica forma de saber si lo que se ve despues del sismo se
# sale de lo normal o es exactamente lo de siempre.
DESDE = "2024-01-01"

# Palabras del evento, las mismas del clasificador en corto. Aqui solo sirven
# para contar cuantos objetos lo nombran, que es una cifra de la pagina.
SISMO = ("SISMO", "SISMIC", "TERREMOTO", "MOVIMIENTO TELURICO",
         "10 DE AGOSTO DE 2026")
EMERGENCIA = ("URGENCIA MANIFIESTA", "CALAMIDAD", "DAMNIFICAD", "EMERGENCIA",
              "DESASTRE", "AYUDA HUMANITARIA", "ALBERGUE", "ESCOMBRO")


def _norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.upper())


def _menciona(texto, palabras):
    t = _norm(texto)
    return any(p in t for p in palabras)


def _num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def _fecha(v):
    return str(v or "")[:10]


def _url(v):
    # urlproceso es una columna de tipo URL de Socrata: llega como {'url': ...}.
    # Tratarla como cadena deja el repr del diccionario en el href.
    if isinstance(v, dict):
        return v.get("url", "")
    return str(v or "")


def _clausula(nits, campo):
    """Compara el NIT contra las variantes que publica la fuente.

    Las variantes salen de config.json y NO se reconstruyen con la formula del
    digito de verificacion: SECOP publica el mismo NIT con digitos que no son el
    matematico -la Gobernacion convive como 890399029, 8903990291 y 8903990295-
    y reconstruirlos ya bloqueo una publicacion entera el 20-ago-2026.

    En contratos de SECOP II nit_entidad es ademas una columna NUMERICA: pasarle
    una cadena con guion aborta la consulta en vez de devolver vacio. Todas las
    variantes de config.json son digitos, asi que sirven en las dos fuentes.
    """
    return "(" + " OR ".join(f"{campo} = '{n}'" for n in nits) + ")"


# --------------------------------------------------------------------------
# Consulta
# --------------------------------------------------------------------------

def consultar(cfg, consultar_api, registrar=print):
    """Baja y arma el paquete que pinta la pagina.

    `consultar_api(dataset, where)` la inyecta el colector para reutilizar sus
    reintentos y su token, igual que en documentos.py: se inyecta en vez de
    importarla para no crear un import circular.
    """
    evento = cfg.get("fecha_evento", "2026-08-10")
    nits = cfg.get("nits_gobernacion_valle") or ["890399029"]

    filtro_c = f"{_clausula(nits, 'nit_entidad')} AND upper(nombre_entidad) like '{PATRON_NOMBRE}'"
    filtro_p = f"{_clausula(nits, 'nit_entidad')} AND upper(entidad) like '{PATRON_NOMBRE}'"

    contratos = consultar_api(
        DATASET_CONTRATOS,
        f"{filtro_c} AND fecha_de_firma >= '{DESDE}T00:00:00'")
    procesos = consultar_api(
        DATASET_PROCESOS,
        f"{filtro_p} AND fecha_de_publicacion_del >= '{DESDE}T00:00:00'")
    registrar(f"    infraestructura: {len(contratos)} contratos y {len(procesos)} "
              f"procesos desde el {DESDE}")

    nombre = ""
    for fila in contratos:
        nombre = fila.get("nombre_entidad") or ""
        if nombre:
            break

    # El corte es el sismo. No se baja dos veces: se parte la misma descarga,
    # que ademas garantiza que las dos columnas de la comparacion salen de los
    # mismos criterios. Bajarlas por separado deja la puerta abierta a que una
    # consulta cambie y la otra no.
    desde_sismo = [c for c in contratos if _fecha(c.get("fecha_de_firma")) >= evento]
    antes_sismo = [c for c in contratos if _fecha(c.get("fecha_de_firma")) < evento]
    registrar(f"    infraestructura: {len(desde_sismo)} desde el sismo, "
              f"{len(antes_sismo)} antes")

    ops = _operaciones(contratos, procesos, evento)
    docs = _documentos(ops, consultar_api, registrar)

    return {
        "entidad": nombre or "Secretaría de Infraestructura - Gobernación del Valle",
        "nit": (contratos or [{}])[0].get("nit_entidad", ""),
        "desde": DESDE,
        "evento": evento,
        "ops": ops,
        "tipos": {
            "desde": _por_tipo(desde_sismo),
            "antes": _por_tipo(antes_sismo),
        },
        "anios": _por_anio(contratos),
        # La obra de todo el periodo, contratos y procesos. Es lo que una
        # secretaria de infraestructura existe para hacer, y por eso va aparte:
        # son 5 contratos entre 1.923, y en una tabla de 1.923 filas se pierden.
        "obra": _fichas_obra(ops),
        "perfil": _perfil(desde_sismo),
        "docs": docs,
    }


def _por_anio(contratos):
    agg = {}
    for c in contratos or []:
        a = _fecha(c.get("fecha_de_firma"))[:4]
        if not a:
            continue
        d = agg.setdefault(a, {"n": 0, "v": 0.0, "obra": 0, "obra_v": 0.0})
        d["n"] += 1
        d["v"] += _num(c.get("valor_del_contrato"))
        if _tipo(c) == "Obra":
            d["obra"] += 1
            d["obra_v"] += _num(c.get("valor_del_contrato"))
    return [dict(a=a, **d) for a, d in sorted(agg.items())]


def _tipo(fila):
    """Tipo de contrato unificado. La fuente lo escribe de varias formas."""
    t = _norm(fila.get("tipo_de_contrato"))
    if "PRESTACION" in t:
        return "Prestación de servicios"
    if t.startswith("OBRA"):
        return "Obra"
    if "SUMINISTRO" in t:
        return "Suministros"
    if "CONSULTORIA" in t:
        return "Consultoría"
    if "INTERVENTORIA" in t:
        return "Interventoría"
    if "COMPRAVENTA" in t:
        return "Compraventa"
    if "ARRENDAMIENTO" in t:
        return "Arrendamiento"
    if "CONCESION" in t:
        return "Concesión"
    if not t or t == "NAN":
        return "Sin tipo en la fuente"
    return fila.get("tipo_de_contrato") or "Otro"


def _por_tipo(filas):
    agg = {}
    for f in filas or []:
        t = _tipo(f)
        d = agg.setdefault(t, {"n": 0, "v": 0.0})
        d["n"] += 1
        d["v"] += _num(f.get("valor_del_contrato"))
    return [{"t": t, "n": d["n"], "v": d["v"]}
            for t, d in sorted(agg.items(), key=lambda kv: -kv[1]["v"])]


def _fichas_obra(ops):
    """La obra del periodo entero, contratos y procesos.

    Va aparte y no solo dentro de la tabla porque son unas pocas filas entre casi
    dos mil: en la tabla se pierden, y son justo lo que esta Secretaria existe
    para hacer. Se listan TODAS -no las N mayores-: un recorte silencioso aqui
    haria creer que hay mas obra de la que hay.
    """
    obra = [o for o in ops if o.get("tc") == "Obra"]
    obra.sort(key=lambda o: -(o.get("v") or o.get("pb") or 0))
    return obra


def _perfil(contratos):
    """Las cuatro o cinco cosas que se repiten en TODOS los contratos.

    Se calculan y solo se muestran las que de verdad son unanimes o casi: decir
    "el 100% es contratacion directa" cuando es el 60% seria peor que callarlo.
    """
    n = len(contratos or [])
    if not n:
        return {}

    def manda(campo, transformar=lambda x: x):
        cuenta = {}
        for f in contratos:
            k = transformar(f.get(campo) or "")
            cuenta[k] = cuenta.get(k, 0) + 1
        k, c = max(cuenta.items(), key=lambda kv: kv[1])
        return {"v": k, "n": c, "pct": round(100.0 * c / n)}

    docs = [str(f.get("documento_proveedor") or "") for f in contratos if f.get("documento_proveedor")]
    repetidos = {d for d in docs if docs.count(d) > 1}

    fechas = sorted({_fecha(f.get("fecha_de_firma")) for f in contratos if f.get("fecha_de_firma")})
    fines = sorted({_fecha(f.get("fecha_de_fin_del_contrato"))
                    for f in contratos if f.get("fecha_de_fin_del_contrato")})

    return {
        "modalidad": manda("modalidad_de_contratacion"),
        "duracion": manda("duraci_n_del_contrato"),
        "fin": manda("fecha_de_fin_del_contrato", _fecha),
        "persona": {
            "n": sum(1 for f in contratos if "CEDULA" in _norm(f.get("tipodocproveedor"))),
            "total": n,
        },
        # Cuantos contratistas tienen mas de un contrato. Cero tambien se dice:
        # es una comprobacion hecha, no un dato que falte.
        "repetidos": len(repetidos),
        "ordenador": manda("nombre_ordenador_del_gasto"),
        "primera_firma": fechas[0] if fechas else "",
        "ultima_firma": fechas[-1] if fechas else "",
        "ultimo_fin": fines[-1] if fines else "",
    }


def _operaciones(contratos, procesos, evento):
    """Una fila por contratacion: el proceso y su contrato son el mismo hecho.

    La llave es el expediente (CO1.BDOS.*), que en contratos se llama
    proceso_de_compra y en procesos id_del_portafolio. El cruce obvio -por
    id_del_proceso- da CERO coincidencias, que es facil de confundir con "no hay
    relacion".

    OJO: UN EXPEDIENTE PUEDE TENER DOS CONTRATOS. Medido el 14-sep-2026: los 148
    contratos de la ventana cuelgan de 147 expedientes, porque CO1.BDOS.10681604
    lleva dos contratos con dos personas distintas por $24.000.000 cada uno. Si
    la fila se construyera indexando por expediente, uno de los dos desapareceria
    sin que nada fallara y la pagina diria 147 donde hay 148. Por eso la lista se
    arma sobre los CONTRATOS y el proceso solo se le adosa a cada uno.
    """
    proceso_de = {}
    for p in procesos or []:
        exp = str(p.get("id_del_portafolio") or "")
        if exp:
            proceso_de[exp] = p

    ops = []
    con_contrato = set()

    for c in contratos or []:
        exp = str(c.get("proceso_de_compra") or "")
        con_contrato.add(exp)
        fila = {
            "exp": exp,
            "r": c.get("referencia_del_contrato", ""),
            "o": c.get("objeto_del_contrato") or c.get("descripcion_del_proceso") or "",
            "v": _num(c.get("valor_del_contrato")),
            "tc": _tipo(c),
            "mod": c.get("modalidad_de_contratacion", ""),
            "est": c.get("estado_contrato", ""),
            "f": _fecha(c.get("fecha_de_firma")),
            "fi": _fecha(c.get("fecha_de_inicio_del_contrato")),
            "ff": _fecha(c.get("fecha_de_fin_del_contrato")),
            "dur": c.get("duraci_n_del_contrato", ""),
            "p": c.get("proveedor_adjudicado", ""),
            "pd": str(c.get("documento_proveedor") or ""),
            "sup": c.get("nombre_supervisor", ""),
            "u": _url(c.get("urlproceso")),
            "up": "",
            "pb": 0.0,
            "estp": "",
            "fp": "",
            "rp": "",
            "firmado": True,
        }
        p = proceso_de.get(exp)
        if p:
            fila.update(_del_proceso(p))
        ops.append(fila)

    for exp, p in proceso_de.items():
        if exp in con_contrato:
            continue
        # Proceso sin contrato: es la contratacion que se abrio y todavia no se
        # firmo. Se muestra igual, marcada, porque es justo lo que hay que vigilar.
        fila = {
            "exp": exp,
            "r": p.get("referencia_del_proceso", ""),
            "o": p.get("descripci_n_del_procedimiento") or p.get("nombre_del_procedimiento") or "",
            "v": 0.0,
            "tc": _tipo(p),
            "mod": p.get("modalidad_de_contratacion", ""),
            "est": "",
            "f": "", "fi": "", "ff": "", "dur": "", "p": "", "pd": "", "sup": "",
            "u": "", "firmado": False,
        }
        fila.update(_del_proceso(p))
        ops.append(fila)

    for o in ops:
        texto = o["o"]
        # A que lado del sismo cae. Se mira la firma si la hay y si no la
        # publicacion del proceso: un proceso abierto sin contrato no tiene
        # fecha de firma y quedaria siempre del lado de antes.
        o["post"] = (o["f"] or o["fp"] or "") >= evento
        o["sismo"] = _menciona(texto, SISMO)
        o["emer"] = _menciona(texto, EMERGENCIA)
        # El objeto que llega justo en el tope de la fuente viene cortado por
        # SECOP, no por nosotros, y presentarlo como entero desinforma.
        o["cortado"] = len(texto) in (300, 500)
        o["ce"] = ""
        o["ep"] = ""
        o["ej"] = ""
        o["dn"] = 0
    ops.sort(key=lambda o: (-(o["v"] or o["pb"]), o["r"]))
    return ops


def _del_proceso(p):
    """Lo que el proceso le aporta a la fila del contrato que salio de el."""
    return {
        "up": _url(p.get("urlproceso")),
        "pb": _num(p.get("precio_base")),
        "estp": p.get("estado_del_procedimiento", ""),
        "fp": _fecha(p.get("fecha_de_publicacion_del")),
        "rp": p.get("referencia_del_proceso", ""),
    }


def _documentos(ops, consultar_api, registrar):
    """Enlaza cada fila con los documentos de su expediente. Best effort.

    Si el dataset no responde, la pagina sale igual sin los botones: de aqui no
    cuelga ninguna cifra, un expediente es un atajo. Devuelve el recuento, que si
    se muestra: que en 148 expedientes no este publicado el texto del contrato es
    un hecho sobre como publica la entidad, no un hueco de esta pagina, y callarlo
    lo haria parecer lo segundo.
    """
    resumen = {"exp": 0, "contrato": 0, "ep": 0, "ejecucion": 0, "fallo": False,
               "solo_post": True}
    # SOLO lo posterior al sismo. Los 1.900 expedientes del periodo entero serian
    # 48 consultas al dataset de documentos en cada corrida, tres veces al dia,
    # para un atajo que en la contratacion de 2024 no le sirve a nadie. Las filas
    # viejas conservan igual sus enlaces al expediente y al proceso, que vienen en
    # el propio registro.
    post = [o for o in ops if o.get("post")]
    try:
        import documentos
        indice = documentos.consultar(
            [o["exp"] for o in post], consultar_api, registrar=lambda *a: None)
        for o in ops:
            d = indice.get(o["exp"])
            if not d:
                continue
            o["ce"] = d.get("contrato", "")
            o["ep"] = d.get("ep", "")
            o["ej"] = d.get("ejecucion", "")
            o["dn"] = d.get("n", 0)
        # Se cuenta sobre EXPEDIENTES y no sobre filas: un expediente puede
        # llevar dos contratos, y contando filas la cobertura saldria "149 de
        # 148", que se lee como un error de la pagina.
        resumen["exp"] = len(indice)
        resumen["contrato"] = sum(1 for d in indice.values() if d.get("contrato"))
        resumen["ep"] = sum(1 for d in indice.values() if d.get("ep"))
        resumen["ejecucion"] = sum(1 for d in indice.values() if d.get("ejecucion"))
        resumen["ops"] = len(post)
        registrar(f"    infraestructura: documentos en {resumen['exp']} expedientes "
                  f"(contrato {resumen['contrato']}, estudios previos {resumen['ep']}, "
                  f"ejecucion {resumen['ejecucion']})")
    except Exception as e:
        resumen["fallo"] = True
        registrar(f"    ! infraestructura: sin documentos del expediente: {e}")
    return resumen


# --------------------------------------------------------------------------
# Escritura
# --------------------------------------------------------------------------

def escribir(datos, generado, base):
    datos = dict(datos)
    datos["generado"] = generado
    destino = os.path.join(base, "infraestructura.html")
    crudo = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    crudo = crudo.replace("</", "<\\/")
    with io.open(destino, "w", encoding="utf-8", newline="") as fh:
        fh.write(PLANTILLA.replace("__DATOS__", crudo))

    try:
        ruta = os.path.join(base, "datos", "infraestructura.json")
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with io.open(ruta, "w", encoding="utf-8", newline="") as fh:
            fh.write(json.dumps(datos, ensure_ascii=False, separators=(",", ":")))
    except OSError as e:
        print(f"  ! no se pudo escribir datos/infraestructura.json: {e}")
    return destino


PLANTILLA = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Contratación de la Secretaría de Infraestructura del Valle · desde 2024</title>
<style>
/* Misma piel que la version ligera y la nacional: blanco, verde de marca y la
   pila del sistema. Cero peticiones de red, cero dependencias externas. */
:root{
  --fondo:#FFFFFF; --texto:#111111; --suave:#5B5B5B; --borde:#E8E6E6;
  --acento:#56A800; --acento-tinta:#3E7C00; --acento-t:#F2F8EA;
  --ambar:#8A6D1F; --ambar-t:#FFF9EC; --ambar-b:#E0C070;
  --gris-t:#F6F6F5;
}
*{box-sizing:border-box}
body{margin:0;background:var(--fondo);color:var(--texto);
     font:15px/1.55 Helvetica,Arial,system-ui,sans-serif}
.hoja{max-width:900px;margin:0 auto;padding:26px 18px 60px}
h1{font-size:25px;line-height:1.25;margin:0 0 6px;font-weight:700}
h2{font-size:12px;letter-spacing:.09em;text-transform:uppercase;color:var(--suave);
   margin:34px 0 12px;font-weight:700}
p{margin:0 0 12px}
.sub{font-size:15px;color:var(--suave);margin:0 0 4px}
.sello{font-size:12px;color:var(--suave);margin:0 0 22px}
.titular{border:2px solid var(--acento);border-radius:4px;padding:22px 24px;
         margin:0 0 12px;background:var(--acento-t)}
.titular .n{font-size:40px;font-weight:700;line-height:1;color:var(--acento-tinta)}
.titular .q{font-size:17px;margin-top:8px;font-weight:700}
.titular .x{font-size:14px;color:var(--suave);margin-top:8px}
.cifras{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:0 0 14px}
.cifra{border:1px solid var(--borde);border-radius:4px;padding:12px 14px}
.cifra .n{font-size:26px;font-weight:700;line-height:1.1}
.cifra .q{font-size:12px;color:var(--suave);margin-top:4px;line-height:1.35}
.cifra.cero .n{color:var(--acento-tinta)}
table{width:100%;border-collapse:collapse;margin:0 0 10px}
th,td{text-align:left;padding:9px 8px;border-bottom:1px solid var(--borde);
      vertical-align:top;font-size:14px}
th{font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:var(--suave)}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
td.n{white-space:nowrap}
/* El encabezado SI parte: con nowrap, '12 meses anteriores' mide 160px y
   saca la tabla entera de la pantalla del telefono. Los numeros no parten. */
th.n{white-space:normal}
.marco{overflow-x:auto}
tr.tot td{font-weight:700;border-top:2px solid var(--borde);border-bottom:none}
.marca{color:var(--acento-tinta);font-weight:700}
.nota{font-size:13px;color:var(--suave);line-height:1.6}
.aviso{border:1px solid var(--ambar-b);background:var(--ambar-t);border-radius:4px;
       padding:16px 18px;margin:0 0 14px;font-size:14px;line-height:1.55;color:#5C4708}
.limite{border:1px solid var(--borde);border-radius:4px;padding:16px 18px;
        font-size:14px;line-height:1.6}
.perfil{list-style:none;padding:0;margin:0}
.perfil li{padding:9px 0;border-bottom:1px solid var(--borde);font-size:14px}
.perfil li:last-child{border-bottom:none}
.perfil b{font-weight:700}
/* position:relative y overflow visible: el panel de anos se ancla al BLOQUE de
   filtros y no a su columna, que mide 180px. Es la misma leccion que ya se pago
   en el tablero grande, donde .plegable llevaba overflow:hidden y cortaba el
   panel en seco sin que nada lo dijera. */
.filtros{border:1px solid var(--borde);border-radius:4px;padding:14px 16px;
         margin:0 0 14px;background:var(--gris-t);position:relative;overflow:visible}
.filtros .fila{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end}
.campo{display:flex;flex-direction:column;gap:4px;flex:1 1 180px}
.campo label{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--suave)}
.campo input,.campo select{font:14px/1.4 inherit;padding:7px 8px;border:1px solid var(--borde);
                           border-radius:3px;background:#fff;color:var(--texto)}
.campo input:focus,.campo select:focus{outline:2px solid var(--acento);outline-offset:-1px}
/* Multiseleccion de anos: un <details> con casillas, no un <select multiple>.
   El nativo obliga a Ctrl+clic y en el telefono es inmanejable. */
.multi{position:static}
.multi>summary{font:14px/1.4 inherit;padding:7px 8px;border:1px solid var(--borde);
               border-radius:3px;background:#fff;cursor:pointer;list-style:none;
               display:flex;justify-content:space-between;gap:8px;align-items:center}
.multi>summary::-webkit-details-marker{display:none}
.multi>summary::after{content:"▾";color:var(--suave);font-size:11px}
.multi[open]>summary{border-color:var(--acento)}
.multi>summary:focus-visible{outline:2px solid var(--acento);outline-offset:-1px}
.multi .panel{position:absolute;left:14px;right:14px;z-index:20;margin-top:6px;
              background:#fff;border:1px solid var(--acento);border-radius:4px;
              padding:12px 14px;box-shadow:0 6px 20px rgba(0,0,0,.10);
              display:flex;flex-wrap:wrap;gap:6px 18px}
.multi .panel label{display:flex;gap:7px;align-items:center;font-size:14px;
                    cursor:pointer;white-space:nowrap}
.multi .panel small{color:var(--suave)}
.acciones{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
button.b{font:13px/1 inherit;padding:8px 12px;border:1px solid var(--borde);
         border-radius:3px;background:#fff;color:var(--texto);cursor:pointer}
button.b:hover{border-color:var(--acento);color:var(--acento-tinta)}
.resumen{font-size:13px;color:var(--suave);margin:0 0 10px}
.op{border:1px solid var(--borde);border-radius:4px;padding:14px 16px;margin-bottom:10px}
.op .cab{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:baseline}
.op .ref{font-weight:700;font-size:14px}
.op .val{font-weight:700;font-size:16px;white-space:nowrap;font-variant-numeric:tabular-nums}
.op .obj{font-size:14px;margin:8px 0 0}
.op .meta{font-size:12.5px;color:var(--suave);margin-top:8px;line-height:1.6}
.op .meta b{color:var(--texto);font-weight:700}
.et{display:inline-block;font-size:11px;padding:2px 7px;border-radius:99px;
    border:1px solid var(--borde);color:var(--suave);margin-left:6px;white-space:nowrap}
.et.ok{border-color:var(--acento);color:var(--acento-tinta);background:var(--acento-t)}
.et.ab{border-color:var(--ambar-b);color:var(--ambar);background:var(--ambar-t)}
.enls{margin-top:10px;display:flex;gap:6px;flex-wrap:wrap}
a.enl{display:inline-block;font-size:11.5px;padding:5px 9px;border-radius:3px;
      border:1px solid var(--borde);text-decoration:none;color:var(--texto)}
a.enl:hover{border-color:var(--acento);color:var(--acento-tinta)}
.pag{display:flex;gap:8px;align-items:center;justify-content:center;margin:16px 0 0;
     font-size:13px;color:var(--suave)}
.vacio{border:1px dashed var(--borde);border-radius:4px;padding:22px;text-align:center;
       font-size:14px;color:var(--suave)}
.pie{font-size:12px;color:var(--suave);line-height:1.6;margin-top:30px;
     border-top:1px solid var(--borde);padding-top:14px}
/* El informe impreso. La pagina entera se oculta y se imprime #impresion, que
   se arma en el momento con TODAS las filas del filtro y no con las 20 de la
   pagina. Es la misma solucion del tablero grande: la impresion del navegador
   con hoja de estilos, no una libreria. */
#impresion{display:none}
@media print{
  .hoja{display:none !important}
  #impresion{display:block}
  @page{margin:14mm 12mm}
  body{background:#fff;color:#000;font:10pt/1.35 Helvetica,Arial,sans-serif;
       print-color-adjust:exact;-webkit-print-color-adjust:exact}
  #impresion h1{font-size:15pt;margin:0 0 4pt}
  #impresion .cab-inf{font-size:8.5pt;color:#333;border-bottom:1.5pt solid #56A800;
                      padding-bottom:6pt;margin-bottom:10pt;line-height:1.45}
  #impresion .cab-inf b{color:#000}
  #impresion table{width:100%;border-collapse:collapse}
  #impresion th{font-size:7.5pt;text-transform:uppercase;letter-spacing:.05em;
                text-align:left;border-bottom:1pt solid #000;padding:4pt 4pt}
  #impresion td{font-size:8.5pt;vertical-align:top;padding:5pt 4pt;
                border-bottom:.5pt solid #ccc}
  #impresion tr{break-inside:avoid;page-break-inside:avoid}
  #impresion td.n{text-align:right;white-space:nowrap}
  #impresion .obj{display:block;margin-top:2pt;color:#222}
  #impresion .enl-inf{font-size:7.5pt;color:#3E7C00;text-decoration:none;
                      word-break:break-all}
  #impresion .pie-inf{margin-top:10pt;font-size:8pt;color:#444;
                      border-top:.5pt solid #999;padding-top:6pt}
}
@media (max-width:640px){
  h1{font-size:21px}
  .titular .n{font-size:32px}
  .cifras{grid-template-columns:repeat(2,1fr)}
  th.vcol,td.vcol{display:none}
}
</style>
</head>
<body>
<div class="hoja">

<h1>La contratación de la Secretaría de Infraestructura del Valle</h1>
<p class="sub">Todo lo que firmó y lo que publicó en el SECOP desde el 1 de enero de
2024 —del sismo del 10 de agosto de 2026 y ordinaria—, y qué cambió después del sismo.</p>
<div class="sello" id="sello"></div>

<div id="titular"></div>

<h2>Año por año</h2>
<div class="marco"><table>
  <thead><tr>
    <th>Año</th>
    <th class="n">Contratos firmados</th>
    <th class="n">Valor</th>
    <th class="n">De ellos, de obra</th>
    <th class="n vcol">Valor de la obra</th>
  </tr></thead>
  <tbody id="anios"></tbody>
</table></div>
<p class="nota" id="nota-anios"></p>

<div id="desde-sismo"></div>
<div class="cifras" id="cifras"></div>
<p class="nota" id="nota-cifras"></p>

<h2>Qué clase de contratación es, antes y después</h2>
<div class="marco"><table>
  <thead><tr>
    <th>Tipo de contrato</th>
    <th class="n">Desde el sismo</th>
    <th class="n vcol">Valor</th>
    <th class="n">Antes del sismo</th>
    <th class="n vcol">Valor</th>
  </tr></thead>
  <tbody id="tipos"></tbody>
</table></div>
<p class="nota" id="nota-tipos"></p>

<div id="obra"></div>

<div id="mayores"></div>

<h2>El perfil de lo firmado desde el sismo</h2>
<ul class="perfil" id="perfil"></ul>

<div id="expedientes"></div>

<h2>Todos los contratos y procesos</h2>
<div class="filtros">
  <div class="fila">
    <div class="campo" style="flex:2 1 260px">
      <label for="f-txt">Buscar en objeto, número o contratista</label>
      <input id="f-txt" type="search" placeholder="vía, puente, ingeniero, 1.360.19.13…">
    </div>
    <div class="campo">
      <label for="f-per">Periodo</label>
      <select id="f-per">
        <option value="">Todo desde 2024</option>
        <option value="post">Desde el sismo</option>
        <option value="pre">Antes del sismo</option>
      </select>
    </div>
    <div class="campo">
      <label id="lab-anios">Años</label>
      <details class="multi" id="f-anios">
        <summary id="res-anios" aria-labelledby="lab-anios">Todos los años</summary>
        <div class="panel" id="panel-anios"></div>
      </details>
    </div>
    <div class="campo">
      <label for="f-tipo">Tipo de contrato</label>
      <select id="f-tipo"><option value="">Todos</option></select>
    </div>
    <div class="campo">
      <label for="f-est">Estado</label>
      <select id="f-est">
        <option value="">Todo</option>
        <option value="si">Solo contratos firmados</option>
        <option value="no">Solo procesos sin contrato</option>
      </select>
    </div>
    <div class="campo">
      <label for="f-rel">Relación con el sismo</label>
      <select id="f-rel">
        <option value="">Todo</option>
        <option value="sismo">Nombra el sismo</option>
        <option value="emer">Vocabulario de emergencia</option>
        <option value="ord">Ni una cosa ni la otra</option>
      </select>
    </div>
    <div class="campo">
      <label for="f-ord">Ordenar por</label>
      <select id="f-ord">
        <option value="v-">Valor, de mayor a menor</option>
        <option value="v+">Valor, de menor a mayor</option>
        <option value="f-">Fecha, más reciente primero</option>
        <option value="f+">Fecha, más antigua primero</option>
        <option value="p+">Contratista, A–Z</option>
      </select>
    </div>
  </div>
  <div class="acciones">
    <button class="b" id="b-limpiar" type="button">Quitar filtros</button>
    <button class="b" id="b-csv" type="button">Descargar lo que se ve (CSV)</button>
    <button class="b" id="b-pdf" type="button">Informe en PDF de lo que se ve</button>
  </div>
</div>

<p class="resumen" id="resumen"></p>
<div id="tabla"></div>
<div class="pag" id="pag"></div>

<h2>Qué no alcanza a ver esta página</h2>
<div class="limite">
  <p><b>Solo mira lo que la Secretaría firma a su nombre.</b> El departamento puede
  ejecutar obra por otras vías que no aparecen aquí: contratación de otra dependencia
  de la Gobernación, la concesión vial <i>Malla Vial del Valle del Cauca y del Cauca</i>
  —que se rige por su propio contrato y no pasa por aquí—, entidades descentralizadas
  como Vallecaucana de Aguas o INFIVALLE, y transferencias a municipios que después
  contratan en su propio nombre.</p>
  <p><b>El tipo de contrato no mide cuánta obra hay.</b> Buena parte del mantenimiento
  y el mejoramiento vial de esta Secretaría va por convenios de «aunar esfuerzos» que
  el SECOP tipifica como <i>Otro</i>, no como <i>Obra</i>. Quien mire solo la fila de
  obra se llevará una idea equivocada, y por eso esta página muestra las dos cosas.</p>
  <p><b>Un contrato de prestación de servicios no es necesariamente ajeno a la
  emergencia.</b> Puede ser el equipo de ingenieros que está estructurando la obra que
  vendrá. Lo que se puede afirmar con el SECOP en la mano es qué se firmó y con qué
  objeto escrito, no qué está haciendo cada persona.</p>
  <p><b>El SECOP publica con rezago.</b> Un contrato firmado ayer puede aparecer
  mañana. La página dice de qué consulta salen sus cifras, y se vuelve a medir con cada
  recolección.</p>
  <p style="margin-bottom:0"><b>La ventana empieza el 1 de enero de 2024</b>, así que un
  contrato de obra firmado antes y todavía en ejecución no aparece aquí, aunque su plata
  siga moviéndose. Lo mismo vale para las adiciones a contratos viejos.</p>
</div>

<div class="pie">
  Fuente: datos.gov.co — SECOP II, contratos (jbjy-vk9h) y procesos (p6dx-8zbt),
  desde el 1 de enero de 2024.
  La dependencia se identifica por el <b>NIT de la Gobernación del Valle más el nombre
  con que SECOP publica la secretaría</b>: la fuente no trae un campo de dependencia y
  el campo <i>orden</i> es autodeclarado —marca «Nacional» a la propia Gobernación—.
  Esta página se actualiza sola con cada recolección del monitor.
</div>

</div>

<div id="impresion"></div>

<script id="datos" type="application/json">__DATOS__</script>
<script>
var D = JSON.parse(document.getElementById("datos").textContent);
var OPS = D.ops || [];
var POR_PAGINA = 20;
var pagina = 1;

function esc(s){
  return String(s == null ? "" : s).replace(/[&<>"']/g, function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
  });
}
function pesos(v){ return "$ " + Math.round(v || 0).toLocaleString("es-CO"); }
function corto(v){
  v = v || 0;
  if (v >= 1e9) return "$" + (v / 1e9).toFixed(1).replace(".", ",") + " mm";
  if (v >= 1e6) return "$" + Math.round(v / 1e6) + " M";
  return "$" + v.toLocaleString("es-CO");
}
var MESES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto",
             "septiembre","octubre","noviembre","diciembre"];
function fechaLarga(s){
  if (!s) return "";
  var p = String(s).split(/[- :]/);
  return (+p[2]) + " de " + MESES[+p[1] - 1] + " de " + p[0];
}
function selloLargo(s){
  if (!s) return "";
  var p = String(s).split(/[- :]/);
  var h = +(p[3] || 0), ap = h >= 12 ? "p. m." : "a. m.", h12 = h % 12 || 12;
  return fechaLarga(s) + ", " + h12 + ":" + String(+(p[4] || 0)).padStart(2, "0") + " " + ap;
}
function norm(s){
  return String(s == null ? "" : s).normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase();
}

/* ---- Cabecera ---- */
var FIRMADOS = OPS.filter(function(o){ return o.firmado; });
var ABIERTOS = OPS.filter(function(o){ return !o.firmado; });
var TOTAL_V = FIRMADOS.reduce(function(s, o){ return s + (o.v || 0); }, 0);

/* Lo posterior al sismo, que es la pregunta por la que existe esta página. */
var POST = OPS.filter(function(o){ return o.post; });
var POST_F = POST.filter(function(o){ return o.firmado; });
var POST_V = POST_F.reduce(function(s, o){ return s + (o.v || 0); }, 0);
var POST_OBRA = POST_F.filter(function(o){ return o.tc === "Obra"; }).length;
var POST_SISMO = POST.filter(function(o){ return o.sismo; }).length;
var POST_EMER = POST.filter(function(o){ return o.emer; }).length;

document.getElementById("sello").textContent =
  D.entidad + " · NIT " + D.nit + " · consulta del " + selloLargo(D.generado) +
  " · ventana del " + fechaLarga(D.desde) + " en adelante";

/* El titular es el periodo entero, que es lo que se pidió consultar. Lo del
   sismo va justo debajo, en su propio bloque: son dos preguntas y una sola cifra
   grande no puede contestar las dos. */
document.getElementById("titular").innerHTML =
  '<div class="titular"><div class="n">' + pesos(TOTAL_V) + "</div>" +
  '<div class="q">en ' + FIRMADOS.length.toLocaleString("es-CO") + " contratos firmados " +
  "desde el " + fechaLarga(D.desde) + "</div>" +
  '<div class="x">Más ' + ABIERTOS.length.toLocaleString("es-CO") + " proceso" +
  (ABIERTOS.length === 1 ? "" : "s") + " publicado" + (ABIERTOS.length === 1 ? "" : "s") +
  " que todavía no tiene" + (ABIERTOS.length === 1 ? "" : "n") + " contrato firmado. " +
  "Es toda la contratación de la dependencia, del sismo y ordinaria.</div></div>";

document.getElementById("desde-sismo").innerHTML =
  "<h2>Y desde el sismo del " + fechaLarga(D.evento) + "</h2>" +
  '<p class="nota" style="margin-bottom:12px">' + POST_F.length + " contratos firmados por <b>" +
  pesos(POST_V) + "</b>" + (function(n){
    return n ? " y " + n + (n === 1 ? " proceso publicado que aún no tiene contrato"
                                    : " procesos publicados que aún no tienen contrato") : "";
  })(POST.length - POST_F.length) + ".</p>";

var CIFRAS = [
  {n: POST_F.length, q: "contratos firmados desde el sismo", cero: false},
  {n: POST_OBRA, q: "de ellos son contratos de obra", cero: POST_OBRA === 0},
  {n: POST_SISMO, q: "nombran el sismo en su objeto", cero: POST_SISMO === 0},
  {n: POST_EMER, q: "usan vocabulario de emergencia", cero: POST_EMER === 0}
];
document.getElementById("cifras").innerHTML = CIFRAS.map(function(c){
  return '<div class="cifra' + (c.cero ? " cero" : "") + '"><div class="n">' +
    c.n.toLocaleString("es-CO") + '</div><div class="q">' + c.q + "</div></div>";
}).join("");

document.getElementById("nota-cifras").innerHTML =
  "Las tres últimas cifras están para que la primera se pueda leer: <b>un cero sobre " +
  POST_F.length + " contratos revisados es un hallazgo; un cero sobre cero sería no " +
  "haber mirado</b>. El vocabulario de emergencia incluye palabras como urgencia " +
  "manifiesta, calamidad, damnificados, albergue o escombros.";

/* ---- Año por año ---- */
(function(){
  var filas = D.anios || [];
  var t = {n: 0, v: 0, obra: 0, obra_v: 0};
  var html = filas.map(function(r){
    t.n += r.n; t.v += r.v; t.obra += r.obra; t.obra_v += r.obra_v;
    var parcial = (r.a === String(D.desde).slice(0, 4) && D.desde.slice(5) !== "01-01");
    return "<tr><td>" + r.a + (parcial ? " (parcial)" : "") + "</td>" +
      '<td class="n">' + r.n.toLocaleString("es-CO") + "</td>" +
      '<td class="n">' + corto(r.v) + "</td>" +
      '<td class="n' + (r.obra ? "" : " marca") + '">' + r.obra + "</td>" +
      '<td class="n vcol">' + (r.obra ? corto(r.obra_v) : "—") + "</td></tr>";
  }).join("");
  html += '<tr class="tot"><td>Total</td><td class="n">' + t.n.toLocaleString("es-CO") +
    '</td><td class="n">' + corto(t.v) + '</td><td class="n">' + t.obra +
    '</td><td class="n vcol">' + corto(t.obra_v) + "</td></tr>";
  document.getElementById("anios").innerHTML = html;

  var ahora = String(D.generado).slice(0, 4);
  document.getElementById("nota-anios").innerHTML =
    "El año en curso va <b>hasta la fecha de la consulta</b>, así que su cifra no es " +
    "comparable con la de un año completo. La columna de obra está aparte porque es " +
    "donde vive casi todo el dinero: <b>" + t.obra + " contratos de obra de " +
    t.n.toLocaleString("es-CO") + "</b> concentran " +
    (t.v ? Math.round(100 * t.obra_v / t.v) : 0) + "% de lo contratado en el periodo.";
})();

/* ---- Tipo de contrato: desde el sismo contra lo anterior de la ventana ---- */
(function(){
  var mapa = {};
  (D.tipos.desde || []).forEach(function(r){ mapa[r.t] = {a: r, b: null}; });
  (D.tipos.antes || []).forEach(function(r){
    if (!mapa[r.t]) mapa[r.t] = {a: null, b: null};
    mapa[r.t].b = r;
  });
  var filas = Object.keys(mapa).sort(function(x, y){
    var vx = (mapa[x].a ? mapa[x].a.v : 0), vy = (mapa[y].a ? mapa[y].a.v : 0);
    if (vy !== vx) return vy - vx;
    var bx = (mapa[x].b ? mapa[x].b.v : 0), by = (mapa[y].b ? mapa[y].b.v : 0);
    return by - bx;
  });
  var tA = {n: 0, v: 0}, tB = {n: 0, v: 0};
  var html = filas.map(function(t){
    var a = mapa[t].a, b = mapa[t].b;
    if (a) { tA.n += a.n; tA.v += a.v; }
    if (b) { tB.n += b.n; tB.v += b.v; }
    return "<tr><td>" + esc(t) + "</td>" +
      '<td class="n' + (a ? "" : " marca") + '">' + (a ? a.n.toLocaleString("es-CO") : "0") + "</td>" +
      '<td class="n vcol">' + (a ? corto(a.v) : "—") + "</td>" +
      '<td class="n">' + (b ? b.n.toLocaleString("es-CO") : "0") + "</td>" +
      '<td class="n vcol">' + (b ? corto(b.v) : "—") + "</td></tr>";
  }).join("");
  html += '<tr class="tot"><td>Total</td><td class="n">' + tA.n.toLocaleString("es-CO") +
    '</td><td class="n vcol">' + corto(tA.v) + '</td><td class="n">' +
    tB.n.toLocaleString("es-CO") + '</td><td class="n vcol">' + corto(tB.v) + "</td></tr>";
  document.getElementById("tipos").innerHTML = html;
})();

document.getElementById("nota-tipos").innerHTML =
  "Las dos columnas <b>no son comparables en duración</b> —una son los dos años y medio " +
  "anteriores y la otra lo corrido desde el sismo—, y por eso no se comparan los " +
  "volúmenes. Lo que se compara es la <b>clase</b> de contratación: qué tipos de contrato " +
  "aparecen a un lado y cuáles no aparecen al otro. La columna de antes va del " +
  fechaLarga(D.desde) + " al día anterior al sismo.";

/* La obra va en su propia sección, con TODAS sus filas. Son unas pocas entre casi
   dos mil y en la tabla general se pierden, y es lo que una secretaría de
   infraestructura existe para hacer: sin verla, el cero de la columna de arriba
   no se puede juzgar —podría ser que nunca firme obra por su cuenta—. */
(function(){
  var obra = D.obra || [];
  var caja = document.getElementById("obra");
  if (!obra.length) {
    caja.innerHTML = "<h2>La obra del periodo</h2>" +
      '<div class="aviso">No hay ningún contrato ni proceso de obra de esta Secretaría ' +
      "desde el " + fechaLarga(D.desde) + ".</div>";
    return;
  }
  var firm = obra.filter(function(o){ return o.firmado; });
  var suma = firm.reduce(function(s, o){ return s + (o.v || 0); }, 0);
  var post = obra.filter(function(o){ return o.post; }).length;
  caja.innerHTML = "<h2>La obra del periodo, una por una</h2>" +
    '<p class="nota">Desde el ' + fechaLarga(D.desde) + " esta Secretaría tiene <b>" +
    firm.length + " contrato" + (firm.length === 1 ? "" : "s") + " de obra por " +
    pesos(suma) + "</b>" + (function(n){
      return n ? " y " + n + (n === 1 ? " proceso de obra sin contrato firmado"
                                      : " procesos de obra sin contrato firmado") : "";
    })(obra.length - firm.length) + ". Están todas, sin recortar. " +
    (post ? "<b>" + post + "</b> de ellas son posteriores al sismo."
          : "<b>Ninguna es posterior al sismo del " + fechaLarga(D.evento) + ".</b>") +
    " Ojo: el tipo <i>Obra</i> no es todo lo que se construye —abajo están los contratos " +
    "más grandes del periodo, y buena parte de la obra vial va por convenios.</p>" +
    obra.map(ficha).join("");
})();

/* ---- Dónde está de verdad el dinero ----
   Mirar solo el tipo «Obra» engañaría: esta Secretaría ejecuta buena parte de la
   obra vial por convenios de «aunar esfuerzos», que SECOP tipifica como «Otro».
   Con cinco contratos de obra a la vista, un lector concluiría que casi no
   construye, y lo que pasa es que construye por otra figura. */
(function(){
  var TOPE = 10;
  var mayores = OPS.filter(function(o){ return o.firmado && o.v > 0; })
                   .slice().sort(function(a, b){ return b.v - a.v; }).slice(0, TOPE);
  if (!mayores.length) return;
  var total = OPS.reduce(function(s, o){ return s + (o.firmado ? o.v : 0); }, 0);
  var suma = mayores.reduce(function(s, o){ return s + o.v; }, 0);
  var conv = mayores.filter(function(o){ return o.tc === "Otro"; }).length;
  document.getElementById("mayores").innerHTML =
    "<h2>Dónde está el dinero: los " + TOPE + " contratos más grandes</h2>" +
    '<p class="nota">Estos ' + TOPE + " contratos concentran <b>" +
    Math.round(100 * suma / total) + "%</b> de todo lo firmado desde el " +
    fechaLarga(D.desde) + "." +
    (conv ? " <b>" + conv + "</b> de ellos no figuran como obra sino como tipo <i>Otro</i>: " +
      "son convenios de «aunar esfuerzos» con terceros —la Federación Nacional de " +
      "Cafeteros, la Fundación Universidad del Valle— por los que pasa buena parte del " +
      "mantenimiento y el mejoramiento vial. Por eso el tipo de contrato, por sí solo, " +
      "no dice cuánta obra hay." : "") + "</p>" +
    mayores.map(ficha).join("");
})();

/* ---- Perfil ---- */
(function(){
  var p = D.perfil || {};
  if (!p.modalidad) { document.getElementById("perfil").innerHTML = ""; return; }
  var items = [];
  items.push("<b>" + p.modalidad.pct + "%</b> de los contratos se celebró por <b>" +
    esc(p.modalidad.v) + "</b> (" + p.modalidad.n + " de " + FIRMADOS.length + ").");
  if (p.persona && p.persona.total)
    items.push("<b>" + p.persona.n + " de " + p.persona.total +
      "</b> se firmaron con <b>persona natural</b>; el resto, con empresas.");
  if (p.duracion && p.duracion.pct >= 50)
    items.push("<b>" + p.duracion.pct + "%</b> tiene un plazo de <b>" + esc(p.duracion.v) +
      "</b>" + (p.fin && p.fin.pct >= 50 ? ", y termina el <b>" + esc(fechaLarga(p.fin.v)) +
      "</b>" : "") + ".");
  if (p.primera_firma)
    items.push("Las firmas se concentran entre el <b>" + esc(fechaLarga(p.primera_firma)) +
      "</b> y el <b>" + esc(fechaLarga(p.ultima_firma)) + "</b>.");
  items.push(p.repetidos
    ? "<b>" + p.repetidos + " contratistas</b> tienen más de un contrato en esta ventana."
    : "<b>Ningún contratista</b> tiene más de un contrato en esta ventana: se comprobó, " +
      "no es un dato que falte.");
  if (p.ordenador && p.ordenador.pct >= 50)
    items.push("El ordenador del gasto de <b>" + p.ordenador.n + "</b> de ellos es <b>" +
      esc(p.ordenador.v) + "</b>.");
  document.getElementById("perfil").innerHTML =
    items.map(function(t){ return "<li>" + t + "</li>"; }).join("");
})();

/* ---- Qué hay publicado en los expedientes ----
   El texto del contrato es lo que dice las obligaciones. Que no esté publicado
   en ninguno de los expedientes es un hecho sobre cómo publica la entidad, no un
   hueco de esta página: si se callara, los botones ausentes se leerían como un
   fallo del tablero. */
(function(){
  var d = D.docs || {};
  var caja = document.getElementById("expedientes");
  if (d.fallo || !d.exp) { caja.innerHTML = ""; return; }
  var sin = d.exp - d.contrato;
  var html = "<h2>Qué hay publicado en los expedientes, desde el sismo</h2>" +
    '<p class="nota" style="margin-bottom:10px">Se revisaron los ' + d.exp +
    " expedientes de la contratación <b>posterior al sismo</b>. Los de 2024 y 2025 no " +
    "se consultan en cada corrida: serían más de mil expedientes tres veces al día para " +
    "un atajo que ahí no le sirve a nadie. Sus enlaces al expediente y al proceso siguen " +
    "en cada fila de la tabla.</p>" +
    '<table><thead><tr><th>Documento</th><th class="n">Expedientes</th>' +
    '<th class="n">Cobertura</th></tr></thead><tbody>' +
    [["Estudios previos", d.ep],
     ["Texto del contrato", d.contrato],
     ["Informe o acta de ejecución", d.ejecucion]].map(function(r){
      var pct = Math.round(100 * r[1] / d.exp);
      return "<tr><td>" + r[0] + '</td><td class="n' + (r[1] ? "" : " marca") + '">' +
        r[1] + " de " + d.exp + '</td><td class="n">' + pct + "%</td></tr>";
    }).join("") + "</tbody></table>";
  if (sin === d.exp)
    html += '<div class="aviso"><b>En ninguno de los ' + d.exp + ' expedientes está ' +
      'publicado el texto del contrato.</b> Lo que sí está es el formato que genera ' +
      'el SECOP al firmar y al poner en ejecución (<i>CO1_PCCNTR…_Firmado.pdf</i>), ' +
      'que es una constancia y no trae el articulado: no dice las obligaciones, ni ' +
      'los productos, ni la forma de pago. Para leer eso hay que pedírselo a la ' +
      'entidad.</div>';
  else if (sin > 0)
    html += '<p class="nota">En <b>' + sin + '</b> expedientes no está publicado el ' +
      'texto del contrato; lo que hay es la constancia que genera el SECOP al firmar, ' +
      'que no trae el articulado.</p>';
  caja.innerHTML = html;
})();

/* ---- Tabla con filtros ---- */
var F = {txt: "", per: "", anios: new Set(), tipo: "", est: "", rel: "", orden: "v-"};

/* Años: multiselección con casillas. Vacío significa TODOS, no ninguno.
   El resumen cerrado dice cuántos hay elegidos, porque un filtro puesto que no
   se ve miente igual que una tabla filtrada en silencio. Y marcar NO repinta la
   lista de casillas: si repintara, saltarían bajo el cursor al elegir la
   segunda. */
var ANIOS = (function(){
  var cuenta = {};
  OPS.forEach(function(o){
    var a = (o.f || o.fp || "").slice(0, 4);
    o.anio = a;
    if (a) cuenta[a] = (cuenta[a] || 0) + 1;
  });
  return Object.keys(cuenta).sort().map(function(a){ return {a: a, n: cuenta[a]}; });
})();

function resumenAnios(){
  var s = document.getElementById("res-anios");
  var n = F.anios.size;
  s.innerHTML = n === 0
    ? "Todos los años"
    : (n === 1 ? "<b>" + Array.from(F.anios)[0] + "</b>"
               : "<b>" + n + " años</b> elegidos");
}

(function(){
  var panel = document.getElementById("panel-anios");
  panel.innerHTML = ANIOS.map(function(x){
    return '<label><input type="checkbox" value="' + x.a + '"> ' + x.a +
      " <small>(" + x.n + ")</small></label>";
  }).join("");
  panel.addEventListener("change", function(e){
    if (e.target.tagName !== "INPUT") return;
    if (e.target.checked) F.anios.add(e.target.value);
    else F.anios["delete"](e.target.value);
    pagina = 1;
    resumenAnios();
    pintar();
  });
  resumenAnios();
})();

/* Cerrar el panel al pulsar fuera. Sin esto se queda abierto tapando la tabla
   que se acaba de filtrar, que es justo lo que se quería mirar. */
document.addEventListener("click", function(e){
  var d = document.getElementById("f-anios");
  if (d.open && !d.contains(e.target)) d.open = false;
});

/* El desplegable de tipo se llena con los tipos que DE VERDAD existen y con su
   cuenta al lado. Ofrecer un tipo que no tiene ninguna fila daría siempre tabla
   vacía sin nada que lo explicara. */
(function(){
  var cuenta = {};
  OPS.forEach(function(o){ cuenta[o.tc] = (cuenta[o.tc] || 0) + 1; });
  var sel = document.getElementById("f-tipo");
  Object.keys(cuenta).sort(function(a, b){ return cuenta[b] - cuenta[a]; })
    .forEach(function(t){
      var op = document.createElement("option");
      op.value = t;
      op.textContent = t + " (" + cuenta[t] + ")";
      sel.appendChild(op);
    });
})();

function filtradas(){
  var t = norm(F.txt).trim();
  return OPS.filter(function(o){
    if (F.per === "post" && !o.post) return false;
    if (F.per === "pre" && o.post) return false;
    if (F.anios.size && !F.anios.has(o.anio)) return false;
    if (F.tipo && o.tc !== F.tipo) return false;
    if (F.est === "si" && !o.firmado) return false;
    if (F.est === "no" && o.firmado) return false;
    if (F.rel === "sismo" && !o.sismo) return false;
    if (F.rel === "emer" && !o.emer) return false;
    if (F.rel === "ord" && (o.sismo || o.emer)) return false;
    if (t && norm(o.o + " " + o.r + " " + o.rp + " " + o.p + " " + o.pd).indexOf(t) < 0) return false;
    return true;
  }).sort(function(a, b){
    var va = a.v || a.pb || 0, vb = b.v || b.pb || 0;
    switch (F.orden) {
      case "v+": return va - vb;
      case "f-": return String(b.f || b.fp).localeCompare(String(a.f || a.fp));
      case "f+": return String(a.f || a.fp).localeCompare(String(b.f || b.fp));
      case "p+": return String(a.p || "zzz").localeCompare(String(b.p || "zzz"), "es");
      default: return vb - va;
    }
  });
}

function ficha(o){
  var valor = o.firmado ? o.v : o.pb;
  var etiquetas = o.firmado
    ? '<span class="et ok">Contratada</span>'
    : '<span class="et ab">Proceso abierto</span>';
  if (o.sismo) etiquetas += '<span class="et ok">nombra el sismo</span>';
  else if (o.emer) etiquetas += '<span class="et">vocabulario de emergencia</span>';

  var meta = [];
  if (o.p) meta.push("Contratista: <b>" + esc(o.p) + "</b>" + (o.pd ? " (" + esc(o.pd) + ")" : ""));
  if (o.tc) meta.push("Tipo: <b>" + esc(o.tc) + "</b>");
  if (o.mod) meta.push("Modalidad: <b>" + esc(o.mod) + "</b>");
  if (o.f) meta.push("Firmado el <b>" + esc(fechaLarga(o.f)) + "</b>");
  else if (o.fp) meta.push("Publicado el <b>" + esc(fechaLarga(o.fp)) + "</b>");
  if (o.fi && o.ff) meta.push("Ejecución: <b>" + esc(fechaLarga(o.fi)) + "</b> a <b>" +
    esc(fechaLarga(o.ff)) + "</b>");
  if (o.est) meta.push("Estado: <b>" + esc(o.est) + "</b>");
  else if (o.estp) meta.push("Estado del proceso: <b>" + esc(o.estp) + "</b>");
  if (o.sup) meta.push("Supervisor: <b>" + esc(o.sup) + "</b>");

  var enlaces = [];
  if (o.u) enlaces.push(['Expediente', o.u]);
  if (o.up && o.up !== o.u) enlaces.push(["Proceso", o.up]);
  if (o.ce) enlaces.push(["Contrato", o.ce]);
  if (o.ep) enlaces.push(["Estudios previos", o.ep]);
  if (o.ej) enlaces.push(["Informe de ejecución", o.ej]);

  return '<div class="op"><div class="cab"><span><span class="ref">' +
    esc(o.r || o.rp || "sin número") + "</span>" + etiquetas + '</span><span class="val">' +
    pesos(valor) + (o.firmado ? "" : " <span style=\"font-size:11px;font-weight:400\">precio base</span>") +
    "</span></div>" +
    '<div class="obj">' + esc(o.o) +
    (o.cortado ? ' <span class="et ab">SECOP cortó este texto</span>' : "") + "</div>" +
    '<div class="meta">' + meta.join(" · ") + "</div>" +
    (enlaces.length ? '<div class="enls">' + enlaces.map(function(e){
      return '<a class="enl" href="' + esc(e[1]) + '" target="_blank" rel="noopener">' +
        e[0] + "</a>";
    }).join("") + "</div>" : "") +
    "</div>";
}

function pintar(){
  var lista = filtradas();
  var paginas = Math.max(1, Math.ceil(lista.length / POR_PAGINA));
  if (pagina > paginas) pagina = paginas;

  /* NUNCA se suma precio base con valor firmado: son la misma plata en dos
     momentos y sumarlos inventa dinero que no existe. Se cuentan aparte y cada
     cifra va rotulada con lo que es. */
  var nf = 0, sf = 0, na = 0, sa = 0;
  lista.forEach(function(o){
    if (o.firmado) { nf++; sf += o.v || 0; } else { na++; sa += o.pb || 0; }
  });
  var partes = [];
  if (nf) partes.push("<b>" + nf + "</b> contrato" + (nf === 1 ? "" : "s") +
    " firmado" + (nf === 1 ? "" : "s") + " por " + pesos(sf));
  if (na) partes.push("<b>" + na + "</b> proceso" + (na === 1 ? "" : "s") +
    " abierto" + (na === 1 ? "" : "s") + " por " + pesos(sa) + " de precio base");

  document.getElementById("resumen").innerHTML = lista.length
    ? partes.join(" · ") + " · " + lista.length + " de " + OPS.length +
      " contrataciones de la ventana"
    : "";

  /* Los dos botones dicen CUÁNTAS filas se llevan. Sin filtros son casi dos mil,
     y un informe de doscientas páginas no puede salir por sorpresa: que la cifra
     esté en el botón evita tanto la sorpresa como la tentación de recortar en
     silencio, que sería peor. */
  document.getElementById("b-csv").textContent =
    "Descargar CSV (" + lista.length + " filas)";
  document.getElementById("b-pdf").textContent =
    "Informe en PDF (" + lista.length + " filas)";

  if (!lista.length) {
    /* Un cero tiene que decir por qué: no es lo mismo "esta Secretaría no firmó
       nada de eso" que "ese filtro no deja pasar nada". */
    var razon = F.rel === "sismo"
      ? "Ningún contrato ni proceso de esta Secretaría nombra el sismo en su objeto. " +
        "<b>El cero es el hallazgo, no un dato que falte.</b>"
      : F.rel === "emer"
      ? "Ningún objeto usa vocabulario de emergencia —urgencia manifiesta, calamidad, " +
        "damnificados, albergue, escombros—."
      : F.tipo && F.per === "post"
      ? "Esta Secretaría <b>no firmó ningún contrato de tipo «" + esc(F.tipo) +
        "» desde el sismo</b>. El cero es el hallazgo, no un dato que falte."
      : F.tipo
      ? "No hay contratación de tipo «" + esc(F.tipo) + "» que cumpla los demás filtros."
      : F.est === "no"
      ? "No hay procesos abiertos sin contrato firmado con esos filtros."
      : "No hay contrataciones que cumplan lo que se está pidiendo. Pruebe quitando filtros.";
    document.getElementById("tabla").innerHTML = '<div class="vacio">' + razon + "</div>";
    document.getElementById("pag").innerHTML = "";
    return;
  }

  var ini = (pagina - 1) * POR_PAGINA;
  document.getElementById("tabla").innerHTML =
    lista.slice(ini, ini + POR_PAGINA).map(ficha).join("");
  document.getElementById("pag").innerHTML = paginas > 1
    ? '<button class="b" id="p-ant"' + (pagina === 1 ? " disabled" : "") + ">← Anterior</button>" +
      "<span>Página " + pagina + " de " + paginas + "</span>" +
      '<button class="b" id="p-sig"' + (pagina === paginas ? " disabled" : "") + ">Siguiente →</button>"
    : "";
  var a = document.getElementById("p-ant"), s = document.getElementById("p-sig");
  if (a) a.onclick = function(){ pagina--; pintar(); window.scrollTo(0, document.getElementById("tabla").offsetTop - 60); };
  if (s) s.onclick = function(){ pagina++; pintar(); window.scrollTo(0, document.getElementById("tabla").offsetTop - 60); };
}

function enganchar(id, campo){
  var el = document.getElementById(id);
  el.addEventListener("input", function(){ F[campo] = el.value; pagina = 1; pintar(); });
  el.addEventListener("change", function(){ F[campo] = el.value; pagina = 1; pintar(); });
}
enganchar("f-txt", "txt");
enganchar("f-per", "per");
enganchar("f-tipo", "tipo");
enganchar("f-est", "est");
enganchar("f-rel", "rel");
enganchar("f-ord", "orden");

document.getElementById("b-limpiar").onclick = function(){
  F = {txt: "", per: "", anios: new Set(), tipo: "", est: "", rel: "", orden: "v-"};
  ["f-txt", "f-per", "f-tipo", "f-est", "f-rel"].forEach(function(i){
    document.getElementById(i).value = "";
  });
  document.getElementById("f-ord").value = "v-";
  [].forEach.call(document.querySelectorAll("#panel-anios input"), function(c){
    c.checked = false;
  });
  resumenAnios();
  pagina = 1;
  pintar();
};

/* El CSV sale de lo que la tabla está mostrando, no de la lista entera: un
   archivo que no cuadra con la pantalla es peor que no tenerlo. Por eso lleva
   también la procedencia y los filtros puestos. */
/* Los filtros puestos, en una frase. La MISMA para el CSV y para el PDF: si
   cada uno describiera lo suyo, dos archivos del mismo tablero podrían decir
   cosas distintas sobre de dónde salen sus filas. */
function descripcionFiltros(lista){
  var partes = [];
  if (F.txt) partes.push('texto "' + F.txt + '"');
  if (F.per === "post") partes.push("solo desde el sismo del " + fechaLarga(D.evento));
  if (F.per === "pre") partes.push("solo antes del sismo del " + fechaLarga(D.evento));
  if (F.anios.size) partes.push("años " + Array.from(F.anios).sort().join(", "));
  if (F.tipo) partes.push("tipo de contrato " + F.tipo);
  if (F.est === "si") partes.push("solo contratos firmados");
  if (F.est === "no") partes.push("solo procesos sin contrato");
  if (F.rel === "sismo") partes.push("solo lo que nombra el sismo");
  if (F.rel === "emer") partes.push("solo vocabulario de emergencia");
  if (F.rel === "ord") partes.push("sin mención del sismo ni de emergencia");
  return (partes.length ? partes.join("; ") : "ninguno, se muestra todo") +
    " · " + lista.length + " de " + OPS.length + " contrataciones";
}

document.getElementById("b-csv").onclick = function(){
  var lista = filtradas();
  var cab = ["Número", "Tipo de vínculo", "Objeto", "Valor", "Precio base",
             "Tipo de contrato", "Modalidad", "Contratista", "Documento",
             "Firma", "Inicio", "Fin", "Estado", "Supervisor", "Nombra el sismo",
             "Expediente", "Contrato", "Estudios previos"];
  function q(v){ return '"' + String(v == null ? "" : v).replace(/"/g, '""') + '"'; }
  var filas = lista.map(function(o){
    return [o.r || o.rp, o.firmado ? "Contrato" : "Proceso abierto", o.o,
            o.firmado ? o.v : "", o.pb || "", o.tc, o.mod, o.p, o.pd, o.f, o.fi,
            o.ff, o.est || o.estp, o.sup, o.sismo ? "Sí" : "No", o.u, o.ce, o.ep]
           .map(q).join(";");
  });
  var cabecera = [
    q("Secretaría de Infraestructura - Gobernación del Valle del Cauca"),
    q("Consulta del " + selloLargo(D.generado) + ". Ventana desde el " + fechaLarga(D.desde)),
    q("Filtros: " + descripcionFiltros(lista)),
    q("Fuente: datos.gov.co, SECOP II")
  ].join("\n");
  var csv = "﻿" + cabecera + "\n\n" + cab.map(q).join(";") + "\n" + filas.join("\n");
  var a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], {type: "text/csv;charset=utf-8"}));
  a.download = "infraestructura-valle-" + String(D.generado).slice(0, 10) + ".csv";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
};

/* ---- Informe en PDF ----
   Es la impresión del navegador con hoja de estilos, no una librería. Misma
   decisión que en el tablero grande (24-ago-2026): una librería obligaría a
   recortar el objeto para que la tabla cuadre, y el objeto es el texto por el
   que se juzga de qué va cada contratación.

   Imprime TODAS las filas del filtro, no las 20 de la página, y encabeza con los
   filtros aplicados y la recolección de la que salen los datos: un informe que
   viaja solo y no dice de dónde sale no se puede verificar.

   Los enlaces van como <a href> de verdad: al imprimir a PDF el navegador los
   conserva y quedan pulsables dentro del archivo. */
function imprimirInforme(){
  var lista = filtradas();
  var nf = 0, sf = 0, na = 0, sa = 0;
  lista.forEach(function(o){
    if (o.firmado) { nf++; sf += o.v || 0; } else { na++; sa += o.pb || 0; }
  });

  var filas = lista.map(function(o){
    var fechas = [];
    if (o.f) fechas.push("Firma: " + o.f);
    else if (o.fp) fechas.push("Publicación: " + o.fp);
    if (o.fi) fechas.push("Inicio: " + o.fi);
    if (o.ff) fechas.push("Fin: " + o.ff);
    var enlaces = [];
    if (o.u) enlaces.push(['Expediente', o.u]);
    if (o.up && o.up !== o.u) enlaces.push(["Proceso", o.up]);
    if (o.ce) enlaces.push(["Contrato", o.ce]);
    if (o.ep) enlaces.push(["Estudios previos", o.ep]);
    if (o.ej) enlaces.push(["Informe de ejecución", o.ej]);
    return "<tr>" +
      "<td>" + esc(o.r || o.rp || "sin número") +
        '<span class="obj">' + esc(o.o) + "</span>" +
        (enlaces.length ? '<span class="obj">' + enlaces.map(function(e){
          return '<a class="enl-inf" href="' + esc(e[1]) + '">' + e[0] + "</a>";
        }).join(" · ") + "</span>" : "") + "</td>" +
      "<td>" + esc(o.p || "—") + (o.pd ? "<br>" + esc(o.pd) : "") + "</td>" +
      "<td>" + esc(o.tc) + "<br>" + esc(o.mod) + "</td>" +
      "<td>" + esc(fechas.join("<br>")).replace(/&lt;br&gt;/g, "<br>") + "</td>" +
      "<td>" + esc(o.firmado ? (o.est || "Contratada") : (o.estp || "Proceso abierto")) + "</td>" +
      '<td class="n">' + pesos(o.firmado ? o.v : o.pb) +
        (o.firmado ? "" : "<br><small>precio base</small>") + "</td></tr>";
  }).join("");

  document.getElementById("impresion").innerHTML =
    "<h1>Contratación de la Secretaría de Infraestructura del Valle del Cauca</h1>" +
    '<div class="cab-inf">' +
    "<b>" + esc(D.entidad) + "</b> · NIT " + esc(D.nit) + "<br>" +
    "Ventana consultada: del <b>" + fechaLarga(D.desde) + "</b> en adelante · " +
    "Datos de la recolección del <b>" + selloLargo(D.generado) + "</b><br>" +
    "Filtros aplicados: <b>" + esc(descripcionFiltros(lista)) + "</b><br>" +
    "En este informe: <b>" + nf + " contratos firmados por " + pesos(sf) + "</b>" +
    (na ? " y <b>" + na + " proceso" + (na === 1 ? "" : "s") + " sin contrato por " +
          pesos(sa) + " de precio base</b>" : "") +
    ". El precio base y el valor firmado no se suman: son la misma plata en dos " +
    "momentos.<br>Fuente: datos.gov.co — SECOP II." +
    "</div>" +
    (lista.length
      ? "<table><thead><tr><th>Número y objeto</th><th>Contratista</th>" +
        "<th>Tipo y modalidad</th><th>Fechas</th><th>Estado</th>" +
        '<th class="n">Valor</th></tr></thead><tbody>' + filas + "</tbody></table>"
      : "<p>Con esos filtros no hay ninguna contratación que listar.</p>") +
    '<div class="pie-inf">Informe generado desde el monitor de contratación del sismo ' +
    "del 10 de agosto de 2026. Las cifras se vuelven a medir contra el SECOP en cada " +
    "recolección; este informe es la foto del " + selloLargo(D.generado) + ".</div>";

  window.print();
}

document.getElementById("b-pdf").onclick = imprimirInforme;

pintar();

/* Alto automático para cuando va incrustada, igual que la versión ligera. Lo
   único que se manda es un número, así que targetOrigin "*" es seguro aquí; la
   comprobación de origen le toca a quien recibe. */
(function(){
  if (window.parent === window) return;
  var ultimo = 0, pend = null;
  function medir(){
    var a = Math.max(document.documentElement.scrollHeight,
                     document.body ? document.body.scrollHeight : 0);
    if (Math.abs(a - ultimo) < 8) return;
    ultimo = a;
    window.parent.postMessage({tipo: "tablero-sismo:alto", alto: a}, "*");
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
