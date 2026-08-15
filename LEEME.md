# Monitor de contratación · Urgencia manifiesta por el sismo del 10 de agosto de 2026

Seguimiento de contratos y procesos de contratación relacionados con la urgencia manifiesta
declarada en Cali y la calamidad pública declarada en el Valle del Cauca, desde las
**00:00 del 10 de agosto de 2026** (día del sismo y de los decretos) y por al menos **6 meses**.

El foco son **Cali y el Valle del Cauca, incluidos sus municipios**. Los indicadores del
tablero cuentan solo ese territorio: si no hay contratación relacionada allí, marcan cero.
Lo que aparezca en otras regiones del país se muestra aparte, como referencia.

Actos administrativos que enmarcan el seguimiento:

| Acto | Autoridad | Contenido |
|---|---|---|
| Decreto 4112.010.20.0963 del 10-ago-2026 | Alcaldía de Cali | Calamidad pública, 6 meses |
| Decreto 4112.010.20.0964 del 10-ago-2026 | Alcaldía de Cali | Urgencia manifiesta, contratación directa (art. 42 Ley 80 de 1993) |
| Decreto 1.03.01-1070 del 10-ago-2026 | Gobernación del Valle | Calamidad pública, 6 meses, contratación por art. 66 Ley 1523 de 2012 |

---

## Uso diario

**No hay que hacer nada.** Desde el 15 de agosto de 2026 el monitoreo se actualiza solo:
GitHub Actions corre el colector todos los días a las **8:30 hora de Colombia**, verifica la
cobertura y publica. No depende de que ningún computador esté encendido.

**Ver los datos:** <https://jlzmontenegro.github.io/contratacion-urgencia-manifiesta-valle/>
La página muestra los datos de la última recolección y dice de cuándo son. **Ya no se abre
con doble clic**: el navegador bloquea la lectura de `datos/tablero.json` desde `file://`.
Para verla en local, sirva la carpeta por HTTP: `py -3 -m http.server 8765` y abra
<http://127.0.0.1:8765/>.

**Forzar una actualización ahora, sin esperar a mañana:** en el repositorio, pestaña
**Actions** → *Actualizar monitoreo* → botón **Run workflow**.

**Ver si algo falló:** la pestaña **Actions** muestra cada corrida. Si sale en rojo, GitHub
manda un correo. Una corrida en rojo significa que **no se publicó nada** y que el sitio
sigue mostrando la última corrida buena, completa. Eso es intencional.

**Publicar un cambio de código** (no de datos): `publicar.bat`. Sincroniza con el remoto y
sube solo el código. Ya **no** sube la carpeta `datos/`: si lo hiciera, borraría los
snapshots que Actions generó los días que este equipo estuvo apagado.

**Correr el colector a mano en este equipo:** `actualizar.bat` (o `py -3 colector.py`).
Sirve para probar cambios en local. Los datos que produzca aquí no se publican.

**Comprobar que no se esté escapando nada:** `py -3 verificar_cobertura.py`. Para cada entidad
vigilada y cada fuente compara tres caminos independientes —la API con el NIT simple, la API
con cualquier forma del NIT, y lo que quedó guardado en los CSV— y avisa si no coinciden. No
usa el código del colector, para que un error en el colector no pase desapercibido por
repetirse en la verificación.

---

## Qué consulta

Datos abiertos en datos.gov.co, las dos plataformas de contratación:

| Plataforma | Fuente | Dataset | Campo de fecha | Identificador |
|---|---|---|---|---|
| SECOP II | Contratos electrónicos | `jbjy-vk9h` | `fecha_de_firma` | `id_contrato` |
| SECOP II | Procesos de contratación | `p6dx-8zbt` | `fecha_de_publicacion_del` | `id_del_proceso` |
| SECOP I | Procesos de compra pública | `f789-7hwg` | `fecha_de_firma_del_contrato`, con respaldo en `fecha_de_cargue_en_el_secop` | `uid` |

