"use strict";

/* Tablero de contratación · sismo del 10 de agosto de 2026
 *
 * Este archivo SOLO pinta. Los datos llegan ya consultados y clasificados en
 * datos/tablero.json, que produce colector.py y GitHub Actions regenera todos
 * los días a las 8:30.
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
const GRUPOS_ORDINARIA = ["Alcaldía de Cali", "Gobernación del Valle",
                          "Descentralizadas de Cali", "Descentralizadas de la Gobernación"];

const esRelevante = r => r.nivel === "Alta" || r.nivel === "Media";

/* Lo que el tablero puede llegar a listar con algún filtro. El resto de la
   contratación ordinaria se descarga y se guarda, pero no es alcanzable desde
   la interfaz, así que tampoco debe aparecer en los conteos: un número que no
   se puede abrir no le sirve a nadie. */
const listable = r => r.nivel !== "Contexto" || GRUPOS_ORDINARIA.includes(r.grupo);
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
const nacionales    = () => DATOS.filter(r => !cuenta(r) && esRelevante(r));

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
  const nuevosRel = DATOS.filter(r =>
    soloDia(NOVEDADES[r.id]) === dia && esRelevante(r) && cuenta(r));

  const cambios = (LOCAL.cambios || []).filter(x => soloDia(x.fecha_deteccion) === dia);

  const partes = [];
  if (nuevosRel.length){
    /* Contratos y procesos se cuentan aparte: un proceso solo tiene precio base
       y todavía puede no firmarse. Sumarlos en una sola cifra hacía que el total
       contradijera la lista que va justo debajo. */
    const cs = nuevosRel.filter(r => r.tipo === "Contrato");
    const ps = nuevosRel.filter(r => r.tipo === "Proceso");
    const vc = cs.reduce((s, r) => s + r.valor, 0);
    const vp = ps.reduce((s, r) => s + r.valor, 0);
    const trozos = [];
    if (cs.length) trozos.push(`<b>${frasePlural(cs.length, "contrato", "contratos")}</b>`
      + (vc ? ` por ${esc(pesos(vc))}` : ""));
    if (ps.length) trozos.push(`<b>${frasePlural(ps.length, "proceso", "procesos")}</b>`
      + (vp ? ` con precio base de ${esc(pesos(vp))}` : ""));
    partes.push(`Apareció contratación nueva relacionada con el sismo: ${trozos.join(" y ")}.`);
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
  const lista = nuevosRel
    .slice().sort((a, b) => b.valor - a.valor).slice(0, 5)
    .map(r => `<li><b>${esc(pesos(r.valor))}</b> · ${esc(r.entidad)}
        <span class="menor">${esc(String(r.objeto).slice(0, 130))}</span></li>`).join("");

  el.className = "novedad" + (nuevosRel.length ? " hay" : "");
  el.innerHTML = `<div class="que">Novedades del ${esc(dia.split("-").reverse().join("/"))}`
    + `</div><p class="frase">${partes.join(" ")}</p>`
    + (lista ? `<ul>${lista}</ul>` : "");
}

