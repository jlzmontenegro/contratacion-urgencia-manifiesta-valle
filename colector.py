# -*- coding: utf-8 -*-
"""
Monitor de contratacion publica asociada a la urgencia manifiesta y al sismo
del 10 de agosto de 2026 (Cali / Valle del Cauca).

Fuentes (datos abiertos, API SODA de datos.gov.co):
  - SECOP II · Procesos de contratacion : p6dx-8zbt  (fecha: fecha_de_publicacion_del)
  - SECOP II · Contratos electronicos   : jbjy-vk9h  (fecha: fecha_de_firma)
  - SECOP I  · Procesos de compra publica: f789-7hwg (fecha: fecha_de_firma_del_contrato,
    con respaldo en fecha_de_cargue_en_el_secop)

Cada ejecucion:
  1. Barre las tres fuentes con cuatro estrategias (NIT de las entidades de los decretos,
     departamento, palabras clave a nivel nacional y NIT de la UNGRD).
  2. Une y deduplica por identificador de contrato / proceso.
  3. Clasifica el nivel de relacion con el sismo (Alta / Media / Contexto).
  4. Compara contra el estado anterior y registra altas y modificaciones en cambios.csv.
  5. Guarda snapshot historico, reporte diario en Markdown y los datos del tablero HTML.

Uso:
    py -3 colector.py                 # actualizacion normal
    py -3 colector.py --sin-red       # reprocesa lo ya descargado (sin consultar la API)
"""

import argparse
import gzip
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, date, timedelta

import pandas as pd
import requests

# --------------------------------------------------------------------------
# Rutas y configuracion
# --------------------------------------------------------------------------

BASE = os.path.dirname(os.path.abspath(__file__))
DIR_DATOS = os.path.join(BASE, "datos")
DIR_HIST = os.path.join(DIR_DATOS, "historial")
DIR_REPORTES = os.path.join(BASE, "reportes")

for d in (DIR_DATOS, DIR_HIST, DIR_REPORTES):
    os.makedirs(d, exist_ok=True)

DOMINIO = "https://www.datos.gov.co/resource"

FUENTES = {
    "contratos": {
        "plataforma": "SECOP II",
        "tipo": "Contrato",
        # En contratos electronicos nit_entidad es una columna NUMERICA: compararla
        # contra '900478966-6' no devuelve cero filas, aborta la consulta entera con
        # un error de tipo. Por eso el NIT se trata distinto en cada fuente.
        "nit": "nit_entidad",
        "nit_texto": False,
        "url": "urlproceso",
        "dataset": "jbjy-vk9h",
        "id": "id_contrato",
        "fecha": "fecha_de_firma",
        "entidad": "nombre_entidad",
        "departamento": "departamento",
        "ciudad": "ciudad",
        "descripcion": ["descripcion_del_proceso", "objeto_del_contrato"],
        "justificacion": "justificacion_modalidad_de",
        "modalidad": "modalidad_de_contratacion",
        "valor": "valor_del_contrato",
        "proveedor": "proveedor_adjudicado",
        "doc_proveedor": "documento_proveedor",
        "estado": "estado_contrato",
        "etiqueta_fecha": "Firma del contrato",
        "fecha_ini": "fecha_de_inicio_del_contrato",
        "fecha_fin": "fecha_de_fin_del_contrato",
        "duracion": "duraci_n_del_contrato",
        "unidad_duracion": None,
        # campos cuyo cambio se audita entre ejecuciones
        "vigilar": [
            "valor_del_contrato", "estado_contrato", "valor_pagado", "valor_facturado",
            "fecha_de_fin_del_contrato", "dias_adicionados", "liquidaci_n",
            "proveedor_adjudicado", "nombre_supervisor", "valor_pendiente_de_pago",
        ],
    },
    "procesos": {
        "plataforma": "SECOP II",
        "tipo": "Proceso",
        "nit": "nit_entidad",
        "nit_texto": True,      # aqui si es texto, a diferencia de contratos
        "url": "urlproceso",
        "dataset": "p6dx-8zbt",
        "id": "id_del_proceso",
        "fecha": "fecha_de_publicacion_del",
        "entidad": "entidad",
        "departamento": "departamento_entidad",
        "ciudad": "ciudad_entidad",
        "descripcion": ["descripci_n_del_procedimiento", "nombre_del_procedimiento"],
        "justificacion": "justificaci_n_modalidad_de",
        "modalidad": "modalidad_de_contratacion",
        "valor": "precio_base",
        "proveedor": "nombre_del_proveedor",
        "doc_proveedor": "nit_del_proveedor_adjudicado",
        "estado": "estado_del_procedimiento",
        "etiqueta_fecha": "Publicación del proceso",
        "fecha_ini": None,
        "fecha_fin": None,
        "duracion": "duracion",
        "unidad_duracion": "unidad_de_duracion",
        "vigilar": [
            "estado_del_procedimiento", "precio_base", "valor_total_adjudicacion",
            "adjudicado", "nombre_del_proveedor", "fase", "fecha_adjudicacion",
            "estado_resumen",
        ],
    },
    # SECOP I es la plataforma anterior y sigue activa: en 2026 se le cargaron
    # 169.224 registros. A diferencia de SECOP II no separa proceso y contrato en
    # dos datasets: cada fila es un proceso que, si llego a celebrarse, trae los
    # datos del contrato en las mismas columnas.
    "secop1": {
        "plataforma": "SECOP I",
        "tipo": None,           # se decide por fila: celebrado -> Contrato, si no -> Proceso
        "nit": "nit_de_la_entidad",
        "nit_texto": True,
        "url": "ruta_proceso_en_secop_i",
        "dataset": "f789-7hwg",
        "id": "uid",
        "fecha": "fecha_de_firma_del_contrato",
        # Muchas filas se cargan dias despues de firmadas, y las que solo estan
        # convocadas no tienen fecha de firma. Sin esta fecha de respaldo se
        # perderian los procesos abiertos, que son justo los que hay que vigilar.
        "fecha_alt": "fecha_de_cargue_en_el_secop",
        "entidad": "nombre_entidad",
        "departamento": "departamento_entidad",
        "ciudad": "municipio_entidad",
        "descripcion": ["detalle_del_objeto_a_contratar", "objeto_del_contrato_a_la",
                        "objeto_a_contratar"],
        # En SECOP I la urgencia manifiesta no es una modalidad sino una causal
        # de contratacion directa: 'Urgencia Manifiesta (Literal A)'.
        "justificacion": "causal_de_otras_formas_de",
        "modalidad": "modalidad_de_contratacion",
        "valor": "cuantia_contrato",
        "valor_alt": "cuantia_proceso",
        "proveedor": "nom_razon_social_contratista",
        "doc_proveedor": "identificacion_del_contratista",
        "estado": "estado_del_proceso",
        "etiqueta_fecha": "Firma del contrato (SECOP I)",
        "etiqueta_fecha_alt": "Cargue en SECOP I",
        "fecha_ini": "fecha_ini_ejec_contrato",
        "fecha_fin": "fecha_fin_ejec_contrato",
        "duracion": "plazo_de_ejec_del_contrato",
        "unidad_duracion": "rango_de_ejec_del_contrato",
        "vigilar": [
            "cuantia_contrato", "cuantia_proceso", "valor_total_de_adiciones",
            "valor_contrato_con_adiciones", "estado_del_proceso", "fecha_fin_ejec_contrato",
            "tiempo_adiciones_en_dias", "tiempo_adiciones_en_meses",
            "nom_razon_social_contratista", "fecha_liquidacion", "numero_de_contrato",
        ],
    },
}


def fuentes_activas(cfg):
    """Nombres de fuente a recolectar. SECOP I se puede apagar desde config.json."""
    activas = ["contratos", "procesos"]
    if cfg.get("secop1_activo", True):
        activas.append("secop1")
    return activas