Sobre cada fuente se corren cuatro barridos que luego se deduplican por identificador:

| Barrido | Qué captura | Por qué |
|---|---|---|
| `nit` | Los 5 NIT de Cali central y Gobernación del Valle | Entidades directamente cobijadas por los decretos |
| `departamento` | Toda entidad con departamento *Valle del Cauca* | Descentralizadas (EMCALI, Metro Cali, ESE) y municipios afectados. El Parágrafo Cuarto del Decreto 0964 obliga a las descentralizadas a declarar **su propia** urgencia manifiesta, con NIT distinto |
| `nacional_clave` | Todo el país por palabras clave o justificación "Urgencia manifiesta" | Entidades nacionales (ministerios) que contraten para la emergencia |
| `ungrd` | Toda la contratación de la UNGRD y del FNGRD | Coordinan la respuesta nacional al desastre. Se traen completas, mencionen o no el sismo |

## SECOP I y UNGRD

Ambos tienen **sección propia en el tablero** y en el reporte diario. Las dos secciones
muestran **solo lo relacionado con el sismo** (relación alta o media). Quedan fuera de la
vista, aunque se sigan descargando y guardando, la contratación ordinaria y la urgencia
manifiesta declarada por otras causas o por calamidades anteriores al 10 de agosto; el pie de
cada sección dice cuántos registros se descartaron. En la tabla de detalle sí se pueden
consultar con el filtro *Urgencia manifiesta por otras causas*.

**SECOP I** es la plataforma anterior y sigue viva: en 2026 se le cargaron 169.224 registros.
Se barre con las mismas cuatro estrategias que SECOP II, pero tiene tres diferencias que
obligaron a tratarla aparte:

- **No separa proceso y contrato.** Cada fila es un proceso que, si llegó a celebrarse, trae
  el contrato en las mismas columnas. El tipo se decide por `estado_del_proceso`: *Celebrado*,
  *Liquidado* y *Terminado sin Liquidar* son contratos; *Convocado*, *Adjudicado* y
  *Terminado Anormalmente después de Convocado* siguen siendo procesos. No sirve mirar
  `numero_de_contrato`: viene diligenciado incluso en procesos apenas convocados.
- **Las fechas no son confiables por sí solas.** Hay filas firmadas antes del sismo que se
  cargaron después, y procesos convocados sin fecha de firma. La ventana acepta cualquiera de
  las dos fechas y el descarte de lo anterior al evento se hace al clasificar.
- **La urgencia manifiesta no es una modalidad sino una causal**, que llega escrita como
  `Urgencia Manifiesta (Literal A)`.

**La UNGRD** (NIT 900.478.966-6) se **revisa** entera dentro de la ventana, en las dos
plataformas, mencione o no el sismo, pero en el tablero y en el reporte **solo se muestra lo
relacionado con el sismo**: su contratación ordinaria queda en los CSV, disponible para
reclasificar, sin ensuciar la vista. Junto con ella se vigila el **Fondo Nacional de Gestión
del Riesgo de Desastres (FNGRD, NIT 900.978.341)**: es una entidad distinta, pero su ordenador
del gasto es el director de la UNGRD y es el vehículo por el que se ejecuta buena parte del
gasto de emergencia, contratando bajo su propio NIT. Vigilar solo 900478966 dejaría esa
contratación por fuera. Lo que de ellas se relacione con el sismo **sí suma en los
indicadores**, porque son las entidades que coordinan y financian la respuesta nacional al
desastre del Valle; su contratación ordinaria, en cambio, no se muestra.

## Descentralizadas: por qué no basta el barrido por departamento

El Parágrafo Cuarto del Decreto 0964 obliga a las descentralizadas a declarar **su propia**
urgencia manifiesta: contratan con NIT propio, no con el de su matriz. El barrido por
`departamento = 'Valle del Cauca'` las capturaba casi todas, pero se descubrió un hueco al
censarlas contra la API el 15 de agosto de 2026:

