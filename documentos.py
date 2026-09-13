# -*- coding: utf-8 -*-
"""Enlaza cada registro con los documentos de su expediente en SECOP II.

Dataset: dmgg-8hin ("Documentos del proceso"). Trae el nombre del archivo y su
url de descarga directa, asi que llegar a los estudios previos pasa de abrir
SECOP y buscar, a un clic.

POR QUE SE CRUZA POR EXPEDIENTE Y NO POR CONTRATO. Los estudios previos son un
documento PRECONTRACTUAL: cuelgan del expediente, no del contrato. Medido el
13-sep-2026 sobre las 218 operaciones confirmadas que cruzan:

    por n_mero_de_contrato   2.374 documentos    26 de 218 con estudios previos (11%)
    por proceso (CO1.BDOS.*) 3.504 documentos   100 de 218 con estudios previos (45%)

El convenio 4163.001.27.1.5-2026 lo resume en una linea: por contrato no aparece
ningun estudio previo; por expediente aparece "2. ESTUDIOS PREVIOS FUNDACION.pdf",
de 1 MB. Cruzar por contrato habria dejado el enlace vacio en 9 de cada 10 filas.

La llave es el CO1.BDOS.*, que el colector guarda en el campo 'portafolio'. Se
llama proceso_de_compra en contratos y id_del_portafolio en procesos: es el mismo
numero con dos nombres. Como el contrato y su proceso comparten expediente, una
sola consulta sirve para los dos, y los PROCESOS QUE AUN NO TIENEN CONTRATO
tambien quedan cubiertos -que era justo el agujero de cruzar por contrato-.

SECOP I no participa: no tiene expediente electronico y no aparece en el dataset.
Su campo 'portafolio' viene vacio y ni se consulta.

Es BEST EFFORT: si el dataset no responde, el tablero sale igual sin los enlaces.
Un expediente es un atajo, no un dato del que dependa ninguna cifra.
"""

import re
import unicodedata

DATASET = "dmgg-8hin"

# Cuantas llaves caben en un 'in (...)'. Con 40 la URL queda holgada y cada lote
# baja en pocos segundos; subirlo mucho hace que Socrata devuelva 414.
TAMANO_LOTE = 40

# 'ESTUDIO PREVIO', 'ESTUDIOS PREVIOS', 'ESTUDIOS Y DOCUMENTOS PREVIOS' y las
# variantes con numero delante ('2. ESTUDIOS PREVIOS'). Se compara sobre el
# nombre normalizado -sin tildes, sin puntuacion, en mayusculas-, porque las
# entidades escriben el mismo archivo de ocho maneras.
PATRON_EP = re.compile(r"ESTUDIO[S]?\s+(?:PREVIO|Y\s+DOCUMENTO)")


def _normalizar(texto):
    t = unicodedata.normalize("NFD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9 ]", " ", t).upper()


def _url(fila):
    """url_descarga_documento llega como objeto {'url': ...}, no como cadena.

    Es una columna de tipo URL de Socrata. Tratarla como texto deja 'None' o el
    repr del diccionario en el enlace, y el boton lleva a ninguna parte.
    """
    v = fila.get("url_descarga_documento")
    if isinstance(v, dict):
        return v.get("url", "") or ""
    return str(v or "")


def consultar(portafolios, consultar_api, registrar=print):
    """Devuelve {portafolio: {'n': cuantos, 'ep': url, 'ep_nombre': archivo}}.

    `consultar_api(dataset, where)` la inyecta el colector para reutilizar sus
    reintentos y su token. Se inyecta en vez de importarla para no crear un
    import circular: el colector importa este modulo.
    """
    llaves = sorted({p for p in portafolios if p and p.startswith("CO1.BDOS.")})
    if not llaves:
        return {}

    # id_documento -> fila, por expediente. La fuente publica el mismo documento
    # repetido (aparece en la fase del proceso y en la del contrato) y contarlo
    # dos veces inflaria el numero que se muestra en la fila.
    crudo = {}
    lotes = -(-len(llaves) // TAMANO_LOTE)
    for i in range(0, len(llaves), TAMANO_LOTE):
        lote = llaves[i:i + TAMANO_LOTE]
        lista = ",".join("'" + k + "'" for k in lote)
        filas = consultar_api(DATASET, f"proceso in ({lista})")
        for f in filas:
            proc = f.get("proceso")
            if proc:
                crudo.setdefault(proc, {})[f.get("id_documento")] = f
        registrar(f"    documentos: lote {i // TAMANO_LOTE + 1}/{lotes}, "
                  f"{len(crudo)} expedientes")

    salida = {}
    for proc, docs in crudo.items():
        filas = list(docs.values())
        # Orden estable: el JSON se regenera cada doce horas y si el archivo
        # elegido cambiara de una corrida a otra, el diff se llenaria de ruido
        # y el enlace bailaria sin que nadie hubiera publicado nada.
        previos = sorted(
            (f for f in filas if PATRON_EP.search(_normalizar(f.get("nombre_archivo")))),
            key=lambda f: (str(f.get("nombre_archivo") or ""), str(f.get("id_documento") or "")))
        ep = previos[0] if previos else None
        salida[proc] = {
            "n": len(filas),
            "ep": _url(ep) if ep else "",
            "ep_nombre": (ep.get("nombre_archivo") or "") if ep else "",
        }
    return salida


def anotar(registros, indice):
    """Pega el expediente a cada registro por su llave 'portafolio'.

    El contrato y su proceso comparten expediente, asi que los dos reciben el
    mismo numero y el mismo enlace: son el mismo hecho en dos momentos y tener
    cuentas distintas en la misma operacion se leeria como un fallo.
    """
    con_ep = tocados = 0
    for r in registros:
        datos = indice.get(r.get("portafolio") or "")
        if not datos:
            continue
        r["docs_n"] = datos["n"]
        r["docs_ep"] = datos["ep"]
        r["docs_ep_nombre"] = datos["ep_nombre"]
        tocados += 1
        if datos["ep"]:
            con_ep += 1
    return tocados, con_ep
