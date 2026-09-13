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

# Los cuatro documentos que se enlazan, medidos el 13-sep-2026 sobre los 272
# expedientes de operaciones del sismo (4.023 documentos):
#
#   contrato          235  86%   el que mas rinde, y el unico con nombre
#                               predecible: lo genera SECOP, no la entidad
#   estudios previos  123  45%
#   acta de inicio     84  30%
#   prueba de ejecucion  6   2%
#
# Todo se compara sobre el nombre normalizado -sin tildes, sin puntuacion, en
# mayusculas-, porque las entidades escriben el mismo archivo de ocho maneras.
PATRON_EP = re.compile(r"ESTUDIO[S]?\s+(?:PREVIO|Y\s+DOCUMENTO)")

# SECOP genera 'CO1_PCCNTR_<id>_Firmado.pdf' con nombre fijo; por eso el contrato
# cubre el 86% y no depende de que la entidad acierte con el nombre. Lo demas
# -clausulado, minuta, 'CONVENIO DE ASOCIACION'- lo pone la entidad y suma.
PATRON_CONTRATO = re.compile(
    r"CO1 PCCNTR \d+ (?:FIRMADO|EN EJECUCION|APROBADO|MODIFICADO)"
    r"|\b(?:CLAUSULADO|MINUTA)\b"
    r"|^\s*\d*\s*CONTRATO\b|\bCONTRATO DE\b|CONVENIO DE ASOCIACION")

PATRON_INICIO = re.compile(r"ACTA DE INIC|ACTA DE INIIC")

# Lo que PRUEBA que se ejecuto, no lo que la justifica. La distincion costo una
# medicion: con un patron suelto salian 34 expedientes (12%) y casi todos eran
# falsos. 'INFORME REVISION DOCUMENTOS' e 'INFORME REQUISITOS IDONEIDAD' son
# precontractuales -revisan los papeles del proponente- y los 'INFORME TECNICO
# PRELIMINAR', 'MALLA VIAL' o 'AFECTACIONES' son diagnosticos del daño, que
# sustentan la contratacion en vez de acreditarla. Y 'CO1_PCCNTR_*_EN
# EJECUCION.pdf' es el CONTRATO en ese estado, no un informe. Con el patron
# afinado quedan 6 de 272, que es la verdad: casi nadie ha publicado todavia
# como va la ejecucion.
PATRON_EJECUCION = re.compile(
    r"ACTA DE (?:SUPERVISION|RECIBO|ENTREGA|PARCIAL|TERMINACION|LIQUIDACION)"
    r"|ACTA PARCIAL"
    r"|INFORME (?:DE )?(?:EJECUCION|SUPERVISION|AVANCE|ACTIVIDADES|GESTION"
    r"|MENSUAL|FINAL|PARCIAL)")
PATRON_NO_EJECUCION = re.compile(
    r"REVISION|VERIFICACION|REQUISITO|IDONEIDAD|PRELIMINAR|AFECTACION"
    r"|COLAPSO|JUSTIFICACION|CO1 PCCNTR")


def _es_ejecucion(nombre):
    return bool(PATRON_EJECUCION.search(nombre)) and not PATRON_NO_EJECUCION.search(nombre)


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

    def _elegir(filas, prueba):
        """El primero que cumpla, con orden ESTABLE.

        El JSON se regenera cada doce horas: si el archivo elegido cambiara de
        una corrida a otra, el diff se llenaria de ruido y el enlace bailaria sin
        que nadie hubiera publicado nada.
        """
        cand = sorted((f for f in filas if prueba(_normalizar(f.get("nombre_archivo")))),
                      key=lambda f: (str(f.get("nombre_archivo") or ""),
                                     str(f.get("id_documento") or "")))
        return cand

    salida = {}
    for proc, docs in crudo.items():
        filas = list(docs.values())
        ep = _elegir(filas, PATRON_EP.search)
        contrato = _elegir(filas, PATRON_CONTRATO.search)
        inicio = _elegir(filas, PATRON_INICIO.search)
        ejec = _elegir(filas, _es_ejecucion)
        salida[proc] = {
            "n": len(filas),
            "ep": _url(ep[0]) if ep else "",
            "ep_nombre": (ep[0].get("nombre_archivo") or "") if ep else "",
            "contrato": _url(contrato[0]) if contrato else "",
            "inicio": _url(inicio[0]) if inicio else "",
            # De los informes de ejecucion se enlaza el primero y se dice cuantos
            # hay: van saliendo con el tiempo y la cuenta es la que avisa de que
            # el expediente se esta moviendo.
            "ejecucion": _url(ejec[0]) if ejec else "",
            "ejecucion_n": len(ejec),
        }
    return salida


def anotar(registros, indice):
    """Pega el expediente a cada registro por su llave 'portafolio'.

    El contrato y su proceso comparten expediente, asi que los dos reciben el
    mismo numero y el mismo enlace: son el mismo hecho en dos momentos y tener
    cuentas distintas en la misma operacion se leeria como un fallo.
    """
    cuenta = {"ep": 0, "contrato": 0, "inicio": 0, "ejecucion": 0}
    tocados = 0
    for r in registros:
        datos = indice.get(r.get("portafolio") or "")
        if not datos:
            continue
        r["docs_n"] = datos["n"]
        r["docs_ep"] = datos["ep"]
        r["docs_ep_nombre"] = datos["ep_nombre"]
        r["docs_contrato"] = datos["contrato"]
        r["docs_inicio"] = datos["inicio"]
        r["docs_ejecucion"] = datos["ejecucion"]
        r["docs_ejecucion_n"] = datos["ejecucion_n"]
        tocados += 1
        for k in cuenta:
            if datos[k]:
                cuenta[k] += 1
    return tocados, cuenta
