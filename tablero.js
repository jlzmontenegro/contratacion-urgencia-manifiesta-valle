"use strict";

/* Tablero de contratación · sismo del 10 de agosto de 2026
 *
 * Este archivo SOLO pinta. Los datos llegan ya consultados y clasificados en
 * datos/tablero.json, que produce colector.py y GitHub Actions regenera cada
 * 12 horas, a las 8:30 y a las 20:30 de Colombia.
 *
 * Antes el navegador consultaba la API por su cuenta y volvía a clasificar
 * todo: eran 477 líneas que repetían en JavaScript lo que colector.py ya hacía
 * en Python, y cada regla había que cambiarla en los dos idiomas. Se arregló un
 * fallo en Python, se olvidó en JavaScript, y el tablero publicado mostró ceros
 * durante una caída de la fuente. Con una sola implementación eso no se repite.
 */

const RUTA_DATOS = "datos/tablero.json";

let LOCAL = null;
let CFG = { inicio: "2026-08-10", evento: "2026-08-10" };

/* ------------------------------------------------------------------ *
 * Formato                                                             *
 * ------------------------------------------------------------------ */
const norm = s => (s == null ? "" : String(s))
  .normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase();

const esc = s => String(s == null ? "" : s)
  .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");

const pesos = v => "$ " + (Number(v) || 0).toLocaleString("es-CO", { maximumFractionDigits: 0 });

const compacto = v => {
  const n = Number(v) || 0;
  if (n >= 1e12) return "$ " + (n / 1e12).toFixed(1) + " B";
  if (n >= 1e9)  return "$ " + (n / 1e9).toFixed(1) + " mm";
  if (n >= 1e6)  return "$ " + (n / 1e6).toFixed(1) + " M";
  return pesos(n);
};

/* ------------------------------------------------------------------ *
 * Render                                                              *
 * ------------------------------------------------------------------ */
let DATOS = [];
/* De mayor a menor valor: lo que más plata mueve se mira primero. */
let orden = { col: "valor", asc: false };

/* Cuándo apareció publicado cada registro, según la bitácora del colector.
   El tablero por sí solo no tiene memoria: consulta el estado actual, no sabe
   qué había ayer. Este mapa es lo que le permite señalar las novedades. */
let NOVEDADES = {};
const diasDesde = fecha => fecha
  ? Math.floor((Date.now() - new Date(fecha + "T00:00:00").getTime()) / 86400000)
  : null;

/* Grupos cuya contratación ordinaria sí se muestra, bajo su propio filtro:
   son las dos entidades que expidieron los decretos. */
/* Las descentralizadas reciben el mismo trato que su matriz: el Parágrafo Cuarto
   del Decreto 0964 las obliga a declarar su propia urgencia manifiesta, así que
   hay que poder revisar todo lo que contraten, no solo lo que nombre el sismo. */
/* Debe coincidir con GRUPOS_ORDINARIA de colector.py: es la lista de grupos cuya
   contratacion ordinaria viaja en el JSON. Si aqui falta uno, sus registros llegan
   pero listable() los descarta y el filtro correspondiente da cero. */
const GRUPOS_ORDINARIA = ["Alcaldía de Cali", "Gobernación del Valle",
                          "Descentralizadas de Cali", "Descentralizadas de la Gobernación",
                          "UNGRD"];

const esRelevante = r => r.nivel === "Alta" || r.nivel === "Media";

/* Lo que el tablero puede llegar a listar con algún filtro. El resto de la
   contratación ordinaria se descarga y se guarda, pero no es alcanzable desde
   la interfaz, así que tampoco debe aparecer en los conteos: un número que no
   se puede abrir no le sirve a nadie. */
/* Lo revisado a mano se lista SIEMPRE, aunque se haya descartado a ordinaria de un
   municipio, que normalmente no se embebe. El colector ya lo hace viajar en el JSON
   por el mismo motivo; si aqui se descartara, la decision desapareceria de la vista
   y no habria forma de comprobarla ni de deshacerla. */
const listable = r => r.nivel !== "Contexto" || GRUPOS_ORDINARIA.includes(r.grupo)
                      || r.revisada;
/* La jerga del clasificador traducida. La etiqueta corta va en la tabla; la
   explicación, en el título emergente y en la leyenda. Nadie que llegue de
   nuevo sabe qué es "relación alta". */
const NIVELES = {
  "Alta":          { corto: "Del sismo",
                     largo: "Nombra el sismo, o cita uno de los decretos de la emergencia." },
  "Media":         { corto: "Por revisar",
                     largo: "Su objeto es propio de una emergencia —albergues, escombros, ayuda humanitaria, maquinaria— pero no nombra el evento. Puede tener relación o no: hay que leerlo." },
  "Otra urgencia": { corto: "Otra emergencia",
                     largo: "Urgencia manifiesta declarada por otra causa, o por una calamidad anterior al 10 de agosto. No cuenta como relacionado." },
  "Contexto":      { corto: "Ordinaria",
                     largo: "Contratación corriente de una entidad vigilada. Sin relación aparente con el sismo." }
};
const nivelCorto = n => (NIVELES[n] || {}).corto || n;
const nivelLargo = n => (NIVELES[n] || {}).largo || "";

/* Los niveles con espacios necesitan una clase CSS válida */
const claseNivel = n => "n-" + ({ "Otra urgencia": "Otra" }[n] || n);
/* Los indicadores cuentan Cali, el Valle del Cauca y la UNGRD/FNGRD, que es la
   entidad que coordina y financia la respuesta nacional al desastre. Queda
   fuera el resto del país, que se muestra aparte como referencia. */
const cuenta = r => r.grupo !== "Fuera del Valle";
const territoriales = () => DATOS.filter(r => cuenta(r) && esRelevante(r));

/* ------------------------------------------------------------------ *
 * Paginación                                                          *
 * ------------------------------------------------------------------ */
/* 20 filas por página. Antes se pintaban 500 de golpe: nadie baja 500 filas
   y el navegador tarda en dibujarlas. */
const POR_PAGINA = 20;
const paginas = {};

function trozo(clave, filas){
  const total = Math.max(1, Math.ceil(filas.length / POR_PAGINA));
  if (!paginas[clave] || paginas[clave] > total) paginas[clave] = 1;
  const p = paginas[clave];
  return { filas: filas.slice((p - 1) * POR_PAGINA, p * POR_PAGINA), pagina: p, total };
}

function pintarPaginacion(destino, clave, t, cuantos, repintar){
  const el = document.getElementById(destino);
  if (!el) return;
  if (cuantos <= POR_PAGINA){ el.innerHTML = ""; return; }
  const desde = (t.pagina - 1) * POR_PAGINA + 1;
  const hasta = Math.min(t.pagina * POR_PAGINA, cuantos);
  el.innerHTML =
    `<button ${t.pagina === 1 ? "disabled" : ""} data-ir="1">« Primera</button>`
  + `<button ${t.pagina === 1 ? "disabled" : ""} data-ir="${t.pagina - 1}">‹ Anterior</button>`
  + `<span class="cual">Mostrando <b>${desde}–${hasta}</b> de <b>${cuantos}</b>`
  + ` · página ${t.pagina} de ${t.total}</span>`
  + `<button ${t.pagina === t.total ? "disabled" : ""} data-ir="${t.pagina + 1}">Siguiente ›</button>`
  + `<button ${t.pagina === t.total ? "disabled" : ""} data-ir="${t.total}">Última »</button>`;
  el.querySelectorAll("button[data-ir]").forEach(b =>
    b.addEventListener("click", () => {
      paginas[clave] = Number(b.dataset.ir);
      repintar();
      el.scrollIntoView({ block: "nearest" });
    }));
}

/* ------------------------------------------------------------------ *
 * Portada: el resumen que entiende alguien que llega sin contexto     *
 * ------------------------------------------------------------------ */

/* Procedencia de los datos que se estan viendo. Se fija desde actualizar()
   y la portada la refleja. Que esto sea explicito y permanente es una
   leccion de la caida del 15-ago-2026: el tablero mostro ceros como si
   fueran un hallazgo. */