def cargar_config():
    with open(os.path.join(BASE, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["app_token"] = cfg.get("app_token") or os.environ.get("SOCRATA_APP_TOKEN", "")
    return cfg


# --------------------------------------------------------------------------
# Utilidades de texto
# --------------------------------------------------------------------------

_PATRONES = {}


def contiene(texto, palabra):
    """Busca la palabra como inicio de palabra, no como fragmento.

    Sin esto 'EDAN' coincide dentro de 'puEDAN' y 'TALUD' dentro de otras
    palabras. Se ancla solo el inicio para que 'DAMNIFICAD' siga sirviendo
    para damnificado, damnificadas, etc.
    """
    patron = _PATRONES.get(palabra)
    if patron is None:
        patron = re.compile(r"\b" + re.escape(palabra))
        _PATRONES[palabra] = patron
    return bool(patron.search(texto))


def normalizar(texto):
    """Mayusculas sin tildes, para comparar palabras clave de forma robusta."""
    if texto is None or (isinstance(texto, float) and pd.isna(texto)):
        return ""
    s = unicodedata.normalize("NFKD", str(texto))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.upper()


def desempacar_url(valor):
    """El campo urlproceso llega como {'url': '...'} en la API."""
    if isinstance(valor, dict):
        return valor.get("url", "")
    return valor if isinstance(valor, str) else ""


def a_numero(serie):
    return pd.to_numeric(serie, errors="coerce").fillna(0)


def objeto_completo(fila, f):
    """El texto mas largo entre los campos de descripcion.

    En contratos, descripcion_del_proceso viene recortado cerca de los 300
    caracteres y objeto_del_contrato trae el objeto completo.
    """
    textos = [str(fila.get(c, "") or "") for c in f["descripcion"]]
    return max(textos, key=len) if textos else ""


def solo_fecha(valor):
    s = str(valor or "")
    return s[:10] if len(s) >= 10 else ""


def calcular_duracion(fila, f):
    """Devuelve (fecha_inicio, fecha_fin, texto_duracion).

    Los contratos traen la duracion como texto ('146 Dia(s)', '5 Mes(es)') y no
    siempre publican la fecha de inicio; en ese caso se estima desde la firma.
    Los procesos la traen partida en numero y unidad.
    """
    ini = solo_fecha(fila.get(f["fecha_ini"])) if f["fecha_ini"] else ""
    fin = solo_fecha(fila.get(f["fecha_fin"])) if f["fecha_fin"] else ""

    texto = str(fila.get(f["duracion"], "") or "").strip() if f["duracion"] else ""
    if f["unidad_duracion"]:
        unidad = str(fila.get(f["unidad_duracion"], "") or "").strip()
        texto = f"{texto} {unidad}".strip()

    if not texto and ini and fin:
        try:
            dias = (pd.Timestamp(fin) - pd.Timestamp(ini)).days
            if dias >= 0:
                texto = f"{dias} Dia(s)"
        except (ValueError, TypeError):
            pass

    # Si no hay fecha de inicio publicada, se usa la firma como referencia
    if not ini and f["fecha_ini"]:
        firma = solo_fecha(fila.get(f["fecha"]))
        if firma:
            ini = firma
    return ini, fin, texto


def pesos(valor):
    try:
        return "$ {:,.0f}".format(float(valor)).replace(",", ".")
    except (TypeError, ValueError):
        return "$ 0"


_MESES = {
    "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6,
    "JULIO": 7, "AGOSTO": 8, "SEPTIEMBRE": 9, "SETIEMBRE": 9, "OCTUBRE": 10,
    "NOVIEMBRE": 11, "DICIEMBRE": 12,
}
_RE_FECHA_LETRAS = re.compile(r"\b(\d{1,2})\s+DE\s+([A-Z]+)\s+(?:DEL?\s+)?(20\d{2})\b")
_RE_FECHA_DMA = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b")
_RE_FECHA_AMD = re.compile(r"\b(20\d{2})[/-](\d{1,2})[/-](\d{1,2})\b")


def fechas_en_texto(texto):
    """Fechas completas citadas en el objeto contractual, ya normalizado.

    Sirven para saber a que acto administrativo alude un contrato: 'calamidad
    publica decretada mediante Decreto Municipal 006 del 13 de febrero de 2026'
    no habla de este sismo, aunque diga 'calamidad' y aunque el ano coincida.
    Solo se reconocen fechas completas: un ano suelto ('vigencia fiscal 2026')
    no es una fecha y se ignora aqui.
    """
    encontradas = []
    for dia, mes, anio in _RE_FECHA_LETRAS.findall(texto):
        numero_mes = _MESES.get(mes)
        if numero_mes:
            try:
                encontradas.append(date(int(anio), numero_mes, int(dia)))
            except ValueError:
                pass
    for dia, mes, anio in _RE_FECHA_DMA.findall(texto):
        try:
            encontradas.append(date(int(anio), int(mes), int(dia)))
        except ValueError:
            pass
    for anio, mes, dia in _RE_FECHA_AMD.findall(texto):
        try:
            encontradas.append(date(int(anio), int(mes), int(dia)))
        except ValueError:
            pass
    return encontradas


def raiz_nit(nit):
    """Los nueve digitos del NIT, sin puntos, guiones ni digito de verificacion."""
    digitos = re.sub(r"\D", "", str(nit or ""))
    return digitos[:9] if len(digitos) >= 9 else digitos


def digito_verificacion(raiz):
    """Digito de verificacion de un NIT colombiano (el '6' de 900478966-6)."""
    pesos_dv = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43]
    suma = sum(int(d) * pesos_dv[i] for i, d in enumerate(reversed(raiz)))
    resto = suma % 11
    return str(resto if resto < 2 else 11 - resto)


def clausula_nit(campo, nits, texto):
    """Condicion SoQL que reconoce un NIT escrito de cualquiera de sus formas.

    El mismo NIT viaja escrito de maneras distintas segun la plataforma y segun
    la entidad que carga el registro. En SECOP I conviven '891900764' y
    '890983664-7' en el mismo dataset, y la UNGRD puede aparecer como 900478966,
    9004789666, 900478966-6 o 900.478.966-6. Sobre una columna de texto se
    compara por prefijo de la raiz de nueve digitos, que cubre todas esas formas
    de una sola vez.

    En contratos electronicos de SECOP II la columna es numerica y no admite
    prefijos: alli se enumeran las formas de digitos, con y sin el digito de
    verificacion. Comparar una columna numerica contra '900478966-6' no
    devuelve cero filas: aborta la consulta con un error de tipo.
    """
    raices = [r for r in (raiz_nit(n) for n in nits) if r]
    if not raices:
        return "1 = 0"

    if not texto:
        valores = set()
        for n in nits:
            digitos = re.sub(r"\D", "", str(n or ""))
            if digitos:
                valores.add(digitos)          # la forma tal como quedo en config.json
        for r in raices:
            valores.add(r)                    # sin digito de verificacion
            if len(r) == 9:
                valores.add(r + digito_verificacion(r))   # con el
        return f"{campo} in (" + ", ".join(f"'{v}'" for v in sorted(valores)) + ")"

    patrones = []
    for r in raices:
        patrones.append(f"{campo} like '{r}%'")
        if len(r) == 9:
            patrones.append(f"{campo} like '{r[:3]}.{r[3:6]}.{r[6:]}%'")
    return "(" + " OR ".join(patrones) + ")"


# --------------------------------------------------------------------------
# Acceso a la API
# --------------------------------------------------------------------------

def consultar(dataset, where, token="", limite_pagina=1000, max_filas=200000):
    """Descarga todas las filas que cumplen la condicion, paginando de forma estable."""
    filas, offset = [], 0
    cabeceras = {"X-App-Token": token} if token else {}
    url = f"{DOMINIO}/{dataset}.json"

    while offset < max_filas:
        params = {
            "$where": where,
            "$limit": limite_pagina,
            "$offset": offset,
            "$order": ":id",
        }
        for intento in range(4):
            try:
                r = requests.get(url, params=params, headers=cabeceras, timeout=120)
                if r.status_code == 200:
                    break
                if r.status_code in (202, 429, 500, 502, 503, 504):
                    time.sleep(3 * (intento + 1))
                    continue
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
            except requests.RequestException as e:
                if intento == 3:
                    raise
                time.sleep(3 * (intento + 1))
        else:
            raise RuntimeError(f"No se pudo consultar {dataset} tras varios intentos")

        lote = r.json()
        filas.extend(lote)
        if len(lote) < limite_pagina:
            break
        offset += limite_pagina
        time.sleep(0.3)

    return filas


def condiciones(nombre_fuente, cfg, hoy):
    """Construye los barridos (nombre -> clausula WHERE) para una fuente."""
    f = FUENTES[nombre_fuente]
    campo_fecha = f["fecha"]
    campo_dep = f["departamento"]
    campo_just = f["justificacion"]
    campo_nit = f["nit"]
    nit_texto = f["nit_texto"]

    inicio = f"{cfg['fecha_inicio']}T00:00:00"
    fin = (hoy + timedelta(days=2)).strftime("%Y-%m-%dT00:00:00")
    ventana = f"{campo_fecha} >= '{inicio}' AND {campo_fecha} < '{fin}'"
    if f.get("fecha_alt"):
        # SECOP I: hay filas firmadas antes del sismo que se cargaron despues, y
        # procesos convocados que todavia no tienen fecha de firma. Se acepta
        # cualquiera de las dos fechas dentro de la ventana y se descarta despues,
        # al clasificar, lo que resulte anterior al evento.
        alt = f["fecha_alt"]
        ventana = (f"(({ventana}) OR ({alt} >= '{inicio}' AND {alt} < '{fin}'))")

    deps = " OR ".join(f"{campo_dep} = '{d}'" for d in cfg["departamentos_vigilados"])

    # Se busca en todos los campos de texto: SECOP recorta
    # descripcion_del_proceso cerca de los 300 caracteres, mientras que
    # objeto_del_contrato trae el texto completo.
    claves = " OR ".join(
        f"upper({campo}) like '%{p}%'"
        for p in cfg["palabras_clave_fuertes"]
        for campo in f["descripcion"]
    )

    # En SECOP II la urgencia manifiesta es el valor de la justificacion de
    # modalidad; en SECOP I es una causal que llega como 'Urgencia Manifiesta
    # (Literal A)'. La comparacion por texto en mayusculas sirve para ambas.
    urgencia = f"upper({campo_just}) like '%URGENCIA MANIFIESTA%'"

    barridos = {
        # A. Entidades senaladas en los decretos (Cali central y Gobernacion del Valle)
        "nit": f"{ventana} AND {clausula_nit(campo_nit, cfg['nits_prioritarios'], nit_texto)}",
        # B. Todo el departamento: descentralizadas de Cali y municipios afectados
        "departamento": f"{ventana} AND ({deps})",
        # C. Barrido nacional por palabras clave y por justificacion de urgencia manifiesta
        "nacional_clave": f"{ventana} AND (({claves}) OR {urgencia})",
    }

    # D-bis. Cualquier entidad, de donde sea, cuyo objeto contractual mencione el
    #    territorio afectado. Es la red para la contratacion del gobierno
    #    nacional: si un ministerio contrata reconstruccion para Cali, entra por
    #    aqui aunque no diga "sismo" y aunque no este en ninguna lista.
    #
    #    Se hace asi y no con un padron de ministerios porque el orden nacional
    #    son 280 entidades que en cinco dias firmaron 3.047 contratos: traerlos
    #    todos ahogaria la senal. Y porque el campo 'orden' de SECOP es
    #    autodeclarado y poco fiable —marca "Nacional" a la CVC—, de modo que una
    #    lista basada en el dejaria huecos. Cruzar por el objeto no necesita
    #    mantenimiento: cubre a las 280 y a las que aparezcan manana.
    #    Se usa la lista corta de nombres inequivocos, no la del clasificador:
    #    SoQL compara por subcadena y no por palabra, asi que '%CALI%' encuentra
    #    tambien CALIDAD, CALIFICACION y CALIBRACION. Con la lista larga, 1.060
    #    de 1.323 registros traidos eran ruido de esa clase.
    territorio_obj = " OR ".join(
        f"upper({campo}) like '%{normalizar(p)}%'"
        for p in cfg.get("nombres_territorio_barrido", [])
        for campo in f["descripcion"]
    )
    if territorio_obj:
        barridos["objeto_territorio"] = f"{ventana} AND ({territorio_obj})"

    # D. UNGRD completa: es la entidad nacional que coordina la respuesta al
    #    desastre, asi que se trae toda su contratacion de la ventana y no solo
    #    la que menciona el sismo. Su relacion con el evento se evalua despues.
    nits_ungrd = cfg.get("nits_ungrd") or []
    if nits_ungrd:
        barridos["ungrd"] = f"{ventana} AND {clausula_nit(campo_nit, nits_ungrd, nit_texto)}"

    # E. Descentralizadas y demas entidades del Valle, por NIT propio.
    #    Es la unica red que las atrapa cuando su campo departamento viene como
    #    'No Definido': hay hospitales departamentales del Valle con departamento
    #    y ciudad sin diligenciar, que el barrido territorial no ve. Se trocea
    #    porque una sola clausula con cien 'like' hace fallar la consulta.
    nits_desc = [e["nit"] for clave in ("descentralizadas_cali", "descentralizadas_valle",
                                        "otras_valle_sin_departamento")
                 for e in cfg.get(clave, [])]
    for i in range(0, len(nits_desc), 15):
        lote = nits_desc[i:i + 15]
        barridos[f"descentralizadas_{i // 15 + 1}"] = (
            f"{ventana} AND {clausula_nit(campo_nit, lote, nit_texto)}"
        )

    return barridos


def descargar_fuente(nombre_fuente, cfg, hoy, verbose=True):
    f = FUENTES[nombre_fuente]
    acumulado = {}
    origenes = {}
    barridos = condiciones(nombre_fuente, cfg, hoy)
    fallos = 0

    for nombre_barrido, where in barridos.items():
        try:
            filas = consultar(f["dataset"], where, cfg["app_token"])
        except Exception as e:
            print(f"  ! barrido '{nombre_barrido}' de {nombre_fuente} fallo: {e}")
            fallos += 1
            continue
        if verbose:
            print(f"  - {nombre_fuente}/{nombre_barrido}: {len(filas)} filas")
        for fila in filas:
            clave = fila.get(f["id"])
            if not clave:
                continue
            acumulado[clave] = fila
            origenes.setdefault(clave, set()).add(nombre_barrido)

    # Distinguir "no hay nada que traer" de "no se pudo traer nada" es critico.
    # Si la API esta caida o limitando peticiones, todos los barridos fallan y
    # el resultado vacio se confundiria con ausencia de contratacion: el colector
    # seguiria adelante y sobrescribiria el tablero con un respaldo en blanco.
    if fallos == len(barridos):
        raise RuntimeError(
            f"los {fallos} barridos de '{nombre_fuente}' fallaron; la fuente no "
            f"esta respondiendo. No se toca nada: es preferible conservar los "
            f"datos de la ultima corrida buena."
        )
    if fallos:
        print(f"  ! atencion: {fallos} de {len(barridos)} barridos fallaron")

    if not acumulado:
        return pd.DataFrame()

    df = pd.DataFrame(list(acumulado.values()))
    df["origen_barrido"] = df[f["id"]].map(lambda k: "+".join(sorted(origenes.get(k, []))))
    campo_url = f["url"]
    if campo_url in df.columns:
        df[campo_url] = df[campo_url].map(desempacar_url)
    return df


# --------------------------------------------------------------------------
# Clasificacion de relacion con el sismo
# --------------------------------------------------------------------------

def clasificar(df, nombre_fuente, cfg):
    """Asigna nivel_relacion (Alta / Media / Contexto) y el motivo de esa asignacion."""
    if df.empty:
        return df

    f = FUENTES[nombre_fuente]
    campos_texto = [c for c in f["descripcion"] if c in df.columns]
    if f["entidad"] in df.columns:
        campos_texto.append(f["entidad"])

    texto = df[campos_texto].fillna("").agg(" | ".join, axis=1).map(normalizar)

    # Frases que se borran antes de buscar palabras clave. 'Estudio de mercado'
    # es contratacion rutinaria de cualquier entidad y no tiene nada que ver con
    # entregar mercados a damnificados; sin esto, la palabra MERCADO seria
    # inservible. Se borra solo la frase y se conserva el resto, de modo que un
    # texto que diga "estudio de mercado para la compra de mercados" se sigue
    # detectando por el segundo uso.
    #
    # Es distinto de frases_excluidas: aquellas solo anulan la coincidencia si el
    # texto no trae ademas una palabra de emergencia. Estas no cuentan nunca.
    neutralizadas = [normalizar(p) for p in cfg.get("frases_neutralizadas", [])]
    if neutralizadas:
        def sin_frases(t):
            for fr in neutralizadas:
                t = t.replace(fr, " ")
            return t
        texto_busqueda = texto.map(sin_frases)
    else:
        texto_busqueda = texto
    justificacion = df.get(f["justificacion"], pd.Series([""] * len(df))).map(normalizar)
    modalidad = df.get(f["modalidad"], pd.Series([""] * len(df))).map(normalizar)
    fecha = pd.to_datetime(df[f["fecha"]], errors="coerce")
    if f.get("fecha_alt") and f["fecha_alt"] in df.columns:
        # Un proceso de SECOP I solo convocado no tiene fecha de firma; sin este
        # respaldo quedaria sin fecha y se descartaria por 'anterior a la ventana'.
        fecha = fecha.fillna(pd.to_datetime(df[f["fecha_alt"]], errors="coerce"))
    corte_sismo = pd.Timestamp(cfg["fecha_inicio"])

    fuertes = [normalizar(p) for p in cfg["palabras_clave_fuertes"]]
    secundarias = [normalizar(p) for p in cfg["palabras_clave_secundarias"]]
    decretos = [normalizar(d) for d in cfg["decretos"]]
    excluidas = [normalizar(p) for p in cfg.get("frases_excluidas", [])]
    emergencia = [normalizar(p) for p in cfg.get("palabras_emergencia", [])]
    emergencia_fuerte = [normalizar(p) for p in cfg.get("palabras_emergencia_fuerte", [])]
    territorio = [normalizar(p) for p in cfg.get("nombres_territorio", [])]
    anio_evento = str(cfg["fecha_evento"])[:4]
    fecha_evento = date.fromisoformat(str(cfg["fecha_evento"])[:10])

    # Grupo por nivel de gobierno y ambito territorial.
    deps_vig = {normalizar(d) for d in cfg["departamentos_vigilados"]}
    # Se compara por la raiz de nueve digitos porque el mismo NIT llega escrito
    # con y sin digito de verificacion, y en SECOP I ademas con guion o puntos.
    nits_alcaldia = {raiz_nit(n) for n in cfg.get("nits_alcaldia_cali", [])}
    nits_gob = {raiz_nit(n) for n in cfg.get("nits_gobernacion_valle", [])}
    nits_ungrd = {raiz_nit(n) for n in cfg.get("nits_ungrd", [])}
    # Descentralizadas: se identifican por NIT propio, no por el de su matriz.
    # El Paragrafo Cuarto del Decreto 0964 las obliga a declarar SU PROPIA
    # urgencia manifiesta, asi que contratan aparte y hay que poder separarlas.
    desc_cali = {raiz_nit(e["nit"]) for e in cfg.get("descentralizadas_cali", [])}
    desc_valle = {raiz_nit(e["nit"]) for e in cfg.get("descentralizadas_valle", [])}
    dep_serie = df.get(f["departamento"], pd.Series([""] * len(df))).map(normalizar)
    nit_serie = df.get(f["nit"], pd.Series([""] * len(df))).astype(str).map(raiz_nit)

    desc_otras = {raiz_nit(e["nit"]) for e in cfg.get("otras_valle_sin_departamento", [])}
    # Un departamento se considera "sin diligenciar" cuando viene vacio o como
    # 'No Definido', que es justo el caso que obliga a barrer por NIT.
    sin_dato = {"", "NO DEFINIDO", "NAN", "NONE"}

    grupos = []
    for i in range(len(df)):
        nit = nit_serie.iloc[i]
        dep = dep_serie.iloc[i]
        # Guarda contra colisiones de NIT en la fuente. Caso real: en SECOP I la
        # cadena '891900493-2' identifica a la alcaldia de Caruru (Vaupes),
        # mientras '891900493' es Cartago (Valle); la busqueda por prefijo se
        # traga ambas. Si el registro dice explicitamente otro departamento, la
        # coincidencia por NIT no es de fiar. No aplica a los NIT centrales de
        # Cali, la Gobernacion y la UNGRD: la Casa del Valle figura en Bogota y
        # si es de la Gobernacion.
        nit_confiable = dep in deps_vig or dep in sin_dato

        if nit and nit in nits_ungrd:
            grupos.append("UNGRD")
        elif nit in nits_alcaldia:
            grupos.append("Alcaldía de Cali")
        elif nit in nits_gob:
            grupos.append("Gobernación del Valle")
        elif nit in desc_cali and nit_confiable:
            grupos.append("Descentralizadas de Cali")
        elif nit in desc_valle and nit_confiable:
            grupos.append("Descentralizadas de la Gobernación")
        elif nit in desc_otras and nit_confiable:
            grupos.append("Otras entidades del Valle")
        elif dep in deps_vig:
            grupos.append("Otras entidades del Valle")
        else:
            grupos.append("Fuera del Valle")

    # La UNGRD es entidad nacional con sede en Bogota. Para clasificar se la trata
    # como no territorial, de modo que solo cuente lo que aluda al sismo; pero lo
    # que si alude al evento SI suma en los indicadores, porque es la entidad que
    # coordina y financia la respuesta nacional al desastre del Valle.
    ambitos = ["Nacional" if g in ("Fuera del Valle", "UNGRD") else "Territorial"
               for g in grupos]
    cuenta_indicador = [g != "Fuera del Valle" for g in grupos]

    niveles, motivos = [], []
    for i in range(len(df)):
        t = texto.iloc[i]
        # tb: el mismo texto sin las frases neutralizadas. Solo se usa para
        # buscar palabras clave; el resto de comprobaciones usa el texto integro.
        tb = texto_busqueda.iloc[i]
        just = justificacion.iloc[i]
        moda = modalidad.iloc[i]
        territorial = ambitos[i] == "Territorial"
        posterior = bool(pd.notna(fecha.iloc[i]) and fecha.iloc[i] >= corte_sismo)
        razones = []

        if "URGENCIA MANIFIESTA" in just:
            razones.append("justificacion: urgencia manifiesta")
        golpes_decreto = [d for d in decretos if d and d in t]
        if golpes_decreto:
            razones.append("cita el decreto " + golpes_decreto[0])
        golpes_fuertes = [p for p in fuertes if contiene(tb, p)]
        if golpes_fuertes:
            razones.append("menciona " + ", ".join(golpes_fuertes[:3]).lower())
        golpes_sec = [p for p in secundarias if contiene(tb, p)]
        if golpes_sec:
            razones.append("objeto de emergencia: " + ", ".join(golpes_sec[:3]).lower())

        # Palabras que apuntan al evento mismo, no a cualquier emergencia
        del_evento = [p for p in golpes_fuertes
                      if p in ("SISMO", "TERREMOTO", "MOVIMIENTO TELURICO")]
        hay_emergencia = any(contiene(t, p) for p in emergencia)
        hay_emergencia_fuerte = any(contiene(t, p) for p in emergencia_fuerte)
        menciona_territorio = any(contiene(t, p) for p in territorio)
        # Fuera del territorio hay que distinguir este sismo de otros eventos
        # anteriores del pais. Exigir el ano 2026 resulto demasiado estricto: hay
        # objetos que escriben "10 de agosto" sin ano. Se descarta solo cuando el
        # texto alude a un ano distinto, como "sismo del 14 de septiembre de 2025".
        anios = set(re.findall(r"\b(20\d{2})\b", t))
        otro_anio = bool(anios) and anio_evento not in anios
        es_este_evento = bool(golpes_decreto) or not otro_anio

        # Una calamidad o una urgencia declarada ANTES del sismo es otro evento,
        # aunque caiga en el mismo ano y en el mismo territorio. Caso real: un
        # municipio del Valle contratando "en el marco de la calamidad publica
        # decretada mediante Decreto Municipal 006 del 13 de febrero de 2026".
        # Solo se degrada cuando la unica evidencia es la palabra generica: si
        # cita uno de los decretos vigilados o menciona el sismo, no se toca.
        fechas_citadas = fechas_en_texto(t)
        citas_previas = sorted(d for d in fechas_citadas if d < fecha_evento)
        hay_cita_posterior = any(d >= fecha_evento for d in fechas_citadas)
        acto_anterior = bool(citas_previas) and not hay_cita_posterior \
            and not golpes_decreto and not del_evento
        # "norma sismo resistente", "microzonificacion sismica" y similares son
        # contratacion tecnica rutinaria, no atencion del evento.
        if del_evento and any(fr in t for fr in excluidas) and not hay_emergencia:
            del_evento = []
            razones.append("coincidencia tecnica rutinaria, no atencion del evento")

        if not posterior:
            # No deberia ocurrir: todos los barridos filtran desde la fecha del evento
            nivel = "Contexto"
            razones.insert(0, "anterior a la ventana de seguimiento")
        elif golpes_decreto:
            nivel = "Alta"
        elif territorial and (del_evento or "URGENCIA MANIFIESTA" in just or golpes_fuertes):
            # Dentro de Cali y el Valle se es generoso: es el territorio del seguimiento
            nivel = "Alta"
        elif territorial and golpes_sec:
            nivel = "Media"
        elif not territorial and menciona_territorio and (del_evento or hay_emergencia_fuerte):
            # Entidad de otra region (UNGRD, ministerios) contratando para Cali o el Valle
            nivel = "Alta"
            razones.append("entidad de otra region con objeto destinado al territorio afectado")
        elif del_evento and hay_emergencia and es_este_evento:
            # Fuera del territorio solo cuenta si se trata de ESTE sismo: hay contratos
            # que atienden terremotos de anos anteriores y no son parte del seguimiento.
            nivel = "Alta"
        elif del_evento or "URGENCIA MANIFIESTA" in just:
            # Urgencia manifiesta u otro sismo del pais: no es lo que se busca, pero se
            # conserva como referencia de cuanta urgencia se declara por otras causas.
            nivel = "Otra urgencia"
            if otro_anio:
                razones.append(f"alude a un evento de {', '.join(sorted(anios))}, "
                               f"no al sismo de {anio_evento}")
            elif "URGENCIA MANIFIESTA" in just:
                razones.append("urgencia manifiesta de otra region, por otra emergencia")
            else:
                razones.append("menciona el termino pero su objeto no atiende el evento")
        elif golpes_fuertes or golpes_sec:
            nivel = "Contexto"
            razones.append("coincidencia de palabras fuera del territorio vigilado")
        else:
            nivel = "Contexto"
            if not razones:
                razones.append("contratacion ordinaria de entidad vigilada")

        # Se aplica al final y solo hacia abajo: nunca convierte en relacionado
        # algo que no lo era, solo descarta lo que resulto serlo por una
        # calamidad o una urgencia anterior al sismo.
        if acto_anterior and nivel in ("Alta", "Media"):
            nivel = "Otra urgencia"
            razones.append(f"alude a un acto del {citas_previas[0]:%d/%m/%Y}, anterior al "
                           f"sismo del {fecha_evento:%d/%m/%Y}")

        # Una entidad de otra region cuyo objeto va destinado al territorio
        # afectado no es "fuera del Valle": es el gobierno nacional u otra region
        # contratando PARA el Valle, y eso si cuenta. Se le da grupo propio para
        # que se distinga de la contratacion ajena al evento. La reasignacion va
        # despues de clasificar, de modo que no altera el criterio: solo cambia
        # como se agrupa lo que ya resulto relacionado.
        if grupos[i] == "Fuera del Valle" and menciona_territorio \
                and nivel in ("Alta", "Media"):
            grupos[i] = "Nacional para el Valle"
            cuenta_indicador[i] = True
            razones.append("entidad de otra region contratando para el territorio afectado")

        if grupos[i] == "UNGRD" and nivel == "Contexto":
            # No se pierde: la seccion de la UNGRD muestra toda su contratacion
            # de la ventana, relacionada o no con el sismo.
            razones.append("contratacion de la UNGRD sin mencion del evento")

        niveles.append(nivel)
        motivos.append("; ".join(razones))

    df = df.copy()
    df["grupo"] = grupos
    df["ambito"] = ambitos
    df["cuenta_indicador"] = cuenta_indicador
    df["nivel_relacion"] = niveles
    df["motivo_relacion"] = motivos
    df["anterior_al_sismo"] = (fecha < corte_sismo).fillna(False).values
    df["plataforma"] = f["plataforma"]
    df["es_ungrd"] = [g == "UNGRD" for g in grupos]
    df["fecha_efectiva"] = fecha.dt.strftime("%Y-%m-%d").fillna("").values
    return df


# Estados de SECOP I en los que ya existe contrato. No sirve mirar
# numero_de_contrato: viene diligenciado incluso en procesos solo convocados. Y
# 'Terminado Anormalmente despues de Convocado' es un proceso que murio antes de
# contratar, pese a empezar por 'Terminado'.
ESTADOS_CELEBRADOS = {"CELEBRADO", "LIQUIDADO", "TERMINADO SIN LIQUIDAR"}


def tipo_registro(fila, f):
    """Etiqueta 'Contrato' o 'Proceso' para una fila.

    En SECOP II lo define el dataset. En SECOP I ambos viven en la misma tabla:
    la fila es un contrato cuando ya se celebro, y un proceso mientras no.
    """
    if f["tipo"]:
        return f["tipo"]
    if solo_fecha(fila.get(f["fecha"])):
        return "Contrato"
    return "Contrato" if normalizar(fila.get(f["estado"])).strip() in ESTADOS_CELEBRADOS else "Proceso"


# --------------------------------------------------------------------------
# Estado, deteccion de cambios e historial
# --------------------------------------------------------------------------

def texto_campo(valor):
    """Normaliza un valor para poder compararlo entre ejecuciones.

    Un campo ausente llega como NaN, que en Python evalua como verdadero; sin
    esta normalizacion 'sin dato' se compara contra el texto 'nan' y cada
    ejecucion reporta cambios que nunca ocurrieron.
    """
    if valor is None:
        return ""
    if isinstance(valor, float) and pd.isna(valor):
        return ""
    s = str(valor).strip()
    return "" if s.lower() in ("nan", "none", "nat", "<na>") else s


def leer_estado(nombre_fuente):
    ruta = os.path.join(DIR_DATOS, f"{nombre_fuente}.csv")
    if os.path.exists(ruta):
        return pd.read_csv(ruta, dtype=str, keep_default_na=False)
    return pd.DataFrame()


def detectar_cambios(previo, actual, nombre_fuente, sello):
    """Devuelve (df_nuevos, lista_de_cambios) comparando contra la ejecucion anterior."""
    f = FUENTES[nombre_fuente]
    clave = f["id"]

    if previo.empty:
        nuevos = actual.copy()
        return nuevos, []

    ids_previos = set(previo[clave])
    nuevos = actual[~actual[clave].isin(ids_previos)].copy()

    prev_idx = previo.set_index(clave)
    cambios = []
    comunes = actual[actual[clave].isin(ids_previos)]

    for _, fila in comunes.iterrows():
        k = fila[clave]
        if k not in prev_idx.index:
            continue
        antes = prev_idx.loc[k]
        if isinstance(antes, pd.DataFrame):
            antes = antes.iloc[0]
        for campo in f["vigilar"]:
            if campo not in actual.columns:
                continue
            v_nuevo = texto_campo(fila.get(campo))
            v_viejo = texto_campo(antes.get(campo))
            if v_nuevo != v_viejo:
                cambios.append({
                    "fecha_deteccion": sello,
                    "fuente": nombre_fuente,
                    "identificador": k,
                    "entidad": fila.get(f["entidad"], ""),
                    "campo": campo,
                    "valor_anterior": v_viejo,
                    "valor_nuevo": v_nuevo,
                    "nivel_relacion": fila.get("nivel_relacion", ""),
                })
    return nuevos, cambios


def guardar_estado(df, nombre_fuente, hoy):
    ruta = os.path.join(DIR_DATOS, f"{nombre_fuente}.csv")
    df.to_csv(ruta, index=False, encoding="utf-8-sig")
    snap = os.path.join(DIR_HIST, f"{nombre_fuente}_{hoy:%Y%m%d}.csv.gz")
    with gzip.open(snap, "wt", encoding="utf-8", newline="") as fh:
        df.to_csv(fh, index=False)
    return ruta


def registrar_novedades(nuevos, nombre_fuente, sello):
    """Bitacora acumulativa de cuando aparecio cada registro en SECOP.

    Es append-only: a diferencia del reporte diario, que se reescribe si el
    colector corre dos veces el mismo dia, esto nunca se pierde. Sirve para
    responder 'cuando aparecio publicado este contrato'.
    """
    if nuevos.empty:
        return
    f = FUENTES[nombre_fuente]
    fechas = nuevos.get(f["fecha"], pd.Series([""] * len(nuevos), index=nuevos.index))
    filas = pd.DataFrame({
        "fecha_deteccion": sello,
        "fuente": nombre_fuente,
        "identificador": nuevos[f["id"]],
        "fecha_registro": nuevos.get("fecha_efectiva", fechas).astype(str).str[:10],
        "entidad": nuevos.get(f["entidad"], ""),
        "grupo": nuevos.get("grupo", ""),
        "nivel_relacion": nuevos.get("nivel_relacion", ""),
        "valor": nuevos.get(f["valor"], ""),
    })
    ruta = os.path.join(DIR_DATOS, "novedades.csv")
    filas.to_csv(ruta, mode="a", header=not os.path.exists(ruta),
                 index=False, encoding="utf-8-sig")


def sembrar_novedades():
    """Crea la bitacora a partir de la columna primera_vez_visto ya guardada.

    Se usa una sola vez, cuando la bitacora todavia no existe: sin esto se
    perderia el registro de los que ya se habian visto en corridas anteriores.
    """
    ruta = os.path.join(DIR_DATOS, "novedades.csv")
    if os.path.exists(ruta):
        return

    partes = []
    for nombre in FUENTES:
        d = leer_estado(nombre)
        if d.empty or "primera_vez_visto" not in d.columns:
            continue
        f = FUENTES[nombre]
        fechas = d.get(f["fecha"], pd.Series([""] * len(d), index=d.index))
        partes.append(pd.DataFrame({
            "fecha_deteccion": d["primera_vez_visto"],
            "fuente": nombre,
            "identificador": d[f["id"]],
            "fecha_registro": d.get("fecha_efectiva", fechas).astype(str).str[:10],
            "entidad": d.get(f["entidad"], ""),
            "grupo": d.get("grupo", ""),
            "nivel_relacion": d.get("nivel_relacion", ""),
            "valor": d.get(f["valor"], ""),
        }))

    if partes:
        todo = pd.concat(partes, ignore_index=True).sort_values("fecha_deteccion")
        todo.to_csv(ruta, index=False, encoding="utf-8-sig")
        print(f"  bitacora de novedades sembrada con {len(todo)} registros ya conocidos")


def leer_novedades(cfg, dias=30):
    """Mapa identificador -> fecha en que se vio por primera vez, ultimos N dias.

    Solo se devuelven registros cuya fecha propia cae dentro de la ventana de
    seguimiento. La bitacora conserva entradas de barridos que ya se retiraron
    (la linea base previa al sismo, por ejemplo) y sin este filtro el tablero
    reportaria mas novedades que registros descargados.
    """
    ruta = os.path.join(DIR_DATOS, "novedades.csv")
    if not os.path.exists(ruta):
        return {}
    d = pd.read_csv(ruta, dtype=str, keep_default_na=False)
    if d.empty:
        return {}
    corte = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")
    d = d[d["fecha_deteccion"].str[:10] >= corte]
    if "fecha_registro" in d.columns:
        d = d[d["fecha_registro"] >= cfg["fecha_inicio"]]
    # Si un identificador aparece varias veces se conserva la primera deteccion
    d = d.sort_values("fecha_deteccion").drop_duplicates("identificador", keep="first")
    return dict(zip(d["identificador"], d["fecha_deteccion"].str[:10]))


def registrar_cambios(cambios):
    if not cambios:
        return
    ruta = os.path.join(DIR_DATOS, "cambios.csv")
    df = pd.DataFrame(cambios)
    cabecera = not os.path.exists(ruta)
    df.to_csv(ruta, mode="a", header=cabecera, index=False, encoding="utf-8-sig")


# --------------------------------------------------------------------------
# Alertas
# --------------------------------------------------------------------------

def calcular_alertas(resultados, cfg):
    """Alertas sobre la contratacion relacionada de Cali y el Valle, en las dos plataformas."""
    alertas = []

    planos = []
    for nombre in fuentes_activas(cfg):
        planos.extend(aplanar(resultados.get(nombre, pd.DataFrame()), nombre))

    # Las alertas se concentran en lo que suma en los indicadores: Cali, el Valle
    # y la UNGRD/FNGRD. La contratacion ordinaria no genera alertas.
    rel = [r for r in planos
           if r.get("cuenta_indicador")
           and r["nivel"] in ("Alta", "Media")
           and r["tipo"] == "Contrato"]

    for r in rel:
        if r["valor"] >= cfg["alerta_valor_contrato"]:
            alertas.append({
                "tipo": "Contrato de alto valor",
                "detalle": f"{r['entidad']} - {pesos(r['valor'])} - {r['proveedor']} "
                           f"[{r['plataforma']}]",
                "identificador": r["id"],
            })

    por_proveedor = {}
    for r in rel:
        nombre_prov = str(r["proveedor"]).strip()
        if not nombre_prov:
            continue
        acc = por_proveedor.setdefault(nombre_prov, {"n": 0, "total": 0.0})
        acc["n"] += 1
        acc["total"] += r["valor"]
    for nombre_prov, acc in por_proveedor.items():
        if acc["n"] >= cfg["alerta_contratos_mismo_proveedor"]:
            alertas.append({
                "tipo": "Proveedor con varios contratos",
                "detalle": f"{nombre_prov}: {acc['n']} contratos por {pesos(acc['total'])}",
                "identificador": "",
            })

    # Contratos de urgencia sin proceso publicado en SECOP II
    contratos = resultados.get("contratos", pd.DataFrame())
    procesos = resultados.get("procesos", pd.DataFrame())
    if not contratos.empty and not procesos.empty:
        fc = FUENTES["contratos"]
        terr = contratos[
            (contratos["nivel_relacion"] == "Alta")
            & contratos["cuenta_indicador"].fillna(False).astype(bool)
        ]
        if not terr.empty:
            refs = set(procesos[FUENTES["procesos"]["id"]].astype(str))
            sin_proceso = terr[
                ~terr.get("proceso_de_compra", pd.Series([""] * len(terr))).astype(str).isin(refs)
            ]
            if len(sin_proceso) > 0:
                alertas.append({
                    "tipo": "Contratos sin proceso publicado",
                    "detalle": f"{len(sin_proceso)} contratos de relacion alta no tienen "
                               f"proceso visible en el dataset de procesos",
                    "identificador": "",
                })
    return alertas


# --------------------------------------------------------------------------
# Reporte diario
# --------------------------------------------------------------------------

def escribir_reporte(hoy, contratos, procesos, nuevos_c, nuevos_p, cambios, alertas, cfg,
                     resultados=None):
    fc, fp = FUENTES["contratos"], FUENTES["procesos"]
    resultados = resultados or {"contratos": contratos, "procesos": procesos}
    lineas = []
    a = lineas.append

    a(f"# Reporte de contratacion - urgencia manifiesta sismo 10 ago 2026")
    a("")
    a(f"**Corte:** {hoy:%Y-%m-%d %H:%M}  |  **Ventana:** {cfg['fecha_inicio']} en adelante")
    a("")

    def relevantes(df, solo_indicador=True):
        if df.empty:
            return pd.DataFrame()
        m = df["nivel_relacion"].isin(["Alta", "Media"])
        if solo_indicador:
            # Cali, el Valle y la UNGRD/FNGRD. Queda fuera el resto del pais.
            m &= df["cuenta_indicador"].fillna(False).astype(bool)
        return df[m]

    rel_c = relevantes(contratos)
    rel_p = relevantes(procesos)
    nac_c = relevantes(contratos, False)
    nac_p = relevantes(procesos, False)
    sin_ind = lambda d: d[~d["cuenta_indicador"].fillna(False).astype(bool)] if not d.empty else pd.DataFrame()
    nac_c = sin_ind(nac_c)
    nac_p = sin_ind(nac_p)
    total_valor = a_numero(rel_c[fc["valor"]]).sum() if not rel_c.empty else 0

    a("## Resumen · Cali, Valle del Cauca y UNGRD")
    a("")
    a("| Indicador | Valor |")
    a("|---|---|")
    a(f"| Contratos relacionados (alta + media) | {len(rel_c)} |")
    a(f"| Valor de esos contratos | {pesos(total_valor)} |")
    a(f"| Procesos relacionados (alta + media) | {len(rel_p)} |")
    a(f"| Contratos nuevos en esta ejecucion | {len(nuevos_c)} |")
    a(f"| Procesos nuevos en esta ejecucion | {len(nuevos_p)} |")
    a(f"| Modificaciones detectadas | {len(cambios)} |")
    a(f"| Registros revisados en total | {len(contratos) + len(procesos)} |")
    a("")

    if not contratos.empty or not procesos.empty:
        a("### Desglose por nivel de gobierno")
        a("")
        a("| Grupo | Contratos | Valor | Procesos |")
        a("|---|---:|---:|---:|")
        for grupo in ("Alcaldía de Cali", "Gobernación del Valle",
                      "Otras entidades del Valle", "UNGRD"):
            gc = rel_c[rel_c["grupo"] == grupo] if not rel_c.empty else pd.DataFrame()
            gp = rel_p[rel_p["grupo"] == grupo] if not rel_p.empty else pd.DataFrame()
            valor = a_numero(gc[fc["valor"]]).sum() if not gc.empty else 0
            etiqueta = "UNGRD y FNGRD" if grupo == "UNGRD" else grupo
            a(f"| {etiqueta} | {len(gc)} | {pesos(valor)} | {len(gp)} |")
        a("")

        # Contratacion ordinaria de las dos entidades del decreto, sin relacion
        # con el sismo. No suma en los indicadores; se lista para dimensionarla.
        a("### Contratación ordinaria de la Alcaldía y la Gobernación")
        a("")
        a("| Grupo | Contratos | Valor | Procesos |")
        a("|---|---:|---:|---:|")
        for grupo in GRUPOS_ORDINARIA:
            oc = contratos[(contratos["nivel_relacion"] == "Contexto")
                           & (contratos["grupo"] == grupo)] if not contratos.empty else pd.DataFrame()
            op = procesos[(procesos["nivel_relacion"] == "Contexto")
                          & (procesos["grupo"] == grupo)] if not procesos.empty else pd.DataFrame()
            valor = a_numero(oc[fc["valor"]]).sum() if not oc.empty else 0
            a(f"| {grupo} | {len(oc)} | {pesos(valor)} | {len(op)} |")
        a("")
        a("No tiene relación con el sismo y no suma en los indicadores de arriba. "
          "Se incluye porque son las dos entidades que expidieron los decretos.")
        a("")

    otras_c = contratos[contratos["nivel_relacion"] == "Otra urgencia"] if not contratos.empty else pd.DataFrame()
    otras_p = procesos[procesos["nivel_relacion"] == "Otra urgencia"] if not procesos.empty else pd.DataFrame()

    if len(nac_c) or len(nac_p) or len(otras_c) or len(otras_p):
        a("### Referencia: fuera del Valle del Cauca")
        a("")
        if len(nac_c) or len(nac_p):
            vn = a_numero(nac_c[fc["valor"]]).sum() if not nac_c.empty else 0
            a(f"- **Relacionados con el sismo:** {len(nac_c)} contratos ({pesos(vn)}) y "
              f"{len(nac_p)} procesos de otras regiones del país.")
        if len(otras_c) or len(otras_p):
            vo = a_numero(otras_c[fc["valor"]]).sum() if not otras_c.empty else 0
            a(f"- **Urgencia manifiesta por otras causas:** {len(otras_c)} contratos "
              f"({pesos(vo)}) y {len(otras_p)} procesos. No tienen relación con el sismo; "
              f"sirven para dimensionar cuánta urgencia manifiesta se declara en el país "
              f"por motivos distintos.")
        a("")
        a("Nada de lo anterior cuenta en los indicadores de Cali y el Valle.")
        a("")

    # ---- SECOP I -----------------------------------------------------------
    planos = []
    for nombre in fuentes_activas(cfg):
        planos.extend(aplanar(resultados.get(nombre, pd.DataFrame()), nombre))

    # Solo lo relacionado con el sismo. La urgencia manifiesta por otras causas y
    # las calamidades anteriores al evento se revisan, pero no se listan.
    s1 = [r for r in planos if r["plataforma"] == "SECOP I"
          and r["nivel"] in ("Alta", "Media")]
    descartados_s1 = len([r for r in planos if r["plataforma"] == "SECOP I"
                          and r["nivel"] == "Otra urgencia"])
    a("## SECOP I")
    a("")
    if s1:
        s1_terr = [r for r in s1 if r.get("cuenta_indicador")]
        valor_s1 = sum(r["valor"] for r in s1_terr if r["tipo"] == "Contrato")
        a(f"- **Relacionados con el sismo: {len(s1)}** "
          f"({len(s1_terr)} que suman en los indicadores, por {pesos(valor_s1)}).")
        a("")
        a("| Fecha | Entidad | Objeto | Valor | Modalidad / causal | Relacion |")
        a("|---|---|---|---:|---|---|")
        for r in sorted(s1, key=lambda x: x["valor"], reverse=True)[:30]:
            obj = str(r["objeto"])[:110].replace("|", "/").replace("\n", " ")
            causal = f"{r['modalidad']} · {r['justificacion']}".strip(" ·")
            a(f"| {r['fecha']} | {r['entidad']} | {obj} | {pesos(r['valor'])} | "
              f"{causal} | {r['nivel']} |")
    else:
        a("Sin contratos ni convenios relacionados con el sismo en SECOP I para esta ventana. "
          "La mayor parte de la contratacion actual se tramita por SECOP II; SECOP I se "
          "revisa porque sigue recibiendo cargues y porque algunas entidades y regimenes "
          "especiales continuan publicando alli.")
    if descartados_s1:
        a("")
        a(f"_No se listan {descartados_s1} registros de SECOP I con urgencia manifiesta por "
          f"otras causas o por calamidades anteriores al sismo. Quedan en `datos/secop1.csv`._")
    a("")

    # ---- UNGRD -------------------------------------------------------------
    # Igual que arriba: solo lo del sismo. Su contratacion ordinaria se revisa
    # entera, pero no se lista.
    ung = [r for r in planos if r["es_ungrd"] and r["nivel"] in ("Alta", "Media")]
    revisados_ung = sum(
        int(d["es_ungrd"].fillna(False).astype(bool).sum())
        for d in resultados.values() if not d.empty and "es_ungrd" in d.columns
    )
    a("## UNGRD y FNGRD · NIT 900.478.966-6 y 900.978.341")
    a("")
    if ung:
        valor_ung = sum(r["valor"] for r in ung if r["tipo"] == "Contrato")
        a(f"- **Relacionados con el sismo: {len(ung)}** registros por {pesos(valor_ung)}.")
        a("")
        a("| Fecha | Entidad | Plataforma | Objeto | Valor | Contratista | Relacion |")
        a("|---|---|---|---|---:|---|---|")
        for r in sorted(ung, key=lambda x: x["valor"], reverse=True)[:30]:
            obj = str(r["objeto"])[:110].replace("|", "/").replace("\n", " ")
            a(f"| {r['fecha']} | {r['entidad']} | {r['plataforma']} | {obj} | "
              f"{pesos(r['valor'])} | {r['proveedor']} | {r['nivel']} |")
        a("")
        a("Se incluye el Fondo Nacional de Gestion del Riesgo (FNGRD), entidad distinta de la "
          "UNGRD pero cuyo ordenador del gasto es su director. Lo que aqui aparece SI suma en "
          "los indicadores: es la entidad que coordina y financia la respuesta nacional al "
          "desastre. Su contratacion ordinaria, en cambio, no se muestra.")
    else:
        a("La UNGRD y el FNGRD no registran todavia contratacion relacionada con el sismo, "
          "ni en SECOP I ni en SECOP II.")
    if revisados_ung:
        a("")
        a(f"_Se revisaron {revisados_ung} registros de contratacion de estas dos entidades en "
          f"la ventana; los que no aluden al sismo no se listan. Quedan en los CSV._")
    a("")

    if not rel_c.empty:
        a("## Contratos por entidad")
        a("")
        g = rel_c.copy()
        g["_v"] = a_numero(g[fc["valor"]])
        tabla = g.groupby(fc["entidad"]).agg(n=(fc["id"], "count"), total=("_v", "sum"))
        tabla = tabla.sort_values("total", ascending=False).head(15)
        a("| Entidad | Contratos | Valor |")
        a("|---|---:|---:|")
        for ent, r in tabla.iterrows():
            a(f"| {ent} | {int(r['n'])} | {pesos(r['total'])} |")
        a("")

    if len(nuevos_c):
        otros = nuevos_c
        nuevos_c = nuevos_c[nuevos_c["nivel_relacion"].isin(["Alta", "Media"])]
        a(f"## Contratos nuevos ({len(nuevos_c)} relacionados de {len(otros)} publicados)")
        a("")
    if len(nuevos_c):
        a("| Fecha de firma | Entidad | Objeto | Valor | Proveedor | Relacion |")
        a("|---|---|---|---:|---|---|")
        n = nuevos_c.copy()
        n["_v"] = a_numero(n[fc["valor"]])
        n = n.sort_values("_v", ascending=False).head(40)
        for _, r in n.iterrows():
            obj = str(r.get(fc["descripcion"][0], ""))[:110].replace("|", "/").replace("\n", " ")
            a(f"| {str(r.get(fc['fecha'],''))[:10]} | {r.get(fc['entidad'],'')} | {obj} | "
              f"{pesos(r['_v'])} | {r.get(fc['proveedor'],'')} | {r.get('nivel_relacion','')} |")
        a("")

    if len(nuevos_p):
        otros = nuevos_p
        nuevos_p = nuevos_p[nuevos_p["nivel_relacion"].isin(["Alta", "Media"])]
        a(f"## Procesos nuevos ({len(nuevos_p)} relacionados de {len(otros)} publicados)")
        a("")
    if len(nuevos_p):
        a("| Fecha de publicacion | Entidad | Objeto | Precio base | Modalidad | Relacion |")
        a("|---|---|---|---:|---|---|")
        n = nuevos_p.copy()
        n["_v"] = a_numero(n[fp["valor"]])
        n = n.sort_values("_v", ascending=False).head(40)
        for _, r in n.iterrows():
            obj = str(r.get(fp["descripcion"][0], ""))[:110].replace("|", "/").replace("\n", " ")
            a(f"| {str(r.get(fp['fecha'],''))[:10]} | {r.get(fp['entidad'],'')} | {obj} | "
              f"{pesos(r['_v'])} | {r.get(fp['modalidad'],'')} | {r.get('nivel_relacion','')} |")
        a("")

    if cambios:
        a("## Modificaciones sobre registros ya conocidos")
        a("")
        a("| Fuente | Identificador | Campo | Antes | Ahora |")
        a("|---|---|---|---|---|")
        for c in cambios[:60]:
            a(f"| {c['fuente']} | {c['identificador']} | {c['campo']} | "
              f"{str(c['valor_anterior'])[:40]} | {str(c['valor_nuevo'])[:40]} |")
        a("")

    if alertas:
        a("## Alertas")
        a("")
        for al in alertas[:40]:
            a(f"- **{al['tipo']}**: {al['detalle']}")
        a("")

    a("---")
    a("")
    a("Fuente: datos.gov.co. SECOP II (`jbjy-vk9h` contratos electronicos, `p6dx-8zbt` procesos) "
      "y SECOP I (`f789-7hwg` procesos de compra publica). "
      "Los registros de SECOP se corrigen despues de publicados; el archivo `datos/cambios.csv` "
      "conserva la traza de cada modificacion.")

    ruta = os.path.join(DIR_REPORTES, f"reporte_{hoy:%Y-%m-%d}.md")
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lineas))

    with open(os.path.join(BASE, "REPORTE_ULTIMO.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lineas))
    return ruta


# --------------------------------------------------------------------------
# Datos para el tablero HTML
# --------------------------------------------------------------------------

# Grupos cuya contratacion ordinaria si se muestra en el tablero, bajo su propio
# filtro. Del resto de entidades solo se muestra lo relacionado con el sismo.
# Las descentralizadas reciben el mismo trato que su matriz: el Paragrafo Cuarto
# del Decreto 0964 las obliga a declarar su propia urgencia manifiesta, asi que
# hay que poder revisar todo lo que contraten, no solo lo que nombre el sismo.
GRUPOS_ORDINARIA = ("Alcaldía de Cali", "Gobernación del Valle",
                    "Descentralizadas de Cali", "Descentralizadas de la Gobernación")


def aplanar(df, nombre_fuente):
    """Registros normalizados, con los mismos nombres de campo en las tres fuentes.

    Se conserva lo relacionado con el sismo y la urgencia manifiesta de otras
    causas, que el tablero deja disponible como filtro explicito. De la
    contratacion ordinaria solo pasa la de la Alcaldia de Cali y la Gobernacion
    del Valle, que el tablero muestra bajo su propio filtro; la del resto se
    queda en los CSV, que es lo que permite reclasificar sin volver a pedirle
    nada a la API.
    """
    if df.empty:
        return []
    f = FUENTES[nombre_fuente]
    visible = df["nivel_relacion"].isin(["Alta", "Media", "Otra urgencia"])
    if "grupo" in df.columns:
        visible |= (
            (df["nivel_relacion"] == "Contexto")
            & df["grupo"].isin(GRUPOS_ORDINARIA)
        )
    d = df[visible].copy()
    if d.empty:
        return []

    d["_v"] = a_numero(d[f["valor"]])
    if f.get("valor_alt") and f["valor_alt"] in d.columns:
        # En SECOP I un proceso aun no celebrado no tiene cuantia de contrato,
        # solo cuantia del proceso.
        d["_v"] = d["_v"].where(d["_v"] > 0, a_numero(d[f["valor_alt"]]))

    salida = []
    for _, r in d.iterrows():
        ini, fin, dur = calcular_duracion(r, f)
        # solo_fecha, no un recorte crudo: un campo vacio llega como NaN y
        # str(NaN)[:10] deja el texto 'nan' en la columna de fecha.
        fecha = solo_fecha(r.get(f["fecha"]))
        etiqueta = f["etiqueta_fecha"]
        if not fecha and f.get("fecha_alt"):
            fecha = solo_fecha(r.get(f["fecha_alt"]))
            etiqueta = f.get("etiqueta_fecha_alt", etiqueta)
        salida.append({
            "tipo": tipo_registro(r, f),
            "plataforma": f["plataforma"],
            "fuente": nombre_fuente,
            "id": r.get(f["id"], ""),
            "fecha": fecha,
            "etiqueta_fecha": etiqueta,
            "fecha_inicio": ini,
            "fecha_fin": fin,
            "duracion": dur,
            "entidad": r.get(f["entidad"], ""),
            "nit": r.get(f["nit"], ""),
            "departamento": r.get(f["departamento"], ""),
            "ciudad": r.get(f["ciudad"], ""),
            "objeto": objeto_completo(r, f),
            "modalidad": r.get(f["modalidad"], ""),
            "justificacion": r.get(f["justificacion"], ""),
            "valor": float(r["_v"]),
            "proveedor": r.get(f["proveedor"], ""),
            "documento_proveedor": r.get(f["doc_proveedor"], ""),
            "estado": r.get(f["estado"], ""),
            "url": r.get(f["url"], ""),
            "grupo": r.get("grupo", ""),
            "ambito": r.get("ambito", ""),
            "cuenta_indicador": bool(r.get("cuenta_indicador", False)),
            "es_ungrd": bool(r.get("es_ungrd", False)),
            "nivel": r.get("nivel_relacion", ""),
            "motivo": r.get("motivo_relacion", ""),
            "barrido": r.get("origen_barrido", ""),
        })
    return salida


GRUPOS_VIGILADOS = ("Alcaldía de Cali", "Descentralizadas de Cali",
                    "Gobernación del Valle", "Descentralizadas de la Gobernación",
                    "Otras entidades del Valle", "UNGRD")


ORDEN_DE_GRUPO = {
    "Alcaldía de Cali": "Territorial · Distrital",
    "Descentralizadas de Cali": "Territorial · Distrital",
    "Gobernación del Valle": "Territorial · Departamental",
    "Descentralizadas de la Gobernación": "Territorial · Departamental",
    "Otras entidades del Valle": "Territorial · Municipal",
    "UNGRD": "Nacional",
    "Nacional para el Valle": "Nacional · destinado al territorio",
    "Fuera del Valle": "Nacional / otras regiones",
}

# La naturaleza de cada dependencia se deduce del nombre con que SECOP la
# publica: la fuente no trae un campo que lo diga. Sirve para filtrar, no es
# un dato oficial. El orden importa: 'DEPARTAMENTO ADMINISTRATIVO' antes que
# 'DEPARTAMENTO', 'RED DE SALUD' antes que cualquier otra cosa.
_TIPOS = [
    ("DEPARTAMENTO ADMINISTRATIVO", "Departamento Administrativo"),
    ("SECRETARIA", "Secretaría"),
    ("UNIDAD ADMINISTRATIVA", "Unidad Administrativa Especial"),
    ("PERSONERIA", "Personería"),
    ("CONTRALORIA", "Contraloría"),
    ("CONCEJO", "Concejo"),
    ("RED DE SALUD", "Hospital / ESE"),
    ("HOSPITAL", "Hospital / ESE"),
    ("E.S.E", "Hospital / ESE"),
    ("EMPRESA SOCIAL DEL ESTADO", "Hospital / ESE"),
    ("INSTITUCION EDUCATIVA", "Institución educativa"),
    ("UNIVERSIDAD", "Universidad"),
    ("INSTITUTO", "Instituto"),
    ("CAMARA DE COMERCIO", "Cámara de Comercio"),
    ("BIBLIOTECA", "Establecimiento cultural"),
    ("GOBERNACION", "Gobernación"),
    ("ALCALDIA", "Alcaldía municipal"),
    ("MUNICIPIO", "Alcaldía municipal"),
    ("FONDO", "Fondo"),
    ("E.S.P", "Empresa de servicios públicos"),
    ("CORPORACION", "Corporación"),
    ("EMPRESA", "Empresa industrial y comercial"),
]


def tipo_entidad(nombre):
    n = normalizar(nombre)
    for clave, etiqueta in _TIPOS:
        if clave in n:
            return etiqueta
    return "Otra"


def padron_entidades(resultados, cfg):
    """Censo de todas las entidades que el monitoreo consulta, con sus cifras.

    Va como agregado y no como filas por una razon de tamano: a cinco dias del
    sismo ya hay 1.745 registros, que a seis meses proyectan unos 62.800.
    Embeberlos haria el tablero inservible. El padron son unos cientos de lineas
    y crece con el numero de entidades, no con el paso del tiempo.

    Cumple dos funciones: es la pestana de consulta del padron, y es lo que la
    vista de contratacion ordinaria usa cuando no hay conexion. Sin el, esa
    vista contaria solo lo que alcanza a viajar embebido y subcontaria sin
    avisar, que es justo lo que no se puede hacer.

    Incluye las entidades configuradas que todavia no han contratado nada: se
    estan consultando igual, y decirlo evita que su ausencia se lea como que no
    se vigilan.
    """
    fijos = {}
    def registrar(nit, nombre, grupo):
        r = raiz_nit(nit)
        if r:
            fijos.setdefault(r, (nombre, grupo))

    for n in cfg.get("nits_alcaldia_cali", []):
        registrar(n, "Alcaldía de Santiago de Cali · nivel central", "Alcaldía de Cali")
    for n in cfg.get("nits_gobernacion_valle", []):
        registrar(n, "Gobernación del Valle del Cauca · nivel central", "Gobernación del Valle")
    for e in cfg.get("descentralizadas_cali", []):
        registrar(e["nit"], e["nombre"], "Descentralizadas de Cali")
    for e in cfg.get("descentralizadas_valle", []):
        registrar(e["nit"], e["nombre"], "Descentralizadas de la Gobernación")
    for e in cfg.get("otras_valle_sin_departamento", []):
        registrar(e["nit"], e["nombre"], "Otras entidades del Valle")
    for n in cfg.get("nits_ungrd", []):
        nom = ("Unidad Nacional para la Gestión del Riesgo de Desastres · UNGRD"
               if raiz_nit(n) == "900478966"
               else "Fondo Nacional de Gestión del Riesgo de Desastres · FNGRD")
        registrar(n, nom, "UNGRD")

    vistos = {}
    for nombre_fuente in fuentes_activas(cfg):
        df = resultados.get(nombre_fuente, pd.DataFrame())
        if df.empty or "grupo" not in df.columns:
            continue
        f = FUENTES[nombre_fuente]
        etiqueta = f["plataforma"] + (" · contratos" if nombre_fuente == "contratos"
                                      else " · procesos" if nombre_fuente == "procesos" else "")
        valores = a_numero(df[f["valor"]])
        if f.get("valor_alt") and f["valor_alt"] in df.columns:
            valores = valores.where(valores > 0, a_numero(df[f["valor_alt"]]))
        for i, (_, r) in enumerate(df.iterrows()):
            nom = str(r.get(f["entidad"], "") or "").strip() or "(sin nombre)"
            nit = str(r.get(f["nit"], "") or "").strip()
            clave = (nom, nit)
            e = vistos.setdefault(clave, {
                "entidad": nom, "tipo": tipo_entidad(nom), "nit": nit,
                "raiz": raiz_nit(nit), "grupo": r.get("grupo", ""),
                "plat": set(), "n": 0, "valor": 0.0, "rel": 0,
            })
            e["plat"].add(etiqueta)
            e["n"] += 1
            if tipo_registro(r, f) == "Contrato":
                e["valor"] += float(valores.iloc[i])
            if r.get("nivel_relacion") in ("Alta", "Media"):
                e["rel"] += 1

    padron = []
    for e in vistos.values():
        padron.append({**e,
                       "plat": " + ".join(sorted(e["plat"])),
                       "orden": ORDEN_DE_GRUPO.get(e["grupo"], e["grupo"]),
                       "via": "NIT en configuración" if e["raiz"] in fijos
                              else "Barrido territorial"})

    # Configuradas que aun no aparecen en ningun dato
    raices_vistas = {e["raiz"] for e in vistos.values()}
    for r, (nom, grupo) in fijos.items():
        if r in raices_vistas:
            continue
        padron.append({"entidad": nom, "tipo": tipo_entidad(nom), "nit": "—", "raiz": r,
                       "grupo": grupo, "orden": ORDEN_DE_GRUPO.get(grupo, grupo),
                       "via": "NIT en configuración", "plat": "—",
                       "n": 0, "valor": 0.0, "rel": 0, "sin_contratacion": True})

    return sorted(padron, key=lambda e: (-e["n"], e["entidad"]))


def exportar_tablero(hoy, resultados, cambios_totales, alertas, cfg, resumen_corrida=None):
    """Arma el paquete de datos que la pagina carga y pinta."""
    registros = []
    for nombre in fuentes_activas(cfg):
        registros.extend(aplanar(resultados.get(nombre, pd.DataFrame()), nombre))

    ruta_cambios = os.path.join(DIR_DATOS, "cambios.csv")
    historial_cambios = []
    if os.path.exists(ruta_cambios):
        dfc = pd.read_csv(ruta_cambios, dtype=str, keep_default_na=False)
        historial_cambios = dfc.tail(300).to_dict("records")

    payload = {
        "generado": hoy.strftime("%Y-%m-%d %H:%M:%S"),
        # Cuando aparecio publicado cada registro. Permite marcar novedades en el
        # tablero, que por si solo no tiene memoria de lo que vio antes.
        "novedades": leer_novedades(cfg, 30),
        "corrida_anterior": resumen_corrida or {},
        "fecha_inicio": cfg["fecha_inicio"],
        "fecha_evento": cfg["fecha_evento"],
        "decretos": cfg.get("decretos", []),
        "registros": registros,
        "padron": padron_entidades(resultados, cfg),
        "cambios": historial_cambios,
        "alertas": alertas,
        "totales": {
            nombre + "_monitoreados": int(len(resultados.get(nombre, pd.DataFrame())))
            for nombre in fuentes_activas(cfg)
        },
    }
    payload["totales"]["cambios_hoy"] = int(len(cambios_totales))

    return escribir_datos_tablero(payload)


def escribir_datos_tablero(payload):
    """Escribe datos/tablero.json, que es lo que la pagina carga y pinta.

    Antes estos datos iban incrustados dentro del propio HTML, para que el
    tablero fuera un archivo autonomo que se pudiera mandar por correo. Se dejo
    de necesitar eso, y el precio era alto: el HTML llegaba a 959 KB, de los
    cuales 864 eran datos, y ademas el navegador tenia que reimplementar el
    clasificador entero para poder consultar la API por su cuenta. Eran 477
    lineas de JavaScript que repetian lo que ya hace este archivo, y cada regla
    habia que cambiarla en dos idiomas. Con los datos ya clasificados aqui, la
    pagina solo pinta.
    """
    ruta = os.path.join(DIR_DATOS, "tablero.json")
    with open(ruta, "w", encoding="utf-8", newline="") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
    return ruta


# --------------------------------------------------------------------------
# Principal
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Monitor de contratacion por urgencia manifiesta")
    ap.add_argument("--sin-red", action="store_true",
                    help="reprocesa los CSV ya descargados sin consultar la API")
    args = ap.parse_args()

    cfg = cargar_config()
    ahora = datetime.now()
    hoy = ahora
    sello = ahora.strftime("%Y-%m-%d %H:%M:%S")

    print(f"Monitor urgencia manifiesta - {sello}")
    print(f"Ventana: desde {cfg['fecha_inicio']} ({cfg['meses_monitoreo']} meses de seguimiento)")

    sembrar_novedades()

    resultados = {}
    cambios_totales = []
    nuevos = {}

    for nombre in fuentes_activas(cfg):
        print(f"\n[{nombre}] {FUENTES[nombre]['plataforma']} · {FUENTES[nombre]['dataset']}")
        if args.sin_red:
            df = leer_estado(nombre)
            print(f"  - modo sin red: {len(df)} filas leidas del disco")
        else:
            try:
                df = descargar_fuente(nombre, cfg, hoy.date())
            except RuntimeError as e:
                # Se aborta sin escribir el tablero ni el reporte. Lo publicado
                # sigue siendo la ultima corrida completa, que es lo correcto:
                # mejor un dato de ayer entero que uno de hoy a medias.
                print(f"\n*** {e}")
                print("*** Corrida abortada. No se modifico el tablero ni el reporte.")
                sys.exit(2)

        if df.empty:
            print("  ! sin datos")
            resultados[nombre] = pd.DataFrame()
            nuevos[nombre] = pd.DataFrame()
            continue

        df = clasificar(df, nombre, cfg)
        previo = leer_estado(nombre)
        df_nuevos, cambios = detectar_cambios(previo, df, nombre, sello)

        f = FUENTES[nombre]
        if not previo.empty and f["id"] in previo.columns and "primera_vez_visto" in previo.columns:
            mapa = dict(zip(previo[f["id"]], previo["primera_vez_visto"]))
            df["primera_vez_visto"] = df[f["id"]].map(mapa).fillna(sello)
        else:
            df["primera_vez_visto"] = sello
        df["ultima_revision"] = sello

        guardar_estado(df, nombre, hoy)
        registrar_novedades(df_nuevos, nombre, sello)
        cambios_totales.extend(cambios)
        resultados[nombre] = df
        nuevos[nombre] = df_nuevos

        conteo = df["nivel_relacion"].value_counts().to_dict()
        print(f"  - total {len(df)} | relacion: {conteo}")
        print(f"  - nuevos: {len(df_nuevos)} | modificaciones: {len(cambios)}")

    registrar_cambios(cambios_totales)

    contratos = resultados.get("contratos", pd.DataFrame())
    procesos = resultados.get("procesos", pd.DataFrame())
    secop1 = resultados.get("secop1", pd.DataFrame())
    alertas = calcular_alertas(resultados, cfg)

    ruta_reporte = escribir_reporte(
        hoy, contratos, procesos,
        nuevos.get("contratos", pd.DataFrame()), nuevos.get("procesos", pd.DataFrame()),
        cambios_totales, alertas, cfg, resultados=resultados,
    )
    estado = {
        "ultima_ejecucion": sello,
        "contratos": int(len(contratos)),
        "procesos": int(len(procesos)),
        "secop1": int(len(secop1)),
        "nuevos_contratos": int(len(nuevos.get("contratos", pd.DataFrame()))),
        "nuevos_procesos": int(len(nuevos.get("procesos", pd.DataFrame()))),
        "nuevos_secop1": int(len(nuevos.get("secop1", pd.DataFrame()))),
        "cambios": len(cambios_totales),
        "alertas": len(alertas),
    }
    with open(os.path.join(DIR_DATOS, "estado.json"), "w", encoding="utf-8") as fh:
        json.dump(estado, fh, ensure_ascii=False, indent=2)

    ruta_tablero = exportar_tablero(hoy, resultados, cambios_totales,
                                    alertas, cfg, resumen_corrida=estado)

    print("\nListo.")
    print(f"  reporte : {ruta_reporte}")
    print(f"  datos   : {ruta_tablero}")
    print(f"  alertas : {len(alertas)}")
    if not secop1.empty:
        rel_s1 = secop1["nivel_relacion"].isin(["Alta", "Media"]).sum()
        print(f"  secop I : {len(secop1)} registros revisados, {rel_s1} relacionados")
    ungrd = sum(int(d.get("es_ungrd", pd.Series(dtype=bool)).sum())
                for d in resultados.values() if not d.empty)
    print(f"  UNGRD   : {ungrd} registros de contratacion en la ventana")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
