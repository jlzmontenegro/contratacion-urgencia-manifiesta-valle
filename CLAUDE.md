# Monitor de contratación · sismo del 10 de agosto de 2026

Seguimiento de la contratación pública relacionada con el sismo de Cali y el Valle del Cauca.
Vigilancia **del 10-ago-2026 hasta al menos feb-2027**. Publicado en
<https://jlzmontenegro.github.io/contratacion-urgencia-manifiesta-valle/>

`LEEME.md` es la documentación completa. Esto es lo que hay que saber **antes de tocar nada**.

**Si llegas nuevo a este proyecto:** el sistema corre solo en la nube y no necesita nada de
nadie. Lo único que pide intervención humana es revisar lo que queda en *Por revisar*, y eso
se hace editando `revisiones.csv` en github.com. Todo lo demás —recolectar, clasificar,
auditar, publicar— ya está automatizado y verificado.

## Cómo está armado

```
colector.py            consulta, clasifica y escribe. La única implementación de las reglas.
config.json            NIT, palabras clave, umbrales. Se ajusta sin tocar código.
revisiones.csv         decisiones humanas. ENTRADA al colector; se edita en github.com
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

**El filtro de entidad admite VARIAS a la vez** (24-ago-2026). Es un `<details>` con casillas,
no un `<select multiple>`: el nativo obliga a Ctrl+clic y en el teléfono es inmanejable. El
estado vive en `ENTIDADES_SEL`, un `Set`; vacío significa *todas*. **El resumen cerrado dice
cuántas hay elegidas** —un filtro puesto que no se ve miente igual que un tablero filtrado en
silencio— y **marcar no repinta la lista**, solo el resumen y la tabla: si repintara, las
casillas saltarían bajo el cursor al elegir la segunda. Se reordena con las marcadas arriba
únicamente al buscar o al recargar datos. Una entidad que deje de venir en el archivo **se
descarta sola** de la selección: dejarla puesta daría tabla vacía sin nada que lo explicara.

**El panel de entidades se ancla al BLOQUE de filtros, no a su columna, y el bloque no
recorta.** Dos trampas seguidas, las dos invisibles en el código: `.plegable` lleva
`overflow:hidden` por las esquinas redondeadas y **cortaba el panel en seco** —se veía el
buscador y la lista quedaba fuera de la caja—; y anclado a su columna, de unos 300px, los
nombres de entidad (hay uno de 118 caracteres) se partían en cuatro renglones y solo cabían
cinco entidades. Anclado al bloque entero son cuatro columnas y 32 entidades a la vista.
**Medir la geometría del panel no cazó el recorte**: el rectángulo era correcto, lo cortaba un
ancestro. Para eso hay que mirar quién tiene `overflow` o probar `elementFromPoint`.

**Agrupar por entidad es ORDENAR, no pintar distinto** (24-ago-2026). `operacionesDeLaVista()`
devuelve las operaciones de cada entidad contiguas y las entidades por lo que suman; la tabla
solo intercala una banda cuando cambia el nombre. Hecho así, la paginación, el informe impreso
y las tres descargas heredan el mismo orden sin tocar nada más. **La banda avisa cuando el grupo
viene partido por la paginación** —"viene de la página anterior"—: sin eso, media docena de filas
quedan bajo un encabezado cuya cuenta no cuadra con lo que se ve.

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

**Prestación de servicios con PERSONA NATURAL no es atención del sismo** (decisión del usuario,
21-ago-2026). Son las nóminas de las secretarías de gestión del riesgo, que enganchan por el
nombre de la dependencia. La regla vive en `clasificar()` y **solo degrada `Media`**: si el objeto
nombra el sismo (`Alta`) o describe una acción concreta —entregar kits, retirar escombros, atender
damnificados: lista `objetos_concretos_emergencia`— se respeta. Movió 35 registros.

**La regla solo puede evaluarse en el CONTRATO**, porque en procesos todavía no hay proveedor, y
se propaga a su proceso en `emparejar_operaciones()`. Un proceso suelto sin contrato queda fuera
de su alcance y hay que revisarlo a mano; así pasó con `CVC CD 1242 2026`.

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

**El mapa `novedades` del JSON lleva fecha Y hora** (`2026-08-12 20:06:54`) desde el
22-ago-2026, porque las opciones *Cuándo apareció → últimas 24 / 48 / 72 horas* son ventanas
rodantes y hay dos recolecciones diarias: recortando a la fecha, "24 horas" se degradaba a "lo
de hoy" y dejaba fuera la corrida de las 20:30. `tablero.js` admite las dos formas —sin hora se toma
medianoche—, así que un JSON viejo no rompe nada; solo que hasta la siguiente recolección esa
opción se comporta como "hoy" (y las de 48 y 72, como "hoy y ayer" y "los tres días").
**El sufijo `h` del valor es lo que distingue una ventana de horas de una de días** en
`filtraRegistro()`: `24h` rueda, `7` cuenta días. **Las ventanas de días siguen contando por día calendario**
(`diasDesde` recorta a la fecha a propósito): si contaran horas rodantes, "últimos 7 días"
incluiría detecciones de hace ocho días por la tarde.

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
- **La Cámara de Comercio de Cali está en `descentralizadas_cali` sin serlo** (22-ago-2026).
  Es una corporación privada con funciones públicas, no una descentralizada del Distrito. Se
  metió ahí a sabiendas: ese grupo está en `GRUPOS_ORDINARIA`, y era la única forma de que su
  contratación **ordinaria** se viera sin inventar un grupo nuevo. Se le advirtió al usuario
  que el desglose por nivel de gobierno la contaría como distrital y decidió asumirlo. Entró
  con 14 registros por $1.324 millones, ninguno del sismo. Si algún día se separa, su sitio
  natural es un grupo propio, como el que ya tiene la UNGRD siendo una sola entidad.
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

**Las tres descargas salen de `operacionesDeLaVista()`**, que es exactamente lo que la tabla
está mostrando. Un archivo que sale del tablero y no cuadra con la pantalla es peor que no
tenerlo: nadie sabe cuál de los dos creer. Al unificarlo apareció un fallo viejo —**el CSV salía
de `filtrados()`, que ignoraba los filtros de estado y de revisión**: pidiendo "solo abiertas"
el archivo traía también las contratadas, y eso no se veía hasta abrirlo.

**El `.xlsx` se escribe a mano —ZIP con XML dentro— y no con una librería de un CDN.** La página
no depende de nadie: el día que ese CDN no responda es justo el día en que un cero se leería como
"no hay contratación del sismo". Las entradas van sin comprimir (método 0), que ahorra meter un
deflate en el navegador y Excel las abre igual. Lleva tres hojas: *Operaciones* (lo que se ve),
*Registros* (contrato y proceso por separado, para cruzar) y ***Procedencia*, que es obligatoria**:
el archivo viaja solo y sin ella nadie sabe si esas 12 filas son todo lo del sismo o el resultado
de tres filtros puestos aquella tarde. **`escXml()` recorre los caracteres a mano** porque XML no
admite caracteres de control y en los objetos llegan —vienen de pegar texto desde un PDF—: uno
solo hace que Excel declare el archivo ilegible sin decir por qué.

**El PDF es la impresión del navegador con hoja de estilos, no una librería** (decisión del
usuario, 24-ago-2026). Una librería obligaría a recortar el objeto para que la tabla cuadre, y el
objeto es el texto por el que se juzga si una contratación tiene que ver con el sismo. En papel
se imprimen **todas** las filas del filtro, no las 20 de la página: `imprimirInforme()` arma
`#impresion` en el momento y `@media print` oculta `.envoltura` entera. El informe encabeza con
los filtros aplicados y la recolección de la que salen los datos.

