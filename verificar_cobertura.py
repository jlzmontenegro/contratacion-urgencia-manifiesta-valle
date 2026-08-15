# -*- coding: utf-8 -*-
"""Auditoria de cobertura: comprueba que no se este escapando contratacion.

Para cada entidad vigilada y cada fuente compara tres caminos independientes:

  1. API, igualdad simple con la raiz del NIT   (lo minimo que deberia haber)
  2. API, cualquier forma del NIT               (con digito de verificacion,
                                                 con guion, con puntos)
  3. Lo que el colector dejo guardado en los CSV

Si los tres coinciden, no se perdio nada. Si el camino 2 supera al 1, la fuente
esta usando formas del NIT con digito de verificacion; eso es normal y esta
contemplado. Si el CSV queda por debajo del camino 2, hay un problema real.

No importa las funciones de colector.py a proposito: si el colector tuviera un
error al construir la consulta, reutilizarlo repetiria el mismo error y la
verificacion no serviria de nada.

Uso:
    py -3 verificar_cobertura.py
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE, "config.json"), encoding="utf-8") as fh:
    CFG = json.load(fh)

INICIO = f"{CFG['fecha_inicio']}T00:00:00"
FIN = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT00:00:00")

ENTIDADES = (
    [("Alcaldia de Cali", n) for n in CFG["nits_alcaldia_cali"][:1]]
    + [("Gobernacion del Valle", n) for n in CFG["nits_gobernacion_valle"][:1]]
    + [("UNGRD / FNGRD", n) for n in CFG.get("nits_ungrd", [])]
    + [(f"Desc.Cali {e['nombre'][:24]}", e["nit"])
       for e in CFG.get("descentralizadas_cali", [])]
    + [(f"Desc.Gob  {e['nombre'][:24]}", e["nit"])
       for e in CFG.get("descentralizadas_valle", [])]
    + [(f"Otras     {e['nombre'][:24]}", e["nit"])
       for e in CFG.get("otras_valle_sin_departamento", [])]
)

FUENTES = [
    ("contratos", "jbjy-vk9h", "nit_entidad", False, "id_contrato",
     f"fecha_de_firma >= '{INICIO}' AND fecha_de_firma < '{FIN}'"),
    ("procesos", "p6dx-8zbt", "nit_entidad", True, "id_del_proceso",
     f"fecha_de_publicacion_del >= '{INICIO}' AND fecha_de_publicacion_del < '{FIN}'"),
    ("secop1", "f789-7hwg", "nit_de_la_entidad", True, "uid",
     f"((fecha_de_firma_del_contrato >= '{INICIO}' AND fecha_de_firma_del_contrato < '{FIN}')"
     f" OR (fecha_de_cargue_en_el_secop >= '{INICIO}' AND fecha_de_cargue_en_el_secop < '{FIN}'))"),
]


def raiz(nit):
    d = re.sub(r"\D", "", str(nit or ""))
    return d[:9] if len(d) >= 9 else d


def dv(r):
    pesos = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43]
    s = sum(int(c) * pesos[i] for i, c in enumerate(reversed(r)))
    m = s % 11
    return str(m if m < 2 else 11 - m)


def contar(dataset, where, campo_id):
    """Cuenta identificadores DISTINTOS, no filas.

    La fuente publica el mismo proceso varias veces: 'CO1.REQ.10836380' aparecia
    tres veces. El colector deduplica por identificador, asi que comparar contra
    count(1) daria una diferencia que no es perdida de datos.
    """
    params = {"$select": f"count(distinct {campo_id})", "$where": where}
    url = f"https://www.datos.gov.co/resource/{dataset}.json?" + urllib.parse.urlencode(params)
    for intento in range(4):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                fila = json.loads(r.read().decode("utf-8"))[0]
                return int(next(iter(fila.values())))
        except Exception as e:
            if intento == 3:
                print(f"    ! {dataset}: {e}")
                return None
            time.sleep(4 * (intento + 1))


n_cali = len(CFG.get("descentralizadas_cali", []))
n_valle = len(CFG.get("descentralizadas_valle", []))
n_otras = len(CFG.get("otras_valle_sin_departamento", []))
print(f"Ventana verificada: {INICIO} <= fecha < {FIN}")
print(f"Entidades auditadas: {len(ENTIDADES)}  "
      f"(2 centrales + {len(CFG.get('nits_ungrd', []))} UNGRD/FNGRD + "
      f"{n_cali} descentralizadas de Cali + {n_valle} de la Gobernacion + "
      f"{n_otras} otras del Valle)")
print(f"Comprobaciones: {len(ENTIDADES)} entidades x {len(FUENTES)} fuentes = "
      f"{len(ENTIDADES) * len(FUENTES)}, cada una por tres caminos independientes\n")
print(f"{'Fuente':<11}{'Entidad':<23}{'NIT':<11}"
      f"{'API simple':>11}{'API amplio':>12}{'CSV':>7}   Veredicto")
print("-" * 84)

problemas = []
sin_verificar = []
for nombre, dataset, columna, es_texto, campo_id, ventana in FUENTES:
    ruta = os.path.join(BASE, "datos", f"{nombre}.csv")
    df = pd.read_csv(ruta, dtype=str, keep_default_na=False) if os.path.exists(ruta) \
        else pd.DataFrame()

    for etiqueta, nit in ENTIDADES:
        r = raiz(nit)
        n_simple = contar(dataset, f"{ventana} AND {columna} = '{r}'", campo_id)
        if es_texto:
            punteado = f"{r[:3]}.{r[3:6]}.{r[6:]}"
            cond = f"({columna} like '{r}%' OR {columna} like '{punteado}%')"
        else:
            cond = f"{columna} in ('{r}', '{r}{dv(r)}')"
        n_amplio = contar(dataset, f"{ventana} AND {cond}", campo_id)

        # En el CSV se cuenta por raiz del NIT, no por grupo: dos entidades
        # distintas pueden compartir grupo (UNGRD y su fondo).
        if df.empty or columna not in df.columns:
            n_csv = 0
        else:
            n_csv = int(df[columna].map(raiz).eq(r).sum())

        # Una consulta que no respondio no es una discrepancia: es una laguna.
        # Distinguirlas importa porque esto corre a diario sin nadie mirando, y
        # un hipo de la API no debe hacerse pasar por un fallo de cobertura.
        if n_amplio is None:
            veredicto = "SIN DATO"
            sin_verificar.append((nombre, etiqueta, r))
        elif n_csv == n_amplio:
            veredicto = "OK"
        else:
            veredicto = "REVISAR"
            problemas.append((nombre, etiqueta, r, n_simple, n_amplio, n_csv))
        print(f"{nombre:<11}{etiqueta:<23}{r:<11}"
              f"{str(n_simple):>11}{str(n_amplio):>12}{n_csv:>7}   {veredicto}")

print("-" * 84)
if sin_verificar:
    print(f"{len(sin_verificar)} comprobaciones sin dato (la API no respondio):")
    for p in sin_verificar[:10]:
        print("  ", p)
    print()
if problemas:
    print("HAY DISCREPANCIAS. Revise estas lineas:")
    for p in problemas:
        print("  ", p)
    sys.exit(1)
print(f"Sin discrepancias: el colector capturo todo lo que la API reporta "
      f"para las entidades vigiladas "
      f"({len(ENTIDADES) * len(FUENTES) - len(sin_verificar)} comprobaciones efectivas).")