let PROCEDENCIA = { estado: "cargando", detalle: "" };

const diasDesdeEvento = () =>
  Math.max(0, Math.floor((Date.now() - new Date(CFG.evento + "T00:00:00").getTime()) / 86400000));

function frasePlural(n, singular, plural){
  return n === 1 ? `1 ${singular}` : `${n} ${plural}`;
}

/* ------------------------------------------------------------------ *
 * Qué cambió desde la recolección anterior                            *
 * ------------------------------------------------------------------ */
/* Esto va antes del acumulado. Un monitoreo diario se abre para saber qué
   apareció, no cuánto hay en total: el acumulado apenas se mueve de un día a
   otro y enterrar la novedad al final obliga a comparar de memoria. */

const soloDia = s => String(s || "").slice(0, 10);

function pintarNovedad(){
  const el = document.getElementById("novedad");
  if (!el || !LOCAL) return;

  const dia = soloDia(LOCAL.generado);
  const c = LOCAL.corrida_anterior || {};
  const nuevosTotal = (Number(c.nuevos_contratos) || 0)
                    + (Number(c.nuevos_procesos) || 0)
                    + (Number(c.nuevos_secop1) || 0);

  /* De lo aparecido hoy, lo que importa es lo que alude al sismo. Los otros
     cientos son contratación corriente del departamento. */
  /* Por operacion, no por registro: el contrato del RCD y su proceso aparecieron
     el mismo dia y la lista los mostraba como dos hallazgos de $3.760 millones
     cada uno. */
  const nuevosRel = operaciones(DATOS.filter(r =>
    soloDia(NOVEDADES[r.id]) === dia && esRelevante(r) && cuenta(r)));

  const cambios = (LOCAL.cambios || []).filter(x => soloDia(x.fecha_deteccion) === dia);

  const partes = [];
  if (nuevosRel.length){
    /* Contratos y procesos se cuentan aparte: un proceso solo tiene precio base
       y todavía puede no firmarse. Sumarlos en una sola cifra hacía que el total
       contradijera la lista que va justo debajo. */
    const firmadas = nuevosRel.filter(o => o.firmado);
    const abiertas = nuevosRel.filter(o => o.abierta);
    const vf = firmadas.reduce((s, o) => s + o.valor, 0);
    const trozos = [];
    if (firmadas.length) trozos.push(`<b>${frasePlural(firmadas.length, "ya contratada", "ya contratadas")}</b>`
      + (vf ? ` por ${esc(pesos(vf))}` : ""));
    if (abiertas.length) trozos.push(`<b>${frasePlural(abiertas.length, "aún abierta", "aún abiertas")}</b>`);
    partes.push(`Apareció contratación nueva relacionada con el sismo: `
      + `<b>${frasePlural(nuevosRel.length, "operación", "operaciones")}</b>`
      + (trozos.length ? `, ${trozos.join(" y ")}` : "") + `.`);
  } else {
    partes.push(`<span class="quieto">No apareció contratación nueva relacionada con el `
      + `sismo en Cali, el Valle ni la UNGRD.</span>`);
  }
  if (nuevosTotal){
    partes.push(`En total se publicaron ${nuevosTotal} registros nuevos, casi todos `
      + `contratación corriente.`);
  }
  if (cambios.length){
    partes.push(`<b>${frasePlural(cambios.length, "modificación", "modificaciones")}</b> `
      + `sobre registros ya conocidos.`);
  }

  /* Los nuevos relacionados se listan con nombre: son pocos y son la noticia. */
  /* En el telefono la lista completa empujaba la tabla a cuatro pantallas de
     distancia. Se muestran menos, pero se DICE cuantas quedan: una lista recortada
     en silencio se lee como si fueran todas las novedades del dia. */
  const tope = (window.innerWidth || 1024) < 700 ? 3 : 5;
  const ordenadas = nuevosRel.slice().sort((a, b) => b.valor - a.valor);
  const restantes = ordenadas.length - tope;
  const lista = ordenadas
    .slice(0, tope)
    .map(o => `<li><b>${esc(pesos(o.valor))}</b>
        <span class="menor">${o.firmado ? "firmado" : "precio base"}</span> · ${esc(o.entidad)}
        <span class="menor">${esc(String(o.objeto).slice(0, 130))}</span>
        ${o.proveedor ? `<span class="menor">Contratista: ${esc(o.proveedor)}</span>` : ""}</li>`).join("")
    + (restantes > 0
        ? `<li class="mas">y ${frasePlural(restantes, "operación más", "operaciones más")}`
          + ` en la tabla, de menor valor.</li>`
        : "");

  el.className = "novedad" + (nuevosRel.length ? " hay" : "");
  el.innerHTML = `<div class="que">Novedades del ${esc(dia.split("-").reverse().join("/"))}`
    + `</div><p class="frase">${partes.join(" ")}</p>`
    + (lista ? `<ul>${lista}</ul>` : "");
}

function pintarPortada(){
  /* La portada cuenta operaciones. Antes decia "84 contratos y 85 procesos", dos
     cifras que el lector suma sin saber que 71 de esos pares son el mismo hecho.
     Una operacion o esta contratada o sigue abierta: nunca las dos. */
  const ops = operaciones(territoriales());
  const rel = territoriales();
  const firmadas = ops.filter(o => o.firmado);
  const abiertas = ops.filter(o => o.abierta);
  const valor = firmadas.reduce((s, o) => s + o.valor, 0);
  const urgencia = ops.filter(o => norm(o.justificacion).includes("URGENCIA MANIFIESTA"));
  /* En operaciones, como el resto del parrafo. Contando registros decia "21"
     junto a "98 operaciones" y el lector comparaba dos unidades distintas sin
     saberlo: esos 21 registros son 11 operaciones. */
  const fuera = operaciones(DATOS.filter(r => !cuenta(r) && esRelevante(r)));
  const dias = diasDesdeEvento();

  const partes = [];
  partes.push(`Han pasado <b>${frasePlural(dias, "día", "días")}</b> desde el sismo del `
            + `10 de agosto de 2026.`);

  if (!rel.length){
    partes.push(`En Cali y el Valle del Cauca <b>todavía no se ha identificado contratación `
              + `relacionada con la emergencia</b>.`);
  } else {
    partes.push(`En Cali y el Valle del Cauca se ${ops.length === 1 ? "ha" : "han"} identificado `
      + `<b>${frasePlural(ops.length, "operación relacionada", "operaciones relacionadas")}</b> `
      + `con la emergencia`
      + (valor ? `: <b>${esc(pesos(valor))}</b> ya firmados en `
                 + `${frasePlural(firmadas.length, "contrato", "contratos")}` : ``)
      + (abiertas.length ? `, y ${frasePlural(abiertas.length, "proceso", "procesos")} `
                           + `todavía sin adjudicar.` : `.`));
    if (urgencia.length){
      partes.push(`${urgencia.length === 1 ? "Uno se tramitó" : urgencia.length + " se tramitaron"}`
                + ` por <b>urgencia manifiesta</b>, la figura que permite contratar sin `
                + `convocatoria previa.`);
    }
  }

  if (fuera.length){
    partes.push(`Fuera del Valle hay ${frasePlural(fuera.length, "operación relacionada",
      "operaciones relacionadas")}, que no suman en estas cifras: para verlas, elija `
      + `<em>Fuera del Valle</em> en el filtro de territorio.`);
  }

  document.getElementById("titular").innerHTML = partes.join(" ");

  /* Cuatro cifras que no se pisan: el total, la plata, lo que falta y la figura
     excepcional. La plata es solo la firmada; el precio base de lo abierto no es
     dinero comprometido. */
  const cifras = [
    [ops.length, "operaciones relacionadas<br>en Cali y el Valle"],
    [compacto(valor), "ya firmados<br>en contratos"],
    [abiertas.length, "procesos abiertos<br>aún sin adjudicar"],
    [urgencia.length, "por urgencia manifiesta"]
  ];
  document.getElementById("cifras-portada").innerHTML = cifras.map(([n, t]) =>
    `<div class="cifra${(n === 0 || n === "$ 0") ? " nula" : ""}">
       <div class="n">${esc(n)}</div><div class="t">${t}</div>
     </div>`).join("");

  pintarNovedad();
  pintarFuente();
}