**El mapa lo dibuja `mapa.json`, que es CÓDIGO y no dato** (24-ago-2026). Lo genera
`preparar_mapa.py` a mano, una sola vez, con los contornos del Marco Geoestadístico del DANE:
33 departamentos y los 42 municipios del Valle, simplificados con Douglas-Peucker y guardados
ya como trazos SVG. Son 53 KB y **`publicar.bat` lo copia**; si no se copiara, la página pediría
`mapa.json`, recibiría un 404 y la sección saldría con su aviso. Las fronteras no cambian cada
doce horas: bajarlas en cada corrida sería pedirle a un tercero algo que ya tenemos, y con un
servidor de teselas el tablero dejaría de ser autosuficiente.

**El municipio se resuelve en el colector, no en la página**, como todo lo que es clasificar.
Cada registro lleva `municipio` (código DIVIPOLA de cinco dígitos), `municipio_nombre` y
**`municipio_origen`, que dice si lo trae la fuente o si se dedujo**. La deducción mira el
nombre de la entidad cuando `ciudad` viene *No Definido*, y solo dentro del Valle: fuera, el
mismo nombre de municipio se repite en varios departamentos. Rescata los 17 registros de la
Alcaldía de La Victoria, que publica ciudad y departamento sin diligenciar y es de los
municipios con más contratación relacionada del norte del Valle. **El origen viaja hasta la
pantalla a propósito:** el mapa dice cuántas piezas ha colocado por deducción y cuántas no ha
podido situar. Un mapa que se come operaciones en silencio se lee como un censo.

