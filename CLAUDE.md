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
ligero.py              genera ligero.html: un HTML autónomo, solo lo confirmado
correo.py              avisa por correo de lo nuevo. Dos correos, dos públicos.
resumen.py             informe semanal de los lunes, con el mapa dibujado en PNG
documentos.py          enlaza cada fila con los estudios previos de su expediente
datos/tablero.json     lo que la página carga
datos/avisados.csv     de qué ya salió correo. Lo escribe correo.py
datos/*.csv            estado y trazas; los mantiene GitHub Actions
```

**GitHub Actions corre el colector cada 12 horas, 8:30 y 20:30 (Colombia)**, audita, **avisa
por correo** y publica —en ese orden, que importa y está explicado abajo—. El runner lleva
`TZ: America/Bogota`: sin eso la corrida de la noche se archivaba
con la fecha del dia siguiente y el sello de la pagina salia cinco horas adelantado.
`publicar.bat` sube **solo código**; los datos son de Actions. Los flujos de
`.github/workflows/` también se editan en esta carpeta y `publicar.bat` los copia: dentro de
`publicar\` no sobreviven, porque ese script hace `git reset --hard` antes de copiar.

## Reglas que no se rompen

**La misma contratación publicada DOS VECES es UNA operación** (13-sep-2026,
`unificar_publicaciones_repetidas()`). No es un fallo del emparejado: son **dos expedientes
distintos** —otro `CO1.NTC`, otro `CO1.REQ`, otro `CO1.BDOS`— con el mismo número de
referencia, el mismo objeto y el mismo valor. Manizales publicó dos veces sus obras por $2.000
millones y solo una llegó a contrato, así que el tablero contaba dos operaciones y mostraba la
misma contratación como *Contratada* y como *Abierta* a la vez.

**Se unifica en la LLAVE DE OPERACIÓN, no en cada consumidor**, y por eso el conteo, el mapa,
la tabla, las descargas y los dos correos se corrigen solos. Es la misma razón por la que la
página no vuelve a clasificar.

**La llave son las tres cosas a la vez: entidad, referencia normalizada y valor**, y ninguna
sirve sola. Se midió: Manizales tiene **seis contratos de $70.000.000 exactos** con proveedores
distintos —entidad + valor los habría fundido— y **dos contratos distintos que comparten la
referencia `2608131019`**, por $1.000 y por $540 millones —entidad + referencia también—. Se
comparan **todas** las referencias de la operación, no una: el proceso y su contrato suelen
tener números distintos (`4182.010.32.1.653` contra `4182.010.26.1.653`) y elegir uno perdería
la mitad de las coincidencias. Normalizar —quitar puntos, guiones y espacios— es lo que hace
coincidir `2608201039.` con `2608201039`, `CI-001-2026-` con `CI-001-2026` y
`SI-CDPS-161-2026*` con `SI-CDPS-161-2026`.

**Sobre 7.995 operaciones fusiona 48, de las cuales 7 son `Alta`. Las cifras bajan de 382 a
375 operaciones y EL DINERO NO SE MUEVE** —$64.230.331.615 antes y después—, porque en cada
par solo una tenía contrato y la plata nunca se contó dos veces. Los convenios gemelos de Cali
(`…1.4-2026` y `…1.5-2026`) **no se tocan**: tienen referencias distintas y el usuario decidió
el 12-sep mostrarlos los dos.

**Se dice, no se esconde.** Cada registro queda marcado con `repetida` = cuántas
publicaciones, y las tres vistas lo muestran: el tablero grande con *"publicada N veces"*, la
versión ligera con una línea bajo el objeto y el resumen semanal con un botón a la otra
publicación. Es un hecho sobre cómo publica la entidad, y quien verifique se va a encontrar
los dos expedientes.

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

**El filtro de monto va sobre la OPERACIÓN y su barra se reparte por CUANTILES.** Filtrar el
registro partiría la operación —entra el contrato y su proceso no— y la fila acabaría diciendo
"aún sin contratar" sobre algo ya firmado. La escala no puede ser lineal (el 95% de las
operaciones se apelotona en el primer centímetro) ni logarítmica: entre lo listable hay
contratación ordinaria de **$220 mil millones**, un orden de magnitud por encima de todo lo del
sismo, y con ella en el extremo la mitad alta de la barra se queda sin nada que seleccionar. Por
cuantiles, cada tramo tiene aproximadamente las mismas operaciones. **La escala se calcula una vez
por carga**, no con cada filtro: si se recalculara, el tramo elegido pasaría a significar otra
cosa sin que nadie lo tocara. Los extremos son *sin límite*, no un número: en el de abajo entran
las operaciones de valor cero y en el de arriba no puede quedar fuera el RCD por un redondeo.

**Los dos pulgares son dos `<input type=range>` superpuestos** —no existe control nativo de rango
doble— y el truco está en `pointer-events`: el control entero no recibe el ratón y solo lo reciben
los pulgares. Sin eso, el de arriba tapa al de abajo y uno de los dos topes se queda muerto.

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

**La prestación de servicios que se relaciona con el sismo ENTRA TODA, y se puede ocultar sin
descartarla** (13-sep-2026). El usuario lo pidió con estas palabras: *"que se incluyan todos los
que se relacionen con el sismo… que haya un filtro o algo que cuando se quiera no los cuente"*.
**No hizo falta tocar el clasificador**: se midió y la regla de persona natural **no estaba
quitando ni uno** que nombrara el evento. De los 252 registros que baja a `Contexto`, **cero**
mencionan sismo, sismico, terremoto o el 10 de agosto: son nómina de la CVC, del Departamento de
Gestión Jurídica de Cali y de las secretarías de gestión del riesgo, que enganchan por el nombre
de la dependencia y nada más. La regla solo actúa sobre `Media`, así que cualquier objeto que
nombre el evento llega a `Alta` intacto. Medido el 13-sep: de 378 operaciones, **200 son
prestación de servicios**.

Lo que se añadió es el **filtro por tipo de contrato**, con *Sin prestación de servicios* como
primera opción y un *Solo …* por cada tipo que de verdad existe, con su cuenta. La ayuda del
filtro dice la frase que importa: **aquí solo se oculta, no se descarta**.

**El tipo de contrato se unifica en el colector** (`tipo_de_contrato()`), porque las tres fuentes
escriben lo mismo distinto: SECOP II dice *Prestación de servicios*, *Suministros* y *Otro*;
SECOP I dice *Prestación de Servicios* con ese mayúscula, *Suministro* en singular y *Otro Tipo
de Contrato*. Sin unificar, el desplegable daría dos entradas para lo mismo y el lector no sabría
cuál elegir. Lo que no encaja en la lista se rotula `Otro` y no se inventa: ahí caen los valores
que no son un tipo sino un régimen (*Decreto 092 de 2017*).

**La obra pública del territorio tiene red de seguridad** (8-sep-2026). El agujero que las
palabras clave no ven es **la reparación descrita en términos neutros**: *"mantenimiento locativo
de las instalaciones físicas"* no nombra el sismo y es exactamente como se describe el arreglo de
un edificio dañado. Fue el caso del hospital de Roldanillo, que llegó por la palabra «escombro» y
necesitó una persona. Ahora, un contrato **de tipo OBRA** dentro del territorio vigilado que iba a
quedar en `Contexto` sube a `Media` si su objeto nombra estructura o cerramiento
(`palabras_obra_edificacion`). **Solo sube; nunca marca nada como del sismo**: eso lo decide una
persona.

**Se midió antes de escribirla, y luego se afinó con lo que salió.** En el Valle hay 9.443
contratos firmados desde el sismo pero **solo 33 de obra pública**, así que el costo en revisión
es mínimo. La primera lista incluía `ADECUACION`, `REPARACION`, `REHABILITACION` y `EDIFICIO`:
subía **30 registros por corrida** —canchas sintéticas, parques lineales, acueductos rurales,
sedes educativas—, palabras de obra corriente y no de daño. Con la lista afinada sube **5**, de
los cuales dos o tres merecen lectura de verdad. `Alta` no se mueve: 485 antes y después.

**El seguimiento cubre CUATRO actos, no dos** (12-sep-2026). A los decretos de Cali
(`4112.010.20.0963` y `0964`) y de la Gobernación (`1.03.01-1070`) se sumaron los dos
nacionales: **Decreto 1171 del 11-ago-2026**, que declara la *situación de desastre de
carácter nacional* por el sismo en doce departamentos —Antioquia, Caldas, Cauca, Chocó,
Quindío, Cundinamarca, Risaralda, Huila, Valle, Tolima, Putumayo, Norte de Santander— por
doce meses prorrogables y crea la **Subcuenta SISMO 2026** del FNGRD; y **Decreto 1261 del
19-ago-2026**, que declara el *Estado de Emergencia Económica, Social y Ecológica* por el
mismo sismo. Los dos hablan **exclusivamente de este evento**: citarlos es nombrarlo, y por
eso valen tanto como la palabra «sismo». El 1171 es además lo que habilita la urgencia
manifiesta fuera del Valle, así que explica por qué hay contratación relacionada en
Antioquia y Risaralda.

**Citar un decreto basta para dar el registro por relacionado**, sin más pruebas
(`elif golpes_decreto: nivel = "Alta"`). Por eso **cada patrón se midió contra la API
antes de escribirlo**, y el número suelto no sirve: `1171` aparece dentro del BPIM
`202500000011717` de Pueblorrico, de la señalización `63600C1171` de AEROCIVIL y de la
referencia `RESHT-SOL-TQ00001171-2026` de la Sociedad Tequendama. Con `DECRETO 1171` y
`1171 DEL 11 DE AGOSTO` son **8 aciertos y cero ruido**. Tampoco sirve `DESASTRE NACIONAL`
como palabra clave: los tres contratos del FNGRD que la usan son de **otros** desastres
—Decreto 2113 de 2022 en Santander, 1372 de 2024 en Boyacá— y están bien como ordinaria.

**Hay que BARRER por el decreto, no solo reconocerlo.** Registrarlo en `decretos` solo
alcanza a lo que otro barrido ya trajo. Un contrato que se ampara en el decreto **sin
escribir «sismo»** no lo trae ninguna palabra clave ni ningún NIT: el Ministerio de
Educación dice *«en el marco del estado de emergencia económica, social y ecológica
declarado mediante el decreto 1261 de 2026»* y nada más. Por eso existe el barrido
`decretos`, que usa `decretos_barrido` de `config.json`. Al estrenarlo aparecieron **5
registros que ningún otro barrido veía**, los cinco del MEN. **Solo van los nacionales**:
Cali y la Gobernación ya se barren enteras por NIT y por departamento, y sus números
cortos (`0964 DE 2026`) sí tienen con qué colisionar en el resto del país.

**Los decretos se buscan sobre un texto aparte, sin el ordinal.** Las entidades escriben
lo mismo de cuatro maneras —«Decreto 1171», «Decreto No. 1171», «DECRETO NACIONAL No.
1171», «Decreto N° 0964»— y con el ordinal en medio el patrón `DECRETO 1171` no coincide.
`texto_decreto` borra `No.` / `Nro.` / `N°` / `Número` cuando van pegados a un número. Va
en su propia serie y no en el texto general **porque cambia cómo se leen los números**, y
el resto del clasificador busca palabras.

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
- **La versión ligera muestra solo `Alta`** (12-sep-2026). El usuario lo pidió así con estas
  palabras: *"solo lo que ya está confirmado que está directamente relacionado con el sismo"*,
  más lo que él haya clasificado a mano como relacionado. Eso último **no exige nada aparte**:
  el colector ya sube a `Alta` lo marcado en `revisiones.csv`.
- **La versión ligera vive en el repo y se regenera sola cada 12 horas** (12-sep-2026), en
  `ligero.html`, para incrustarla por iframe o enlace desde otra instancia. Se descartó
  generarla a mano y subirla: dejaría de actualizarse el día que a nadie se le ocurra.
- **La versión ligera se incrusta en `estebanoliveros.com`** (12-sep-2026), y por eso lleva la
  piel de ese sitio y no la del tablero grande: blanco, verde de marca `#56A800` y Helvetica,
  medidos sobre el propio sitio. **Sin modo oscuro**, porque la página que la aloja es blanca y
  solo blanca. La tipografía de titulares del sitio es Cocosharp, con licencia de Wix: no se
  puede incrustar, y la identidad la llevan el color y la geometría.
- **Orden de la versión ligera: guía → mapa → filtros → tabla** (13-sep-2026), a petición del
  usuario. El mapa va primero porque es el control con el que se empieza.
- **Agrupar por entidad viene marcado de entrada** (13-sep-2026) y **no se desmarca al quitar los
  filtros**: agrupar no esconde nada, solo cambia el orden, y quitar los filtros no tiene por qué
  deshacer cómo el lector prefiere ver la tabla.
- **El monto se filtra por rangos con nombre, no con barra deslizante** (13-sep-2026). El tablero
  grande conserva la barra por cuantiles; aquí el usuario pidió rangos.
- **En la versión ligera no se muestra el distintivo de revisión humana** (13-sep-2026). En el
  tablero grande es imprescindible —ahí conviven lo dudoso y lo decidido—; aquí todo lo que se ve
  está confirmado, así que marcar unas pocas filas sugeriría que las demás lo están menos.
- **Los correos salen de una cuenta Gmail/Workspace con contraseña de aplicación**
  (12-sep-2026), no de un servicio transaccional. Si el dominio bloquea las contraseñas de
  aplicación, la alternativa acordada era Resend o SendGrid.
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

## La versión ligera (`ligero.html`)

**Existe para incrustarse en OTRA página**, en una instancia ajena donde no se puede contar
con que se sirvan cuatro archivos desde el mismo sitio. Por eso todo —datos, estilos, guion
y contornos del mapa— viaja **dentro del HTML**: 420 KB en crudo, **87 KB servidos con gzip**,
cero peticiones de red después de la primera y ninguna dependencia externa. Lo escribe
`ligero.py`, al que llama `colector.py` al final de cada corrida, así que **se actualiza solo
cada doce horas** con el mismo sello de hora que el tablero grande. No se edita a mano: se
edita `ligero.py`.

**Ni siquiera las tipografías de Google.** El tablero grande usa Zilla Slab, Public Sans e
IBM Plex Mono; este usa la pila del sistema. Una página incrustada en otra no puede quedarse
esperando una fuente remota, y una que no llega deja el texto saltando. Es el único sitio
donde los dos tableros no se parecen, y es a propósito.

**Muestra UNA sola clase de registro: `Alta`.** El tablero grande existe para dudar en voz
alta —*Por revisar*, *Otra emergencia*, *Ordinaria*—; este es para publicar hacia afuera, y
ahí lo que no está confirmado no se muestra. Incluye lo que una persona marcó como
relacionado en `revisiones.csv`, porque el colector ya lo sube a `Alta` antes de llegar aquí:
**no hay que filtrar dos veces**.

**Seis grupos, y el sexto no es lo que parece.** `Otras entidades del Valle` del colector
**no** es lo mismo que "municipios y alcaldías del Valle": ahí caben también hospitales,
instituciones educativas, cámaras de comercio y personerías. Se separan por el nombre de la
entidad, que es lo único que lo dice —`orden` y `entidad_centralizada` son autodeclarados—, y
lo que no es alcaldía ni municipio se va a *Otros*, igual que se hizo en el Excel de agosto a
petición del usuario. La UAESP se cuenta como la Alcaldía de Cali, misma decisión.

**Los seis grupos van SIEMPRE en el desplegable, con su cuenta al lado, incluidos los que
están en cero.** La Gobernación del Valle no tiene contratación confirmada del sismo, y esa
es justamente una de las cosas que hay que poder ver: si la opción desapareciera, la página
no diría nada y el lector supondría que no se la vigila. Al elegirla, el mensaje de tabla
vacía lo dice con todas sus letras —*"el cero es un hallazgo, no un dato que falte"*.

**La cifra de cabecera reparte Valle y fuera del Valle.** El título dice "Cali y Valle del
Cauca" y en la vista sin filtros **más de la mitad de lo firmado es de Antioquia, Risaralda
y Chocó**, que entran por *Otras entidades y otras regiones*. Una sola cifra grande debajo de
ese título se leería como si toda fuera del Valle: es la misma trampa que costó el episodio
de los $14,0 mm contra $10,2 mm. Se separa por el departamento de la entidad, que es lo mismo
que pinta el mapa.

**El desempate de etiquetas del mapa se mide con `getBBox()` sobre el SVG ya puesto en la
página.** Estimar el ancho por el número de letras deja solapes; con `getBBox` son **cero en
los dos mapas**, comprobado. Es el mismo algoritmo de `tablero.js`, copiado a propósito y no
factorizado: son dos páginas que tienen que poder divergir sin romperse la una a la otra.

**El mapa es el control principal, y por eso NO se respeta a sí mismo** (13-sep-2026). Pulsar
un municipio o un departamento filtra la tabla. Los mapas respetan todos los demás filtros pero
**no el territorio que ellos mismos ponen**: si lo respetaran, al elegir un municipio los demás
quedarían en cero y no habría con qué cambiar de selección — el mapa dejaría de ser un control y
pasaría a ser un callejón. La pieza elegida muestra la misma cifra que la tabla y va con borde
grueso; las demás muestran la suya. El texto de ayuda del mapa lo dice con esas palabras, que es
lo que impide que se lea como las dos cifras contradictorias del episodio de los $14,0 mm.

**El reparto Valle / otras regiones desaparece cuando hay un territorio elegido.** El reparto
mira el departamento de la **entidad** y el filtro del mapa mira el **municipio asignado**, y los
dos no siempre coinciden: la Escuela Nacional del Deporte está en Cali y SECOP la publica en
Bogotá. Con *municipio: CALI* puesto, la frase salía diciendo *"$36 M de otras regiones"* y se
leía como un error del tablero. No lo era, pero da igual: una cifra que hay que explicar para que
no parezca un error no debe estar ahí.

**El objeto ya viene completo hasta donde la fuente da, y cuando no, se dice.** Comprobado contra
la API el 12-sep-2026 sobre toda la ventana: en SECOP II `objeto_del_contrato` mide **como máximo
500 caracteres exactos**, `descripci_n_del_procedimiento` también 500 y `descripcion_del_proceso`
300. **Es un tope de la fuente, no un recorte nuestro**, y no hay campo más largo que pedir;
SECOP I no tiene tope (el objeto más largo de la ventana mide 1.417). La operación ya toma el más
largo de sus registros. Cuando el resultado llega justo en el tope, la fila **avisa que SECOP lo
cortó** y remite al expediente: un texto cortado a mitad de palabra que se presenta como entero
desinforma.

**Los botones de compartir: tres funcionan y uno copia, y se dice cuál.** WhatsApp, X y Facebook
tienen URL de compartir. **Instagram no tiene ninguna** —no existe forma de publicar en Stories
desde otra página—, así que ese botón **copia el texto al portapapeles y lo explica**, en vez de
abrir algo que no va a funcionar. **X tiene su propio mensaje**, no el largo recortado: X corta en
280 y cuenta cualquier enlace como 23 caracteres pase lo que pase. El mensaje largo mide 768. Se
arma lo fijo primero, se mide, y lo que sobra del presupuesto se le da al objeto, que es lo único
elástico; si ni así cabe, cede el nombre de la entidad. **El enlace no se toca nunca**, porque es
lo que hace verificable el dato. Comprobado sobre las 380 operaciones: ninguna pasa de 280.

**La (i) de cada filtro abre por CLIC, no por hover.** En el teléfono no hay hover, y un tooltip
que solo existe con ratón no existe para la mitad de los lectores.

**Se ORDENA primero y se agrupa después** (13-sep-2026). Primero se hizo al revés —entidades por
lo que suman, y el orden elegido aplicado solo dentro de cada bloque— y **no servía: casi toda
entidad tiene una sola operación**, así que pulsar la columna *Valor* no movía nada y el
encabezado parecía roto. Ahora el orden manda y `agrupar()` respeta el orden que ya trae la
lista: cada entidad aparece donde caiga su primera operación. Con *valor de mayor a menor* eso
pone arriba a la entidad del contrato más grande, que es lo que espera quien pulsa esa columna.
**La banda sigue diciendo el total real de la entidad**, así que el cambio de criterio no hace
que nada mienta.

**El encabezado ordenable es un `<button>` dentro del `<th>`**, no un `th` con `onclick`: así
llega por tabulador y el lector de pantalla lo anuncia como algo que se pulsa. Y como en móvil
`thead` va oculto, **el mismo estado vive también en un `<select>` «Ordenar por»** dentro de los
filtros; los dos escriben en `F.orden` y se pintan sincronizados. Sin ese select, ordenar sería
una función que en el teléfono no existe.

**El filtro de nivel de gobierno admite VARIOS a la vez** (13-sep-2026), con la misma solución
del tablero grande: un `<details>` con casillas, panel anclado al **bloque** de filtros —que
lleva `position:relative` y `overflow:visible`— y **el resumen cerrado dice cuántos hay
elegidos**. Marcar no repinta la lista, solo el resumen y la tabla, o las casillas saltarían bajo
el cursor. Se llamaba *Entidad contratante* y se renombró porque se confundía con el filtro
*Entidad*, que es otra cosa: uno es el nivel, el otro la entidad concreta.

**En el PDF los enlaces van como `<a href>` de verdad.** Al imprimir a PDF el navegador conserva
el hipervínculo y el botón queda pulsable dentro del archivo; escritos como texto, habría que
copiar la URL a mano. El informe lleva además las tres fechas —firma, inicio y terminación— que
en pantalla van en la columna de estado.

**El PDF imprime TODAS las filas del filtro y los dos mapas**, no las 20 de la página. Los SVG se
clonan con `outerHTML`, así que conservan sus clases `m0..m4`; aun así el bloque `@media print`
lleva **sus propias reglas de relleno** para `#impresion .mapas-papel`, porque las de pantalla
cuelgan de `.lienzo` y ahí dentro no hay ningún `.lienzo` — es la trampa que ya sacó los mapas
enteros en negro una vez.

## Los avisos por correo (`correo.py`)

**Dos correos, dos públicos, porque son dos decisiones distintas.** El de `Alta` va al
equipo: es contratación ya dada por atención del sismo, y trae lo necesario para verificarla
sin abrir el tablero (entidad, número, proveedor, valor, objeto completo, firma, inicio, fin
y el botón a SECOP). El de `Media` va **solo a quien revisa**. Mezclarlos sería el peor
resultado posible: lo dudoso acabaría leyéndose como confirmado.

**No se avisa dos veces del mismo registro.** La bitácora es `datos/avisados.csv`, con pares
`(identificador, aviso)`. Se lleva **por registro y no por operación** a propósito: si un
proceso ya avisado se firma después, el contrato es un identificador nuevo y **la firma vuelve
a avisarse**, que es exactamente la noticia.

**El paso va DESPUÉS de la auditoría y ANTES de publicar.** Después de la auditoría porque si
el candado salta no hay que avisar de datos que no se van a publicar. Antes de publicar porque
así `avisados.csv` viaja **en el mismo commit que los datos**; al revés, una segunda corrida
del mismo día encontraría la bitácora vacía y repetiría todos los avisos. Y lleva
`continue-on-error`: publicar no puede depender de que responda un servidor de correo.

**En la primera corrida no se manda nada**: se siembra la bitácora con lo que ya existe. Sin
eso, el estreno serían quinientos correos de contratación de hace un mes.

**Sin credenciales o sin destinatarios no se anota nada.** Se avisa por el registro de la
corrida y los pendientes quedan pendientes: en cuanto se configuren, la siguiente corrida
manda lo acumulado. Un correo que no salió no puede darse por avisado.

**Las direcciones están en `config.json`, la contraseña en los secretos.** Las direcciones no
son secretas; la contraseña de aplicación va en *Settings > Secrets and variables > Actions*
como `CORREO_CLAVE`, junto con `CORREO_USUARIO` y, si hace falta, `CORREO_REMITENTE`.
`CORREO_SERVIDOR` y `CORREO_PUERTO` son *variables* opcionales (por defecto
`smtp.gmail.com:465`).

**`os.environ.get(clave, defecto)` no sirve aquí.** GitHub Actions define la variable igual
cuando no existe, solo que **vacía**: el defecto nunca se usaría y `int("")` reventaría la
corrida. Va con `or`.

**El correo lleva `<meta charset>` aunque el MIME ya lo diga.** Hay clientes —y
previsualizadores— que abren el HTML por su cuenta y sin esa línea leen el archivo en la
codificación del sistema: «contratación» sale como «contrataciÃ³n» en todas las tildes.

## Los estudios previos (`documentos.py`)

Estaba en *Lo que quedó sin construir* desde agosto. Se construyó el 13-sep-2026.

**Se cruza por EXPEDIENTE (`CO1.BDOS.*`), no por contrato, y esa es toda la historia.**
Los estudios previos son un documento **precontractual**: cuelgan del expediente, no del
contrato. Medido sobre las 218 operaciones confirmadas que cruzan:

| cruce | documentos | con estudios previos |
|---|---|---|
| `n_mero_de_contrato` | 2.374 | 26 de 218 — **11%** |
| `proceso` (`CO1.BDOS.*`) | 3.504 | 100 de 218 — **45%** |

El convenio `4163.001.27.1.5-2026` lo resume: por contrato no aparece ninguno; por expediente
aparece *«2. ESTUDIOS PREVIOS FUNDACION.pdf»*. Cruzar por contrato habría dejado el botón
vacío en 9 de cada 10 filas, que es peor que no ponerlo: enseña a no pulsarlo.

**La llave se llama distinto en cada dataset y es el mismo número.** `proceso_de_compra` en
contratos, `id_del_portafolio` en procesos. El colector la guarda en `portafolio`, y como el
contrato y su proceso **comparten expediente**, una consulta sirve para los dos y los
**procesos que aún no tienen contrato quedan cubiertos** — que era justo el agujero de cruzar
por contrato. SECOP I no participa: no tiene expediente electrónico y su `portafolio` va vacío.

**Solo se consulta lo que se mira: `Alta` y `Media`.** La ordinaria son doce mil registros y
multiplicaría por veinte el tiempo de corrida para un atajo que ahí no le sirve a nadie. En
`Media` es donde más rinde: la respuesta a si una fila tiene que ver con el sismo suele estar
en los estudios previos y no en el objeto, que viene en términos administrativos.

**Es best effort, como `ligero.html`.** Si el dataset no responde, el tablero sale igual sin
los enlaces. De aquí no cuelga ninguna cifra: un expediente es un atajo.

**`url_descarga_documento` llega como objeto `{'url': ...}`, no como cadena.** Es una columna
de tipo URL de Socrata. Tratarla como texto deja el `repr` del diccionario en el `href` y el
botón lleva a ninguna parte.

**El documento elegido se ordena para que sea estable.** Cuando hay varios candidatos se toma
el primero por nombre e id. Si la elección cambiara de una corrida a otra, el diff se llenaría
de ruido y el enlace bailaría sin que nadie hubiera publicado nada.

**La fuente publica el mismo documento repetido** —aparece en la fase del proceso y otra vez
en la del contrato—, así que se deduplica por `id_documento` antes de contar. Sin eso, la fila
anunciaría el doble de documentos de los que hay.

**En el tablero grande, cuando no hay estudios previos la fila dice cuántos documentos tiene
el expediente; en la versión ligera NO** (decisión del usuario, 13-sep-2026). Se probó con el
aviso en los dos y en el ligero ocupaba dos renglones en dos tercios de las filas para decir
que algo no está: esa página va incrustada en otro sitio, se lee de arriba abajo y ahí manda
la densidad. En el tablero grande se revisa fila por fila y el detalle se gana el espacio.
**Quitarlo ahorró 1 KB servido, no los 15 que se supusieron**: gzip ya comprimía la frase
repetida. El motivo bueno era el espacio vertical, no el peso.

**Que el botón falte no significa que los estudios no se hayan hecho**, sino que en el
expediente no están publicados con ese nombre. La guía de la versión ligera lo dice con esas
palabras, y añade que eso también se le puede preguntar a la entidad. Un hueco mudo se lee
como un fallo del tablero.

**En el payload de `ligero.html` viaja solo el `DocumentId`,** no la URL entera: son 140
caracteres de los que únicamente cambia ese número, y en el payload van cien. `urlEp()` la
rearma, y lo que no encaje en el patrón se guarda entero y se usa tal cual, así que el día que
SECOP cambie la forma esto no se rompe. **Ahorra 13 KB en crudo y CERO servidos**: gzip ya
deduplicaba el prefijo. Se conserva por el coste de parseo, no por el peso. La versión ligera
pasó de 87 KB a **101 KB servidos**.

## El resumen semanal (`resumen.py`)

**Sale los lunes a las 9:30 de Colombia, y a las 9:30 a propósito.** La recolección diaria
arranca a las 8:30 y tarda unos seis minutos: a la misma hora, el resumen leería el
`tablero.json` de la noche anterior y contaría una semana incompleta sin que nadie lo notara.
La ventana es de **ayer menos seis a ayer**, contada hacia atrás desde ayer y no desde hoy,
porque lo de hoy todavía no ha pasado. No toca `datos/avisados.csv`: es un informe, no un
aviso, y de cada contrato ya se avisó el día que apareció.

**SALE SIEMPRE, también cuando no hubo nada.** Un informe periódico que se calla cuando no hay
novedades es indistinguible de uno que se rompió: quien lo espera no sabría si la semana
estuvo tranquila o si el flujo lleva tres lunes cayéndose. Los avisos diarios son al revés
—solo si hay algo— porque ahí el silencio no promete nada.

**El mapa se dibuja aquí, con Pillow, no en el navegador.** En el correo no sirve un SVG:
Gmail y Outlook lo descartan, así que tiene que ser un PNG incrustado. Rasterizarlo obligaría
a cargar cairo o a levantar un navegador en el runner, y no hace falta ninguna de las dos:
**los trazos de `mapa.json` solo usan `M`, `L` y `Z`** —son polígonos, porque Douglas-Peucker
no produce curvas—, así que se parsean en diez líneas y se pintan con `ImageDraw.polygon`.
`_subtrazos()` **revienta si aparece una curva** en vez de dibujar algo torcido en silencio.
Se dibuja al doble y se reduce con LANCZOS, o los bordes salen dentados.

**Solo se rotulan los ocho mayores, con figuras compactas y con desempate.** A 620 px de
ancho, un rótulo por municipio es ilegible; el cuerpo de letra va en unidades del `viewBox`
(18–34) y las cifras en forma corta (`$2,4 mm`, no `$2.381.278.400`). El desempate aparta
etiquetas por aritmética de rectángulos —aquí no hay `getBBox()`, que es de navegador— y
después mete hacia dentro las que se salgan por cualquiera de los cuatro lados.

**Primero Cali y el Valle, y lo de fuera en su propia sección** (13-sep-2026, a petición del
usuario). Antes iba todo mezclado: las cuatro cifras sumaban Valle y fuera bajo un titular que
nombra el Valle, y *«Lo más grande de la semana»* podía encabezarse con un contrato de Caldas.
Es exactamente la trampa que costó el episodio de los $14,0 mm contra $10,2 mm. Ahora son dos
bloques con **sus propias cuatro cifras cada uno**, y el de abajo lleva escrito *«no suma en
las cifras de arriba»*, igual que el desglose del tablero grande.

**El reparto mira el departamento de la ENTIDAD** (`dep_codigo == "76"`), que es lo mismo que
pinta el mapa y lo mismo que usa `ligero.py` (`dp === "76"`). **Cali entra en el bloque del
Valle**, no en uno propio: es 76001. Si los tres criterios se desincronizan, el mapa y las
cifras dirán cosas distintas sobre la misma pantalla.

**Las novedades se cuentan por bloque, no se reparte un total global.** Por eso la operación
lleva `ids` con los identificadores de **todos** sus registros: es nueva si lo es cualquiera
de los dos. Con un solo número global, ninguno de los dos bloques cuadraría con él.

**El mapa se alimenta solo de las operaciones del Valle.** Antes daba igual —los códigos de
fuera no están en la definición y se ignoraban—, pero contarlas ahí y no en ningún bloque
sería una cuenta que no cuadra con nada de lo que se ve.

**`No Definido` no sale tal cual a una barra.** Es literalmente lo que publica SECOP cuando la
entidad no diligencia el departamento; puesto como etiqueta se lee como un fallo del informe.
Va como *«Sin departamento en la fuente»*, que dice de quién es el hueco.

**Fuera del Valle, el municipio no dice nada sin su departamento**, así que la ficha escribe
`Manizales (Caldas)`. Dentro del Valle va solo el municipio.

**El texto plano lleva las MISMAS dos secciones.** Si las dos versiones contaran distinto,
quien tenga el cliente en texto estaría leyendo otro correo.

**Cada ficha lleva el botón de estudios previos cuando el documento existe** (13-sep-2026),
en hueco junto al de *Ver en SECOP*, que va macizo: uno lleva a un PDF y el otro a la ficha, y
dos botones rellenos seguidos compiten entre sí. **Sin aviso cuando falta**, igual que en la
versión ligera. En el texto plano va como una línea `Estudios previos: <url>`. Aquí viaja la
URL entera y no el `DocumentId`: en un correo no hay guion que la rearme.

**La misma contratación publicada DOS VECES cuenta como UNA**, y eso se resuelve en
`colector.py` (`unificar_publicaciones_repetidas()`), no aquí: ver *Reglas que no se rompen*.
El correo solo lee la marca `repetida` y lo dice en la ficha, con enlace al otro expediente.
Antes estuvo resuelto solo en el correo; el usuario pidió el 13-sep-2026 que el conteo también
las descontara, y el sitio correcto para eso es la llave de operación.

**La misma contratación publicada DOS VECES se junta en una sola ficha**
(13-sep-2026). **No era un fallo del emparejado**: son dos expedientes
distintos de SECOP —otro `CO1.NTC`, otro `CO1.REQ`, otro `CO1.BDOS`— con el mismo número de
referencia, el mismo objeto y el mismo valor. Manizales publicó dos veces sus obras por $2.000
millones y solo una llegó a contrato, así que salían dos fichas seguidas, una *Contratada* y
otra *Abierta*, comiéndose dos de las tres del bloque de fuera del Valle.

**La llave son las tres cosas a la vez: entidad, referencia normalizada y valor.** Ninguna
sirve sola, y se comprobó por qué: Manizales tiene **seis contratos de $70.000.000 exactos**
con proveedores distintos —entidad + valor los habría fundido— y **dos contratos distintos que
comparten la referencia `2608131019`**, por $1.000 y por $540 millones —entidad + referencia
también—. Normalizar la referencia (quitar puntos, guiones y espacios) es lo que hace coincidir
`2608201039.` con `2608201039` y `CI-001-2026-` con `CI-001-2026`.

Sobre 382 operaciones confirmadas **colapsa 4**. Los convenios gemelos de Cali
(`…1.4-2026` y `…1.5-2026`) **no se tocan**: tienen números de referencia distintos y el
usuario decidió el 12-sep mostrarlos los dos.

**Se dice, no se esconde**, y la ficha enlaza la otra publicación: es un hecho sobre cómo
publica la entidad, y quien vaya a verificar se va a encontrar los dos expedientes. **Las
cifras siguen contando lo que la fuente publicó** —son 382 operaciones— porque cuántas veces
publicó la entidad es un hecho distinto de cuántas contrataciones hay. Solo se junta la lista.

**Una prueba no puede salir hacia afuera: `--solo-a`.** Lanzar el flujo a mano le mandaba el
resumen a todo `para_resumen`, es decir también a Esteban; pasó **dos veces el 13-sep-2026**
antes de arreglarlo. Ahora el `workflow_dispatch` tiene una entrada `solo_a`: con dirección,
manda solo ahí y **antepone `[PRUEBA]` al asunto** —si alguien reenvía el correo tiene que
verse que no es el informe del lunes—; en blanco, es el envío de verdad. El cron no pasa la
entrada, así que el lunes sale como siempre.

## Cómo probar

**El panel del navegador SÍ abre `localhost`** desde `.claude/launch.json` (comprobado el
24-ago-2026; la nota anterior decía lo contrario y ya no vale). `preview_start` levanta
`py -3 -m http.server 8765` y desde ahí se puede leer el DOM y la geometría real que calcula
el navegador, que es la única forma de cazar las trampas de especificidad del CSS.

**Capturas de pantalla SÍ hay** (comprobado el 12-sep-2026; la nota anterior decía que no y
ya no vale). `computer{action:"screenshot"}` compone imagen, y con eso se vieron los mapas de
`ligero.html` y el correo de muestra. Dos límites reales: **captura el principio de la página,
no donde se haya desplazado** —para ver algo que queda abajo hay que ocultar lo de arriba con
`style.display='none'` y recargar después—, y **`zoom` con recorte de región no está
soportado**: devuelve la captura entera. Para lo fino —solapes de etiquetas, desbordes— sigue
mandando medir (`getBBox`, `getBoundingClientRect`, `getComputedStyle`): la captura dice que
algo se ve mal, la medida dice cuánto.

`correo.py --probar` no manda nada y escribe los dos correos en `reportes/`, listos para
abrirlos en el navegador. Para simular que hay novedades, se borran unas líneas de
`datos/avisados.csv` y se vuelve a correr.

**`resumen.py --probar` en local sale VACÍO, y no es un fallo.** Los `datos/` de esta carpeta
están viejos a propósito —los mantiene Actions—, así que la ventana de la semana pasada no
tiene nada. Para ejercitar el código de verdad hay que fijar a mano una ventana con datos
(`ventana()` devuelve ayer−6 … ayer) y llamar a `cuerpo()` y `texto_plano()` directamente. Sin
eso se prueba únicamente la rama de «esta semana no hubo nada».

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

**El conjunto `dmgg-8hin` ya está construido** (13-sep-2026), en `documentos.py`. Sigue
valiendo lo que se midió en agosto: **ningún nombre de archivo menciona el sismo** —son
nombres administrativos— así que **no sirve para clasificar**, solo como atajo. Lo que
cambió al construirlo es el cruce: se hace por expediente y no por contrato, y eso sube los
estudios previos del 11% al 45%. La sección **Los estudios previos** lo explica entero.

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