/* De dónde salen los datos y de cuándo son. En palabras, no en jerga. */
function pintarFuente(){
  const luz = document.getElementById("luz-fuente");
  const txt = document.getElementById("texto-fuente");

  if (PROCEDENCIA.estado === "cargando"){
    luz.className = "luz vieja";
    txt.textContent = "Cargando los datos de la última recolección…";
    return;
  }
  if (PROCEDENCIA.estado === "sin-datos"){
    luz.className = "luz rota";
    txt.innerHTML = `<b>No se pudieron cargar los datos.</b> ${esc(PROCEDENCIA.detalle)}`;
    return;
  }

  /* El colector corre en la nube cada 12 horas —8:30 y 20:30— y publica. El
     umbral va atado a esa cadencia: si pasan 26 horas es que se saltaron dos
     recolecciones seguidas, y hay que decirlo, porque una cifra vieja presentada
     sin fecha se lee como si fuera de hoy. */
  const horas = PROCEDENCIA.horas;
  const vieja = horas !== null && horas > 26;
  luz.className = "luz " + (vieja ? "vieja" : "viva");
  txt.innerHTML = `<b>Datos de la recolección del ${esc(LOCAL.generado)}</b>`
    + (horas === null ? ""
        : horas < 1 ? " · recién recogidos"
        : horas < 24 ? ` · hace ${frasePlural(horas, "hora", "horas")}`
        : ` · hace ${frasePlural(Math.round(horas / 24), "día", "días")}`)
    + `. El colector consulta SECOP I y SECOP II dos veces al día, a las 8:30 y a las `
    + `20:30, y verifica la cobertura antes de publicar.`
    + (vieja ? ` <b>Se saltó al menos una recolección:</b> revise la pestaña Actions `
             + `del repositorio, es probable que una corrida haya fallado.` : "");
}

/* ------------------------------------------------------------------ *
 * Vista de contratación ordinaria                                     *
 * ------------------------------------------------------------------ */
/* Todo lo que contrataron las entidades vigiladas desde el sismo, tenga o no
   relación con él. No hay comparación contra periodos anteriores: el
   seguimiento arranca el 10 de agosto de 2026 y hacia atrás no se mira. El
   valor de esta vista es servir de denominador. */

const GRUPOS_VIGILADOS = ["Alcaldía de Cali", "Descentralizadas de Cali",
  "Gobernación del Valle", "Descentralizadas de la Gobernación",
  "Otras entidades del Valle", "UNGRD"];


/* Agrupa por entidad. Solo entidades vigiladas: el resto del país no es objeto
   de este seguimiento y meterlo aquí volvería la tabla ilegible.

   Cuando los datos vienen del respaldo embebido no sirve contar sobre DATOS: en
   el HTML solo viaja una parte de la contratación ordinaria, porque embeberla
   toda haría el archivo inservible. En ese caso se usan las cifras agregadas
   que precalculó el colector, que sí cubren el universo completo. Contar sobre
   lo embebido daría un número menor sin avisar. */
let PADRON = [];





/* ------------------------------------------------------------------ *
 * Padrón de entidades                                                 *
 * ------------------------------------------------------------------ */

/* Vigilada y en silencio: se consulta todos los días y no ha publicado nada
   desde el sismo. Solo aplica a las que tienen NIT en la configuración; las
   del barrido territorial aparecen precisamente porque contrataron algo, así
   que un cero ahí no significa lo mismo. */
const enSilencio = e => e.n === 0 && e.via === "NIT en configuración";

function filtradosPadron(){
  const txt = norm(document.getElementById("fp-texto").value.trim());
  const via = document.getElementById("fp-via").value;
  const tipo = document.getElementById("fp-tipo").value;
  const grupo = document.getElementById("fp-grupo").value;
  const act = document.getElementById("fp-actividad").value;
  return PADRON.filter(e => {
    if (via && e.via !== via) return false;
    if (tipo && e.tipo !== tipo) return false;
    if (grupo && e.grupo !== grupo) return false;
    if (act === "sin" && e.n !== 0) return false;
    if (act === "con" && e.n === 0) return false;
    if (act === "sismo" && !e.rel) return false;
    if (txt && !norm(e.entidad + " " + e.nit + " " + e.raiz).includes(txt)) return false;
    return true;
  });
}

/* Fila de cifras grandes. La usan el padron y el detalle por nivel de gobierno. */
function tarjetas(destino, lista){
  document.getElementById(destino).innerHTML = lista.map(([e, v, p]) =>
    `<div class="kpi${(v === 0 || v === "$ 0") ? " cero" : ""}">
       <div class="etq">${esc(e)}</div><div class="val">${esc(v)}</div><div class="pie">${esc(p)}</div>
     </div>`).join("");
}

/* Entidades desplegadas en el padron. Se guarda por nombre y no por indice porque
   la tabla se repinta al filtrar y al cambiar de pagina. */
const padronAbierto = new Set();

/* Lo que el archivo trae de una entidad. OJO: casi nunca es todo lo que el padron
   cuenta. El padron cuenta sobre el corpus completo -344 entidades, 231 de ellas
   con mas registros de los que viajan- mientras que en el JSON solo se embeben los
   relacionados con el sismo y, ademas, la contratacion ordinaria de los grupos de
   GRUPOS_ORDINARIA. Mostrar 28 bajo un contador que dice 244 parece un error si no
   se explica, asi que se explica. */
function registrosDeEntidad(nombre){
  return DATOS.filter(r => r.entidad === nombre)
    .slice()
    .sort((a, b) => String(b.fecha).localeCompare(String(a.fecha)) || b.valor - a.valor);
}

function detallePadron(e){
  const suyos = registrosDeEntidad(e.entidad);
  const faltan = e.n - suyos.length;

  /* Tres casos distintos, y confundirlos desinforma: no haber contratado nada no es
     lo mismo que haber contratado y que el dato no viaje en el archivo. */
  const aviso = !e.n
    ? `<p class="aviso-detalle">Esta entidad <b>no ha publicado ninguna contratación</b>
       desde el 10 de agosto de 2026. Se consulta en cada corrida: el cero es un hallazgo,
       no un vacío del monitoreo.</p>`
    : !suyos.length
    ? `<p class="aviso-detalle">Sus ${frasePlural(e.n, "registro", "registros")} no
       viaja${e.n === 1 ? "" : "n"} en este archivo: ninguno se relaciona con el sismo, y la
       contratación corriente solo se embebe para Cali, la Gobernación, sus descentralizadas
       y la UNGRD. El colector sí ${e.n === 1 ? "lo descarga y lo guarda" : "los descarga y los guarda"}.</p>`
    : faltan > 0
      ? `<p class="aviso-detalle">Se listan <b>${suyos.length}</b> de sus
         ${frasePlural(e.n, "registro", "registros")}: los relacionados con el sismo y, si es
         de Cali o de la Gobernación, también los ordinarios.
         ${faltan === 1 ? "El otro se descarga y se guarda, pero no se lista aquí."
                        : `Los otros ${faltan} se descargan y se guardan, pero no se listan aquí.`}</p>`
      : `<p class="aviso-detalle">Se listan sus
         ${frasePlural(e.n, "registro", "registros")}, que es todo lo que el colector le encontró.</p>`;

  const items = suyos.map(r => `
    <li class="reg">
      <div class="reg-cab">
        <span class="etiqueta ${claseNivel(r.nivel)}"
              title="${esc(nivelLargo(r.nivel))}">${esc(nivelCorto(r.nivel))}</span>
        <span class="menor">${esc(r.tipo)} · ${esc(r.fecha)}</span>
        ${r.referencia ? `<span class="ref">${esc(r.referencia)}</span>` : ""}
        ${r.revisada ? `<span class="revisada">✓ revisado</span>` : ""}
      </div>
      <div class="reg-obj">${esc(r.objeto)}</div>
      <div class="reg-pie">
        <b>${esc(pesos(r.valor))}</b>
        <span class="menor">${r.tipo === "Contrato" ? "valor firmado" : "precio base"}</span>
        ${r.proveedor && r.proveedor !== "No Definido"
            ? `<span class="menor">· ${esc(r.proveedor)}</span>` : ""}
        ${r.url ? `<a class="boton boton-secop" href="${esc(r.url)}" target="_blank"
                      rel="noopener">Ver en SECOP</a>` : ""}
      </div>
      <div class="menor">${esc(r.motivo)}</div>
    </li>`).join("");

  return `<td colspan="7" class="detalle-padron">
      ${aviso}
      ${items ? `<ul class="regs">${items}</ul>` : ""}
    </td>`;
}


