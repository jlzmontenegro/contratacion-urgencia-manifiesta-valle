# -*- coding: utf-8 -*-
"""Borradores de copy para Stories, armados con los campos del contrato.

Lo pidio el usuario el 22-sep-2026: que el correo de contratacion relacionada
con el sismo -el que va al equipo- traiga listos unos textos para darle difusion
en las Stories del diputado.

SON BORRADORES PARA QUE UNA PERSONA LOS REVISE Y LOS PUBLIQUE, no una cuenta
automatica. Esa frase va tambien en el correo, y no es una formalidad: quien
publica responde por lo que publica, y este archivo no sabe que paso hoy en el
Valle ni que dijo la entidad esta manana.

LAS CUATRO REGLAS QUE LO GOBIERNAN
==================================

1. SE CITA, NO SE PARAFRASEA. El objeto del contrato va TAL COMO LO ESCRIBIO LA
   ENTIDAD, entre comillas y recortado en una frontera de palabra cuando no
   cabe. Reescribirlo "para que suene mejor" es inventar: un objeto contractual
   resumido a mano deja de ser citable, y lo unico que hace publicable esto es
   que se pueda cotejar palabra por palabra contra el SECOP. Si viene en
   mayusculas sostenidas, sale en mayusculas sostenidas: asi lo publico la
   entidad.

   Lo unico que se toca son los espacios de mas y las tildes que la fuente
   degrado al exportar ("RECUPERACIoN" -> "RECUPERACIÓN"). Eso no es reescribir:
   es devolver lo que la entidad habia escrito antes de que el archivo lo
   estropeara. La ficha del correo sigue mostrando el texto crudo, que es contra
   lo que se coteja.

2. NI UNA PALABRA DE JUICIO. Aqui no hay "millonario", "insolito", "polemico" ni
   "mientras tanto". La cifra y el objeto hablan solos, y el que firma la Story
   es un diputado: un adjetivo suyo sobre un contratista con nombre propio es
   otra clase de riesgo, y no es este programa quien debe asumirlo por el. El
   copy DESCRIBE; opinar es decision de quien publica.

3. NADA QUE NO ESTE EN LA FUENTE. Si no hay contratista, se dice "aun sin
   contratista" y no se deduce de nada. Si el valor es precio base y no valor
   firmado, se rotula: son la misma plata en dos momentos y confundirlos es la
   forma mas facil de publicar una cifra falsa.

4. SIEMPRE LA FUENTE Y LA FECHA. Una Story sin de-donde-salio es un rumor con
   tipografia bonita. Va "Fuente: SECOP" y va el enlace, aparte, porque en
   Stories el texto no admite enlaces pulsables: eso es el sticker.

POR QUE ESTE MODULO Y NO UNAS LINEAS DENTRO DE correo.py: correo.py se ocupa de
entregar y este archivo de como se dice. El dia que el resumen del lunes o la
version ligera quieran el mismo texto, lo piden aqui y no lo reescriben; es la
misma razon por la que el clasificador vive en un solo sitio.
"""

import re

# Cuanto texto cabe en una Story sin que haya que achicar la letra hasta lo
# ilegible. No es un limite de la plataforma -Instagram admite mucho mas- sino
# de lo que una persona alcanza a leer en los dos o tres segundos que dura una
# diapositiva antes de que el pulgar siga. Medido a ojo sobre el formato
# vertical: por encima de esto hay que reducir el cuerpo y deja de leerse.
TOPE_STORY = 280

# Lo minimo que se le deja al objeto. Si ni recortando cabe, es preferible una
# Story sin objeto -con la cifra, la entidad y el enlace- que una con un jiron
# de frase que no se entiende y que ademas cita mal.
MINIMO_OBJETO = 60

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def _pesos(v):
    try:
        n = int(round(float(v or 0)))
    except (TypeError, ValueError):
        return "$ 0"
    return "$ " + f"{n:,}".replace(",", ".")


def _fecha_larga(iso):
    """'2026-08-25' -> '25 de agosto de 2026'. Vacio si no es una fecha."""
    s = str(iso or "")[:10]
    if len(s) < 10:
        return ""
    try:
        a, m, d = int(s[:4]), int(s[5:7]), int(s[8:10])
        return "%d de %s de %d" % (d, MESES[m - 1], a)
    except (ValueError, IndexError):
        return ""