> **Hay entidades del Valle cuyo campo `departamento` dice `No Definido`.** Y su campo
> `ciudad` también. No hay ningún campo geográfico que las delate; lo único que las identifica
> es el NIT. El barrido territorial no las ve.

Entre ellas, tres **hospitales departamentales** —Roldanillo, Zarzal y el Centenario de
Sevilla— y varios hospitales municipales. Justo el tipo de entidad que más contrata tras un
sismo. Por eso `config.json` trae tres listas de NIT (`descentralizadas_cali`,
`descentralizadas_valle`, `otras_valle_sin_departamento`) que se barren por NIT propio, además
del barrido territorial. Todos esos NIT se obtuvieron consultando la API; ninguno se supuso.

De estas entidades se muestra **toda** su contratación bajo su propio filtro, igual que la de
Cali y la Gobernación centrales, no solo lo que nombre el sismo.

### Cuidado con las colisiones de NIT

Buscar por prefijo de la raíz de nueve dígitos tiene un riesgo real, no teórico: en SECOP I la
cadena `891900493-2` identifica a la **alcaldía de Caruru (Vaupés)**, mientras `891900493` es
**Cartago (Valle)**. La búsqueda por prefijo se traga las dos. Por eso una coincidencia por NIT
contra estas listas solo se acepta si el registro dice Valle del Cauca o trae el departamento
sin diligenciar; si nombra explícitamente otro departamento, se descarta como colisión. La
guarda **no** se aplica a los NIT centrales: la Casa del Valle figura en Bogotá y sí es de la
Gobernación.

### El NIT se escribe distinto en cada plataforma

Esto no es un detalle menor, es la parte que más fácil hace perder registros:

| Fuente | Columna | Tipo | Cómo se consulta |
|---|---|---|---|
| SECOP II · contratos | `nit_entidad` | **numérica** | Lista de dígitos, con y sin dígito de verificación |
| SECOP II · procesos | `nit_entidad` | texto | Prefijo de la raíz de 9 dígitos |
| SECOP I | `nit_de_la_entidad` | texto | Prefijo de la raíz de 9 dígitos, y también con puntos |

En SECOP I conviven en el mismo dataset `891900764` (sin dígito de verificación) y
`890983664-7` (con él). Y en contratos electrónicos de SECOP II la columna es numérica:
compararla contra `'900478966-6'` **no devuelve cero filas, aborta la consulta entera** con un
error de tipo y se pierde el barrido completo. Por eso el colector genera las formas que
corresponden a cada fuente a partir de la raíz de nueve dígitos, calculando el dígito de
verificación cuando hace falta. En `config.json` basta con listar la raíz.

## Cómo se clasifica cada registro

Dos ejes independientes, para no perder nada y a la vez poder filtrar el ruido.

**Grupo** (nivel de gobierno, y filtro principal del tablero)

| Grupo | Quién entra |
|---|---|
| `Alcaldía de Cali` | NIT 890399011 y 8903990113 (nivel central) |
| `Descentralizadas de Cali` | EMCALI, Metro Cali, las cuatro redes de salud, Fondo de Vivienda, IPC… |
| `Gobernación del Valle` | NIT 890399029, 8903990291 y 8903990295 (nivel central) |
| `Descentralizadas de la Gobernación` | HUV, INDERVALLE, INFIVALLE, INCIVA, ACUAVALLE, hospitales departamentales… |
| `Otras entidades del Valle` | Municipios del departamento y sus entidades |
| `UNGRD` | NIT 900478966 y 900978341 (FNGRD), en cualquiera de sus formas |
| `Fuera del Valle` | Resto del país. **No** cuenta en los indicadores |

Los cuatro primeros suman en los indicadores; el último se muestra aparte, como referencia.

Para clasificar, en cambio, la UNGRD se trata como entidad no territorial: se le exige que el
objeto aluda al sismo, no basta la justificación de urgencia manifiesta. Así entra lo del
evento y queda fuera su contratación corriente.

**Nivel de relación**

