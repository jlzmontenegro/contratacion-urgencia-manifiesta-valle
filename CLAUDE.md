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

**Vacío nunca es lo mismo que fallido.** Si todos los barridos de una fuente fallan, el
colector aborta con código 2 sin tocar nada. Si el navegador no puede cargar el JSON, lo dice.
Un cero en este tablero se lee como "no hay contratación del sismo": no puede aparecer por un
fallo técnico.

**Nunca mostrar un conteo parcial como si fuera el total.** Las cifras de la vista ordinaria
salen del padrón, no de los registros embebidos: en el archivo viaja una parte. Cuando el
detalle es parcial, la página lo dice.

**Ningún NIT se inventa.** Todos los de `config.json` se obtuvieron consultando la API.

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
- Publicar solo cuando lo pida.

## Cómo está la página

Tres pestañas: **Por el sismo** · **Contratación ordinaria** · **Padrón de entidades**.

Arriba, común a todas: una portada con resumen redactado automáticamente, cuatro cifras y un
**semáforo de procedencia** que dice de qué recolección son los datos y hace cuánto (en ámbar
si pasan de 48 horas). Debajo, un desplegable *"¿Cómo se lee este tablero?"* con glosario.

Orden dentro de "Por el sismo", de lo que exige acción a lo que da contexto:
**alertas → cifras → tabla de operaciones → (plegados: filtros, detalle por nivel, gráficos) →
resto del país → SECOP I y UNGRD → modificaciones**.

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

**Nunca se suma precio base con valor firmado.** Son la misma plata en dos momentos. La operación
muestra el valor firmado si hay contrato y el precio base si no, siempre rotulado.

**Lo que no exige acción va plegado**: filtros, detalle por nivel de gobierno, gráficos y leyenda.
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