function pintarPadron(){
  const rotulo = document.getElementById("n-padron");
  if (rotulo) rotulo.textContent = PADRON.length
    ? `· ${PADRON.length} entidades, ${PADRON.filter(e => e.sin_contratacion).length} sin contratación`
    : "";
  if (!PADRON.length){
    document.getElementById("secciones-padron").innerHTML =
      '<div class="vacio">El padrón lo genera <code>colector.py</code>. Esta copia del '
      + 'tablero no lo trae incorporado todavía.</div>';
    return;
  }

  const fijas = PADRON.filter(e => e.via === "NIT en configuración").length;
  const nits = new Set(PADRON.map(e => e.raiz)).size;
  const conSismo = PADRON.filter(e => e.rel > 0).length;
  const registros = PADRON.reduce((s, e) => s + e.n, 0);
  const calladas = PADRON.filter(enSilencio).length;
  tarjetas("kpis-padron", [
    ["Entidades en el padrón", PADRON.length, nits + " NIT distintos"],
    ["Por NIT en configuración", fijas, "se consultan siempre"],
    ["Por barrido territorial", PADRON.length - fijas, "aparecen por estar en el Valle"],
    ["Vigiladas sin contratar", calladas, "no han publicado nada desde el sismo"],
    ["Con registros del sismo", conSismo, registros + " registros en total"]
  ]);

  const filas = filtradosPadron();
  document.getElementById("conteo-padron").textContent =
    `${filas.length} de ${PADRON.length}`;

  const cont = document.getElementById("secciones-padron");
  if (!filas.length){
    cont.innerHTML = '<div class="vacio">Ninguna entidad coincide con el filtro.</div>';
    document.getElementById("pag-padron").innerHTML = "";
    return;
  }

  /* Una sola tabla, de mayor a menor valor contratado. Antes iba partida en
     siete secciones por grupo; con el filtro de grupo al lado, la división
     sobraba y obligaba a recorrer toda la página para encontrar una entidad. */
  const ordenadas = filas.slice().sort((a, b) =>
    b.valor - a.valor || b.n - a.n || a.entidad.localeCompare(b.entidad, "es"));
  const t = trozo("padron", ordenadas);
  pintarPaginacion("pag-padron", "padron", t, ordenadas.length, pintarPadron);

  cont.innerHTML = `
    <div class="tabla-envoltura">
      <table>
        <thead><tr>
          <th>Entidad</th><th>Nivel de gobierno</th><th>NIT</th><th>Cómo entra</th>
          <th class="num">Registros</th><th class="num">Valor contratado</th><th>Del sismo</th>
        </tr></thead>
        <tbody>${t.filas.map(e => `
          <tr class="fila-entidad ${enSilencio(e) ? "silenciosa" : ""}${
              padronAbierto.has(e.entidad) ? " abierta" : ""}"
              data-entidad="${esc(e.entidad)}" tabindex="0" role="button"
              aria-expanded="${padronAbierto.has(e.entidad)}"
              title="Pulse para ver los registros de esta entidad">
            <td data-etq="Entidad"><span class="flecha" aria-hidden="true"></span><b>${esc(e.entidad)}</b>
              ${enSilencio(e) ? ' <span class="chip silencio">sin contratar</span>' : ""}
              <div class="menor">${esc(e.tipo)}${e.plat !== "—" ? " · " + esc(e.plat) : ""}</div></td>
            <td data-etq="Nivel de gobierno">${esc(e.grupo)}
              <div class="menor">${esc(e.orden)}</div></td>
            <td class="nit-col" data-etq="NIT">${esc(e.nit)}${
              e.nit !== e.raiz && e.nit !== "—"
                ? `<span class="raiz">raíz ${esc(e.raiz)}</span>` : ""}</td>
            <td data-etq="Cómo entra"><span class="chip${
              e.via === "NIT en configuración" ? " fija" : ""}"
              title="${e.via === "NIT en configuración"
                ? "Se consulta siempre, aunque no contrate nada y aunque su departamento venga mal diligenciado."
                : "Aparece por tener departamento Valle del Cauca. Si ese campo viniera vacío, no se vería."}"
              >${esc(e.via)}</span></td>
            <td class="num" data-etq="Registros">${e.n}</td>
            <td class="num" data-etq="Valor">${esc(compacto(e.valor))}</td>
            <td data-etq="Del sismo">${e.rel
              ? `<span class="etiqueta n-Alta">${e.rel}</span>`
              : '<span class="menor">—</span>'}</td>
          </tr>
          ${padronAbierto.has(e.entidad) ? `<tr class="fila-detalle">${detallePadron(e)}</tr>` : ""}
          `).join("")}</tbody>
      </table>
    </div>`;
}


/* Desglose por nivel de gobierno, con las MISMAS cuatro medidas de la portada:
   operaciones, valor firmado, procesos abiertos y urgencia manifiesta. Antes solo
   daba operaciones y valor, y la pregunta natural —cuanto de esto es de Cali y
   cuanto de la Gobernacion— habia que hacerla a mano.

   La fila de total no es decorativa: es la comprobacion de que el desglose cuadra
   con la portada. Si un dia no cuadra, se ve aqui. */
function pintarKpis(){
  const ops = operaciones(territoriales());

  const GRUPOS = [
    ["Alcaldía de Cali", "Alcaldía de Cali", "nivel central"],
    ["Descentralizadas de Cali", "Descentralizadas de Cali", "EMCALI, Metro Cali, redes de salud…"],
    ["Gobernación del Valle", "Gobernación del Valle", "nivel central"],
    ["Descentralizadas de la Gobernación", "Descentralizadas de la Gobernación",
     "HUV, INDERVALLE, ACUAVALLE…"],
    ["Municipios del Valle", "Otras entidades del Valle", "y sus entidades"],
    ["UNGRD y FNGRD", "UNGRD", "respuesta nacional al desastre"],
    /* Entidades de otras regiones contratando PARA el Valle. Cuenta en los
       indicadores desde siempre, pero estuvo en cero hasta el 20-ago-2026 y por eso
       nadie noto que le faltaba fila: el desglose sumaba 101 y la portada 102. */
    ["Nacional para el Valle", "Nacional para el Valle",
     "de otras regiones, contratando para el territorio afectado"],
  ];

  const mide = suyas => ({
    n: suyas.length,
    firmado: suyas.filter(o => o.firmado).reduce((s, o) => s + o.valor, 0),
    contratos: suyas.filter(o => o.firmado).length,
    abiertas: suyas.filter(o => o.abierta).length,
    urgencia: suyas.filter(o => norm(o.justificacion).includes("URGENCIA MANIFIESTA")).length,
  });

  const filas = GRUPOS.map(([rotulo, grupo, quienes]) =>
    ({ rotulo, quienes, ...mide(ops.filter(o => o.grupo === grupo)) }));

  /* Red de seguridad: si apareciera un grupo nuevo sin fila, el desglose dejaria de
     cuadrar con la portada y nadie se enteraria. Antes que callar, se muestra. */
  const contadas = filas.reduce((s, f) => s + f.n, 0);
  if (ops.length > contadas){
    const sueltas = ops.filter(o => !GRUPOS.some(([, g]) => g === o.grupo));
    filas.push({ rotulo: "Otros grupos", quienes: "cuentan en el total y no tienen fila propia",
                 ...mide(sueltas) });
  }

  const total = mide(ops);
  const celda = (f) => `
      <tr class="${f.n ? "" : "cero"}">
        <th scope="row">${esc(f.rotulo)}<div class="menor">${esc(f.quienes)}</div></th>
        <td class="num" data-etq="Operaciones">${f.n || "—"}</td>
        <td class="num" data-etq="Valor firmado">${f.firmado ? esc(compacto(f.firmado)) : "—"}
          ${f.contratos ? `<div class="menor">en ${frasePlural(f.contratos, "contrato", "contratos")}</div>` : ""}</td>
        <td class="num" data-etq="Abiertas">${f.abiertas || "—"}</td>
        <td class="num" data-etq="Urgencia manifiesta">${f.urgencia || "—"}</td>
      </tr>`;

  document.getElementById("kpis").innerHTML = `
    <table id="tabla-niveles">
      <thead><tr>
        <th>Nivel de gobierno</th>
        <th class="num">Operaciones</th>
        <th class="num">Valor firmado</th>
        <th class="num">Abiertas</th>
        <th class="num">Urgencia manifiesta</th>
      </tr></thead>
      <tbody>${filas.map(celda).join("")}</tbody>
      <tfoot><tr>
        <th scope="row">Cali y el Valle</th>
        <td class="num" data-etq="Operaciones">${total.n}</td>
        <td class="num" data-etq="Valor firmado">${esc(compacto(total.firmado))}
          <div class="menor">en ${frasePlural(total.contratos, "contrato", "contratos")}</div></td>
        <td class="num" data-etq="Abiertas">${total.abiertas}</td>
        <td class="num" data-etq="Urgencia manifiesta">${total.urgencia}</td>
      </tr></tfoot>
    </table>`;
}