| Nivel | Criterio |
|---|---|
| `Alta` | Cita uno de los decretos; o menciona sismo/terremoto siendo territorial o tratándose de atención de la emergencia; o tiene justificación "Urgencia manifiesta" y es territorial |
| `Media` | Justificación "Urgencia manifiesta" fuera del territorio vigilado; u objeto propio de emergencia (albergue, escombros, ayuda humanitaria, demolición…) en entidad territorial |
| `Otra urgencia` | Urgencia manifiesta de otra región por **otra** emergencia, u otro sismo. No cuenta como relacionado; se conserva como referencia |
| `Contexto` | Contratación ordinaria, sin relación con el sismo |

**La contratación ordinaria solo se muestra para la Alcaldía de Cali y la Gobernación del
Valle**, que son las dos entidades que expidieron los decretos, y solo al elegirla en el
filtro de nivel. No suma en ningún indicador.

La del resto de entidades se sigue descargando y guardando en los CSV, aunque no se liste.
Es lo que permite reclasificar sin volver a pedirle nada a la API si más adelante se ajusta
alguna palabra clave, y es sobre ese universo completo que opera la detección de cambios.

Dentro de Cali y el Valle el criterio es generoso, porque es el territorio del seguimiento.
**Fuera del territorio se exige una señal inequívoca**: que el objeto mencione a Cali o al
Valle junto con una palabra fuerte de emergencia, o que aluda al sismo sin referirse a otro
año. Un contrato de Bogotá declarado bajo urgencia manifiesta por una emergencia distinta
cae en `Otra urgencia`, no en los indicadores.

Cuatro filtros evitan falsos positivos que se detectaron con datos reales:

- **Acto administrativo anterior al sismo.** Una calamidad o una urgencia declarada antes del
  10 de agosto de 2026 es otro evento, aunque caiga en el mismo año y en el mismo territorio.
  Caso real: un municipio del Valle contratando *"en el marco de la calamidad pública decretada
  mediante Decreto Municipal No. 006 del 13 de febrero de 2026"*. Se leen las fechas completas
  citadas en el objeto —en letras (*13 de febrero de 2026*) o en números (*13/02/2026*,
  *2026-02-13*)— y si todas son anteriores al sismo, el registro baja a `Otra urgencia`. Un año
  suelto (*"vigencia fiscal 2026"*) no es una fecha y no cuenta. El filtro **solo degrada**:
  nunca convierte en relacionado algo que no lo era. Y no se aplica si el texto cita uno de los
  decretos vigilados o menciona el sismo, que mandan sobre cualquier fecha.

- **Coincidencia técnica rutinaria.** "Norma sismo resistente" o "microzonificación sísmica"
  sin palabra de emergencia no cuentan como atención del evento.
- **Otro evento.** Si el texto alude a un año distinto ("sismo del 14 de septiembre de 2025")
  se descarta. No basta con exigir "2026": hay objetos que escriben "10 de agosto" sin año.
- **Coincidencia parcial.** Las palabras se buscan como inicio de palabra, no como fragmento;
  de lo contrario "EDAN" coincide dentro de "pu**edan**". Se ancla solo el inicio, para que
  "DAMNIFICAD" siga sirviendo para damnificado y damnificadas.

Todo esto se ajusta en `config.json` sin tocar el código: NIT, departamentos, palabras clave,
frases excluidas, umbrales de alerta.

## Archivos que se generan

```
datos/
  contratos.csv              estado actual, todas las columnas de la API + clasificación
  procesos.csv               idem para procesos
  secop1.csv                 idem para SECOP I
  cambios.csv                log acumulado de modificaciones (adiciones, prórrogas, estado…)
  estado.json                resumen de la última ejecución
  historial/                 snapshot comprimido de cada día
reportes/
  reporte_AAAA-MM-DD.md      reporte diario
REPORTE_ULTIMO.md            copia del reporte más reciente
datos/tablero.json           lo que la pagina carga y pinta
index.html                   estructura de la pagina (16 KB)
tablero.css                  estilos
tablero.js                   render
publicar/                    copia del repositorio publicado en GitHub Pages
```

