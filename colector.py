# -*- coding: utf-8 -*-
"""
Monitor de contratacion publica asociada a la urgencia manifiesta y al sismo
del 10 de agosto de 2026 (Cali / Valle del Cauca).

Fuentes (datos abiertos - SECOP II, API SODA de datos.gov.co):
  - Procesos de contratacion : p6dx-8zbt  (campo de fecha: fecha_de_publicacion_del)
  - Contratos electronicos   : jbjy-vk9h  (campo de fecha: fecha_de_firma)

Cada ejecucion:
  1. Barre las dos fuentes con tres estrategias (NIT, departamento, palabras clave nacional)
     mas una linea base historica de urgencia manifiesta en el Valle.
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
}


def cargar_config():
    with open(os.path.join(BASE, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["app_token"] = cfg.get("app_token") or os.environ.get("SOCRATA_APP_TOKEN", "")
    return cfg


# --------------------------------------------------------------------------
# Utilidades de texto
# --------------------------------------------------------------------------

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

    inicio = f"{cfg['fecha_inicio']}T00:00:00"
    fin = (hoy + timedelta(days=2)).strftime("%Y-%m-%dT00:00:00")
    ventana = f"{campo_fecha} >= '{inicio}' AND {campo_fecha} < '{fin}'"

    nits = ", ".join(f"'{n}'" for n in cfg["nits_prioritarios"])
    deps = " OR ".join(f"{campo_dep} = '{d}'" for d in cfg["departamentos_vigilados"])

    # Se busca en todos los campos de texto: SECOP recorta
    # descripcion_del_proceso cerca de los 300 caracteres, mientras que
    # objeto_del_contrato trae el texto completo.
    claves = " OR ".join(
        f"upper({campo}) like '%{p}%'"
        for p in cfg["palabras_clave_fuertes"]
        for campo in f["descripcion"]
    )

    barridos = {
        # A. Entidades senaladas en los decretos (Cali central y Gobernacion del Valle)
        "nit": f"{ventana} AND nit_entidad in ({nits})",
        # B. Todo el departamento: descentralizadas de Cali y municipios afectados
        "departamento": f"{ventana} AND ({deps})",
        # C. Barrido nacional por palabras clave y por justificacion de urgencia manifiesta
        "nacional_clave": (
            f"{ventana} AND (({claves}) OR {campo_just} = 'Urgencia manifiesta')"
        ),
        # D. Linea base: urgencia manifiesta en el Valle desde enero, para comparar
        #    el comportamiento previo al sismo y detectar contratos antefechados
        "linea_base": (
            f"{campo_fecha} >= '2026-01-01T00:00:00' AND {campo_fecha} < '{inicio}' "
            f"AND ({deps}) AND {campo_just} = 'Urgencia manifiesta'"
        ),
    }
    return barridos


def descargar_fuente(nombre_fuente, cfg, hoy, verbose=True):
    f = FUENTES[nombre_fuente]
    acumulado = {}
    origenes = {}

    for nombre_barrido, where in condiciones(nombre_fuente, cfg, hoy).items():
        try:
            filas = consultar(f["dataset"], where, cfg["app_token"])
        except Exception as e:
            print(f"  ! barrido '{nombre_barrido}' de {nombre_fuente} fallo: {e}")
            continue
        if verbose:
            print(f"  - {nombre_fuente}/{nombre_barrido}: {len(filas)} filas")
        for fila in filas:
            clave = fila.get(f["id"])
            if not clave:
                continue
            acumulado[clave] = fila
            origenes.setdefault(clave, set()).add(nombre_barrido)

    if not acumulado:
        return pd.DataFrame()

    df = pd.DataFrame(list(acumulado.values()))
    df["origen_barrido"] = df[f["id"]].map(lambda k: "+".join(sorted(origenes.get(k, []))))
    if "urlproceso" in df.columns:
        df["urlproceso"] = df["urlproceso"].map(desempacar_url)
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
    justificacion = df.get(f["justificacion"], pd.Series([""] * len(df))).map(normalizar)
    modalidad = df.get(f["modalidad"], pd.Series([""] * len(df))).map(normalizar)
    fecha = pd.to_datetime(df[f["fecha"]], errors="coerce")
    corte_sismo = pd.Timestamp(cfg["fecha_inicio"])

    fuertes = [normalizar(p) for p in cfg["palabras_clave_fuertes"]]
    secundarias = [normalizar(p) for p in cfg["palabras_clave_secundarias"]]
    decretos = [normalizar(d) for d in cfg["decretos"]]
    excluidas = [normalizar(p) for p in cfg.get("frases_excluidas", [])]
    emergencia = [normalizar(p) for p in cfg.get("palabras_emergencia", [])]

    # Grupo por nivel de gobierno y ambito territorial.
    deps_vig = {normalizar(d) for d in cfg["departamentos_vigilados"]}
    nits_alcaldia = set(cfg.get("nits_alcaldia_cali", []))
    nits_gob = set(cfg.get("nits_gobernacion_valle", []))
    dep_serie = df.get(f["departamento"], pd.Series([""] * len(df))).map(normalizar)
    nit_serie = df.get("nit_entidad", pd.Series([""] * len(df))).astype(str)

    grupos = []
    for i in range(len(df)):
        nit = nit_serie.iloc[i]
        if nit in nits_alcaldia:
            grupos.append("Alcaldía de Cali")
        elif nit in nits_gob:
            grupos.append("Gobernación del Valle")
        elif dep_serie.iloc[i] in deps_vig:
            grupos.append("Otras entidades del Valle")
        else:
            grupos.append("Fuera del Valle")

    ambitos = ["Nacional" if g == "Fuera del Valle" else "Territorial" for g in grupos]

    niveles, motivos = [], []
    for i in range(len(df)):
        t = texto.iloc[i]
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
        golpes_fuertes = [p for p in fuertes if p in t]
        if golpes_fuertes:
            razones.append("menciona " + ", ".join(golpes_fuertes[:3]).lower())
        golpes_sec = [p for p in secundarias if p in t]
        if golpes_sec:
            razones.append("objeto de emergencia: " + ", ".join(golpes_sec[:3]).lower())

        # Palabras que apuntan al evento mismo, no a cualquier emergencia
        del_evento = [p for p in golpes_fuertes
                      if p in ("SISMO", "TERREMOTO", "MOVIMIENTO TELURICO")]
        hay_emergencia = any(p in t for p in emergencia)
        # "norma sismo resistente", "microzonificacion sismica" y similares son
        # contratacion tecnica rutinaria, no atencion del evento.
        if del_evento and any(fr in t for fr in excluidas) and not hay_emergencia:
            del_evento = []
            razones.append("coincidencia tecnica rutinaria, no atencion del evento")

        if not posterior:
            # Anterior a la ventana: linea base para comparar el comportamiento
            # de la urgencia manifiesta antes del sismo.
            nivel = "Linea base"
            razones.insert(0, "anterior al 9 de agosto de 2026")
        elif golpes_decreto:
            nivel = "Alta"
        elif del_evento and (territorial or hay_emergencia):
            # Fuera del territorio vigilado se exige que el objeto sea de atencion
            # de la emergencia, no cualquier mencion del sismo.
            nivel = "Alta"
        elif "URGENCIA MANIFIESTA" in just and territorial:
            nivel = "Alta"
        elif "URGENCIA MANIFIESTA" in just:
            nivel = "Media"
            razones.append("urgencia manifiesta fuera del territorio vigilado")
        elif golpes_fuertes and territorial:
            nivel = "Alta"
        elif golpes_sec and territorial:
            nivel = "Media"
        elif golpes_fuertes or golpes_sec:
            nivel = "Contexto"
            razones.append("coincidencia de palabras fuera del territorio vigilado")
        else:
            nivel = "Contexto"
            if not razones:
                razones.append("contratacion ordinaria de entidad vigilada")

        niveles.append(nivel)
        motivos.append("; ".join(razones))

    df = df.copy()
    df["grupo"] = grupos
    df["ambito"] = ambitos
    df["nivel_relacion"] = niveles
    df["motivo_relacion"] = motivos
    df["anterior_al_sismo"] = (fecha < corte_sismo).fillna(False).values
    return df


# --------------------------------------------------------------------------
# Estado, deteccion de cambios e historial
# --------------------------------------------------------------------------

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
            v_nuevo = str(fila.get(campo, "") or "")
            v_viejo = str(antes.get(campo, "") or "")
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

def calcular_alertas(contratos, procesos, cfg):
    alertas = []
    fc = FUENTES["contratos"]

    if not contratos.empty:
        # Las alertas se concentran en Cali y el Valle, que es el objeto del seguimiento.
        rel = contratos[
            contratos["nivel_relacion"].isin(["Alta", "Media"])
            & (contratos["ambito"] == "Territorial")
        ].copy()
        if not rel.empty:
            rel["_valor"] = a_numero(rel[fc["valor"]])

            grandes = rel[rel["_valor"] >= cfg["alerta_valor_contrato"]]
            for _, r in grandes.iterrows():
                alertas.append({
                    "tipo": "Contrato de alto valor",
                    "detalle": f"{r.get(fc['entidad'],'')} - {pesos(r['_valor'])} - {r.get(fc['proveedor'],'')}",
                    "identificador": r[fc["id"]],
                })

            conteo = rel.groupby(fc["proveedor"]).agg(
                n=(fc["id"], "count"), total=("_valor", "sum")
            ).reset_index()
            repetidos = conteo[conteo["n"] >= cfg["alerta_contratos_mismo_proveedor"]]
            for _, r in repetidos.iterrows():
                if not str(r[fc["proveedor"]]).strip():
                    continue
                alertas.append({
                    "tipo": "Proveedor con varios contratos",
                    "detalle": f"{r[fc['proveedor']]}: {int(r['n'])} contratos por {pesos(r['total'])}",
                    "identificador": "",
                })

            # Contrato de emergencia con fecha de firma anterior al sismo/decreto
            firma = pd.to_datetime(rel[fc["fecha"]], errors="coerce")
            antefechados = rel[firma < pd.Timestamp(cfg["fecha_evento"])]
            for _, r in antefechados.iterrows():
                alertas.append({
                    "tipo": "Firmado antes del sismo",
                    "detalle": f"{r.get(fc['entidad'],'')} - firma {str(r.get(fc['fecha'],''))[:10]} - {pesos(r['_valor'])}",
                    "identificador": r[fc["id"]],
                })

            # Contratos de urgencia sin proceso publicado en SECOP
            if not procesos.empty:
                refs = set(procesos[FUENTES["procesos"]["id"]].astype(str))
                sin_proceso = rel[
                    (rel["nivel_relacion"] == "Alta")
                    & (~rel.get("proceso_de_compra", pd.Series([""] * len(rel))).astype(str).isin(refs))
                ]
                if len(sin_proceso) > 0:
                    alertas.append({
                        "tipo": "Contratos sin proceso publicado",
                        "detalle": f"{len(sin_proceso)} contratos de relacion alta no tienen proceso visible en el dataset de procesos",
                        "identificador": "",
                    })
    return alertas


# --------------------------------------------------------------------------
# Reporte diario
# --------------------------------------------------------------------------

def escribir_reporte(hoy, contratos, procesos, nuevos_c, nuevos_p, cambios, alertas, cfg):
    fc, fp = FUENTES["contratos"], FUENTES["procesos"]
    lineas = []
    a = lineas.append

    a(f"# Reporte de contratacion - urgencia manifiesta sismo 10 ago 2026")
    a("")
    a(f"**Corte:** {hoy:%Y-%m-%d %H:%M}  |  **Ventana:** {cfg['fecha_inicio']} en adelante")
    a("")

    def relevantes(df, solo_territorial=True):
        if df.empty:
            return pd.DataFrame()
        m = df["nivel_relacion"].isin(["Alta", "Media"])
        if solo_territorial:
            m &= df["ambito"] == "Territorial"
        return df[m]

    rel_c = relevantes(contratos)
    rel_p = relevantes(procesos)
    nac_c = relevantes(contratos, False)
    nac_p = relevantes(procesos, False)
    nac_c = nac_c[nac_c["ambito"] == "Nacional"] if not nac_c.empty else pd.DataFrame()
    nac_p = nac_p[nac_p["ambito"] == "Nacional"] if not nac_p.empty else pd.DataFrame()
    total_valor = a_numero(rel_c[fc["valor"]]).sum() if not rel_c.empty else 0

    a("## Resumen · Cali y Valle del Cauca")
    a("")
    a("| Indicador | Valor |")
    a("|---|---|")
    a(f"| Contratos relacionados (alta + media) | {len(rel_c)} |")
    a(f"| Valor de esos contratos | {pesos(total_valor)} |")
    a(f"| Procesos relacionados (alta + media) | {len(rel_p)} |")
    a(f"| Contratos nuevos en esta ejecucion | {len(nuevos_c)} |")
    a(f"| Procesos nuevos en esta ejecucion | {len(nuevos_p)} |")
    a(f"| Modificaciones detectadas | {len(cambios)} |")
    base_c = int((contratos["nivel_relacion"] == "Linea base").sum()) if not contratos.empty else 0
    base_p = int((procesos["nivel_relacion"] == "Linea base").sum()) if not procesos.empty else 0
    a(f"| Linea base previa al sismo (urgencia manifiesta ene-ago 8) | {base_c + base_p} |")
    a(f"| Filas totales monitoreadas (incluye contexto) | {len(contratos) + len(procesos)} |")
    a("")

    if not contratos.empty or not procesos.empty:
        a("### Desglose por nivel de gobierno")
        a("")
        a("| Grupo | Contratos | Valor | Procesos |")
        a("|---|---:|---:|---:|")
        for grupo in ("Alcaldía de Cali", "Gobernación del Valle", "Otras entidades del Valle"):
            gc = rel_c[rel_c["grupo"] == grupo] if not rel_c.empty else pd.DataFrame()
            gp = rel_p[rel_p["grupo"] == grupo] if not rel_p.empty else pd.DataFrame()
            valor = a_numero(gc[fc["valor"]]).sum() if not gc.empty else 0
            a(f"| {grupo} | {len(gc)} | {pesos(valor)} | {len(gp)} |")
        a("")

    if len(nac_c) or len(nac_p):
        vn = a_numero(nac_c[fc["valor"]]).sum() if not nac_c.empty else 0
        a("### Referencia: fuera del Valle del Cauca")
        a("")
        a(f"Se registran {len(nac_c)} contratos ({pesos(vn)}) y {len(nac_p)} procesos de otras "
          f"regiones del país relacionados con el sismo o con urgencia manifiesta. "
          f"No cuentan en los indicadores de arriba; sirven como punto de comparación.")
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
    a("Fuente: SECOP II via datos.gov.co (datasets `jbjy-vk9h` y `p6dx-8zbt`). "
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

def exportar_tablero(hoy, contratos, procesos, cambios_totales, alertas, cfg):
    """Genera datos/historial_tablero.js, que el tablero carga con <script src>
    (funciona incluso abriendo el HTML con doble clic, sin servidor web)."""
    fc, fp = FUENTES["contratos"], FUENTES["procesos"]

    def compactar(df, f, tipo):
        if df.empty:
            return []
        d = df[df["nivel_relacion"].isin(["Alta", "Media", "Linea base"])].copy()
        if d.empty:
            return []
        d["_v"] = a_numero(d[f["valor"]])
        salida = []
        for _, r in d.iterrows():
            ini, fin, dur = calcular_duracion(r, f)
            salida.append({
                "tipo": tipo,
                "id": r.get(f["id"], ""),
                "fecha": str(r.get(f["fecha"], ""))[:10],
                "etiqueta_fecha": f["etiqueta_fecha"],
                "fecha_inicio": ini,
                "fecha_fin": fin,
                "duracion": dur,
                "entidad": r.get(f["entidad"], ""),
                "nit": r.get("nit_entidad", ""),
                "departamento": r.get(f["departamento"], ""),
                "ciudad": r.get(f["ciudad"], ""),
                "objeto": objeto_completo(r, f),
                "modalidad": r.get(f["modalidad"], ""),
                "justificacion": r.get(f["justificacion"], ""),
                "valor": float(r["_v"]),
                "proveedor": r.get(f["proveedor"], ""),
                "documento_proveedor": r.get(f["doc_proveedor"], ""),
                "estado": r.get(f["estado"], ""),
                "url": r.get("urlproceso", ""),
                "grupo": r.get("grupo", ""),
                "ambito": r.get("ambito", ""),
                "nivel": r.get("nivel_relacion", ""),
                "motivo": r.get("motivo_relacion", ""),
                "barrido": r.get("origen_barrido", ""),
            })
        return salida

    registros = compactar(contratos, fc, "Contrato") + compactar(procesos, fp, "Proceso")

    ruta_cambios = os.path.join(DIR_DATOS, "cambios.csv")
    historial_cambios = []
    if os.path.exists(ruta_cambios):
        dfc = pd.read_csv(ruta_cambios, dtype=str, keep_default_na=False)
        historial_cambios = dfc.tail(300).to_dict("records")

    payload = {
        "generado": hoy.strftime("%Y-%m-%d %H:%M:%S"),
        "fecha_inicio": cfg["fecha_inicio"],
        "nits": cfg["nits_prioritarios"],
        "departamentos": cfg["departamentos_vigilados"],
        "palabras_fuertes": cfg["palabras_clave_fuertes"],
        "registros": registros,
        "cambios": historial_cambios,
        "alertas": alertas,
        "totales": {
            "contratos_monitoreados": int(len(contratos)),
            "procesos_monitoreados": int(len(procesos)),
            "cambios_hoy": int(len(cambios_totales)),
        },
    }

    return incrustar_en_tablero(payload)


MARCA_INI = '<script id="datos-locales" type="application/json">'
MARCA_FIN = "</script>"


def incrustar_en_tablero(payload):
    """Escribe el historial dentro de tablero.html.

    El tablero queda autonomo: un solo archivo, sin dependencias, que se puede
    enviar por correo o publicar en cualquier servidor y sigue consultando la
    API en vivo desde el navegador.
    """
    ruta = os.path.join(BASE, "tablero.html")
    if not os.path.exists(ruta):
        print("  ! no se encontro tablero.html; no se incrusto el historial")
        return ""

    with open(ruta, encoding="utf-8") as fh:
        html = fh.read()

    ini = html.find(MARCA_INI)
    if ini == -1:
        print("  ! tablero.html no tiene el bloque 'datos-locales'; no se incrusto nada")
        return ruta
    fin = html.find(MARCA_FIN, ini)

    # '<' escapado para que ningun texto del objeto contractual pueda cerrar la etiqueta
    datos = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    nuevo = html[:ini] + MARCA_INI + "\n" + datos + "\n" + html[fin:]

    with open(ruta, "w", encoding="utf-8", newline="") as fh:
        fh.write(nuevo)
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

    resultados = {}
    cambios_totales = []
    nuevos = {}

    for nombre in ("contratos", "procesos"):
        print(f"\n[{nombre}]")
        if args.sin_red:
            df = leer_estado(nombre)
            print(f"  - modo sin red: {len(df)} filas leidas del disco")
        else:
            df = descargar_fuente(nombre, cfg, hoy.date())

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
        cambios_totales.extend(cambios)
        resultados[nombre] = df
        nuevos[nombre] = df_nuevos

        conteo = df["nivel_relacion"].value_counts().to_dict()
        print(f"  - total {len(df)} | relacion: {conteo}")
        print(f"  - nuevos: {len(df_nuevos)} | modificaciones: {len(cambios)}")

    registrar_cambios(cambios_totales)

    contratos = resultados.get("contratos", pd.DataFrame())
    procesos = resultados.get("procesos", pd.DataFrame())
    alertas = calcular_alertas(contratos, procesos, cfg)

    ruta_reporte = escribir_reporte(
        hoy, contratos, procesos,
        nuevos.get("contratos", pd.DataFrame()), nuevos.get("procesos", pd.DataFrame()),
        cambios_totales, alertas, cfg,
    )
    ruta_tablero = exportar_tablero(hoy, contratos, procesos, cambios_totales, alertas, cfg)

    estado = {
        "ultima_ejecucion": sello,
        "contratos": int(len(contratos)),
        "procesos": int(len(procesos)),
        "nuevos_contratos": int(len(nuevos.get("contratos", pd.DataFrame()))),
        "nuevos_procesos": int(len(nuevos.get("procesos", pd.DataFrame()))),
        "cambios": len(cambios_totales),
        "alertas": len(alertas),
    }
    with open(os.path.join(DIR_DATOS, "estado.json"), "w", encoding="utf-8") as fh:
        json.dump(estado, fh, ensure_ascii=False, indent=2)

    print("\nListo.")
    print(f"  reporte : {ruta_reporte}")
    print(f"  tablero : {ruta_tablero}")
    print(f"  alertas : {len(alertas)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
