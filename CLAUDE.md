# Monitor de contratación · sismo del 10 de agosto de 2026

Seguimiento de la contratación pública relacionada con el sismo de Cali y el Valle del Cauca.
Vigilancia **del 10-ago-2026 hasta al menos feb-2027**. Publicado en
<https://jlzmontenegro.github.io/contratacion-urgencia-manifiesta-valle/>

`LEEME.md` es la documentación completa. Esto es lo que hay que saber **antes de tocar nada**.

## Cómo está armado

```
colector.py            consulta, clasifica y escribe. La única implementación de las reglas.
config.json            NIT, palabras clave, umbrales. Se ajusta sin tocar código.
verificar_cobertura.py auditoría independiente. No importa colector.py, a propósito.
index.html             estructura       ┐
tablero.css            estilos          ├ la página SOLO pinta
tablero.js             render           ┘
datos/tablero.json     lo que la página carga
datos/*.csv            estado y trazas; los mantiene GitHub Actions
```

**GitHub Actions corre el colector cada 12 horas, 8:30 y 20:30 (Colombia)**, audita y
publica. El runner lleva `TZ: America/Bogota`: sin eso la corrida de la noche se archivaba
con la fecha del dia siguiente y el sello de la pagina salia cinco horas adelantado.
`publicar.bat` sube **solo código**; los datos son de Actions. Los flujos de
`.github/workflows/` también se editan en esta carpeta y `publicar.bat` los copia: dentro de
`publicar\` no sobreviven, porque ese script hace `git reset --hard` antes de copiar.

## Reglas que no se rompen

**La página no vuelve a clasificar.** Hubo 477 líneas de JavaScript que repetían el colector.
Se arregló un fallo en Python, se olvidó en JavaScript, y el sitio mostró ceros durante una
caída de la fuente. Si algo hay que clasificar, va en `colector.py` y viaja en el JSON.

**`llenarFiltroEntidades()` llena el desplegable de entidad, y el nombre es deliberado:** se
llamaba `pintarEntidades` y en la unificación se borró creyendo que pintaba una de las secciones
que se estaban eliminando. El filtro quedó con una sola opción. Lista las 119 entidades
**alcanzables por algún filtro**, no las 341 del padrón: 27 no han contratado nada y elegirlas
daría siempre tabla vacía.

**No toda entidad del desplegable está vigilada.** 83 entradas del padrón son de otras regiones
—Pasto, Honda, el Meta— y aparecen porque un barrido encontró contratación suya con vocabulario
de urgencia. Estar en el padrón no basta para llamarlas vigiladas; la prueba es no ser del grupo
`Fuera del Valle`.

**Ninguna lista se recorta en silencio.** La portada listaba 5 novedades de 28 sin decir que
faltaban 23: una lista recortada sin avisar se lee como si fueran todas. Ahora cierra con "y N
operaciones más en la tabla". En pantalla estrecha muestra 3 en vez de 5 —la portada dejaba la
tabla a casi cuatro pantallas de distancia— y el aviso se ajusta solo.

**Un cero tiene que decir por qué.** En este tablero un cero se lee como "no hay contratación
del sismo", que es una afirmación fuerte. El mensaje de tabla vacía se redacta según el filtro
activo: no da lo mismo "esa entidad está vigilada y no ha publicado nada" que "ese dato no
viaja en el archivo".

**Vacío nunca es lo mismo que fallido.** Si todos los barridos de una fuente fallan, el
colector aborta con código 2 sin tocar nada. Si el navegador no puede cargar el JSON, lo dice.
Un cero en este tablero se lee como "no hay contratación del sismo": no puede aparecer por un
fallo técnico.

**Nunca mostrar un conteo parcial como si fuera el total.** En el JSON viaja alrededor de la
mitad de lo monitoreado: la contratación ordinaria solo se embebe para los grupos de
`GRUPOS_ORDINARIA` (Cali, la Gobernación, sus descentralizadas y la UNGRD). Cuando el filtro
incluye ordinaria, la página muestra un aviso de que esa cuenta no es el total y remite al
padrón. **`GRUPOS_ORDINARIA` está en `colector.py` y en `tablero.js`: si se desincronizan,
los registros llegan pero `listable()` los descarta y el filtro da cero sin explicación.**
Así estuvo la UNGRD hasta el 19-ago-2026.

**El patrón de palabra clave se ancla al INICIO de palabra** (`SISMO`), no a cualquier
fragmento —si no, `EDAN` coincidiría dentro de "puEDAN"—. La consecuencia es que **`SISMO` no
coincide con `SISMICO`**: "evento sísmico", que es como lo escribe media Colombia, no contaba
como nombrar el sismo. Se añadió `SISMIC` el 20-ago-2026 y rescató 11 registros, ninguno falso.
Al añadir una palabra, comprobar si necesita su propia raíz.

**Las palabras que nombran el evento están en `palabras_del_evento` de `config.json`**, aparte de
`palabras_clave_fuertes`. Una palabra tiene que estar en **las dos** para que cuente como "nombra
el sismo": la primera la detecta, la segunda decide que apunta al evento y no a cualquier
emergencia. Estuvo escrita a mano en `colector.py` y añadirla solo a la configuración no hacía
nada, en silencio.

**Ningún NIT se inventa.** Todos los de `config.json` se obtuvieron consultando la API.

**Y no se reconstruyen con la fórmula del dígito de verificación.** SECOP publica el mismo NIT
con dígitos que no son el matemático: la Gobernación convive como `890399029`, `8903990291` y
`8903990295`. `verificar_cobertura.py` los reconstruía y solo acertaba dos, así que contaba 951
donde el colector tenía 984 y **bloqueaba la publicación con una discrepancia inexistente**. Pasó
el 20-ago-2026, cuando la variante `...1` dejó de estar en cero. La auditoría usa ahora las
variantes de `config.json`, que es de donde bebe el colector.

**Las revisiones humanas están en `revisiones.csv`, y son una ENTRADA.** El colector reclasifica
todo en cada corrida: una decisión guardada en la salida duraría doce horas. Se edita en
github.com y un `push` sobre ese archivo dispara el flujo, así que la decisión llega a todos los
lectores en minutos. **`publicar.bat` no lo copia** —la copia local está vieja y pisaría lo
revisado desde el navegador—, igual que pasa con `datos\`.

**Una decisión humana nunca parece una del clasificador.** La fila lleva su distintivo con quién
y cuándo, el motivo conserva el criterio automático debajo, y lo revisado **viaja siempre** al
JSON aunque se haya descartado a ordinaria de un municipio: si no, la decisión desaparece de la
vista y no hay forma de comprobarla ni de deshacerla. Para deshacer se borra la línea.

**Lo del día se cuenta por día, no por corrida.** Hay dos recolecciones diarias y la portada
titula *"Novedades del DD/MM"* listando por nombre todo lo detectado en la fecha. Los totales
que la acompañan salen de `nuevos_del_dia()` y `cambios_del_dia()`, que leen las bitácoras
acumulativas; si vinieran de una sola corrida, la frase diría "2 registros nuevos" encima de
una lista de cinco.

**Código y datos van juntos si se toca el formato del JSON.** La página lee `operacion` de
`tablero.json`; si se publica el código sin recolectar, el archivo viejo no trae la llave, cada
registro se vuelve su propia operación y los duplicados reaparecen hasta la siguiente corrida.
Publicar y **enseguida** lanzar *Run workflow*. GitHub Pages tarda unos minutos más en servir el
JSON nuevo: hasta que lo haga se ve el efecto, y no es un fallo del código.

**La auditoria que vale es la de Actions.** Ahi es un candado: corre el colector, audita lo que
acaba de recolectar y si falla no publica. Compara API-simple / API-amplio / CSV por entidad y
fuente.

**Correrla en local antes de publicar ya no sirve** (decidido el 19-ago-2026). `publicar.bat`
sube solo codigo, y `verificar_cobertura.py` compara la API contra los `datos/*.csv` de esta
carpeta, que estan viejos porque los datos los mantiene Actions: marcaria como faltante todo lo
publicado desde la ultima vez que alguien corrio el colector aqui. Ademas no importa
`colector.py` a proposito, asi que tampoco prueba los cambios al colector. Para eso esta
`py -3 colector.py --sin-red` sobre una copia de la carpeta.

## Trampas de la fuente, ya pagadas

**El NIT se escribe distinto en cada dataset.** En contratos de SECOP II `nit_entidad` es
columna **numérica**: compararla contra `'900478966-6'` **aborta la consulta**, no devuelve
vacío. En SECOP I es texto y conviven `891900764` y `890983664-7`. De ahí `clausula_nit()`.

**Los NIT colisionan.** En SECOP I la cadena `891900493-2` es Caruru (Vaupés) y `891900493`
es Cartago (Valle). Por eso una coincidencia por NIT contra las listas de descentralizadas
solo vale si el departamento es del Valle o viene sin diligenciar.

**Hay entidades del Valle con `departamento` y `ciudad` en "No Definido"** —entre ellas tres
hospitales departamentales—. Ningún campo geográfico las delata: solo el NIT. De ahí las tres
listas de `config.json`.

**SoQL compara subcadenas, no palabras.** `like '%CALI%'` encuentra CALIDAD. El barrido usa
`nombres_territorio_barrido` (nombres largos); el clasificador usa la lista larga porque
compara por inicio de palabra.

**La fuente publica el mismo proceso repetido.** Contar con `count(1)` en vez de
`count(distinct id)` da diferencias que no son pérdida de datos.

**SECOP I no separa proceso y contrato.** El tipo se decide por `estado_del_proceso`; no sirve
`numero_de_contrato`, que viene lleno incluso en procesos solo convocados.

**`entidad_centralizada` y `orden` son autodeclarados y poco fiables**: marcan "Descentralizada"
a la Gobernación y "Nacional" a la CVC. No basar nada en ellos.

**En bash, `python x.py | tee log` devuelve el código de `tee`.** Sin `set -o pipefail` una
auditoría fallida pasa por buena.

## Decisiones del usuario, no cambiar sin preguntar

- **Solo del 10-ago-2026 en adelante.** Nada de comparar contra periodos anteriores.
- **Solo se muestra lo relacionado con el sismo.** La contratación ordinaria se descarga y se
  guarda, pero fuera de la vista; la excepción es Cali, la Gobernación y sus descentralizadas,
  visibles bajo su propio filtro.
- **El ruido del nivel Media se tolera**: prefiere que sobre por revisar. No proponer volver
  a recortarlo salvo que lo pida.
- **El objeto se muestra completo en la tabla, sin truncar.** Se recortó a tres líneas durante
  el rediseño del 19-ago-2026 para ganar densidad y el usuario lo revirtió: es el texto por el
  que se juzga si una contratación tiene que ver con el sismo, y recortarlo obliga a abrir SECOP
  para saberlo. Cuesta una pantalla más en móvil y está bien pagado.
- **El foco se mantiene en Cali y el Valle, pero lo de fuera queda a la vista** (21-ago-2026).
  Los indicadores siguen contando solo el Valle; la contratación de otras regiones que nombra el
  sismo se muestra al pie del desglose, separada por un filete y rotulada *"no suma en las cifras
  de arriba"*, desglosada por departamento. Al 21-ago son 32 operaciones por $3.247 millones en
  Caldas, Risaralda, Quindío, Antioquia y Chocó: un tercio de lo del Valle, y esconderlo tras un
  filtro lo hacía invisible.
- Publicar solo cuando lo pida.

## Cómo está la página

**Una sola vista.** Hubo tres pestañas —sismo, ordinaria, padrón— y tres bloques aparte
—SECOP I, UNGRD, resto del país—, cada uno con su propio juego de filtros: el mismo concepto
"territorio" salía tres veces con 10, 7 y 9 opciones distintas, y cambiar de pestaña cambiaba
lo que se podía preguntar. Ahora es **una tabla de operaciones con un solo juego de filtros**,
y cada uno lleva etiqueta visible que dice qué hace. Las secciones son estados de filtro.

**El padrón sigue siendo un bloque propio, al pie**, y no puede dejar de serlo: 27 de las 341
entidades vigiladas no han contratado nada y por tanto no tienen ninguna operación. En una
tabla de operaciones desaparecerían, y el padrón existe justamente para probar que se las
vigila, incluido su silencio.

Arriba, común a todas: una portada con resumen redactado automáticamente, cuatro cifras y un
**semáforo de procedencia** que dice de qué recolección son los datos y hace cuánto (en ámbar
si pasan de 48 horas). Debajo, un desplegable *"¿Cómo se lee este tablero?"* con glosario.

Orden, de lo que exige acción a lo que da contexto: **portada → alertas → cifras → tabla de
operaciones → (plegados: filtros, detalle por nivel, gráficos, leyenda, padrón,
modificaciones)**.

**La tabla del sismo lista OPERACIONES, no registros.** Un proceso y el contrato que salió de él
son el mismo hecho en dos momentos; la fuente los publica en datasets distintos y el tablero los
mostraba dos veces, con el mismo valor. `emparejar_operaciones()` les pone la misma clave
`operacion` y la página los junta en una fila. **La llave no es la obvia:** en contratos
`proceso_de_compra` trae un `CO1.BDOS.*` que cruza contra `id_del_portafolio` de procesos, no
contra `id_del_proceso`. El cruce obvio da **cero** coincidencias, fácil de confundir con "no hay
relación". Enlaza el 77% de los contratos; el resto se muestra como operación suelta y la fila
avisa "sin proceso publicado".

**Se agrupa primero y se filtra después.** `operacionesFiltradas()` arma la operación con todos
sus registros y la conserva si alguno pasa el filtro. Al revés —filtrar y luego agrupar— buscar
por el número del proceso devolvía la operación sin su contrato y la fila anunciaba "aún sin
contratar" algo ya firmado.

**Todo lo que se cuenta en pantalla se cuenta en operaciones.** El desglose por nivel de
gobierno contaba registros y sumaba 169 frente a las 98 de la portada; y rotulaba sus 85
procesos como "aún sin contrato" cuando 71 ya lo tenían. Al cambiar la unidad en un sitio hay
que revisar los demás: la portada, las tarjetas y el conteo de la tabla deben cuadrar entre sí.
El desglose lleva una red: si aparece un grupo sin tarjeta, añade una de *Otros grupos* en vez
de callar. Hizo falta el 20-ago-2026, cuando `Nacional para el Valle` dejó de estar en cero y
el desglose sumó 101 frente a 102.

**En la serie por día, una operación cuenta una sola vez**, en su primera fecha (`primeraFecha`):
la del contrato es la firma y la del proceso la publicación, así que la que se publicó el 14 y se
firmó el 17 aparecía en los dos días. **Los días sin contratación salen en cero, no desaparecen**
—antes se tomaban las últimas N fechas *con datos* y un día en blanco se comprimía en silencio—,
y la serie termina en el último día con datos y no en hoy: SECOP publica con un día de rezago y
el último tramo saldría siempre en cero por el rezago, no por falta de contratación.

**Nunca se suma precio base con valor firmado.** Son la misma plata en dos momentos. La operación
muestra el valor firmado si hay contrato y el precio base si no, siempre rotulado.

**Lo que no exige acción va plegado**: gráficos y leyenda. Los filtros y el detalle por nivel
de gobierno se abren de entrada, a petición del usuario (21-ago-2026): prefiere ver de una qué
se puede preguntar y cómo se reparte. Cuesta pantalla en móvil y está asumido.
Con el panel de filtros cerrado su título dice cuáles están activos: un tablero filtrado en
silencio miente.

**Las tablas van de a 20 filas con paginación, ordenadas de mayor a menor valor.** Al cambiar
un filtro se vuelve a la página 1.

**Cada fila muestra el número de referencia** (`4182.010.32.1.653-2026`), que es por el que
pregunta quien llega desde el buscador de SECOP; el id interno `CO1.REQ.*` no aparece en
ninguna pantalla pública. El buscador de la página encuentra por los dos. Sale de
`referencia_del_contrato` / `referencia_del_proceso` / `numero_de_proceso` según la fuente
—no de `numero_de_contrato`, que viene lleno también en procesos solo convocados—. En
procesos la fuente le agrega la fase entre paréntesis al republicar; se conserva tal cual
porque el número va al principio.

**Nada de jerga del clasificador en pantalla.** `Alta` se muestra como *"Del sismo"*, `Media`
como *"Por revisar"*, `Otra urgencia` como *"Otra emergencia"* y `Contexto` como *"Ordinaria"*,
cada una con su explicación completa en la leyenda y en el título emergente. Los nombres
internos siguen vivos en los datos y en `config.json`; solo no se muestran.

## Cómo probar sin navegador

El panel del navegador de este entorno **no abre `file://` ni `localhost`**. La forma de
probar el tablero es cargar `tablero.js` en Node con un DOM mínimo simulado y un `fetch` que
sirva `datos/tablero.json`. Ojo con dos trampas del arnés: `querySelector` debe devolver un
nodo distinto por selector, y hay que fijar a mano los valores por defecto de los `<select>`
(`f-grupo="territorial"`, `f-nivel="rel"`), o los filtros se comportan distinto que en el
navegador y los conteos salen en cero.

Para verlo de verdad: `py -3 -m http.server 8765` y abrir <http://127.0.0.1:8765/>.

La portada **abre por lo que cambió**, no por el acumulado: cuánta contratación nueva del
sismo apareció en la recolección del día, cuántos registros en total y cuántas
modificaciones, con los relacionados listados por nombre y valor. El acumulado va después.

## Estado al 19 de agosto de 2026

El sistema **lleva cuatro días corriendo solo**: las corridas programadas del 16, 17, 18 y 19
en verde, sin intervención. El candado diario funciona.

Cifras del momento: **62 contratos y 85 procesos** relacionados en Cali y el Valle, por
**$1.973 millones**, 23 por urgencia manifiesta.

El primero grande de Cali llegó el **17 de agosto**: la UAESP publicó por urgencia manifiesta
el cargue y transporte de residuos de construcción y demolición, **$3.759.980.000**, citando
"los hechos acaecidos el 10 de agosto de 2026". Aún sin contratista.

**Bugalagrande y Andalucía** contratan demolición de viviendas afectadas y materiales de
reparación, nombrando el evento de forma explícita.

## Falsos positivos conocidos, ya informados al usuario

Decidió **tolerarlos** para no perder cobertura. No proponer quitarlos salvo que lo pida:

- **`DESASTRE`** solo atrapa "Gestión del Riesgo de **Desastres**", el nombre de la
  dependencia. Es borrar una línea de `config.json`.
- **`MERCADO`** atrapa "ingeniero de **mercados**" de la Secretaría de Infraestructura. Se
  corrige añadiendo la frase a `frases_neutralizadas`.
- **`GESTION DEL RIESGO`** marca toda la nómina de esas secretarías.

## Al escribir código

Comentarios en español, sin tildes en `colector.py` (evita problemas de consola en Windows).
Explican **por qué**, no qué: casi todos documentan una trampa real de la fuente. Los mensajes
de commit llevan el razonamiento completo; `git log` es la memoria del proyecto.