function pintarPortada(){
  const rel = territoriales();
  const contratos = rel.filter(r => r.tipo === "Contrato");
  const procesos  = rel.filter(r => r.tipo === "Proceso");
  const valor = contratos.reduce((s, r) => s + r.valor, 0);
  const urgencia = rel.filter(r => norm(r.justificacion).includes("URGENCIA MANIFIESTA"));
  const fuera = DATOS.filter(r => !cuenta(r) && esRelevante(r));
  const dias = diasDesdeEvento();

  const partes = [];
  partes.push(`Han pasado <b>${frasePlural(dias, "día", "días")}</b> desde el sismo del `
            + `10 de agosto de 2026.`);

  if (!rel.length){
    partes.push(`En Cali y el Valle del Cauca <b>todavía no se ha identificado contratación `
              + `relacionada con la emergencia</b>.`);
  } else {
    const trozos = [];
    if (contratos.length) trozos.push(`<b>${frasePlural(contratos.length, "contrato", "contratos")}</b>`);
    if (procesos.length)  trozos.push(`<b>${frasePlural(procesos.length, "proceso", "procesos")}</b>`);
    const total = contratos.length + procesos.length;
    partes.push(`En Cali y el Valle del Cauca se ${total === 1 ? "ha" : "han"} identificado `
      + `${trozos.join(" y ")} ${total === 1 ? "relacionado" : "relacionados"} con la emergencia`
      + (valor ? `, por <b>${esc(pesos(valor))}</b>.` : `.`));
    if (urgencia.length){
      partes.push(`${urgencia.length === 1 ? "Uno se tramitó" : urgencia.length + " se tramitaron"}`
                + ` por <b>urgencia manifiesta</b>, la figura que permite contratar sin `
                + `convocatoria previa.`);
    }
  }

  if (fuera.length){
    partes.push(`Fuera del Valle hay ${frasePlural(fuera.length, "registro relacionado",
      "registros relacionados")}, que se muestran aparte y no suman en estas cifras.`);
  }

  document.getElementById("titular").innerHTML = partes.join(" ");

  const cifras = [
    [contratos.length, "contratos relacionados<br>en Cali y el Valle"],
    [compacto(valor), "valor de esos contratos"],
    [procesos.length, "procesos abiertos<br>aún sin contrato"],
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

  /* El colector corre en la nube todos los días a las 8:30 y publica. Si la
     recolección es de hace más de dos días, algo se atascó y hay que decirlo:
     una cifra vieja presentada sin fecha se lee como si fuera de hoy. */
  const horas = PROCEDENCIA.horas;
  const vieja = horas !== null && horas > 48;
  luz.className = "luz " + (vieja ? "vieja" : "viva");
  txt.innerHTML = `<b>Datos de la recolección del ${esc(LOCAL.generado)}</b>`
    + (horas !== null ? ` · hace ${horas < 24 ? horas + " horas" : Math.round(horas/24) + " días"}` : "")
    + `. El colector consulta SECOP I y SECOP II todos los días a las 8:30 y verifica la `
    + `cobertura antes de publicar.`
    + (vieja ? ` <b>Hace más de dos días que no se actualiza:</b> revise la pestaña Actions `
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

let entidadAbierta = null;

/* Agrupa por entidad. Solo entidades vigiladas: el resto del país no es objeto
   de este seguimiento y meterlo aquí volvería la tabla ilegible.

   Cuando los datos vienen del respaldo embebido no sirve contar sobre DATOS: en
   el HTML solo viaja una parte de la contratación ordinaria, porque embeberla
   toda haría el archivo inservible. En ese caso se usan las cifras agregadas
   que precalculó el colector, que sí cubren el universo completo. Contar sobre
   lo embebido daría un número menor sin avisar. */
let PADRON = [];

/* Las cifras SIEMPRE salen del padrón, nunca de contar los registros que viajan.
   No es lo mismo: el padrón cubre los 2.635 registros de la ventana, mientras
   que en el archivo solo viajan 1.024 —la contratación ordinaria de los 177
   municipios se queda fuera porque embeberla llevaría el archivo a decenas de
   megas—. Contar sobre lo que viaja mostraba 11 registros donde hay 1.540.
   Los registros sirven para el detalle de cada entidad, no para los totales. */
function agregarPorEntidad(){
  const detalle = new Map();
  for (const r of DATOS){
    if (!GRUPOS_VIGILADOS.includes(r.grupo)) continue;
    const k = r.entidad || "(sin nombre)";
    if (!detalle.has(k)) detalle.set(k, []);
    detalle.get(k).push(r);
  }
  return PADRON
    .filter(e => GRUPOS_VIGILADOS.includes(e.grupo))
    .map(e => {
      const filas = detalle.get(e.entidad) || [];
      return { ...e, filas, parcial: filas.length < e.n };
    });
}

function filtradosOrdinaria(){
  const txt = norm(document.getElementById("fo-texto").value.trim());
  const grupo = document.getElementById("fo-grupo").value;
  const orden = document.getElementById("fo-orden").value;
  let filas = agregarPorEntidad();
  if (grupo) filas = filas.filter(e => e.grupo === grupo);
  if (txt) filas = filas.filter(e => norm(e.entidad + " " + e.nit).includes(txt));
  const clave = orden === "n" ? "n" : orden === "rel" ? "rel" : "valor";
  return filas.sort((a, b) => b[clave] - a[clave] || b.valor - a.valor);
}

function pintarOrdinaria(){
  const todas = agregarPorEntidad();
  const registros = todas.reduce((s, e) => s + e.n, 0);
  const valor = todas.reduce((s, e) => s + e.valor, 0);
  const rel = todas.reduce((s, e) => s + e.rel, 0);
  const porcentaje = registros ? (rel / registros * 100) : 0;

  tarjetas("kpis-ordinaria", [
    ["Registros en total", registros, "desde el 10 de agosto"],
    ["Valor contratado", compacto(valor), "solo contratos firmados"],
    ["Entidades que contrataron", todas.length, "de las vigiladas"],
    ["Relacionados con el sismo", rel,
     registros ? porcentaje.toFixed(1).replace(".", ",") + " % del total" : "—"]
  ]);

  const filas = filtradosOrdinaria();
  document.getElementById("conteo-ordinaria").textContent =
    filas.length + (filas.length === 1 ? " entidad" : " entidades");

  const vacio = document.getElementById("vacio-ordinaria");
  vacio.hidden = filas.length > 0;
  if (!filas.length) vacio.textContent = "Ninguna entidad coincide con el filtro.";

  const max = Math.max(...filas.map(e => e.valor), 1);
  const t = trozo("ordinaria", filas);
  pintarPaginacion("pag-ordinaria", "ordinaria", t, filas.length, pintarOrdinaria);

  document.querySelector("#tabla-ordinaria tbody").innerHTML = t.filas.map(e => {
    const abierta = entidadAbierta === e.entidad;
    const fila = `
      <tr class="abrible" data-entidad="${esc(e.entidad)}">
        <td data-etq="Entidad">${esc(e.entidad)}
          <div class="menor">NIT ${esc(e.nit) || "—"}${abierta ? " · pulse para cerrar" : ""}</div></td>
        <td data-etq="Grupo"><span class="menor">${esc(e.grupo)}</span></td>
        <td class="num" data-etq="Registros">${e.n}</td>
        <td class="num" data-etq="Valor">${esc(pesos(e.valor))}
          <div class="barra-mini"><i style="width:${(e.valor / max * 100).toFixed(1)}%"></i></div></td>
        <td data-etq="Del sismo">${e.rel
          ? `<span class="etiqueta n-Alta">${e.rel}</span>`
          : '<span class="menor">ninguno</span>'}</td>
      </tr>`;
    if (!abierta) return fila;
    return fila + `
      <tr class="detalle-entidad"><td colspan="5">${e.filas.length
        ? detalleEntidad(e)
        : `<div class="menor" style="padding:10px 2px">Esta entidad tiene
             <b>${e.n}</b> registros en la ventana, pero su contratación ordinaria no viaja
             en el archivo del tablero: son 2.635 registros en total y embeberlos todos lo
             haría inservible. Las cifras de la fila son completas; el detalle registro por
             registro está en <code>datos/contratos.csv</code> y <code>datos/procesos.csv</code>
             del repositorio.</div>`}</td></tr>`;
  }).join("");

  document.querySelectorAll("#tabla-ordinaria tr.abrible").forEach(tr =>
    tr.addEventListener("click", () => {
      entidadAbierta = entidadAbierta === tr.dataset.entidad ? null : tr.dataset.entidad;
      pintarOrdinaria();
    }));
}

/* Detalle de una entidad: sus registros, los del sismo primero. Se limita a 60
   porque una alcaldia puede tener cientos y la tabla dejaria de leerse. */
function detalleEntidad(e){
  const filas = e.filas.slice()
    .sort((a, b) => (esRelevante(b) - esRelevante(a)) || (b.valor - a.valor))
    .slice(0, POR_PAGINA);
  const oculto = e.filas.length - filas.length;
  const faltan = e.n - e.filas.length;
  return `
    <div class="tabla-envoltura">
      <table>
        <thead><tr><th>Fecha</th><th>Tipo</th><th>Objeto</th>
          <th class="num">Valor</th><th>Contratista</th><th>Relación</th><th></th></tr></thead>
        <tbody>${filas.map(r => `
          <tr>
            <td class="col-fecha">${esc(r.fecha)}</td>
            <td><span class="etiqueta t-${r.tipo}">${esc(r.tipo)}</span>
              <div class="menor">${etiquetaPlataforma(r.plataforma)}</div></td>
            <td class="objeto">${esc(String(r.objeto).slice(0, 220))}</td>
            <td class="num">${esc(pesos(r.valor))}</td>
            <td>${esc(r.proveedor) || '<span class="menor">sin adjudicar</span>'}</td>
            <td><span class="etiqueta ${claseNivel(r.nivel)}" title="${esc(nivelLargo(r.nivel))}">${esc(nivelCorto(r.nivel))}</span></td>
            <td>${r.url ? `<a class="boton boton-secop" href="${esc(r.url)}" target="_blank"
                 rel="noopener">Ver</a>` : ""}</td>
          </tr>`).join("")}</tbody>
      </table>
    </div>
    ${oculto > 0 ? `<div class="menor" style="padding:8px 2px">Se muestran los 20 de mayor
      valor; hay ${oculto} más en el archivo.</div>` : ""}
    ${faltan > 0 ? `<div class="menor" style="padding:8px 2px">De los <b>${e.n}</b> registros
      de esta entidad, ${faltan} son contratación ordinaria que no viaja en el archivo del
      tablero. Están en los CSV del repositorio.</div>` : ""}`;
}

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

function pintarPadron(){
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
          <tr class="${enSilencio(e) ? "silenciosa" : ""}">
            <td data-etq="Entidad"><b>${esc(e.entidad)}</b>
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
          </tr>`).join("")}</tbody>
      </table>
    </div>`;
}

function cambiarVista(cual){
  for (const v of ["sismo", "ordinaria", "padron"]){
    document.getElementById("vista-" + v).hidden = (v !== cual);
    document.getElementById("tab-" + v).setAttribute("aria-selected", String(v === cual));
  }
  if (cual === "ordinaria") pintarOrdinaria();
  if (cual === "padron") pintarPadron();
}

function pintarKpis(){
  const rel = territoriales();
  const contratos = rel.filter(r => r.tipo === "Contrato");
  const procesos  = rel.filter(r => r.tipo === "Proceso");
  const total = contratos.reduce((s, r) => s + r.valor, 0);
  const porGrupo = g => rel.filter(r => r.grupo === g).length;

  const tarjetas = [
    ["Contratos relacionados", contratos.length,
     rel.filter(r => r.nivel === "Alta" && r.tipo === "Contrato").length + " con relación alta"],
    ["Valor contratado", compacto(total), "Cali, Valle y UNGRD"],
    ["Procesos de contratación", procesos.length, "publicados, aún sin contrato"],
    ["Alcaldía de Cali", porGrupo("Alcaldía de Cali"), "nivel central"],
    ["Descentralizadas de Cali", porGrupo("Descentralizadas de Cali"),
     "EMCALI, Metro Cali, redes de salud…"],
    ["Gobernación del Valle", porGrupo("Gobernación del Valle"), "nivel central"],
    ["Descentralizadas de la Gobernación", porGrupo("Descentralizadas de la Gobernación"),
     "HUV, INDERVALLE, ACUAVALLE…"],
    ["Municipios del Valle", porGrupo("Otras entidades del Valle"), "y sus entidades"],
    ["UNGRD y FNGRD", porGrupo("UNGRD"), "respuesta nacional al desastre"]
  ];
  document.getElementById("kpis").innerHTML = tarjetas.map(([e, v, p]) =>
    `<div class="kpi${(v === 0 || v === "$ 0") ? " cero" : ""}">
       <div class="etq">${esc(e)}</div><div class="val">${esc(v)}</div><div class="pie">${esc(p)}</div>
     </div>`).join("");

  const nac = nacionales();
  const vnac = nac.filter(r => r.tipo === "Contrato").reduce((s, r) => s + r.valor, 0);
  const otras = DATOS.filter(r => r.nivel === "Otra urgencia");
  const votras = otras.filter(r => r.tipo === "Contrato").reduce((s, r) => s + r.valor, 0);
  const lineas = [];

  if (nac.length){
    lineas.push(`<b>Relacionados con el sismo:</b> ${nac.filter(r => r.tipo === "Contrato").length}
      contratos (<b>${esc(compacto(vnac))}</b>) y ${nac.filter(r => r.tipo === "Proceso").length}
      procesos de otras regiones del país.`);
  }
  if (otras.length){
    lineas.push(`<b>Urgencia manifiesta por otras causas:</b>
      ${otras.filter(r => r.tipo === "Contrato").length} contratos
      (<b>${esc(compacto(votras))}</b>) y ${otras.filter(r => r.tipo === "Proceso").length} procesos.
      Sin relación con el sismo — otras emergencias del país. Sirven para dimensionar cuánta
      urgencia manifiesta se declara por motivos distintos.`);
  }
  document.getElementById("bloque-nacional").innerHTML = lineas.length
    ? lineas.map(l => `<div style="margin:4px 0">${l}</div>`).join("")
      + `<div style="margin-top:8px">Nada de esto cuenta en los indicadores de arriba.
         Para verlo, elija <em>Fuera del Valle</em> o el nivel <em>Otra urgencia</em> en los filtros.</div>`
    : "Sin registros relacionados fuera del Valle del Cauca.";
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

function pintarGraficos(){
  const rel = territoriales();
  barras("graf-entidades", agrupar(rel.filter(r => r.tipo === "Contrato"), "entidad", true).slice(0, 8), compacto);
  barras("graf-dias", agrupar(rel, "fecha", false).sort((a, b) => a[0] < b[0] ? -1 : 1).slice(-14), v => v);
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

function filtrados(){
  const txt = norm(document.getElementById("f-texto").value.trim());
  const grupo = document.getElementById("f-grupo").value;
  const niv = document.getElementById("f-nivel").value;
  const tipo = document.getElementById("f-tipo").value;
  const nov = document.getElementById("f-novedad").value;
  const ent = document.getElementById("f-entidad").value;
  const plat = document.getElementById("f-plataforma").value;

  return DATOS.filter(r => {
    // La contratación ordinaria solo se muestra para la Alcaldía de Cali y la
    // Gobernación del Valle, y solo cuando se pide expresamente en el filtro.
    // La del resto de entidades se sigue descargando y guardando en los CSV
    // — es lo que permite reclasificar si se ajustan las palabras clave — pero
    // no se lista. Esto incluye a la UNGRD: se revisa entera, se muestra solo
    // lo del sismo.
    if (!listable(r)) return false;
    if (r.nivel === "Contexto" && niv !== "Contexto") return false;
    if (plat && r.plataforma !== plat) return false;
    if (nov){
      const d = diasDesde(NOVEDADES[r.id]);
      if (d === null || d > Number(nov)) return false;
    }
    if (grupo === "territorial" && !cuenta(r)) return false;
    if (grupo !== "territorial" && grupo !== "todos" && r.grupo !== grupo) return false;
    if (niv === "rel" && !esRelevante(r)) return false;
    if (niv !== "rel" && niv !== "todos" && r.nivel !== niv) return false;
    if (tipo && r.tipo !== tipo) return false;
    if (ent && r.entidad !== ent) return false;
    if (txt && !norm([r.objeto, r.entidad, r.proveedor, r.id].join(" ")).includes(txt)) return false;
    return true;
  }).sort((a, b) => {
    const x = a[orden.col], y = b[orden.col];
    const cmp = (typeof x === "number" && typeof y === "number") ? x - y : String(x).localeCompare(String(y));
    return orden.asc ? cmp : -cmp;
  });
}

function celdaDuracion(r){
  const partes = [];
  if (r.fecha_inicio) partes.push(`Inicio ${esc(r.fecha_inicio)}`);
  if (r.fecha_fin) partes.push(`Fin ${esc(r.fecha_fin)}`);
  const dur = r.duracion ? `<div><b>${esc(r.duracion)}</b></div>` : "";
  return dur + (partes.length ? `<div class="menor">${partes.join("<br>")}</div>`
                              : '<div class="menor">sin fechas publicadas</div>');
}

/* La leyenda explica los cuatro niveles con palabras, no con etiquetas. Va
   junto a la tabla porque es ahí donde el lector se topa con ellas. */
function pintarLeyenda(){
  const el = document.getElementById("leyenda-niveles");
  if (!el) return;
  el.innerHTML = Object.entries(NIVELES).map(([n, d]) =>
    `<div><span class="etiqueta ${claseNivel(n)}">${esc(d.corto)}</span>
       <span>${esc(d.largo)}</span></div>`).join("");
}

function pintarTabla(){
  pintarLeyenda();
  const filas = filtrados();
  const cuerpo = document.querySelector("#tabla tbody");
  const valorFiltrado = filas.reduce((s, r) => s + (r.tipo === "Contrato" ? r.valor : 0), 0);
  document.getElementById("conteo-filtro").textContent =
    filas.length + " registros · " + compacto(valorFiltrado);

  const vacio = document.getElementById("vacio");
  vacio.hidden = filas.length > 0;
  if (!filas.length){
    const grupo = document.getElementById("f-grupo").value;
    const niv = document.getElementById("f-nivel").value;
    vacio.textContent =
      niv === "Contexto"
        ? "La contratación ordinaria solo se muestra para la Alcaldía de Cali y la Gobernación "
          + "del Valle. Con el grupo seleccionado no hay registros."
      : grupo === "territorial"
        ? "Todavía no hay contratos ni procesos relacionados con el sismo en Cali ni en el Valle "
          + "del Cauca. SECOP publica con alrededor de un día de rezago."
        : "Sin registros con los filtros actuales.";
  }

  const t = trozo("tabla", filas);
  pintarPaginacion("pag-tabla", "tabla", t, filas.length, pintarTabla);

  cuerpo.innerHTML = t.filas.map(r => `
    <tr>
      <td class="col-fecha" data-etq="Fecha">${esc(r.fecha)}
        <div class="menor">${esc(r.etiqueta_fecha || "")}</div></td>
      <td data-etq="Tipo"><span class="etiqueta t-${r.tipo}">${esc(r.tipo)}</span>
        <div class="menor">${etiquetaPlataforma(r.plataforma)}</div>
        ${NOVEDADES[r.id] ? `<div class="menor"><span class="nuevo">nuevo</span>
          visto el ${esc(NOVEDADES[r.id])}</div>` : ""}</td>
      <td data-etq="Entidad">${esc(r.entidad)}
        <div class="menor">${esc(r.ciudad || r.departamento)} · ${esc(r.grupo)}</div></td>
      <td class="objeto" data-etq="Objeto">${esc(r.objeto)}</td>
      <td class="num" data-etq="Valor">${esc(pesos(r.valor))}
        <div class="menor">${esc(r.tipo === "Proceso" ? "precio base" : "valor del contrato")}</div></td>
      <td class="col-dur" data-etq="Duración">${celdaDuracion(r)}</td>
      <td data-etq="Contratista">${esc(r.proveedor) || '<span class="menor">sin adjudicar</span>'}</td>
      <td data-etq="Modalidad">${esc(r.modalidad)}
        <div class="menor">${esc(r.justificacion)}</div>
        <div class="menor">${esc(r.estado)}</div></td>
      <td data-etq="Relación"><span class="etiqueta ${claseNivel(r.nivel)}"
          title="${esc(nivelLargo(r.nivel))}">${esc(nivelCorto(r.nivel))}</span>
        <div class="menor">${esc(r.motivo)}</div></td>
      <td data-etq="Enlace">${r.url
        ? `<a class="boton boton-secop" href="${esc(r.url)}" target="_blank" rel="noopener">Ver en SECOP</a>`
        : '<span class="menor">sin enlace</span>'}
        <div class="menor">${esc(r.id)}</div></td>
    </tr>`).join("");
}

/* ------------------------------------------------------------------ *
 * Sección exclusiva: SECOP I y UNGRD                                  *
 * ------------------------------------------------------------------ */
const etiquetaPlataforma = p =>
  `<span class="plat ${p === "SECOP I" ? "plat-1" : "plat-2"}">${esc(p || "—")}</span>`;

function tarjetas(destino, lista){
  document.getElementById(destino).innerHTML = lista.map(([e, v, p]) =>
    `<div class="kpi${(v === 0 || v === "$ 0") ? " cero" : ""}">
       <div class="etq">${esc(e)}</div><div class="val">${esc(v)}</div><div class="pie">${esc(p)}</div>
     </div>`).join("");
}

/* Filas de las tablas de la sección. La segunda columna cambia: en SECOP I
   interesa qué entidad contrató; en la UNGRD, siempre la misma entidad, lo que
   interesa es por cuál de las dos plataformas se tramitó. */
function filasSeccion(destinoTabla, destinoVacio, filas, segunda, mensajeVacio){
  const vacio = document.getElementById(destinoVacio);
  vacio.hidden = filas.length > 0;
  if (!filas.length) vacio.textContent = mensajeVacio;

  document.querySelector("#" + destinoTabla + " tbody").innerHTML = filas
    .slice()
    .sort((a, b) => b.valor - a.valor)
    .slice(0, 200)
    .map(r => `
      <tr>
        <td class="col-fecha" data-etq="Fecha">${esc(r.fecha) || "<span class='menor'>sin fecha</span>"}
          <div class="menor">${esc(r.etiqueta_fecha || "")}</div></td>
        <td data-etq="${segunda === "entidad" ? "Entidad" : "Plataforma"}">
          ${segunda === "entidad"
            ? esc(r.entidad) + `<div class="menor">${esc(r.ciudad || r.departamento)}</div>`
            : etiquetaPlataforma(r.plataforma)
              + `<div class="menor">${esc(r.entidad)}</div>`}
          <div class="menor"><span class="etiqueta t-${r.tipo}">${esc(r.tipo)}</span>
            ${NOVEDADES[r.id] ? ` <span class="nuevo">nuevo</span>` : ""}</div></td>
        <td class="objeto" data-etq="Objeto">${esc(r.objeto)}</td>
        <td class="num" data-etq="Valor">${esc(pesos(r.valor))}</td>
        <td data-etq="Contratista">${esc(r.proveedor) || '<span class="menor">sin adjudicar</span>'}</td>
        <td data-etq="Modalidad">${esc(r.modalidad)}
          <div class="menor">${esc(r.justificacion)}</div>
          <div class="menor">${esc(r.estado)}</div></td>
        <td data-etq="Relación"><span class="etiqueta ${claseNivel(r.nivel)}"
            title="${esc(nivelLargo(r.nivel))}">${esc(nivelCorto(r.nivel))}</span>
          <div class="menor">${esc(r.motivo)}</div></td>
        <td data-etq="Enlace">${r.url
          ? `<a class="boton boton-secop" href="${esc(r.url)}" target="_blank" rel="noopener">Ver</a>`
          : '<span class="menor">sin enlace</span>'}
          <div class="menor">${esc(r.id)}</div></td>
      </tr>`).join("");
}

/* Las dos secciones muestran únicamente lo relacionado con el sismo: relación
   alta o media. Lo demás se sigue descargando y guardando en los CSV —es lo que
   permite reclasificar sin volver a pedirle nada a la API— pero no se muestra.
   Quedan fuera a propósito la contratación ordinaria y la urgencia manifiesta
   declarada por otras causas o por calamidades anteriores al 10 de agosto. */
function pintarSecopI(){
  const filas = DATOS.filter(r => r.plataforma === "SECOP I" && esRelevante(r));
  const terr = filas.filter(cuenta);
  const contratos = filas.filter(r => r.tipo === "Contrato");
  const valorTerr = terr.filter(r => r.tipo === "Contrato").reduce((s, r) => s + r.valor, 0);
  const urgencia = filas.filter(r => norm(r.justificacion).includes("URGENCIA MANIFIESTA"));

  tarjetas("kpis-secop1", [
    ["Relacionados con el sismo", filas.length, "en toda la plataforma"],
    ["En Cali y el Valle", terr.length, "de esos registros"],
    ["Valor en el territorio", compacto(valorTerr), "contratos ya celebrados"],
    ["Con urgencia manifiesta", urgencia.length, "causal Literal A"]
  ]);

  filasSeccion("tabla-secop1", "vacio-secop1", filas, "entidad",
    "Sin contratos ni convenios relacionados con el sismo en SECOP I. La mayor parte de la "
    + "contratación actual se tramita por SECOP II; SECOP I se revisa porque sigue recibiendo "
    + "cargues y porque algunas entidades y regímenes especiales continúan publicando allí.");
}

function pintarUngrd(){
  const filas = DATOS.filter(r => r.es_ungrd && esRelevante(r));
  const contratos = filas.filter(r => r.tipo === "Contrato");
  const valor = contratos.reduce((s, r) => s + r.valor, 0);
  const enS1 = filas.filter(r => r.plataforma === "SECOP I").length;

  tarjetas("kpis-ungrd", [
    ["Relacionados con el sismo", filas.length, "UNGRD y FNGRD"],
    ["Valor contratado", compacto(valor), "contratos firmados"],
    ["Contratos", contratos.length, "el resto son procesos"],
    ["Por SECOP I", enS1, "el resto por SECOP II"]
  ]);

  filasSeccion("tabla-ungrd", "vacio-ungrd", filas, "plataforma",
    "La UNGRD y el FNGRD no registran todavía contratación relacionada con el sismo, "
    + "ni en SECOP I ni en SECOP II. Su contratación ordinaria del periodo se sigue "
    + "revisando, pero no se muestra aquí.");
}

function pintarEntidades(){
  const sel = document.getElementById("f-entidad");
  const previo = sel.value;
  const ents = [...new Set(DATOS.filter(esRelevante).map(r => r.entidad).filter(Boolean))].sort();
  sel.innerHTML = '<option value="">Todas las entidades</option>' +
    ents.map(e => `<option${e === previo ? " selected" : ""}>${esc(e)}</option>`).join("");
}

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

function pintarContadoresPestanas(){
  const sismo = DATOS.filter(r => cuenta(r) && esRelevante(r)).length;
  /* Del padrón, no de DATOS: el contador debe decir lo mismo que la pestaña. */
  const ordinaria = PADRON.filter(e => GRUPOS_VIGILADOS.includes(e.grupo))
                          .reduce((s, e) => s + e.n, 0);
  document.getElementById("n-tab-sismo").textContent = sismo ? `· ${sismo}` : "";
  document.getElementById("n-tab-ordinaria").textContent = ordinaria ? `· ${ordinaria}` : "";
  document.getElementById("n-tab-padron").textContent = PADRON.length ? `· ${PADRON.length}` : "";
}

function pintarTodo(){
  pintarContadoresPestanas();
  if (!document.getElementById("vista-ordinaria").hidden) pintarOrdinaria();
  pintarPortada(); pintarKpis(); pintarSecopI(); pintarUngrd(); pintarGraficos();
  pintarAlertas(); pintarEntidades(); pintarTabla(); pintarCambios(); pintarSello();
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

    const t = Date.parse(String(LOCAL.generado).replace(" ", "T"));
    PROCEDENCIA = { estado: "archivo", detalle: "",
                    horas: isNaN(t) ? null : Math.round((Date.now() - t) / 3600000) };

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
  const cols = ["plataforma","tipo","id","fecha","etiqueta_fecha","entidad","nit","departamento",
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
["f-texto","f-grupo","f-nivel","f-tipo","f-novedad","f-entidad","f-plataforma"].forEach(id =>
  document.getElementById(id).addEventListener("input",
    () => { paginas.tabla = 1; pintarTabla(); }));
["sismo","ordinaria","padron"].forEach(v =>
  document.getElementById("tab-" + v).addEventListener("click", () => cambiarVista(v)));
["fo-texto","fo-grupo","fo-orden"].forEach(id =>
  document.getElementById(id).addEventListener("input",
    () => { entidadAbierta = null; paginas.ordinaria = 1; pintarOrdinaria(); }));
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
  const nuevos = (Number(c.nuevos_contratos) || 0) + (Number(c.nuevos_procesos) || 0);
  const partes = ["recolección: " + LOCAL.generado];
  if (nuevos) partes.push(nuevos + " registros nuevos");
  if (Number(c.cambios)) partes.push(c.cambios + " modificaciones");
  const recientes = DATOS.filter(r => {
    if (!listable(r)) return false;
    const d = diasDesde(NOVEDADES[r.id]);
    return d !== null && d <= 7;
  }).length;
  if (recientes) partes.push(recientes + " aparecidos en los últimos 7 días");
  document.getElementById("sello-local").textContent = partes.join(" · ");
}

cargar();