**El mapa pinta el municipio de la ENTIDAD QUE CONTRATA, no dónde se ejecuta**, y el rótulo lo
dice con esas palabras. El campo `ciudad` de SECOP es el domicilio de la entidad: la Cámara de
Comercio de Tuluá compró alimentos para damnificados **de Zarzal** y carpas para un comedor **de
Bolívar**, y las dos operaciones se pintan en Tuluá. Se comprobó contra los 109 registros del
Valle: el objeto coincide con el municipio asignado en 89, no nombra ninguno en 18 y **discrepa
en 2**, que son justo esos. No es lo mismo el municipio que mueve la plata que el que recibe la
ayuda, y el mapa no puede dar a entender lo segundo.

**El objeto es el ÚLTIMO recurso para situar, y solo si nombra un único municipio.** Ahí sí se
entra aunque la fuente traiga ciudad, porque el caso que lo justifica es ese: DICITEC SEM SAS
contrata desde Bogotá —y así lo publica— materiales para reparar Vijes. Con dos o más nombres se
queda sin situar: el objeto de la Cámara de Tuluá nombra Zarzal y Tuluá, y elegir uno sería
inventar. `municipio_origen` distingue los tres caminos (`fuente`, `entidad`, `objeto`) y el mapa
los cuenta por separado en pantalla.

**Los dos mapas respetan TODOS los filtros, y lo que el filtro deja fuera tiene color propio.**
El mapa del país llegó a saltarse el filtro de territorio, para que no saliera en blanco al
arrancar; el precio fue que **el Valle sumaba $14,0 mm en el mapa mientras la tabla listaba
$10,2 mm** del grupo filtrado —dos cifras del mismo sitio en la misma pantalla, que es la regla
que más caro sale—. Lo detectó el usuario, no la revisión. Ahora los departamentos con
contratación que el filtro oculta van en **tierra**, fuera de la rampa, con su propia entrada en
la leyenda y su cuenta en el título emergente: si salieran como los vacíos, sería el cero mudo una
escala más arriba. Al pie va cuántas operaciones quedan fuera.

**Una leyenda POR MAPA.** Los tramos se calculan sobre los datos de cada uno —un municipio y un
departamento no juegan en la misma escala— y con una sola leyenda la del Valle describía los
colores del mapa del país.

**Cada pieza lleva su etiqueta dentro del SVG**, no como capa aparte: así se escala con el mapa
y viaja tal cual al informe impreso y al PNG del Excel. El cuerpo de letra sale de la raíz del
área de la pieza (`a` en `mapa.json`), porque con uno solo el nombre de un municipio pequeño se
derramaba sobre tres vecinos. Van con halo del color del panel —`paint-order:stroke`, que pinta
el borde debajo del relleno de la letra— o el nombre no se lee sobre el tono oscuro de la rampa.
`separarEtiquetas()` resuelve los dos o tres solapes por mapa apartando la de la pieza **menor**,
y luego mete hacia dentro las que se salgan por cualquiera de los cuatro lados: **San Andrés
tiene su centroide en (0.9, 2.8)**, la esquina noroeste, y su rótulo centrado se salía por la
izquierda y por arriba a la vez. Los nombres que no caben llevan `rotulo` corto en `mapa.json`
—San Andrés, Bogotá D.C.—; `nombre` se conserva **porque es la llave con la que el colector
empareja lo que publica SECOP**.

**El informe impreso necesita SUS PROPIAS reglas de relleno.** Las de pantalla cuelgan de
`.lienzo` y dentro de `#impresion` no hay ningún `.lienzo`: los mapas salían **enteros en negro**
—el relleno por defecto de un `<path>`— mientras la leyenda, cuyas reglas no dependen del
contenedor, salía en color. No hay error, simplemente no coincide el selector; se vio en el papel,
no en el código. Y `print-color-adjust:exact`, o el navegador descarta los rellenos al imprimir.

**Los tramos de color son por cuantiles, no lineales.** El RCD de Cali, $3.760 millones en una
sola operación, aplastaría a los demás municipios contra el extremo bajo de cualquier escala
lineal. Y el cero tiene color propio, separado de la rampa: "no ha contratado" no es "ha
contratado poco".

