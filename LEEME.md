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

**Ver los datos:** abra `tablero.html` con doble clic. Consulta la API en vivo al cargar
y tiene el botón **Actualizar datos** para volver a consultarla en cualquier momento.

**Actualizar el histórico, el reporte y el log de cambios:** doble clic en `actualizar.bat`
(o `py -3 colector.py` desde la consola).

**Dejarlo corriendo solo:** doble clic en `registrar_tarea_diaria.bat`. Registra una tarea de
Windows que ejecuta la actualización todos los días a las 8:30 a.m. Para otra hora:
`registrar_tarea_diaria.bat 19:00`. Para eliminarla:
`schtasks /delete /tn "UrgenciaManifiesta_Sismo2026" /f`.

---

## Qué consulta

Datos abiertos de SECOP II en datos.gov.co:

| Fuente | Dataset | Campo de fecha | Identificador |
|---|---|---|---|
| Contratos electrónicos | `jbjy-vk9h` | `fecha_de_firma` | `id_contrato` |
| Procesos de contratación | `p6dx-8zbt` | `fecha_de_publicacion_del` | `id_del_proceso` |

Sobre cada fuente se corren cuatro barridos que luego se deduplican por identificador:

| Barrido | Qué captura | Por qué |
|---|---|---|
| `nit` | Los 5 NIT de Cali central y Gobernación del Valle | Entidades directamente cobijadas por los decretos |
| `departamento` | Toda entidad con departamento *Valle del Cauca* | Descentralizadas (EMCALI, Metro Cali, ESE) y municipios afectados. El Parágrafo Cuarto del Decreto 0964 obliga a las descentralizadas a declarar **su propia** urgencia manifiesta, con NIT distinto |
| `nacional_clave` | Todo el país por palabras clave o justificación "Urgencia manifiesta" | Entidades nacionales (UNGRD, ministerios) que contraten para la emergencia |

## Cómo se clasifica cada registro

Dos ejes independientes, para no perder nada y a la vez poder filtrar el ruido.

**Grupo** (nivel de gobierno, y filtro principal del tablero)

| Grupo | Quién entra |
|---|---|
| `Alcaldía de Cali` | NIT 890399011 y 8903990113 |
| `Gobernación del Valle` | NIT 890399029, 8903990291 y 8903990295 |
| `Otras entidades del Valle` | Municipios del departamento y descentralizadas (EMCALI, Metro Cali, ESE…) |
| `Fuera del Valle` | Resto del país. No cuenta en los indicadores |

Los tres primeros forman el ámbito `Territorial`; el último, el ámbito `Nacional`.

**Nivel de relación**

| Nivel | Criterio |
|---|---|
| `Alta` | Cita uno de los decretos; o menciona sismo/terremoto siendo territorial o tratándose de atención de la emergencia; o tiene justificación "Urgencia manifiesta" y es territorial |
| `Media` | Justificación "Urgencia manifiesta" fuera del territorio vigilado; u objeto propio de emergencia (albergue, escombros, ayuda humanitaria, demolición…) en entidad territorial |
| `Otra urgencia` | Urgencia manifiesta de otra región por **otra** emergencia, u otro sismo. No cuenta como relacionado; se conserva como referencia |
| `Contexto` | Contratación ordinaria de las entidades vigiladas. **No se muestra** en el tablero ni en el reporte |

La contratación ordinaria se sigue descargando y guardando en los CSV, aunque no se muestre.
Es lo que permite reclasificar sin volver a pedirle nada a la API si más adelante se ajusta
alguna palabra clave, y es sobre ese universo completo que opera la detección de cambios.

Dentro de Cali y el Valle el criterio es generoso, porque es el territorio del seguimiento.
**Fuera del territorio se exige una señal inequívoca**: que el objeto mencione a Cali o al
Valle junto con una palabra fuerte de emergencia, o que aluda al sismo sin referirse a otro
año. Un contrato de Bogotá declarado bajo urgencia manifiesta por una emergencia distinta
cae en `Otra urgencia`, no en los indicadores.

Tres filtros evitan falsos positivos que se detectaron con datos reales:

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
  cambios.csv                log acumulado de modificaciones (adiciones, prórrogas, estado…)
  estado.json                resumen de la última ejecución
  historial/                 snapshot comprimido de cada día
reportes/
  reporte_AAAA-MM-DD.md      reporte diario
REPORTE_ULTIMO.md            copia del reporte más reciente
tablero.html                 el colector le incrusta el historial en cada ejecución
publicar/                    copia del repositorio publicado en GitHub Pages
```

## El tablero es un archivo autónomo

`tablero.html` no depende de ningún otro archivo ni de librerías externas: el historial va
incrustado dentro del propio HTML y los datos se consultan directamente contra datos.gov.co
desde el navegador. Se puede enviar por correo, copiar a una USB o publicar en cualquier
servidor, y quien lo reciba ve todo y puede pulsar **Actualizar datos**.

Está publicado en
**https://jlzmontenegro.github.io/contratacion-urgencia-manifiesta-valle/**

Para actualizar los datos y republicar en un solo paso: `publicar.bat`.
Para republicar sin volver a consultar la API: `publicar.bat solo`.

## Alertas que levanta

- Contratos por encima de $500 millones (umbral configurable).
- Un mismo contratista con 3 o más contratos relacionados.
- Contratos de emergencia con fecha de firma anterior al sismo.
- Contratos de relación alta sin proceso publicado en el dataset de procesos.
- Contratos relacionados con valor en cero.

## Advertencias sobre la fuente

- **SECOP II publica con aproximadamente un día de rezago.** Un contrato firmado hoy suele
  aparecer mañana. Por eso la ventana se reconsulta completa en cada ejecución.
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