function barras(destino, pares, formato){
  const cont = document.getElementById(destino);
  if (!pares.length){ cont.innerHTML = '<div class="sub">Sin datos todavía.</div>'; return; }
  const max = Math.max(...pares.map(p => p[1])) || 1;
  cont.innerHTML = pares.map(([nom, val]) => `
    <div>
      <div class="fila"><span class="nom" title="${esc(nom)}">${esc(nom)}</span>
        <span class="num">${esc(formato(val))}</span></div>
      <div class="pista"><div class="relleno" style="width:${(val / max * 100).toFixed(1)}%"></div></div>
    </div>`).join("");
}

function agrupar(filas, clave, sumarValor){
  const m = new Map();
  for (const r of filas){
    const k = (r[clave] || "(sin dato)").toString();
    m.set(k, (m.get(k) || 0) + (sumarValor ? r.valor : 1));
  }
  return [...m.entries()].sort((a, b) => b[1] - a[1]);
}

/* Operaciones nuevas por dia, cada una contada UNA vez, en la fecha en que
   aparecio. Antes se contaban registros: las barras sumaban 169 mientras la
   pagina entera hablaba de 98 operaciones.

   Los dias sin contratacion salen en CERO en vez de desaparecer. La version
   anterior tomaba las ultimas N fechas *con datos*, asi que un dia en blanco se
   comprimia en silencio; en este tablero "ese dia no se contrato nada" es
   informacion, no ausencia de informacion.

   La serie termina en el ultimo dia con datos y no en hoy: SECOP publica con
   alrededor de un dia de rezago y el ultimo tramo saldria siempre en cero por el
   rezago, no por falta de contratacion. */
function operacionesPorDia(ops, dias){
  const cuenta = new Map();
  ops.forEach(o => {
    if (o.primeraFecha) cuenta.set(o.primeraFecha, (cuenta.get(o.primeraFecha) || 0) + 1);
  });
  const conDatos = [...cuenta.keys()].sort();
  if (!conDatos.length) return [];

  const fin = new Date(conDatos[conDatos.length - 1] + "T00:00:00");
  const inicioVentana = new Date(CFG.inicio + "T00:00:00");
  const serie = [];
  for (let i = dias - 1; i >= 0; i--){
    const d = new Date(fin.getTime() - i * 86400000);
    /* Nada antes del 10 de agosto: fuera de la ventana no hay nada que contar y
       un cero ahi se leeria como "no se contrato", cuando es "no se vigila". */
    if (d < inicioVentana) continue;
    const clave = d.toISOString().slice(0, 10);
    serie.push([clave, cuenta.get(clave) || 0]);
  }
  return serie;
}

function pintarGraficos(){
  const rel = territoriales();
  barras("graf-entidades", agrupar(rel.filter(r => r.tipo === "Contrato"), "entidad", true).slice(0, 8), compacto);
  barras("graf-dias", operacionesPorDia(operaciones(rel), 14), v => v);
  barras("graf-proveedores", agrupar(rel.filter(r => r.tipo === "Contrato" && r.proveedor), "proveedor", true).slice(0, 8), compacto);
}

function pintarAlertas(){
  const rel = territoriales().filter(r => r.tipo === "Contrato");
  const alertas = [];

  rel.filter(r => r.valor >= 500000000).forEach(r =>
    alertas.push(["Alto valor", `${r.entidad} · ${pesos(r.valor)} · ${r.proveedor || "sin contratista"}`]));
  agrupar(rel.filter(r => r.proveedor), "proveedor", false).filter(([, n]) => n >= 3)
    .forEach(([p, n]) => alertas.push(["Contratista recurrente", `${p}: ${n} contratos`]));
  const sinValor = rel.filter(r => !r.valor).length;
  if (sinValor) alertas.push(["Sin valor publicado", `${sinValor} contratos relacionados con valor en cero`]);

  const cont = document.getElementById("lista-alertas");
  cont.innerHTML = alertas.length
    ? alertas.slice(0, 12).map(([t, d]) =>
        `<div class="alerta"><span class="tipo">${esc(t)}</span><span>${esc(d)}</span></div>`).join("")
    : '<div class="sub">Sin alertas en Cali y el Valle con los datos actuales.</div>';
}

/* La prueba se hace por registro pero se aplica por operacion (ver
   operacionesFiltradas): si se filtra antes de agrupar, una busqueda por el
   numero del proceso devuelve la operacion sin su contrato y la fila anuncia
   "aun sin contratar" algo que ya se firmo. */
function filtraRegistro(r, ctx){
  const { txt, grupo, niv, nov, ent, plat } = ctx;

  // La contratación ordinaria solo se muestra para la Alcaldía de Cali y la
  // Gobernación del Valle, y solo cuando se pide expresamente en el filtro.
  // La del resto de entidades se sigue descargando y guardando en los CSV
  // — es lo que permite reclasificar si se ajustan las palabras clave — pero
  // no se lista. Esto incluye a la UNGRD: se revisa entera, se muestra solo
  // lo del sismo.
  if (!listable(r)) return false;
  /* La ordinaria no se muestra por defecto —decision del usuario— pero si cuando
     se pide expresamente, sea con su propia opcion o con "todo". Antes "todo" la
     excluia y la opcion mentia: daba 99 donde la ordinaria sola daba 1.319. */
  if (r.nivel === "Contexto" && niv !== "Contexto" && niv !== "todos") return false;
  if (plat && r.plataforma !== plat) return false;
  if (nov){
    const d = diasDesde(NOVEDADES[r.id]);
    if (d === null || d > Number(nov)) return false;
  }
  if (grupo === "territorial" && !cuenta(r)) return false;
  if (grupo !== "territorial" && grupo !== "todos" && r.grupo !== grupo) return false;
  if (niv === "rel" && !esRelevante(r)) return false;
  if (niv !== "rel" && niv !== "todos" && r.nivel !== niv) return false;
  if (ent && r.entidad !== ent) return false;
  if (txt && !norm([r.objeto, r.entidad, r.proveedor, r.id, r.referencia].join(" ")).includes(txt)) return false;
  return true;
}