# Las vocales acentuadas en caja alta llegan de SECOP I degradadas a minuscula
# sin tilde: "RECUPERACIoN", "CaMARA", "PuBLICA", "TeCNICAS". Medido el
# 22-sep-2026 sobre los 602 registros Alta: pasa en 81 objetos (13%), y 78 de
# ellos son de SECOP I. La secuencia mas comun es "IoN" -374 apariciones-, que
# es "CIÓN".
#
# REPARARLO NO ES PARAFRASEAR: es deshacer un defecto de codificacion de la
# fuente para devolver lo que la entidad escribio. Se hace SOLO en el copy, no
# en la ficha del correo: la ficha existe para cotejar contra el SECOP y ahi el
# texto tiene que llegar tal como esta publicado, con defecto y todo.
#
# La regla es estrecha a proposito: solo una vocal minuscula ACORRALADA entre
# dos mayusculas. En castellano no hay palabra en caja alta con una vocal
# minuscula legitima en medio, y exigir mayuscula a los dos lados evita tocar
# los nombres propios y las siglas mixtas.
_TILDES = {"a": "Á", "e": "É", "i": "Í", "o": "Ó", "u": "Ú"}
_ACORRALADA = re.compile(r"(?<=[A-ZÁÉÍÓÚÑ])([aeiou])(?=[A-ZÁÉÍÓÚÑ])")


def _reparar_mayusculas(s):
    return _ACORRALADA.sub(lambda m: _TILDES[m.group(1)], str(s or ""))


def _limpiar(s):
    """Colapsa espacios y saltos. No toca ni una letra del texto.

    Los objetos vienen pegados desde documentos de Word y traen saltos de linea
    y dobles espacios en medio de la frase; en una Story eso abre huecos que
    parecen un error de quien publica.
    """
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _recortar(texto, tope):
    """Recorta en frontera de PALABRA y avisa con el caracter de elipsis.

    Cortar a mitad de palabra hace que la cita parezca manipulada, que es
    exactamente lo que no puede pasar cuando el que publica es un diputado.
    """
    t = _limpiar(texto)
    if len(t) <= tope:
        return t
    corte = t[:tope - 1]
    espacio = corte.rfind(" ")
    if espacio > tope * 0.6:          # si el ultimo espacio esta muy al principio,
        corte = corte[:espacio]       # mejor cortar por caracter que dejar dos palabras
    return corte.rstrip(" ,;:.") + "…"


def _valor_rotulado(r):
    """El valor, siempre diciendo cual de los dos es.

    Precio base y valor firmado son la misma plata en dos momentos. Publicar un
    precio base como si fuera lo pagado es la forma mas facil de que a uno le
    desmientan una Story con razon.
    """
    firmado = (r.get("tipo") == "Contrato")
    return _pesos(r.get("valor")), ("valor firmado" if firmado else "precio base")