**En el Excel el mapa va como PNG rasterizado en el navegador.** Excel no dibuja SVG. Dos
trampas que cuestan una tarde: dentro de una imagen **no viajan las clases CSS** —hay que
escribir el color en cada trazo— y **un SVG sin ancho ni alto explícitos se rasteriza a cero
píxeles**, porque el `viewBox` solo da proporciones. El dibujo cuelga de la hoja *Territorio* por
una cadena de cuatro piezas (hoja → rels → drawing → media) y **`<drawing>` va después de
`<autoFilter>`**: el esquema fija el orden y con un elemento fuera de sitio Excel declara el
archivo corrupto. Si la rasterización falla, el libro sale igual con sus cifras.

**Nunca se suma precio base con valor firmado.** Son la misma plata en dos momentos. La operación
muestra el valor firmado si hay contrato y el precio base si no, siempre rotulado.

**Lo que no exige acción va plegado**: gráficos y leyenda. Los filtros y el detalle por nivel
de gobierno se abren de entrada, a petición del usuario (21-ago-2026): prefiere ver de una qué
se puede preguntar y cómo se reparte. Cuesta pantalla en móvil y está asumido.
Con el panel de filtros cerrado su título dice cuáles están activos: un tablero filtrado en
silencio miente.

**El padrón se despliega.** Pulsar una entidad muestra los registros que el archivo trae de
ella, con objeto completo, valor, contratista y enlace a SECOP. **El aviso de cuántos se
listan es obligatorio y son tres casos distintos:** no haber contratado nada (0 registros),
haber contratado y que nada viaje en el archivo, y que viaje solo una parte —231 de las 344
entidades con registros traen menos de los que anuncia su contador; Jamundí dice 249 y
viajan 28—. Confundirlos desinforma.

**El padrón se ordena por registros del sismo, no por valor contratado.** Ordenando por
valor, la primera fila era una agencia del Meta con cero registros del sismo y $19,7 mm de
contratación ordinaria. Las que no han contratado nada siguen al final, que es para lo que
existe el padrón.

**El bloque se llama "Padrón de entidades", no "de entidades vigiladas":** 101 de las 397
son de otras regiones y entraron por barrido, no porque se las siga.

**La piel es la misma que la del tablero de contratación logística** (`ContratacionLogisticaCaliYValle`),
para que los dos se lean como del mismo autor: Zilla Slab en titulares y cifras, Public Sans
en el cuerpo, IBM Plex Mono en etiquetas y referencias; verde azulado `#0E5C58` sobre
`#F5F7F6`; esquinas de 3px y filetes finos. Modo oscuro de tres estados.

**Las cifras de titular van en números PROPORCIONALES.** Con `tabular-nums` el "1" de Zilla
Slab ocupa 19,7px midiendo 12,8 y "114" se leía como "1 14". La cifra tabular es para
alinear columnas de una tabla, no para un número grande suelto.

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

## Cómo probar

**El panel del navegador SÍ abre `localhost`** desde `.claude/launch.json` (comprobado el
24-ago-2026; la nota anterior decía lo contrario y ya no vale). `preview_start` levanta
`py -3 -m http.server 8765` y desde ahí se puede leer el DOM y la geometría real que calcula
el navegador, que es la única forma de cazar las trampas de especificidad del CSS. **Capturas de
pantalla no hay**: el panel no compone imagen, así que lo visual se comprueba midiendo
(`getBoundingClientRect`, `getComputedStyle`), no mirando.

Para lógica pura sigue sirviendo cargar `tablero.js` en Node con un DOM mínimo simulado y un
`fetch` que sirva `datos/tablero.json`. Ojo con dos trampas del arnés: `querySelector` debe devolver un
nodo distinto por selector, y hay que fijar a mano los valores por defecto de los `<select>`
(`f-grupo="territorial"`, `f-nivel="rel"`), o los filtros se comportan distinto que en el
navegador y los conteos salen en cero.

Para verlo de verdad: `py -3 -m http.server 8765` y abrir <http://127.0.0.1:8765/>.

La portada **abre por lo que cambió**, no por el acumulado: cuánta contratación nueva del
sismo apareció en la recolección del día, cuántos registros en total y cuántas
modificaciones, con los relacionados listados por nombre y valor. El acumulado va después.

## Estado al 22 de agosto de 2026

Siete días corriendo solo, dos recolecciones diarias. **Las cifras cambian en cada corrida:
lo de abajo es una foto, no una constante.** Para el dato vivo, mirar la página.

**53 operaciones relacionadas en Cali y el Valle por $9.642 millones.** El reparto es el
hallazgo que conviene no olvidar: **los municipios contratan la emergencia**, no las dos
entidades que expidieron los decretos. La Alcaldía de Cali tiene 1 operación —el RCD de la
UAESP, $3.759.980.000 con la Empresa Regional de Aseo de Candelaria— y la Gobernación
ninguna: sus 39 operaciones originales eran prestación de servicios con persona natural.