function contextoFiltros(){
  return {
    txt: norm(document.getElementById("f-texto").value.trim()),
    grupo: document.getElementById("f-grupo").value,
    niv: document.getElementById("f-nivel").value,
    nov: document.getElementById("f-novedad").value,
    ent: document.getElementById("f-entidad").value,
    plat: document.getElementById("f-plataforma").value,
  };
}

/* Para la descarga: registros sueltos, que es lo que espera quien abre el CSV. */
function filtrados(){
  const ctx = contextoFiltros();
  return DATOS.filter(r => filtraRegistro(r, ctx));
}

/* Para la pantalla: operaciones completas. Se arma la operacion con TODOS sus
   registros y se conserva si alguno pasa el filtro, de modo que la fila siempre
   muestra el estado real. */
function operacionesFiltradas(){
  const ctx = contextoFiltros();
  return operaciones(DATOS.filter(listable))
    .filter(o => [o.contrato, o.proceso].some(r => r && filtraRegistro(r, ctx)));
}

/* Un contrato y el proceso que lo convoco son el mismo hecho en dos momentos.
   El colector los marca con la misma clave `operacion`; aqui se juntan en una
   fila. Antes se listaban por separado y el lector veia el RCD de la UAESP dos
   veces, con el mismo valor, como si fueran $7.500 millones. */
function operaciones(filas){
  const mapa = new Map();
  filas.forEach(r => {
    const k = r.operacion || r.id;
    if (!mapa.has(k)) mapa.set(k, { clave: k, contrato: null, proceso: null });
    const o = mapa.get(k);
    /* Si la fuente publicara dos contratos para una misma operacion, manda el de
       mayor valor: es el vigente tras las adiciones. */
    if (r.tipo === "Contrato"){ if (!o.contrato || r.valor > o.contrato.valor) o.contrato = r; }
    else { if (!o.proceso || r.valor > o.proceso.valor) o.proceso = r; }
  });

  return [...mapa.values()].map(o => {
    const c = o.contrato, pr = o.proceso;
    const jefe = c || pr;              // el contrato manda cuando existe
    const otro = c ? pr : null;
    /* El valor mostrado es el firmado si ya hay contrato, y el precio base si no.
       Nunca se suman: son la misma plata en dos momentos. */
    const nov = [c, pr].filter(Boolean).map(r => NOVEDADES[r.id]).filter(Boolean).sort();
    return {
      clave: o.clave, contrato: c, proceso: pr, jefe: jefe, otro: otro,
      entidad: jefe.entidad, objeto: jefe.objeto, grupo: jefe.grupo,
      valor: jefe.valor,
      firmado: !!c,
      abierta: !c,
      huerfana: !!c && !pr,           // contrato sin proceso publicado
      proveedor: c ? c.proveedor : "",
      fecha: jefe.fecha,
      /* La fecha del contrato es la firma y la del proceso la publicacion. Para
         contar una operacion UNA sola vez en una serie temporal hace falta la
         primera de las dos: si no, la que se publico el 14 y se firmo el 17
         aparece en los dos dias y los dias dejan de repartir el total. */
      primeraFecha: [c, pr].filter(Boolean).map(r => r.fecha).filter(Boolean).sort()[0] || "",
      nivel: (c && c.nivel === "Alta") || (pr && pr.nivel === "Alta") ? "Alta" : jefe.nivel,
      motivo: jefe.motivo,
      plataforma: jefe.plataforma,
      modalidad: jefe.modalidad,
      justificacion: jefe.justificacion,
      duracion: jefe.duracion,
      novedad: nov.length ? nov[nov.length - 1] : null,
      revisada: !!jefe.revisada,
      revisionNota: jefe.revision_nota || "",
      revisionRevisor: jefe.revision_revisor || "",
      revisionFecha: jefe.revision_fecha || "",
    };
  });
}

const ordenarOperaciones = (lista) => lista.sort((a, b) => {
  const col = orden.col;
  const x = col === "valor" ? a.valor : String(a.jefe[col] ?? "");
  const y = col === "valor" ? b.valor : String(b.jefe[col] ?? "");
  const cmp = (typeof x === "number") ? x - y : String(x).localeCompare(String(y));
  return orden.asc ? cmp : -cmp;
});


/* La leyenda explica los cuatro niveles con palabras, no con etiquetas. Va
   junto a la tabla porque es ahí donde el lector se topa con ellas. */
function pintarLeyenda(){
  const el = document.getElementById("leyenda-niveles");
  if (!el) return;
  el.innerHTML = Object.entries(NIVELES).map(([n, d]) =>
    `<div><span class="etiqueta ${claseNivel(n)}">${esc(d.corto)}</span>
       <span>${esc(d.largo)}</span></div>`).join("");
}

/* El panel de filtros va cerrado para no llenar la pantalla, asi que el resumen
   tiene que decir que se esta viendo: un tablero filtrado en silencio miente. */
function pintarResumenFiltros(){
  const el = document.getElementById("resumen-filtros");
  if (!el) return;
  /* Por valor y no por selectedIndex: cada control tiene un valor por defecto
     distinto y el indice no dice cual es. */
  const PORDEFECTO = { "f-grupo": "territorial", "f-nivel": "rel", "f-plataforma": "", "f-revision": "",
                       "f-tipo": "", "f-novedad": "", "f-entidad": "" };
  const texto = id => {
    const s = document.getElementById(id);
    if (!s || s.value === PORDEFECTO[id]) return "";
    const op = s.options && [...s.options].find(o => o.value === s.value);
    return op ? op.text : String(s.value);
  };
  const activos = ["f-grupo","f-plataforma","f-nivel","f-tipo","f-revision","f-novedad","f-entidad"]
    .map(texto).filter(Boolean);
  const busq = document.getElementById("f-texto").value.trim();
  if (busq) activos.unshift(`"${busq}"`);
  el.textContent = activos.length ? "· " + activos.join(" · ") : "· sin filtros";
  el.className = "resumen-filtros" + (activos.length ? " hay" : "");
}

/* En el JSON viaja alrededor de la mitad de lo monitoreado: la contratacion
   ordinaria solo se embebe para Cali y la Gobernacion. Mostrar ese conteo sin
   decirlo lo convierte en un total falso, que es la regla que mas caro sale.
   Las cifras completas por entidad estan en el padron, al pie. */
function pintarAvisoParcial(){
  const el = document.getElementById("aviso-parcial");
  if (!el) return;
  const niv = document.getElementById("f-nivel").value;
  const parcial = niv === "Contexto" || niv === "todos";
  el.hidden = !parcial;
  if (parcial) el.innerHTML =
    `<b>Esta cuenta no es el total.</b> De la contratación corriente solo viaja en el archivo `
    + `la de la Alcaldía de Cali y la Gobernación del Valle; la del resto de entidades se `
    + `descarga y se guarda, pero no se lista aquí. Los totales completos por entidad están `
    + `en <em>Padrón de entidades vigiladas</em>, al pie de la página.`;
}