def story(r):
    """Borrador de Story para una contratacion. Devuelve un diccionario.

    Claves: `texto` (lo que va sobre la imagen), `enlace` (para el sticker),
    `largo` y `avisos` (lo que quien publica tiene que saber antes de publicar).
    """
    plata, rotulo = _valor_rotulado(r)
    # Las entidades escriben su propio nombre con asteriscos y comillas sueltas
    # ("GOBERNACION DE RISARALDA**"). Quitarlos es limpiar presentacion, como
    # colapsar espacios: en una Story esos signos se leen como un error de quien
    # publica, no de quien diligencio el formulario.
    entidad = _reparar_mayusculas(_limpiar(r.get("entidad"))).strip("*\"' ")
    contratista = _reparar_mayusculas(_limpiar(r.get("proveedor")))
    firmado = (r.get("tipo") == "Contrato")
    fecha = _fecha_larga(r.get("fecha"))
    objeto = _reparar_mayusculas(_limpiar(r.get("objeto")))

    # Se arma lo fijo primero y se mide; lo unico elastico es el objeto. Es la
    # misma mecanica del mensaje de X en la version ligera, y por el mismo
    # motivo: lo que nunca se toca es el dato que hace verificable la cifra.
    cabeza = "%s\n(%s)" % (plata, rotulo)

    # NUNCA se dice "contrató" sobre un proceso abierto. El nombre que trae un
    # proceso en el campo de proveedor NO es un adjudicado: medido el
    # 16-sep-2026, de 2.000 procesos del Valle con nombre de proveedor, 1.965
    # tenian adjudicado=No. Publicar "la Gobernacion contrato a X" cuando X solo
    # figura en el formulario seria señalar a una empresa por algo que no ha
    # ocurrido. En un proceso el copy dice lo unico cierto -que aun no hay
    # contrato- y el nombre, si lo hay, se queda en los avisos.
    if firmado:
        quien = "Contratista: %s" % (contratista or "sin contratista en la fuente")
    else:
        quien = "Aún sin contrato firmado"
    cuerpo = "%s\n%s" % (entidad, quien)
    if fecha:
        cuerpo += ("\nFirmado el %s" % fecha) if firmado else ("\nPublicado el %s" % fecha)
    pie = "Fuente: SECOP · enlace en el sticker"

    fijo = len("%s\n\n\n\n%s\n\n%s" % (cabeza, cuerpo, pie))
    espacio = TOPE_STORY - fijo - 2          # las dos comillas angulares
    partes = [cabeza]
    if objeto and espacio >= MINIMO_OBJETO:
        partes.append("«%s»" % _recortar(objeto, espacio))
    partes += [cuerpo, pie]
    texto = "\n\n".join(partes)

    # Lo que quien publica tiene que saber ANTES de publicar. Van como avisos y
    # no escondidos en el texto: el copy se pega en Instagram, estas lineas no.
    avisos = []
    if objeto and espacio < MINIMO_OBJETO:
        avisos.append("El objeto no cabe: va la cifra sin la cita. Tómelo del correo.")
    elif objeto and len(objeto) > espacio:
        avisos.append("El objeto va recortado; el texto completo está arriba en la ficha.")
    if rotulo == "precio base":
        avisos.append("Es PRECIO BASE, no lo pagado: el contrato aún no se ha firmado.")
    if not firmado and contratista:
        avisos.append("El proceso trae «%s» en el campo de proveedor, pero NO está "
                      "adjudicado. No lo publique como contratista." % contratista)
    if firmado and not contratista:
        avisos.append("El contrato está firmado pero la fuente no trae contratista.")
    grupo = _limpiar(r.get("grupo"))
    if grupo and "fuera del valle" in grupo.lower():
        avisos.append("Esta contratación NO es del Valle (%s). Decida si encaja en "
                      "el mensaje antes de publicarla." % grupo)
    if int(r.get("repetida") or 0) > 1:
        avisos.append("La entidad publicó esta misma contratación %d veces."
                      % int(r["repetida"]))

    return {"texto": texto, "enlace": r.get("url") or "",
            "largo": len(texto), "avisos": avisos}


def resumen(regs, generado=""):
    """Una Story para el conjunto del dia, cuando hay mas de una contratacion.

    Es aritmetica sobre lo que ya viaja: cuantas y cuanto suman. No se calcula
    ningun porcentaje ni se compara con nada, porque cualquier comparacion
    -"un 40% mas que ayer"- exigiria un denominador que este correo no tiene.
    """
    n = len(regs or [])
    if n < 2:
        return None
    total = sum(float(x.get("valor") or 0) for x in regs)
    firmados = [x for x in regs if x.get("tipo") == "Contrato"]
    entidades = len({_limpiar(x.get("entidad")) for x in regs if x.get("entidad")})

    lineas = ["%d contrataciones nuevas" % n,
              "relacionadas con el sismo",
              "",
              "Suman %s" % _pesos(total)]
    if entidades > 1:
        lineas.append("en %d entidades" % entidades)
    if firmados and len(firmados) != n:
        lineas.append("(%d ya firmadas, %d aún en proceso)" % (len(firmados), n - len(firmados)))
    lineas += ["", "Fuente: SECOP · enlace en el sticker"]

    texto = "\n".join(lineas)
    avisos = []
    if len(firmados) != n:
        avisos.append("La suma mezcla valores firmados y precios base: son la misma "
                      "plata en dos momentos. Si va a publicar una sola cifra, use "
                      "la de lo firmado.")
    return {"texto": texto, "enlace": "", "largo": len(texto), "avisos": avisos}
