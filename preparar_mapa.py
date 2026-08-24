# -*- coding: utf-8 -*-
"""Genera mapa.json: los contornos que dibuja el tablero.

Se corre A MANO y una sola vez; no forma parte de la recoleccion. Las fronteras
no cambian cada doce horas y bajarlas en cada corrida seria pedirle a un tercero
algo que ya tenemos. El resultado se publica como codigo, no como dato.

De donde salen
--------------
Marco Geoestadistico Nacional del DANE (2018), a traves del espejo publico
caticoa3/colombia_mapa en GitHub. Son los limites oficiales: departamentos con
codigo DANE de dos digitos y municipios con el de cinco. Se guarda el codigo
ademas del nombre porque el nombre es justo lo que baila entre fuentes.

Por que se guardan trazos SVG y no coordenadas
----------------------------------------------
El tablero solo tiene que dibujarlos, no calcular sobre ellos. Guardar el
atributo `d` ya proyectado ahorra la mitad del peso -no se repiten corchetes ni
comas- y le quita a la pagina el trabajo de proyectar 1.100 poligonos. Si algun
dia hiciera falta calcular distancias o centroides, hay que volver aqui.

Se simplifica con Douglas-Peucker escrito a mano para no depender de shapely,
que no esta instalado y que este proyecto no necesita para nada mas.
"""

import io
import json
import math
import os
import urllib.request

# En la raiz y no en datos\: datos\ lo mantiene GitHub Actions y publicar.bat no lo
# sube, asi que ahi el archivo no llegaria nunca a la pagina. Esto es codigo.
BASE = os.path.dirname(os.path.abspath(__file__))

FUENTE_DEPARTAMENTOS = ("https://gist.githubusercontent.com/john-guerra/"
                        "43c7656821069d00dcbc/raw/"
                        "be6a6e239cd5b5b803c6e7c2ec405b793a9064dd/Colombia.geo.json")
FUENTE_MUNICIPIOS = ("https://raw.githubusercontent.com/caticoa3/colombia_mapa/"
                     "master/co_2018_MGN_MPIO_POLITICO.geojson")

# Tolerancias en grados. El mapa nacional se ve a 1000px de ancho para 1.300 km:
# un punto son 1,3 km, asi que afinar mas solo engorda el archivo. El del Valle
# se ve mucho mas grande en proporcion y necesita cinco veces mas detalle.
TOLERANCIA_PAIS = 0.012
TOLERANCIA_VALLE = 0.0022

# Las islas y los cayos sueltos por debajo de esto no se dibujan: a esta escala
# son menos de un pixel. San Andres y Providencia entran por su propio anillo.
AREA_MINIMA_PAIS = 0.004
AREA_MINIMA_VALLE = 0.0004


# Como se ESCRIBE cada pieza en el mapa, cuando el nombre oficial no cabe. El
# nombre oficial se conserva en `nombre` porque es la llave con la que el colector
# empareja lo que publica SECOP; esto es solo el rotulo.
ROTULOS = {
    "ARCHIPIELAGO DE SAN ANDRES PROVIDENCIA Y SANTA CATALINA": "SAN ANDRES",
    "SANTAFE DE BOGOTA D.C": "BOGOTA D.C.",
}


def bajar(url):
    print("  bajando", url.split("/")[-1])
    with urllib.request.urlopen(url, timeout=300) as r:
        return json.loads(r.read().decode("utf-8"))


def distancia_a_recta(p, a, b):
    if a == b:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def simplificar(puntos, tol):
    """Douglas-Peucker iterativo: recursivo se pasa de profundidad con anillos
    de veinte mil puntos, que los hay."""
    if len(puntos) < 3:
        return puntos
    conservar = [False] * len(puntos)
    conservar[0] = conservar[-1] = True
    pilas = [(0, len(puntos) - 1)]
    while pilas:
        ini, fin = pilas.pop()
        if fin <= ini + 1:
            continue
        peor, cual = 0.0, -1
        for i in range(ini + 1, fin):
            d = distancia_a_recta(puntos[i], puntos[ini], puntos[fin])
            if d > peor:
                peor, cual = d, i
        if peor > tol:
            conservar[cual] = True
            pilas.append((ini, cual))
            pilas.append((cual, fin))
    return [p for p, c in zip(puntos, conservar) if c]