function pintarTabla(){
  pintarLeyenda();
  pintarResumenFiltros();
  pintarAvisoParcial();
  /* El filtro de estado se aplica sobre la operacion y no sobre el registro:
     "aun abierta" significa que no existe contrato, y eso solo se sabe despues
     de juntar el proceso con su contrato. */
  const estado = document.getElementById("f-tipo").value;
  let filas = ordenarOperaciones(operacionesFiltradas());
  if (estado === "firmada") filas = filas.filter(o => o.firmado);
  if (estado === "abierta") filas = filas.filter(o => o.abierta);
  /* "Por revisar" es la bandeja de trabajo: lo que el clasificador marco como
     posible pero nadie ha confirmado ni descartado todavia. */
  const rev = document.getElementById("f-revision").value;
  if (rev === "pendiente") filas = filas.filter(o => o.nivel === "Media" && !o.revisada);
  if (rev === "revisada") filas = filas.filter(o => o.revisada);
  const cuerpo = document.querySelector("#tabla tbody");
  /* Solo se suma lo firmado. El precio base de un proceso abierto no es plata
     comprometida y mezclarlo inflaba el total. */
  const valorFiltrado = filas.reduce((s, o) => s + (o.firmado ? o.valor : 0), 0);
  const abiertas = filas.filter(o => o.abierta).length;
  document.getElementById("conteo-filtro").textContent =
    frasePlural(filas.length, "operación", "operaciones") + " · " + compacto(valorFiltrado)
    + " firmado" + (abiertas ? " · " + abiertas + " aún sin contratar" : "");

  const vacio = document.getElementById("vacio");
  vacio.hidden = filas.length > 0;
  if (!filas.length){
    /* Un cero tiene que decir POR QUE. En este tablero un cero se lee como "no hay
       contratación del sismo", que es una afirmación fuerte: si en realidad es que
       el filtro no da o que el dato no viaja en el archivo, hay que decirlo. */
    const grupo = document.getElementById("f-grupo").value;
    const niv = document.getElementById("f-nivel").value;
    const ent = document.getElementById("f-entidad").value;
    const busq = document.getElementById("f-texto").value.trim();
    vacio.textContent =
      busq
        ? `Ninguna operación coincide con "${busq}". Se busca en el objeto, la entidad, el `
          + "contratista y los números de proceso y de contrato."
      : ent
        /* No todas las entidades del desplegable están vigiladas: 83 del padrón son de
           otras regiones —Pasto, Honda, el Meta— y entraron porque un barrido encontró
           contratación suya, no porque se las siga. La prueba no es estar en el padrón,
           que también las incluye, sino no ser del grupo "Fuera del Valle". */
        ? (!(PADRON.find(e => e.entidad === ent) || {}).grupo
           || (PADRON.find(e => e.entidad === ent) || {}).grupo !== "Fuera del Valle"
            ? "Esa entidad está vigilada y no tiene operaciones que cumplan los demás "
              + "filtros: no ha publicado nada que encaje, no es que no se la mire."
            : "Esa entidad no es de Cali ni del Valle. Aparece porque un barrido nacional "
              + "encontró contratación suya que menciona una urgencia; para verla, cambie "
              + "el filtro de relación a «Otra emergencia» o el de territorio.")
      : grupo === "UNGRD"
        ? "La UNGRD y el FNGRD no han publicado contratación en la ventana de seguimiento. "
          + "Se consultan en cada corrida por NIT: el cero es un hallazgo, no un vacío del "
          + "monitoreo."
      : niv === "Contexto" || niv === "todos"
        ? "De la contratación corriente solo viaja en el archivo la de Cali, la Gobernación, "
          + "sus descentralizadas y la UNGRD. Con el territorio seleccionado no hay nada que "
          + "listar; los totales completos están en el padrón, al pie."
      : grupo === "territorial"
        ? "Todavía no hay contratación relacionada con el sismo en Cali ni en el Valle del "
          + "Cauca. SECOP publica con alrededor de un día de rezago."
        : "Ninguna operación cumple los filtros actuales.";
  }

  const t = trozo("tabla", filas);
  pintarPaginacion("pag-tabla", "tabla", t, filas.length, pintarTabla);

  cuerpo.innerHTML = t.filas.map(o => {
    const est = o.abierta
      ? `<span class="est est-abierta">Abierta</span>`
      : `<span class="est est-firmada">Contratada</span>`;
    /* Las dos referencias cuando existen: la entidad numera distinto el proceso
       y el contrato (…010.32.1.653 contra …010.26.1.653) y quien busca en SECOP
       puede llegar por cualquiera de las dos. */
    const refs = [o.proceso, o.contrato].filter(Boolean)
      .map(r => `<span class="ref" title="Número de ${r.tipo.toLowerCase()} en SECOP">${esc(r.referencia || r.id)}</span>`).join("");
    const enlaces = [o.contrato, o.proceso].filter(r => r && r.url)
      .map(r => `<a class="boton boton-secop" href="${esc(r.url)}" target="_blank" rel="noopener">${r.tipo === "Contrato" ? "Contrato" : "Proceso"}</a>`).join("");
    return `
    <tr>
      <td class="col-est" data-etq="Estado">${est}
        <div class="menor">${esc(o.fecha)}</div>
        ${o.huerfana ? '<div class="menor aviso" title="El contrato se firmó pero la entidad no publicó el proceso que lo convocó">sin proceso publicado</div>' : ""}
        ${o.novedad ? `<div class="menor"><span class="nuevo">nuevo</span></div>` : ""}</td>
      <td class="col-que" data-etq="Qué y quién">
        <div class="ent">${esc(o.entidad)}</div>
        <div class="obj" title="${esc(o.objeto)}">${esc(o.objeto)}</div>
        <div class="menor pie">${esc(o.grupo)} · ${esc(o.modalidad)}${o.justificacion ? " · " + esc(o.justificacion) : ""}</div>
        <div class="refs">${refs}</div></td>
      <td class="num" data-etq="Valor">${esc(pesos(o.valor))}
        <div class="menor">${o.firmado ? "valor firmado" : "precio base"}</div>
        ${o.duracion && !o.duracion.startsWith("0 ") ? `<div class="menor">${esc(o.duracion)}</div>` : ""}</td>
      <td data-etq="Contratista">${o.proveedor
        ? esc(o.proveedor)
        : '<span class="menor">aún sin contratista</span>'}</td>
      <td data-etq="Relación"><span class="etiqueta ${claseNivel(o.nivel)}"
          title="${esc(nivelLargo(o.nivel))}">${esc(nivelCorto(o.nivel))}</span>
        ${o.revisada ? `<div class="revisada" title="Lo decidió una persona, no el clasificador automático">✓ revisado${o.revisionRevisor ? " · " + esc(o.revisionRevisor) : ""}${o.revisionFecha ? " · " + esc(o.revisionFecha) : ""}</div>` : ""}
        <div class="menor">${esc(o.motivo)}</div></td>
      <td class="col-enl" data-etq="SECOP">${enlaces || '<span class="menor">sin enlace</span>'}</td>
    </tr>`;
  }).join("");
}

/* ------------------------------------------------------------------ *
 * Sección exclusiva: SECOP I y UNGRD                                  *
 * ------------------------------------------------------------------ */
const etiquetaPlataforma = p =>
  `<span class="plat ${p === "SECOP I" ? "plat-1" : "plat-2"}">${esc(p || "—")}</span>`;






function pintarCambios(){
  const cambios = (LOCAL && LOCAL.cambios) || [];
  document.getElementById("n-cambios").textContent = cambios.length;
  document.querySelector("#tabla-cambios tbody").innerHTML = cambios.length
    ? cambios.slice().reverse().slice(0, 200).map(c => `
      <tr><td>${esc(c.fecha_deteccion)}</td><td>${esc(c.fuente)}</td><td>${esc(c.identificador)}</td>
      <td>${esc(c.campo)}</td><td>${esc(String(c.valor_anterior).slice(0, 60))}</td>
      <td>${esc(String(c.valor_nuevo).slice(0, 60))}</td></tr>`).join("")
    : `<tr><td colspan="6" class="sub">${LOCAL
        ? "Todavía no se han detectado modificaciones sobre registros ya conocidos."
        : "Esta copia del tablero no trae historial embebido. Los datos en vivo de arriba "
          + "funcionan igual; el registro de modificaciones lo produce colector.py al ejecutarse."
      }</td></tr>`;
}


/* Una sola vista: no hay pestanas que sincronizar ni secciones que pintar aparte.
   SECOP I, la UNGRD y el resto del pais eran bloques propios y ahora son estados
   del filtro; el padron sigue siendo su propio bloque porque una entidad que no
   ha contratado nada no tiene ninguna operacion que mostrar en la tabla. */
function pintarTodo(){
  llenarFiltroEntidades();
  pintarPortada(); pintarKpis(); pintarGraficos();
  pintarAlertas(); pintarTabla(); pintarPadron(); pintarCambios(); pintarSello();
}

/* ------------------------------------------------------------------ *
 * Ciclo de actualización                                              *
 * ------------------------------------------------------------------ */