**Lo más grande después del RCD:** Calima El Darién, 6 contratos por $2.734 millones
—albergues temporales, rehabilitación de vías, demolición de viviendas, aulas temporales,
kits alimentarios y cubiertas escolares—, todos citando "el sismo de magnitud 7,4".

**Fuera del Valle, 32 operaciones por $3.247 millones** que nombran el sismo, en Caldas,
Risaralda, Quindío, Antioquia y Chocó. No suma en los indicadores; se muestra al pie del
desglose.

### Revisión humana: cómo va y qué queda

`revisiones.csv` lleva **97 decisiones**, todas descartes. Quedaban **5 pendientes** el
22-ago, pero ese número sube y baja en cada corrida: **la lista viva está en el filtro
*Revisión humana → Solo las que faltan por revisar***. No hace falta recalcularla a mano.

**El grueso ya no exige trabajo:** la regla de persona natural despacha sola las nóminas.
A la bandeja solo llegan los tres casos que la regla no puede juzgar:

1. **Procesos sin contrato adjudicado** — sin proveedor no se sabe si es persona natural.
2. **Contratos con empresa** que enganchan por vocabulario (El Cerrito, mantenimiento de
   vehículos, $248 M).
3. **Contratos con persona natural protegidos** por `objetos_concretos_emergencia`.

**Patrón útil al revisar:** casi todo lo que llega es apoyo a la gestión en dependencias de
riesgo, y va a ordinaria. Lo que merece lectura es lo que tiene objeto concreto —compra de
elementos de emergencia, alquiler de carpas, obra— porque ahí sí puede haber respuesta real.

### Lo que quedó sin construir

**El conjunto `dmgg-8hin`** trae los archivos del expediente y **cruza limpio**: por
`n_mero_de_contrato` = `id_contrato` para contratos, y por `proceso` = `id_del_portafolio`
para procesos. Medido sobre 30 contratos en duda y sobre el expediente de Yotoco (17
archivos): **ningún nombre de archivo menciona el sismo** — son nombres administrativos
("06. ESTUDIOS PREVIOS.pdf", "14. RESOLUCION DE JUSTIFICACION.pdf"). **No sirve para
clasificar.** Sí serviría como atajo: trae `url_descarga_documento`, así que la fila podría
llevar enlace directo a los estudios previos, que es donde está la respuesta. Con eso, revisar
una duda pasa de abrir SECOP y buscar, a un clic. **Propuesto y no construido.**

## Trampas del entorno, ya pagadas

**El orden al publicar revisiones importa.** `revisiones.csv` se confirma y se empuja
**antes** de correr `publicar.bat`, nunca después: ese script hace `git reset --hard` y
se lleva por delante lo no confirmado. Pasó el 21-ago y se perdieron 38 revisiones.

**Dos corridas seguidas se pisaban al publicar.** Editar `revisiones.csv` dispara una
corrida, y encadenar dos hacía fallar el `git rebase` con "could not apply". Los datos se
regeneran enteros en cada corrida, así que ante conflicto manda la más nueva: el paso de
publicar usa `rebase -X theirs` con tres reintentos.

**La API se pone lentísima a ratos.** El 21-ago un solo barrido de 22 filas tardó
**18 minutos** y GitHub corto la corrida a los 25. No es el código: al reintentar pasó.
Gracias a `PYTHONUNBUFFERED` el registro ahora dice en qué barrido se quedó. **Si una
corrida se atasca, reintentar antes de tocar nada.**

**La especificidad de CSS muerde en silencio.** Tres veces el 20-ago: una regla escrita al
final no se aplicaba porque otra anterior era más específica (`.portada .cifras` contra
`.cifras`, `.portada .cifra .n` contra `.cifra .n`, `.refs .ref` contra `.ref`). No hay
error, simplemente no pasa nada. **Comprobar el resultado en la página, no en el código.**

**`#kpis` era una rejilla.** Al meterle una tabla más un bloque, los colocaba en columnas
paralelas y se solapaban encima de la tabla. Lleva `display:block` explícito.

**Generar código con scripts de Python se come los escapes.** Escribiendo un arreglo quedó
un **byte 0x08 literal** donde debía ir `\b`, y la expresión regular no coincidía nunca.
En el diff se ve idéntico y `node --check` pasa. **Preferir construcciones sin escapes**
—`startsWith` en vez de una regex— y comprobar que no haya bytes de control.

**Pages cachea `index.html`.** Para verificar un despliegue hay que recargar con una cadena
de consulta (`?recarga=...`); si no, se mide la versión anterior y parece que el arreglo
falló.

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