def area(anillo):
    """Area por la formula del cordon de zapato. Solo sirve para comparar
    tamanos entre anillos, no como superficie real."""
    s = 0.0
    for i in range(len(anillo)):
        x1, y1 = anillo[i]
        x2, y2 = anillo[(i + 1) % len(anillo)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def centroide(anillo):
    """Centroide del poligono, ponderado por area, no la media de los vertices.

    La media simple se va hacia donde el contorno tiene mas puntos, que es donde
    mas recovecos hay: en el Valle, hacia la cordillera. Esta formula da el centro
    de masa de la figura, que es donde una etiqueta se ve centrada.
    """
    a = 0.0
    cx = 0.0
    cy = 0.0
    for i in range(len(anillo)):
        x1, y1 = anillo[i]
        x2, y2 = anillo[(i + 1) % len(anillo)]
        cruz = x1 * y2 - x2 * y1
        a += cruz
        cx += (x1 + x2) * cruz
        cy += (y1 + y2) * cruz
    if a == 0:
        # Poligono degenerado: se cae a la media de los vertices antes que fallar.
        return (sum(x for x, _ in anillo) / len(anillo),
                sum(y for _, y in anillo) / len(anillo))
    a *= 0.5
    return cx / (6 * a), cy / (6 * a)


def anillos_de(geom):
    """Los anillos EXTERIORES de un Polygon o MultiPolygon. Los interiores -los
    agujeros- se descartan: a esta escala no se ven y duplicarian el peso."""
    t = geom.get("type")
    if t == "Polygon":
        return [geom["coordinates"][0]]
    if t == "MultiPolygon":
        return [p[0] for p in geom["coordinates"]]
    return []


def preparar(features, clave_codigo, clave_nombre, tol, area_min, extra=None):
    piezas = []
    for f in features:
        pr = f["properties"]
        crudos = [[(float(x), float(y)) for x, y in a] for a in anillos_de(f["geometry"])]
        if not crudos:
            continue
        # El anillo mayor entra SIEMPRE, mida lo que mida. Filtrando solo por area
        # desaparecian piezas enteras: Bogota cabe en el umbral pensado para cayos,
        # y un departamento que falta en un mapa se lee como que no contrato nada.
        mayor = max(range(len(crudos)), key=lambda i: area(crudos[i]))
        anillos = []
        for i, limpio in enumerate(crudos):
            if i != mayor and area(limpio) < area_min:
                continue
            s = simplificar(limpio, tol)
            if len(s) >= 3:
                anillos.append(s)
        if not anillos:
            continue
        nombre = str(pr[clave_nombre]).strip()
        pieza = {"codigo": str(pr[clave_codigo]).strip(),
                 "nombre": nombre,
                 "anillos": anillos}
        if nombre in ROTULOS:
            pieza["rotulo"] = ROTULOS[nombre]
        if extra:
            pieza.update({k: str(pr[v]).strip() for k, v in extra.items()})
        piezas.append(pieza)
    return piezas


def proyectar(piezas, ancho=1000.0):
    """Equirectangular con correccion por latitud. Colombia esta sobre el
    ecuador, asi que sin corregir el ancho por el coseno de la latitud media el
    pais sale estirado de lado."""
    xs = [x for p in piezas for a in p["anillos"] for x, _ in a]
    ys = [y for p in piezas for a in p["anillos"] for _, y in a]
    lat0 = (min(ys) + max(ys)) / 2.0
    k = math.cos(math.radians(lat0))
    x0, x1 = min(xs) * k, max(xs) * k
    y0, y1 = min(ys), max(ys)
    escala = ancho / (x1 - x0)
    alto = (y1 - y0) * escala

    def punto(x, y):
        return (round((x * k - x0) * escala, 1), round((y1 - y) * escala, 1))

    for p in piezas:
        trazos = []
        proyectados = []
        for anillo in p["anillos"]:
            pts = [punto(x, y) for x, y in anillo]
            proyectados.append(pts)
            trazos.append("M" + "L".join(f"{x} {y}" for x, y in pts) + "Z")
        p["d"] = "".join(trazos)
        # Donde va la etiqueta: el centroide del anillo MAYOR, no el de todos. Con
        # todos, Buenaventura -que tiene islas- se llevaria el nombre mar adentro.
        mayor = max(proyectados, key=area)
        cx, cy = centroide(mayor)
        p["cx"], p["cy"] = round(cx, 1), round(cy, 1)
        # El tamano de la pieza, para que la etiqueta se encoja en las pequenas:
        # con un solo cuerpo de letra, el nombre de Yotoco tapaba tres municipios.
        p["a"] = round(area(mayor))
        del p["anillos"]
    return round(alto, 1)


def main():
    print("Preparando los contornos del mapa")
    deps_geo = bajar(FUENTE_DEPARTAMENTOS)
    muni_geo = bajar(FUENTE_MUNICIPIOS)

    deps = preparar(deps_geo["features"], "DPTO", "NOMBRE_DPT",
                    TOLERANCIA_PAIS, AREA_MINIMA_PAIS)
    alto_pais = proyectar(deps)
    print(f"  departamentos: {len(deps)}")

    valle_features = [f for f in muni_geo["features"]
                      if str(f["properties"]["DPTO_CCDGO"]) == "76"]
    # MPIO_CCNCT y no MPIO_CCDGO: el segundo son los tres digitos del municipio
    # dentro de su departamento ('001' es Cali, pero tambien Medellin y Tunja). El
    # concatenado de cinco es el codigo DIVIPOLA que identifica de verdad.
    valle = preparar(valle_features, "MPIO_CCNCT", "MPIO_CNMBR",
                     TOLERANCIA_VALLE, AREA_MINIMA_VALLE)
    alto_valle = proyectar(valle)
    print(f"  municipios del Valle: {len(valle)}")

    salida = {
        "_fuente": "Marco Geoestadistico Nacional del DANE (2018). Codigos DANE: "
                   "dos digitos el departamento, cinco el municipio.",
        "_generado_por": "preparar_mapa.py, a mano. No lo toca la recoleccion.",
        "pais": {"ancho": 1000, "alto": alto_pais, "piezas": deps},
        "valle": {"ancho": 1000, "alto": alto_valle, "piezas": valle},
    }
    ruta = os.path.join(BASE, "mapa.json")
    with io.open(ruta, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  escrito {ruta}: {os.path.getsize(ruta) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