function estado(texto, clase){
  document.getElementById("mensaje-estado").textContent = texto;
  document.getElementById("punto").className = "punto" + (clase ? " " + clase : "");
}

async function cargar(){
  const boton = document.getElementById("btn-refrescar");
  boton.disabled = true;
  PROCEDENCIA = { estado: "cargando", detalle: "", horas: null };
  pintarFuente();
  estado("Cargando los datos de la última recolección…", "cargando");
  try{
    /* cache: "no-store" es indispensable: sin esto el navegador reutiliza la
       respuesta anterior y el botón devuelve datos viejos. */
    const r = await fetch(RUTA_DATOS + "?v=" + Date.now(), { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status + " al pedir " + RUTA_DATOS);
    LOCAL = await r.json();

    DATOS = LOCAL.registros || [];
    PADRON = LOCAL.padron || [];
    NOVEDADES = LOCAL.novedades || {};
    CFG.inicio = LOCAL.fecha_inicio || CFG.inicio;
    CFG.evento = LOCAL.fecha_evento || CFG.evento;

    /* El sello no lleva huso: el navegador lo lee como hora local. Si quien
       consulta no está en Colombia, la resta puede salir negativa y el semáforo
       anunciaba 'hace -5 horas'. Se acota en cero: la antigüedad nunca es menos
       que nada. */
    const t = Date.parse(String(LOCAL.generado).replace(" ", "T"));
    PROCEDENCIA = { estado: "archivo", detalle: "",
                    horas: isNaN(t) ? null : Math.max(0, Math.round((Date.now() - t) / 3600000)) };

    llenarTipos();
    pintarTitulos();
    pintarTodo();
    estado(`${DATOS.length} registros · recolección del ${LOCAL.generado}`, "");
  }catch(e){
    console.error(e);
    const local = location.protocol === "file:";
    PROCEDENCIA = { estado: "sin-datos", horas: null, detalle: local
      ? "Al abrir el archivo con doble clic, el navegador bloquea la lectura de "
        + "datos/tablero.json. Use la dirección publicada en GitHub Pages."
      : e.message };
    pintarFuente();
    estado(PROCEDENCIA.detalle, "error");
  }finally{
    boton.disabled = false;
  }
}

/* El desplegable de tipos se llena con lo que traiga el padrón: si mañana
   aparece una clase de entidad que hoy no existe, sale sola. */
/* Llena el desplegable de entidad. El nombre dice "llenarFiltro" a proposito: se
   llamaba pintarEntidades y en la unificacion del 19-ago-2026 se borro creyendo que
   pintaba una de las secciones que se estaban eliminando. El filtro quedo con una
   sola opcion, "Todas las entidades", y sin manera de elegir ninguna.

   Se listan las entidades ALCANZABLES por algun filtro (listable), no solo las que
   tienen contratacion relacionada: si el usuario pone el nivel en ordinaria, las
   entidades de esa vista tienen que poder elegirse. Son 119; las 341 del padron no,
   porque 27 no han contratado nada y elegirlas daria siempre una tabla vacia. */
function llenarFiltroEntidades(){
  const sel = document.getElementById("f-entidad");
  if (!sel) return;
  const previo = sel.value;
  const ents = [...new Set(DATOS.filter(listable).map(r => r.entidad).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b, "es"));
  sel.innerHTML = '<option value="">Todas las entidades</option>'
    + ents.map(e => `<option${e === previo ? " selected" : ""}>${esc(e)}</option>`).join("");
}

function llenarTipos(){
  const sel = document.getElementById("fp-tipo");
  const previo = sel.value;
  sel.innerHTML = '<option value="">Todos los tipos</option>';
  [...new Set(PADRON.map(e => e.tipo))].sort((a, b) => a.localeCompare(b, "es"))
    .forEach(t => {
      const o = document.createElement("option");
      o.value = t; o.textContent = t; o.selected = (t === previo); sel.append(o);
    });
}

function pintarTitulos(){
  document.getElementById("titulo-kpis").textContent =
    "Detalle por nivel de gobierno · Cali, Valle del Cauca y UNGRD desde el "
    + CFG.inicio.split("-").reverse().join("/");
}

function descargarCsv(){
  const filas = filtrados();
  const cols = ["plataforma","tipo","operacion","id","referencia","fecha","etiqueta_fecha","entidad","nit","departamento",
                "ciudad","grupo","es_ungrd","objeto","modalidad","justificacion","valor",
                "fecha_inicio","fecha_fin","duracion","proveedor","estado","ambito","nivel",
                "motivo","url"];
  const csv = [cols.join(";")].concat(filas.map(r =>
    cols.map(c => `"${String(r[c] ?? "").replace(/"/g, '""').replace(/\r?\n/g, " ")}"`).join(";")
  )).join("\r\n");
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "contratacion_urgencia_manifiesta_" + new Date().toISOString().slice(0,10) + ".csv";
  a.click();
  URL.revokeObjectURL(a.href);
}

document.getElementById("btn-refrescar").addEventListener("click", cargar);
document.getElementById("btn-csv").addEventListener("click", descargarCsv);
["f-texto","f-grupo","f-nivel","f-tipo","f-revision","f-novedad","f-entidad","f-plataforma"].forEach(id =>
  document.getElementById(id).addEventListener("input",
    () => { paginas.tabla = 1; pintarTabla(); }));

/* El padron se repinta entero al filtrar y al paginar, asi que la escucha va en el
   contenedor y no en cada fila: delegar evita volver a enganchar 341 escuchas. */
document.getElementById("secciones-padron").addEventListener("click", ev => {
  const fila = ev.target.closest(".fila-entidad");
  if (!fila || ev.target.closest("a")) return;
  const ent = fila.dataset.entidad;
  if (padronAbierto.has(ent)) padronAbierto.delete(ent); else padronAbierto.add(ent);
  pintarPadron();
});
document.getElementById("secciones-padron").addEventListener("keydown", ev => {
  if (ev.key !== "Enter" && ev.key !== " ") return;
  const fila = ev.target.closest(".fila-entidad");
  if (!fila) return;
  ev.preventDefault();
  fila.click();
});

["fp-texto","fp-via","fp-tipo","fp-grupo","fp-actividad"].forEach(id =>
  document.getElementById(id).addEventListener("input",
    () => { paginas.padron = 1; pintarPadron(); }));
document.querySelectorAll("#tabla th[data-col]").forEach(th =>
  th.addEventListener("click", () => {
    const col = th.dataset.col;
    orden = { col, asc: orden.col === col ? !orden.asc : false };
    paginas.tabla = 1;
    pintarTabla();
  }));

/* El sello se recalcula tras cada carga: las novedades se cuentan sobre los
   registros que el tablero realmente muestra, no sobre el tamaño de la bitácora.
   La bitácora puede conservar identificadores de barridos ya retirados, y usar su
   tamaño hacía que el sello anunciara más novedades que registros descargados. */
function pintarSello(){
  if (!LOCAL) return;
  const c = LOCAL.corrida_anterior || {};
  /* Las tres fuentes, como en la portada. Sumar solo dos hacia que el sello
     dijera 800 y la portada 808 a diez centimetros de distancia. */
  const nuevos = (Number(c.nuevos_contratos) || 0) + (Number(c.nuevos_procesos) || 0)
                + (Number(c.nuevos_secop1) || 0);
  const partes = ["recolección: " + LOCAL.generado];
  if (nuevos) partes.push(nuevos + " registros nuevos");
  if (Number(c.cambios)) partes.push(c.cambios + " modificaciones");
  const recientes = DATOS.filter(r => {
    if (!listable(r)) return false;
    const d = diasDesde(NOVEDADES[r.id]);
    return d !== null && d <= 7;
  }).length;
  /* Solo si informa: mientras el sismo sea reciente, "aparecidos en los ultimos
     7 dias" es el tablero entero y no dice nada. */
  const listables = DATOS.filter(listable).length;
  if (recientes && recientes < listables * 0.9)
    partes.push(recientes + " aparecidos en los últimos 7 días");
  document.getElementById("sello-local").textContent = partes.join(" · ");
}

cargar();