## El tablero es un archivo autónomo

La página está partida en cuatro archivos: `index.html` (16 KB) con la estructura,
`tablero.css` con los estilos, `tablero.js` con el render, y `datos/tablero.json` con los
datos ya consultados y clasificados por el colector.

**La página solo pinta.** Antes el navegador consultaba la API por su cuenta y volvía a
clasificar todo: eran 477 líneas de JavaScript que repetían lo que ya hace `colector.py`, y
cada regla había que cambiarla en dos idiomas. Se arregló un fallo en Python, se olvidó en
JavaScript, y el tablero publicado llegó a mostrar ceros durante una caída de la fuente. Con
una sola implementación eso no se repite, la página carga en una petición en vez de 24, y
deja de volverse más lenta a medida que crece la ventana.

Está publicado en
**https://jlzmontenegro.github.io/contratacion-urgencia-manifiesta-valle/**

Los datos se actualizan y publican solos cada día. `publicar.bat` sirve únicamente para
subir cambios de código.

## Qué pasa cuando la fuente se cae

Ocurrió el 15 de agosto de 2026: la plataforma Socrata que aloja datos.gov.co se cayó
entera —no era un límite de peticiones nuestro; los portales de otros países también
respondían 503—. El colector distingue **"no hay nada que traer"** de **"no se pudo traer
nada"**: si fallan todos los barridos de una fuente, aborta con código 2 y **no toca el
tablero ni el reporte**. Sin eso habría confundido el vacío con ausencia de contratación y
habría reescrito el respaldo sin conexión en blanco.

En ese caso la corrida sale en rojo, no se publica nada, y el sitio sigue mostrando la
última corrida completa. Al día siguiente reintenta solo.

## Alertas que levanta

- Contratos por encima de $500 millones (umbral configurable).
- Un mismo contratista con 3 o más contratos relacionados.
- Contratos de emergencia con fecha de firma anterior al sismo.
- Contratos de relación alta sin proceso publicado en el dataset de procesos.
- Contratos relacionados con valor en cero.

## Advertencias sobre la fuente

- **SECOP II publica con aproximadamente un día de rezago.** Un contrato firmado hoy suele
  aparecer mañana. Por eso la ventana se reconsulta completa en cada ejecución.
- **En SECOP I el rezago es mayor e irregular**, y la fecha de cargue a veces es anterior a la
  de firma. No sirve para ordenar cronológicamente; sirve para no perder registros.
- **Los registros se corrigen después de publicados.** Valor, plazo, estado y liquidación
  cambian. `cambios.csv` conserva la traza de cada modificación: es el insumo para el
  control fiscal previsto en el artículo 43 de la Ley 80 de 1993 y el 66 de la Ley 1523 de 2012.
- **La contratación por urgencia manifiesta no siempre se marca como tal.** Algunas entidades
  la registran como contratación directa con otra justificación. Por eso el barrido por
  palabras clave del objeto es tan importante como el filtro por modalidad.
- **El campo `descripcion_del_proceso` viene recortado cerca de los 300 caracteres.** El
  objeto completo está en `objeto_del_contrato`. Se consultan y se muestran ambos, tomando el
  más largo; buscar solo en el campo recortado hace perder contratos cuya palabra clave
  aparece al final del objeto.
- **Los procesos de contratación no tienen fechas de inicio y fin**, solo duración y unidad.
  En los contratos, cuando no hay fecha de inicio publicada se usa la de firma como referencia.
- La API anónima tiene límite de peticiones. Si aparecen errores intermitentes, registre un
  app token gratuito en datos.gov.co y póngalo en `config.json` o en la variable de entorno
  `SOCRATA_APP_TOKEN`.

## Requisitos

Python 3 con `requests` y `pandas` (ya instalados en este equipo). El tablero no necesita
Python: consulta la API directamente desde el navegador.
