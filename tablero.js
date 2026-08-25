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
/* Entidades elegidas en el filtro. Vacio = todas, que es lo que dice el resumen.
   Es un Set y no el valor de un <select> porque ahora se pueden marcar varias. */
let ENTIDADES_SEL = new Set();
/* De mayor a menor valor: lo que más plata mueve se mira primero. */
let orden = { col: "valor", asc: false };

/* Cuándo apareció publicado cada registro, según la bitácora del colector.
   El tablero por sí solo no tiene memoria: consulta el estado actual, no sabe
   qué había ayer. Este mapa es lo que le permite señalar las novedades. */
let NOVEDADES = {};
/* La bitacora trae la deteccion con hora ("2026-08-12 20:06:54"), pero las
   corridas anteriores al 22-ago-2026 solo dejaron la fecha. Se admiten las dos
   formas: sin hora se toma medianoche, que es exactamente lo que hacia el tablero
   antes. El sufijo con T y sin zona obliga al navegador a leerlo en hora local;
   "2026-08-12" a secas se interpreta como UTC y en Colombia retrasaria cinco horas
   cada deteccion. */
const momento = fecha => {
  const s = String(fecha || "");
  if (!s) return null;
  const t = new Date(s.slice(0, 10) + "T" + (s.slice(11, 19) || "00:00:00")).getTime();
  return isNaN(t) ? null : t;
};
/* Las ventanas de dias siguen contando desde la medianoche de la deteccion, que
   es lo que hacian cuando la bitacora solo traia la fecha: si contaran horas
   rodantes, "ultimos 7 dias" pasaria a incluir detecciones de hace ocho dias por
   la tarde. Solo la ventana de 24 horas rueda, y para eso esta horasDesde. */
const diasDesde = fecha => {
  const t = momento(String(fecha || "").slice(0, 10));
  return t === null ? null : Math.floor((Date.now() - t) / 86400000);
};
/* Ventana rodante de verdad, para el filtro de las ultimas 24 horas: hay dos
   recolecciones diarias y "hoy" dejaba fuera la de anoche. Si el dato viene sin
   hora (JSON de antes del cambio) la cuenta arranca en medianoche y la opcion se
   comporta como "lo de hoy" hasta la siguiente recoleccion. */
const horasDesde = fecha => {
  const t = momento(fecha);
  return t === null ? null : Math.floor((Date.now() - t) / 3600000);
};

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
    /* Con su cifra: decir solo cuantas son deja fuera lo que mide el hallazgo. */
    const vf = fuera.filter(o => o.firmado).reduce((s, o) => s + o.valor, 0);
    partes.push(`Fuera del Valle hay ${frasePlural(fuera.length, "operación relacionada",
      "operaciones relacionadas")}` + (vf ? ` por <b>${esc(pesos(vf))}</b>` : "")
      + `, que no suman en estas cifras: el foco es Cali y el Valle. Se ven eligiendo `
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
  /* Los del sismo, no todos: el pie decia "5971 registros en total" bajo la tarjeta
     de "con registros del sismo", cuando 5971 es la contratacion entera de las 397
     entidades y los del sismo son 212. Se leia como un dato 28 veces mayor. */
  const registrosSismo = PADRON.reduce((s, e) => s + e.rel, 0);
  const registrosTodos = PADRON.reduce((s, e) => s + e.n, 0);
  const calladas = PADRON.filter(enSilencio).length;
  tarjetas("kpis-padron", [
    ["Entidades en el padrón", PADRON.length,
     nits + " NIT distintos · " + registrosTodos + " registros en total"],
    ["Por NIT en configuración", fijas, "se consultan siempre"],
    ["Por barrido territorial", PADRON.length - fijas, "aparecen por estar en el Valle"],
    ["Vigiladas sin contratar", calladas, "no han publicado nada desde el sismo"],
    ["Con registros del sismo", conSismo, registrosSismo + " registros del sismo entre ellas"]
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

  /* Una sola tabla. Antes iba partida en siete secciones por grupo; con el filtro
     de grupo al lado, la división sobraba y obligaba a recorrer toda la página.

     Primero las que tienen contratación DEL SISMO, que es lo que este tablero
     vigila; el resto detrás, por valor. Ordenando solo por valor contratado, la
     primera fila era una agencia del Meta con cero registros del sismo y $19.7 mm
     de contratación ordinaria: encabezaba el padrón algo ajeno a la emergencia.
     Las que no han contratado nada siguen estando, al final, que es justo para lo
     que existe el padrón. */
  const ordenadas = filas.slice().sort((a, b) =>
    (b.rel > 0) - (a.rel > 0)
    || b.rel - a.rel
    || b.valor - a.valor
    || b.n - a.n
    || a.entidad.localeCompare(b.entidad, "es"));
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


/* Lo relacionado con el sismo FUERA del Valle. No suma en ningun indicador -el foco
   es Cali y el Valle, decision del usuario- pero tampoco puede quedar escondido
   detras de un filtro: a 21-ago-2026 son 32 operaciones por $3.247 millones en el
   Eje Cafetero y Antioquia, un tercio de lo del Valle. Se muestra al pie del
   desglose, separado del total y rotulado. */
function resumenFueraDelValle(){
  const ops = operaciones(DATOS.filter(r => !cuenta(r) && esRelevante(r)));
  if (!ops.length) return "";
  const firmadas = ops.filter(o => o.firmado);
  const valor = firmadas.reduce((s, o) => s + o.valor, 0);
  const porDepto = new Map();
  ops.forEach(o => {
    const d = (o.jefe.departamento || "sin departamento").trim();
    const p = porDepto.get(d) || { n: 0, valor: 0 };
    p.n += 1;
    if (o.firmado) p.valor += o.valor;
    porDepto.set(d, p);
  });
  const deptos = [...porDepto.entries()].sort((a, b) => b[1].valor - a[1].valor || b[1].n - a[1].n);
  return `
    <div class="fuera-valle">
      <div class="fuera-cab">
        <span class="etq">Fuera del Valle · no suma en las cifras de arriba</span>
        <span class="fuera-tot">${frasePlural(ops.length, "operación", "operaciones")}
          · ${esc(compacto(valor))} firmados</span>
      </div>
      <p class="menor">Contratación de otras regiones que <b>nombra el sismo del 10 de agosto</b>.
        El tablero la detecta y la conserva, pero los indicadores cuentan solo Cali y el Valle.
        Para verla en detalle, elija <em>Fuera del Valle</em> en el filtro de territorio.</p>
      <ul class="deptos">
        ${deptos.map(([d, p]) => `<li><b>${esc(d)}</b>
           <span class="menor">${p.n} · ${esc(compacto(p.valor))}</span></li>`).join("")}
      </ul>
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
    </table>` + resumenFueraDelValle();
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
  const { txt, grupo, niv, nov, ents, plat } = ctx;

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
    /* Las opciones en horas ("24h", "48h", "72h") ruedan de verdad; las de dias
       cuentan por dia calendario. El sufijo distingue unas de otras. */
    const enHoras = nov.endsWith("h");
    const transcurrido = enHoras ? horasDesde(NOVEDADES[r.id]) : diasDesde(NOVEDADES[r.id]);
    if (transcurrido === null || transcurrido > parseInt(nov, 10)) return false;
  }
  if (grupo === "territorial" && !cuenta(r)) return false;
  if (grupo !== "territorial" && grupo !== "todos" && r.grupo !== grupo) return false;
  if (niv === "rel" && !esRelevante(r)) return false;
  if (niv !== "rel" && niv !== "todos" && r.nivel !== niv) return false;
  if (ents && ents.size && !ents.has(r.entidad)) return false;
  if (txt && !norm([r.objeto, r.entidad, r.proveedor, r.id, r.referencia].join(" ")).includes(txt)) return false;
  return true;
}

/* `sobre` permite pedir el mismo contexto con un filtro cambiado. Lo usa el mapa
   del pais, que ignora a proposito el de territorio y lo dice en su rotulo. */
function contextoFiltros(sobre){
  return Object.assign({
    txt: norm(document.getElementById("f-texto").value.trim()),
    grupo: document.getElementById("f-grupo").value,
    niv: document.getElementById("f-nivel").value,
    nov: document.getElementById("f-novedad").value,
    ents: ENTIDADES_SEL,
    plat: document.getElementById("f-plataforma").value,
  }, sobre || {});
}

/* Para la pantalla: operaciones completas. Se arma la operacion con TODOS sus
   registros y se conserva si alguno pasa el filtro, de modo que la fila siempre
   muestra el estado real. */
function operacionesFiltradas(sobre){
  const ctx = contextoFiltros(sobre);
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
      /* Del registro que manda: el contrato si existe. Proceso y contrato son el
         mismo hecho, asi que comparten municipio. */
      municipio: jefe.municipio || "",
      municipioNombre: jefe.municipio_nombre || "",
      municipioOrigen: jefe.municipio_origen || "",
      depCodigo: jefe.dep_codigo || "",
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

/* Que filtros hay puestos, en palabras. Lo usan el titulo del panel y tambien lo
   que se descarga: el Excel y el informe impreso tienen que decir de que estan
   hechos, y leerlo del texto ya pintado en pantalla obligaba a repintar antes de
   descargar para no escribir el estado anterior. */
function filtrosActivos(){
  /* Por valor y no por selectedIndex: cada control tiene un valor por defecto
     distinto y el indice no dice cual es. */
  const PORDEFECTO = { "f-grupo": "territorial", "f-nivel": "rel", "f-plataforma": "", "f-revision": "",
                       "f-tipo": "", "f-novedad": "" };
  const texto = id => {
    const s = document.getElementById(id);
    if (!s || s.value === PORDEFECTO[id]) return "";
    const op = s.options && [...s.options].find(o => o.value === s.value);
    return op ? op.text : String(s.value);
  };
  const activos = ["f-grupo","f-plataforma","f-nivel","f-tipo","f-revision","f-novedad"]
    .map(texto).filter(Boolean);
  /* Las entidades van aparte: son varias y no hay <option> del que sacar el texto. */
  const nEnt = ENTIDADES_SEL.size;
  if (nEnt === 1) activos.push([...ENTIDADES_SEL][0]);
  if (nEnt > 1) activos.push(nEnt + " entidades");
  const monto = rangoMonto();
  if (monto.activo) activos.push("monto " + textoMonto(monto));
  const busq = document.getElementById("f-texto").value.trim();
  if (busq) activos.unshift(`"${busq}"`);
  return activos;
}

/* El panel de filtros puede ir cerrado, asi que su titulo tiene que decir que se
   esta viendo: un tablero filtrado en silencio miente. */
function pintarResumenFiltros(){
  const el = document.getElementById("resumen-filtros");
  if (!el) return;
  const activos = filtrosActivos();
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

/* Las operaciones tal como quedan en pantalla, ya ordenadas. Lo usan la tabla, el
   Excel y el informe impreso: si cada uno filtrara por su cuenta, el archivo
   descargado diria 53 operaciones donde la tabla dice 47 y no habria forma de
   saber cual de los dos miente. */
function operacionesDeLaVista(sobre){
  let filas = ordenarOperaciones(operacionesFiltradas(sobre));
  /* El filtro de estado se aplica sobre la operacion y no sobre el registro:
     "aun abierta" significa que no existe contrato, y eso solo se sabe despues
     de juntar el proceso con su contrato. */
  const estado = document.getElementById("f-tipo").value;
  if (estado === "firmada") filas = filas.filter(o => o.firmado);
  if (estado === "abierta") filas = filas.filter(o => o.abierta);
  /* "Por revisar" es la bandeja de trabajo: lo que el clasificador marco como
     posible pero nadie ha confirmado ni descartado todavia. */
  const rev = document.getElementById("f-revision").value;
  if (rev === "pendiente") filas = filas.filter(o => o.nivel === "Media" && !o.revisada);
  if (rev === "revisada") filas = filas.filter(o => o.revisada);
  const monto = rangoMonto();
  if (monto.activo) filas = filas.filter(o => o.valor >= monto.min && o.valor <= monto.max);
  return agrupando() ? agruparPorEntidad(filas) : filas;
}

/* Agrupar es, en el fondo, ORDENAR: las operaciones de una misma entidad quedan
   contiguas y las entidades se ordenan por lo que suman. Hecho asi, la paginacion,
   el informe impreso y las tres descargas heredan el mismo orden sin tocar nada
   mas; si cada uno agrupara por su cuenta volveriamos a tener cuatro verdades. */
const agrupando = () => {
  const c = document.getElementById("f-agrupar");
  return !!(c && c.checked);
};

function agruparPorEntidad(filas){
  const por = new Map();
  filas.forEach(o => {
    if (!por.has(o.entidad)) por.set(o.entidad, []);
    por.get(o.entidad).push(o);
  });
  const suma = ops => ops.reduce((t, o) => t + (o.firmado ? o.valor : 0), 0);
  return [...por.values()]
    .sort((a, b) => suma(b) - suma(a) || b.length - a.length)
    .reduce((todo, ops) => todo.concat(ops), []);
}

/* Cuanto suma y cuantas hay de cada entidad, para la banda que encabeza el grupo. */
function totalesPorEntidad(filas){
  const m = new Map();
  filas.forEach(o => {
    if (!m.has(o.entidad)) m.set(o.entidad, { n: 0, valor: 0, abiertas: 0 });
    const g = m.get(o.entidad);
    g.n++;
    if (o.firmado) g.valor += o.valor; else g.abiertas++;
  });
  return m;
}

/* La banda que encabeza cada entidad. `sigue` marca el grupo partido por la
   paginacion: sin ese aviso, media docena de filas quedan bajo un encabezado que
   parece decir que ahi empieza la entidad, y su cuenta no cuadra con lo visible. */
function bandaEntidad(entidad, tot, sigue, columnas){
  return `<tr class="grupo-ent"><td colspan="${columnas}">
    <span class="ent">${esc(entidad)}</span>
    <span class="cuenta">${frasePlural(tot.n, "operación", "operaciones")}`
    + ` · ${esc(compacto(tot.valor))} firmado${tot.abiertas ? " · " + tot.abiertas + " sin contratar" : ""}</span>`
    + `${sigue ? '<span class="sigue">viene de la página anterior</span>' : ""}</td></tr>`;
}

function pintarTabla(){
  pintarLeyenda();
  pintarResumenFiltros();
  pintarAvisoParcial();
  /* El mapa colorea lo mismo que la tabla, asi que se repinta con ella y no hace
     falta acordarse de llamarlo en cada filtro nuevo. */
  pintarMapas();
  const filas = operacionesDeLaVista();
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
    const elegidas = [...ENTIDADES_SEL];
    const ent = elegidas.length === 1 ? elegidas[0] : "";
    const grupoDe = e => (PADRON.find(p => p.entidad === e) || {}).grupo;
    const busq = document.getElementById("f-texto").value.trim();
    const monto = rangoMonto();
    vacio.textContent =
      monto.activo
        ? `Ninguna operación queda entre ${textoMonto(monto)}. El monto es el valor `
          + "firmado, o el precio base cuando todavía no hay contrato."
      : busq
        ? `Ninguna operación coincide con "${busq}". Se busca en el objeto, la entidad, el `
          + "contratista y los números de proceso y de contrato."
      : elegidas.length > 1
        ? `Ninguna de las ${elegidas.length} entidades elegidas tiene operaciones que `
          + "cumplan los demás filtros. Quite entidades o amplíe la relación para ver "
          + "qué han contratado."
      : ent
        /* No todas las entidades del desplegable están vigiladas: 83 del padrón son de
           otras regiones —Pasto, Honda, el Meta— y entraron porque un barrido encontró
           contratación suya, no porque se las siga. La prueba no es estar en el padrón,
           que también las incluye, sino no ser del grupo "Fuera del Valle". */
        ? (grupoDe(ent) !== "Fuera del Valle"
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

  const porEntidad = agrupando() ? totalesPorEntidad(filas) : null;
  const desde = (t.pagina - 1) * POR_PAGINA;
  let entidadEnCurso = null;
  cuerpo.innerHTML = t.filas.map((o, i) => {
    let banda = "";
    if (porEntidad && (i === 0 || o.entidad !== entidadEnCurso)){
      /* En la primera fila de la pagina siempre se encabeza, aunque el grupo venga
         de la anterior: si no, esas filas quedan sin decir de quien son. */
      const partido = i === 0 && desde > 0 && filas[desde - 1].entidad === o.entidad;
      banda = bandaEntidad(o.entidad, porEntidad.get(o.entidad), partido, 6);
    }
    entidadEnCurso = o.entidad;
    return banda + filaOperacion(o);
  }).join("");
}

function filaOperacion(o){
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
  /* Los topes de la barra de monto, antes del primer pintado: dependen de los
     datos recien cargados, no de los filtros. */
  calcularLimitesValor();
  pintarRangoMonto();
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

async function cargarMapa(){
  try{
    const r = await fetch("mapa.json");
    if (!r.ok) throw new Error("HTTP " + r.status);
    MAPA = await r.json();
  }catch(e){
    MAPA_ERROR = "No se pudo leer mapa.json: " + e.message + ".";
  }
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

    /* Los contornos se piden una sola vez: no cambian entre recolecciones, y son
       codigo publicado, no dato recolectado. */
    if (!MAPA && !MAPA_ERROR) await cargarMapa();

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
  const lista = document.getElementById("f-entidad-lista");
  if (!lista) return;
  const ents = [...new Set(DATOS.filter(listable).map(r => r.entidad).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b, "es"));
  /* Si una entidad deja de venir en el archivo, su marca se cae con ella: dejarla
     puesta daria tabla vacia sin nada en pantalla que explicara por que. */
  const vivas = new Set(ents);
  [...ENTIDADES_SEL].forEach(e => { if (!vivas.has(e)) ENTIDADES_SEL.delete(e); });

  const caja = document.getElementById("f-entidad-buscar");
  const busca = norm(caja && caja.value ? caja.value.trim() : "");
  const visibles = busca ? ents.filter(e => norm(e).includes(busca)) : ents;
  /* Las marcadas arriba: con mas de cien entidades, lo elegido se pierde de vista.
     El reorden ocurre al repintar la lista, no al marcar, para que las casillas no
     salten bajo el cursor mientras se eligen varias. */
  const orden = visibles.slice().sort((a, b) =>
    (ENTIDADES_SEL.has(b) ? 1 : 0) - (ENTIDADES_SEL.has(a) ? 1 : 0));
  lista.innerHTML = orden.length
    ? orden.map(e => `<label class="opt" title="${esc(e)}"><input type="checkbox" value="${esc(e)}"`
        + `${ENTIDADES_SEL.has(e) ? " checked" : ""}><span>${esc(e)}</span></label>`).join("")
    : `<p class="nada">Ninguna entidad coincide con esa búsqueda.</p>`;
  pintarResumenEntidades();
}

/* El desplegable cerrado tiene que decir cuantas hay elegidas: un filtro puesto
   que no se ve miente igual que un tablero filtrado en silencio. */
function pintarResumenEntidades(){
  const el = document.getElementById("f-entidad-resumen");
  if (!el) return;
  const n = ENTIDADES_SEL.size;
  el.textContent = n === 0 ? "Todas las entidades"
                 : n === 1 ? [...ENTIDADES_SEL][0]
                 : n + " entidades elegidas";
  el.className = n ? "hay" : "";
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

/* ------------------------------------------------------------------ *
 * Filtro por monto                                                    *
 * ------------------------------------------------------------------ */
/* Se filtra la OPERACION, no el registro, y por el valor que la tabla muestra:
   el firmado si hay contrato y el precio base si todavia no. Filtrar el registro
   partiria la operacion -el contrato entra y su proceso no- y la fila acabaria
   diciendo "aun sin contratar" sobre algo ya firmado, que es el fallo que ya
   costo arreglar una vez. */
const POS_MAX = 1000;

/* La escala se calcula una vez por carga, sobre TODO lo listable: si se
   recalculara con cada filtro, la barra cambiaria de escala bajo el dedo y el
   tramo elegido pasaria a significar otra cosa sin que nadie lo tocara. */
let VALORES_ORD = [];

function calcularLimitesValor(){
  VALORES_ORD = operaciones(DATOS.filter(listable))
    .map(o => o.valor).filter(v => v > 0).sort((a, b) => a - b);
}

/* Por CUANTILES, no lineal ni logaritmica. Lineal no sirve -el 95% de las
   operaciones se apelotona en el primer centimetro- y logaritmica tampoco: entre
   lo listable hay contratacion ordinaria de $220 mil millones, un orden de
   magnitud por encima de todo lo del sismo, y con ella en el extremo la mitad
   alta de la barra se queda sin nada que seleccionar. Repartiendo por cuantiles,
   cada tramo de la barra tiene aproximadamente las mismas operaciones. */
function posAValor(pos){
  if (!VALORES_ORD.length) return 0;
  const t = Math.min(1, Math.max(0, pos / POS_MAX));
  return VALORES_ORD[Math.min(VALORES_ORD.length - 1,
                              Math.round(t * (VALORES_ORD.length - 1)))];
}

function rangoMonto(){
  const a = document.getElementById("f-monto-min");
  const b = document.getElementById("f-monto-max");
  if (!a || !b) return { activo: false, min: 0, max: Infinity };
  /* Los dos pulgares pueden cruzarse: manda el orden, no cual se movio. */
  const p1 = Math.min(Number(a.value), Number(b.value));
  const p2 = Math.max(Number(a.value), Number(b.value));
  /* Los extremos son "sin limite" y no un numero: en el tope de abajo entran los
     de valor cero -hay dos- y en el de arriba no puede quedar fuera el RCD por un
     redondeo de la escala. */
  return {
    activo: p1 > 0 || p2 < POS_MAX,
    min: p1 <= 0 ? 0 : posAValor(p1),
    max: p2 >= POS_MAX ? Infinity : posAValor(p2),
    p1, p2,
  };
}

function textoMonto(r){
  if (!r.activo) return "";
  if (r.min && r.max !== Infinity) return `${compacto(r.min)} a ${compacto(r.max)}`;
  if (r.min) return `desde ${compacto(r.min)}`;
  return `hasta ${compacto(r.max)}`;
}

function pintarRangoMonto(){
  const r = rangoMonto();
  const cifras = document.getElementById("rango-cifras");
  if (cifras){
    cifras.textContent = r.activo ? textoMonto(r) : "Cualquier monto";
    cifras.className = "rango-cifras" + (r.activo ? " hay" : "");
  }
  /* El tramo elegido, pintado sobre la pista: sin esto no se ve donde estan los
     dos pulgares cuando quedan juntos. */
  const tramo = document.getElementById("rango-tramo");
  if (tramo){
    tramo.style.left = (r.p1 / POS_MAX * 100) + "%";
    tramo.style.right = (100 - r.p2 / POS_MAX * 100) + "%";
  }
  const quitar = document.getElementById("f-monto-quitar");
  if (quitar) quitar.hidden = !r.activo;
}

function quitarFiltroMonto(){
  document.getElementById("f-monto-min").value = 0;
  document.getElementById("f-monto-max").value = POS_MAX;
  pintarRangoMonto();
  paginas.tabla = 1;
  pintarTabla();
}

/* ------------------------------------------------------------------ *
 * Mapas                                                              *
 * ------------------------------------------------------------------ */
/* Los contornos son del DANE y viven en mapa.json, que genera preparar_mapa.py a
   mano y se publica como CODIGO: no hay servidor de mapas ni tesela que pedirle a
   nadie, igual que no hay libreria para el Excel. Si el archivo no carga, la
   seccion lo dice y el resto del tablero sigue funcionando.

   El mapa colorea lo MISMO que la tabla: sale de operacionesDeLaVista(), asi que
   filtrar por entidad o por fecha repinta los dos a la vez. Un mapa que ignora los
   filtros mientras la tabla los aplica es la peor version de dos verdades. */
let MAPA = null;
let MAPA_ERROR = "";

/* Cinco tramos: el cero tiene color propio -y significa "no ha contratado", que en
   este tablero es una afirmacion fuerte- y los otros cuatro reparten lo que hay por
   cuantiles. Cuantiles y no tramos iguales porque el RCD de Cali, con $3.760
   millones de una sola operacion, aplanaria a los demas municipios contra el
   extremo bajo de cualquier escala lineal. */
function tramos(valores){
  const v = valores.filter(x => x > 0).sort((a, b) => a - b);
  if (!v.length) return [];
  const corte = q => v[Math.min(v.length - 1, Math.floor(q * v.length))];
  return [...new Set([corte(0.25), corte(0.5), corte(0.75), v[v.length - 1]])];
}

/* Tres situaciones distintas, tres colores: no haber contratado nada, haber
   contratado solo procesos que aun no se firman -valor cero, pero contratacion
   hay- y tener valor firmado. Con la rampa sola, Vijes -una operacion abierta de
   $20 millones- se pintaba del mismo color que un municipio en blanco, y eso es
   justo el cero que no dice por que. */
const claseMapa = (dato, metrica, cortes, fuera) => {
  /* Una pieza sin dato puede ser dos cosas MUY distintas: que no haya contratacion,
     o que la haya y el filtro la deje fuera. Pintarlas igual es el cero mudo de
     siempre, una escala mas arriba. */
  if ((!dato || !dato.n) && fuera && fuera.n) return "mf";
  if (!dato || !dato.n) return "m0";
  if (!dato[metrica]) return "mp";
  return claseTramo(dato[metrica], cortes);
};

const claseTramo = (valor, cortes) => {
  if (!valor) return "m0";
  for (let i = 0; i < cortes.length; i++) if (valor <= cortes[i]) return "m" + (i + 1);
  return "m" + cortes.length;
};

/* Lo que cada pieza suma, en operaciones y en plata, sobre lo que hay filtrado. */
function porTerritorio(ops, clave){
  const m = new Map();
  ops.forEach(o => {
    const k = o[clave];
    if (!k) return;
    if (!m.has(k)) m.set(k, { n: 0, valor: 0, abiertas: 0, deducidas: 0 });
    const g = m.get(k);
    g.n++;
    if (o.firmado) g.valor += o.valor; else g.abiertas++;
    if (o.municipioOrigen === "entidad") g.deducidas++;
  });
  return m;
}

const mostrarNombres = () => {
  const c = document.getElementById("f-mapa-nombres");
  return !c || c.checked;
};

const metricaMapa = () => {
  const s = document.getElementById("f-mapa-metrica");
  return s && s.value === "n" ? "n" : "valor";
};

/* El cuerpo de letra sale del tamano de la pieza: con uno solo, el nombre de un
   municipio pequeno se derrama sobre tres vecinos. La raiz del area porque lo que
   importa es cuanto mide de ancho, no cuanta superficie tiene. */
const letraPieza = area => Math.max(11, Math.min(21, Math.round(Math.sqrt(area || 0) / 7)));

/* Las etiquetas van DENTRO del SVG y no como capa aparte, para que se escalen con
   el mapa y viajen tal cual al informe impreso y al PNG del Excel. El halo del
   color del panel es lo que las hace legibles sobre cualquier relleno; sin el, un
   nombre sobre el tono mas oscuro de la rampa no se lee. */
function etiquetaPieza(p, dato, metrica, mostrar){
  if (!mostrar) return "";
  const cuerpo = letraPieza(p.a);
  /* "$ 0" no es una cifra, es un cero sin explicacion: pasa en los municipios que
     solo tienen procesos sin firmar, que ya van en su propio color. Se escribe lo
     que de verdad hay. */
  const cifra = !dato || !dato.n ? ""
    : metrica === "n" ? dato.n + (dato.n === 1 ? " op." : " ops.")
    : dato.valor ? compacto(dato.valor)
    : dato.n + (dato.n === 1 ? " sin firmar" : " sin firmar");
  const nombre = `<tspan x="${p.cx}" dy="0">${esc(p.rotulo || p.nombre)}</tspan>`;
  const linea2 = cifra
    ? `<tspan x="${p.cx}" dy="${(cuerpo * 1.05).toFixed(1)}" class="cifra">${esc(cifra)}</tspan>`
    : "";
  return `<text class="etq${dato && dato.n ? " con" : ""}" x="${p.cx}" `
    + `y="${cifra ? p.cy - cuerpo * 0.5 : p.cy}" font-size="${cuerpo}">${nombre}${linea2}</text>`;
}

/* Separa las etiquetas que se pisan. Manda la de la pieza mas grande -se queda
   quieta- y la pequena se aparta en vertical lo justo. Son dos o tres casos por
   mapa, no hace falta nada mas sofisticado; y con tres pasadas se corta, que un
   ajuste de etiquetas no puede colgar la pagina. */
function separarEtiquetas(svg, ancho, alto){
  const etqs = [...svg.querySelectorAll("text")]
    .map(t => ({ t, tam: Number(t.getAttribute("font-size")) || 12 }))
    .sort((a, b) => b.tam - a.tam);
  for (let pasada = 0; pasada < 3; pasada++){
    let movio = false;
    const cajas = etqs.map(e => e.t.getBBox());
    for (let i = 0; i < etqs.length; i++){
      for (let j = i + 1; j < etqs.length; j++){
        const a = cajas[i], b = cajas[j];
        const solapeX = Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x);
        const solapeY = Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y);
        if (solapeX <= 0 || solapeY <= 0) continue;
        /* La pequena se aparta hacia el lado contrario a la grande. */
        const haciaAbajo = (b.y + b.height / 2) >= (a.y + a.height / 2);
        const salto = (solapeY + 1.5) * (haciaAbajo ? 1 : -1);
        /* Sin acotar, el empujon sacaba a San Andres por el borde de arriba y su
           nombre se cortaba. Fuera del lienzo una etiqueta no existe. */
        const margen = etqs[j].tam;
        const y = Math.max(margen, Math.min(alto - margen,
          Number(etqs[j].t.getAttribute("y")) + salto));
        etqs[j].t.setAttribute("y", y.toFixed(1));
        cajas[j] = etqs[j].t.getBBox();
        movio = true;
      }
    }
    if (!movio) break;
  }
  /* Y hacia dentro por los cuatro lados. San Andres, que es la esquina noroeste del
     pais, tenia su centroide en (0.9, 2.8): el rotulo centrado se salia por la
     izquierda y por arriba a la vez. Se mueve con transform y no con la x y la y,
     para no tener que tocar tambien las de cada tspan. */
  etqs.forEach(e => {
    const b = e.t.getBBox();
    let dx = 0, dy = 0;
    if (b.x < 2) dx = 2 - b.x;
    else if (b.x + b.width > ancho - 2) dx = ancho - 2 - (b.x + b.width);
    if (b.y < 2) dy = 2 - b.y;
    else if (b.y + b.height > alto - 2) dy = alto - 2 - (b.y + b.height);
    if (dx || dy)
      e.t.setAttribute("transform", `translate(${dx.toFixed(1)},${dy.toFixed(1)})`);
  });
}

function pintarUnMapa(destino, def, datos, metrica, rotulo, dejaFuera){
  const el = document.getElementById(destino);
  if (!el) return;
  const cortes = tramos(def.piezas.map(p => (datos.get(p.codigo) || {})[metrica] || 0));
  const nombres = mostrarNombres();
  const piezas = def.piezas.map(p => {
    const d = datos.get(p.codigo) || { n: 0, valor: 0, abiertas: 0 };
    const f = dejaFuera ? dejaFuera.get(p.codigo) : null;
    const cual = (d[metrica] || 0);
    /* El titulo emergente es el unico sitio donde el mapa da la cifra exacta. Sin
       el, un color oscuro solo dice "mas que el vecino". */
    const dice = !d.n && f && f.n
      ? `${p.nombre}: ${frasePlural(f.n, "operación", "operaciones")} que los filtros `
        + `actuales dejan fuera`
      : !d.n
      ? `${p.nombre}: sin contratación que cumpla los filtros`
      : d.valor
        ? `${p.nombre}: ${frasePlural(d.n, "operación", "operaciones")}, `
          + `${pesos(d.valor)} firmado${d.abiertas ? ", " + d.abiertas + " sin contratar" : ""}`
        : `${p.nombre}: ${frasePlural(d.n, "operación", "operaciones")}, `
          + `ninguna firmada todavía`;
    return `<path d="${p.d}" class="${claseMapa(d, metrica, cortes, f)}">`
      + `<title>${esc(dice)}</title></path>`;
  }).join("");
  /* Todas las etiquetas despues de todos los contornos: si fueran por parejas, el
     relleno del municipio siguiente taparia el nombre del anterior. */
  const etiquetas = def.piezas.map(p =>
    etiquetaPieza(p, datos.get(p.codigo), metrica, nombres)).join("");

  el.innerHTML = `<svg viewBox="0 0 ${def.ancho} ${def.alto}" role="img"
      aria-label="${esc(rotulo)}" preserveAspectRatio="xMidYMid meet">${piezas}${etiquetas}</svg>`;
  if (nombres) separarEtiquetas(el.querySelector("svg"), def.ancho, def.alto);
  return cortes;
}

function leyendaMapa(cortes, metrica, hayAbiertas, hayFuera){
  const fmt = v => metrica === "n" ? String(v) : compacto(v);
  const trozos = ['<span class="tramo"><i class="m0"></i>sin contratación</span>'];
  if (hayAbiertas) trozos.push('<span class="tramo"><i class="mp"></i>'
    + 'solo procesos aún sin firmar</span>');
  if (hayFuera) trozos.push('<span class="tramo"><i class="mf"></i>'
    + 'tiene contratación, pero los filtros la dejan fuera</span>');
  let desde = 1;
  cortes.forEach((c, i) => {
    trozos.push(`<span class="tramo"><i class="m${i + 1}"></i>`
      + `${esc(desde === c ? fmt(c) : fmt(desde) + "–" + fmt(c))}</span>`);
    desde = c + 1;
  });
  return trozos.join("");
}

function pintarMapas(){
  const caja = document.getElementById("mapa-aviso");
  if (!caja) return;
  if (MAPA_ERROR){
    /* Que el mapa no cargue no puede parecerse a que no haya contratacion. */
    caja.innerHTML = `<b>El mapa no se pudo dibujar.</b> ${esc(MAPA_ERROR)} `
      + `Las cifras de la tabla y del resto de la página no dependen de esto.`;
    caja.hidden = false;
    return;
  }
  if (!MAPA) return;

  const ops = operacionesDeLaVista();
  /* El mapa del pais respeta TODOS los filtros, incluido el de territorio: si no,
     el Valle sumaba ahi $14,0 mm -todas sus entidades- mientras la tabla listaba
     $10,2 mm del grupo filtrado, dos cifras distintas del mismo sitio en la misma
     pantalla. Lo que se pinta aparte es lo que el filtro DEJA FUERA, con color
     propio: si esas piezas salieran como las vacias, seria un cero mudo. */
  const opsPais = operacionesDeLaVista({ grupo: "todos" });
  const metrica = metricaMapa();
  const porMun = porTerritorio(ops.filter(o => o.grupo !== "Fuera del Valle"), "municipio");
  const porDep = porTerritorio(ops, "depCodigo");
  const porDepTodo = porTerritorio(opsPais, "depCodigo");
  /* Lo que hay en un departamento y el filtro no deja ver. */
  const fueraDelFiltro = new Map();
  porDepTodo.forEach((g, cod) => {
    const visible = porDep.get(cod);
    if (!visible || !visible.n) fueraDelFiltro.set(cod, g);
  });

  const cortesValle = pintarUnMapa("mapa-valle", MAPA.valle, porMun, metrica,
    "Municipios del Valle del Cauca según la contratación relacionada con el sismo");
  const abiertasValle = [...porMun.values()].some(g => g.n && !g[metrica]);
  document.getElementById("leyenda-valle").innerHTML =
    leyendaMapa(cortesValle, metrica, abiertasValle, false);
  const cortesPais = pintarUnMapa("mapa-pais", MAPA.pais, porDep, metrica,
    "Departamentos de Colombia según la contratación relacionada con el sismo",
    fueraDelFiltro);
  const abiertasPais = [...porDep.values()].some(g => g.n && !g[metrica]);
  document.getElementById("leyenda-pais").innerHTML =
    leyendaMapa(cortesPais, metrica, abiertasPais, fueraDelFiltro.size > 0);
  const ocultas = opsPais.length - ops.length;
  document.getElementById("pie-pais").textContent = ocultas
    ? frasePlural(ops.length, "operación", "operaciones") + " con los filtros puestos · "
      + ocultas + " más quedan fuera, en color aparte"
    : frasePlural(ops.length, "operación", "operaciones") + " en todo el país";



  /* Lo que el mapa NO puede dibujar, dicho con nombre y numero. Un mapa que se come
     operaciones en silencio es peor que no tener mapa: se lee como un censo. */
  const delValle = ops.filter(o => o.grupo !== "Fuera del Valle");
  const deducidas = delValle.filter(o => o.municipioOrigen === "entidad").length;
  const porObjeto = delValle.filter(o => o.municipioOrigen === "objeto").length;
  const sinSitio = delValle.filter(o => !o.municipio).length;
  const conMunicipio = [...porMun.values()].reduce((s, g) => s + g.n, 0);
  const notas = [
    `${frasePlural(conMunicipio, "operación", "operaciones")} situadas en `
      + `${frasePlural(porMun.size, "municipio", "municipios")} del Valle`,
  ];
  if (deducidas) notas.push(`<b>${deducidas}</b> por el nombre de la entidad, porque la `
    + `fuente publica su municipio como «No Definido»`);
  if (porObjeto) notas.push(`<b>${porObjeto}</b> por el municipio que nombra el objeto, `
    + `porque la entidad contrata desde fuera del Valle`);

  if (sinSitio) notas.push(`<b>${sinSitio}</b> sin municipio ni pista en el nombre de la `
    + `entidad: ${sinSitio === 1 ? "no aparece" : "no aparecen"} en el mapa del Valle`);
  const fuera = opsPais.filter(o => o.grupo === "Fuera del Valle").length;
  if (fuera) notas.push(`el mapa de Colombia añade <b>${fuera}</b> de otras regiones que `
    + `nombran el sismo, que no suman en las cifras del tablero`);
  document.getElementById("mapa-notas").innerHTML = notas.join(" · ") + ".";
  /* El titulo dice lo esencial aunque la seccion este plegada, que es como arranca
     en el telefono: dos mapas ocupan ahi tres pantallas. */
  const res = document.getElementById("mapa-resumen");
  if (res) res.textContent = "· " + frasePlural(porMun.size, "municipio", "municipios")
    + " del Valle con contratación";
  caja.hidden = true;
}

/* Las cifras por territorio, para el Excel y para quien quiera cruzarlas. Sale de
   lo mismo que colorea el mapa. */
function filasTerritorio(){
  const ops = operacionesDeLaVista();
  const nombreMun = new Map((MAPA ? MAPA.valle.piezas : []).map(p => [p.codigo, p.nombre]));
  const nombreDep = new Map((MAPA ? MAPA.pais.piezas : []).map(p => [p.codigo, p.nombre]));
  const filas = [];
  [...porTerritorio(ops.filter(o => o.grupo !== "Fuera del Valle"), "municipio").entries()]
    .sort((a, b) => b[1].valor - a[1].valor)
    .forEach(([cod, g]) => filas.push(["Municipio del Valle", cod,
      nombreMun.get(cod) || cod, g.n, g.valor, g.abiertas, g.deducidas]));
  [...porTerritorio(ops, "depCodigo").entries()]
    .sort((a, b) => b[1].valor - a[1].valor)
    .forEach(([cod, g]) => filas.push(["Departamento", cod,
      nombreDep.get(cod) || cod, g.n, g.valor, g.abiertas, g.deducidas]));
  return filas;
}

/* ------------------------------------------------------------------ *
 * Descargas: CSV, Excel e informe para papel                          *
 * ------------------------------------------------------------------ */
/* Las tres salidas parten de operacionesDeLaVista(), que es lo que la tabla esta
   mostrando. Un archivo que sale del tablero y no coincide con lo que se ve en
   pantalla es peor que no tenerlo: nadie sabe cual de los dos creer. */
function registrosDeLaVista(){
  return operacionesDeLaVista().flatMap(o => [o.contrato, o.proceso].filter(Boolean));
}

/* Los registros sueltos, que es lo que espera quien abre el archivo para cruzarlo
   con otra cosa. Un contrato y su proceso van en dos filas, con la misma clave en
   la columna `operacion`. */
const COLS_REGISTRO = ["plataforma","tipo","operacion","id","referencia","fecha","etiqueta_fecha",
                       "entidad","nit","departamento","ciudad","grupo","es_ungrd","objeto",
                       "modalidad","justificacion","valor","fecha_inicio","fecha_fin","duracion",
                       "proveedor","estado","ambito","nivel","motivo","url"];

/* Las operaciones, una por fila, tal como se leen en la tabla. Los rotulos van en
   castellano y sin jerga del clasificador, igual que en pantalla. */
const COLS_OPERACION = [
  ["Estado", o => o.firmado ? "Contratada" : "Abierta"],
  ["Fecha", o => o.fecha],
  ["Entidad", o => o.entidad],
  ["Grupo", o => o.grupo],
  ["Objeto", o => o.objeto],
  ["Valor", o => o.valor],
  ["Que es ese valor", o => o.firmado ? "valor firmado" : "precio base"],
  ["Contratista", o => o.proveedor],
  ["Duracion", o => o.duracion],
  ["Modalidad", o => o.modalidad],
  ["Justificacion", o => o.justificacion],
  ["Relacion con el sismo", o => nivelCorto(o.nivel)],
  ["Por que se clasifico asi", o => o.motivo],
  ["Revisado por una persona", o => o.revisada ? (o.revisionRevisor || "si") : ""],
  ["Fecha de la revision", o => o.revisionFecha],
  ["Referencia del proceso", o => o.proceso ? (o.proceso.referencia || o.proceso.id) : ""],
  ["Referencia del contrato", o => o.contrato ? (o.contrato.referencia || o.contrato.id) : ""],
  ["Aparecio en el monitoreo", o => o.novedad || ""],
  ["Enlace a SECOP", o => (o.contrato && o.contrato.url) || (o.proceso && o.proceso.url) || ""],
];

const hoyArchivo = () => {
  const d = new Date(), p = n => String(n).padStart(2, "0");
  return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate());
};

function bajarArchivo(blob, nombre){
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = nombre;
  a.click();
  URL.revokeObjectURL(a.href);
}

/* De que esta hecho lo que se descarga. El archivo se va del tablero y viaja solo:
   sin esto, dentro de un mes nadie sabe si esas 12 filas son todo lo del sismo o
   el resultado de tres filtros puestos aquella tarde. */
function procedencia(){
  const filas = operacionesDeLaVista();
  const valor = filas.reduce((s, o) => s + (o.firmado ? o.valor : 0), 0);
  const abiertas = filas.filter(o => o.abierta).length;
  const activos = filtrosActivos();
  const aviso = document.getElementById("aviso-parcial");
  const lineas = [
    ["Tablero", "Contratacion asociada a la urgencia manifiesta - sismo del 10 de agosto de 2026"],
    ["Pagina", "https://jlzmontenegro.github.io/contratacion-urgencia-manifiesta-valle/"],
    ["Descargado el", new Date().toLocaleString("es-CO")],
    ["Datos de la recoleccion", LOCAL ? String(LOCAL.generado) : "sin datos"],
    ["Filtros aplicados", activos.length ? activos.join(" · ") : "ninguno"],
    ["Operaciones", filas.length],
    ["Valor firmado", valor],
    ["Aun sin contratar", abiertas],
  ];
  if (aviso && !aviso.hidden)
    lineas.push(["Advertencia", "Esta cuenta no es el total: de la contratacion corriente solo "
      + "viaja en el archivo la de Cali, la Gobernacion, sus descentralizadas y la UNGRD."]);
  lineas.push(["Fuente", "datos.gov.co - SECOP II jbjy-vk9h y p6dx-8zbt - SECOP I f789-7hwg"]);
  return lineas;
}

/* ---- Excel ---------------------------------------------------------- *
 * Un .xlsx es un ZIP con varios XML dentro. Se escribe a mano y no con una
 * libreria traida de un CDN: la pagina no depende de nadie mas y sigue
 * funcionando el dia que ese CDN no responda, que es justo el dia en que un
 * cero se leeria como "no hay contratacion del sismo". Las entradas van SIN
 * comprimir (metodo 0), lo que ahorra meter un deflate en el navegador; Excel
 * las abre igual.
 * ------------------------------------------------------------------- */
const CRC_TABLA = (() => {
  const t = new Uint32Array(256);
  for (let i = 0; i < 256; i++){
    let c = i;
    for (let k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
    t[i] = c >>> 0;
  }
  return t;
})();

function crc32(bytes){
  let c = 0xFFFFFFFF;
  for (let i = 0; i < bytes.length; i++) c = CRC_TABLA[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8);
  return (c ^ 0xFFFFFFFF) >>> 0;
}

const bytesDe = txt => new TextEncoder().encode(txt);

function zip(archivos){
  /* El contenido llega como texto (los XML) o como bytes (el PNG del mapa). */
  const cod = archivos.map(a => ({
    nombre: bytesDe(a.nombre),
    datos: a.contenido instanceof Uint8Array ? a.contenido : bytesDe(a.contenido),
  }));
  cod.forEach(a => { a.crc = crc32(a.datos); });
  const total = cod.reduce((s, a) => s + 30 + a.nombre.length + a.datos.length
                                       + 46 + a.nombre.length, 0) + 22;
  const buf = new Uint8Array(total);
  const dv = new DataView(buf.buffer);
  const donde = [];
  let pos = 0;
  cod.forEach(a => {
    donde.push(pos);
    dv.setUint32(pos, 0x04034b50, true);
    dv.setUint16(pos + 4, 20, true);
    dv.setUint16(pos + 6, 0x0800, true);      // los nombres van en UTF-8
    dv.setUint16(pos + 8, 0, true);           // sin comprimir
    dv.setUint16(pos + 12, 0x2100, true);     // fecha fija y valida: 1-ene-2000
    dv.setUint32(pos + 14, a.crc, true);
    dv.setUint32(pos + 18, a.datos.length, true);
    dv.setUint32(pos + 22, a.datos.length, true);
    dv.setUint16(pos + 26, a.nombre.length, true);
    pos += 30;
    buf.set(a.nombre, pos); pos += a.nombre.length;
    buf.set(a.datos, pos);  pos += a.datos.length;
  });
  const central = pos;
  cod.forEach((a, i) => {
    dv.setUint32(pos, 0x02014b50, true);
    dv.setUint16(pos + 4, 20, true);
    dv.setUint16(pos + 6, 20, true);
    dv.setUint16(pos + 8, 0x0800, true);
    dv.setUint16(pos + 10, 0, true);
    dv.setUint16(pos + 14, 0x2100, true);
    dv.setUint32(pos + 16, a.crc, true);
    dv.setUint32(pos + 20, a.datos.length, true);
    dv.setUint32(pos + 24, a.datos.length, true);
    dv.setUint16(pos + 28, a.nombre.length, true);
    dv.setUint32(pos + 42, donde[i], true);
    pos += 46;
    buf.set(a.nombre, pos); pos += a.nombre.length;
  });
  dv.setUint32(pos, 0x06054b50, true);
  dv.setUint16(pos + 8, cod.length, true);
  dv.setUint16(pos + 10, cod.length, true);
  dv.setUint32(pos + 12, pos - central, true);
  dv.setUint32(pos + 16, central, true);
  return buf;
}

/* XML no admite caracteres de control, y en los objetos llegan: vienen de pegar
   texto desde un PDF. Uno solo hace que Excel declare el archivo ilegible sin
   decir por que. Se recorren a mano y no con una expresion regular, que es donde
   se cuelan los escapes rotos. */
function escXml(valor){
  const s = String(valor === null || valor === undefined ? "" : valor);
  let salida = "";
  for (let i = 0; i < s.length; i++){
    const c = s.charCodeAt(i);
    if (c < 32 && c !== 9 && c !== 10 && c !== 13){ salida += " "; continue; }
    const ch = s[i];
    salida += ch === "&" ? "&amp;"
            : ch === "<" ? "&lt;"
            : ch === ">" ? "&gt;"
            : ch === '"' ? "&quot;"
            : ch === "'" ? "&apos;" : ch;
  }
  return salida;
}

function letraCol(i){
  let n = i + 1, s = "";
  while (n > 0){ const r = (n - 1) % 26; s = String.fromCharCode(65 + r) + s; n = (n - r - 1) / 26; }
  return s;
}

function hojaXml(titulos, filas, anchos, conDibujo){
  const celda = (v, fila, col) => {
    const ref = letraCol(col) + fila;
    const numero = typeof v === "number" && isFinite(v);
    const estilo = fila === 1 ? ' s="1"' : (numero ? ' s="2"' : "");
    return numero
      ? `<c r="${ref}"${estilo}><v>${v}</v></c>`
      : `<c r="${ref}"${estilo} t="inlineStr"><is><t xml:space="preserve">${escXml(v)}</t></is></c>`;
  };
  const filaXml = (vals, i) =>
    `<row r="${i + 1}">` + vals.map((v, c) => celda(v, i + 1, c)).join("") + "</row>";
  const cols = (anchos || titulos.map(() => 22))
    .map((a, i) => `<col min="${i + 1}" max="${i + 1}" width="${a}" customWidth="1"/>`).join("");
  const ultima = letraCol(titulos.length - 1) + (filas.length + 1);
  return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    + '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    + (conDibujo ? ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"' : "")
    + '>'
    /* Fila de titulos congelada: con trescientas filas, a la mitad ya no se sabe
       que columna se esta mirando. */
    + '<sheetViews><sheetView workbookViewId="0">'
    + '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
    + '</sheetView></sheetViews>'
    + `<cols>${cols}</cols><sheetData>`
    + [titulos].concat(filas).map(filaXml).join("")
    /* El dibujo va DESPUES del autofiltro: el esquema de Excel fija el orden de
       los elementos y con uno fuera de sitio el archivo se declara corrupto. */
    + `</sheetData><autoFilter ref="A1:${ultima}"/>`
    + (conDibujo ? '<drawing r:id="rId1"/>' : "")
    + '</worksheet>';
}

const ESTILOS_XLSX = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
  + '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
  + '<numFmts count="1"><numFmt numFmtId="164" formatCode="#,##0"/></numFmts>'
  + '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
  + '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
  + '<fills count="2"><fill><patternFill patternType="none"/></fill>'
  + '<fill><patternFill patternType="gray125"/></fill></fills>'
  + '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
  + '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
  + '<cellXfs count="3">'
  + '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
  + '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
  + '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
  + '</cellXfs>'
  + '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
  + '</styleSheet>';

/* ---- El mapa dentro del Excel --------------------------------------- *
 * Excel no dibuja SVG: hay que llevarle un PNG. Se rasteriza en el propio
 * navegador, sin servidor ni libreria. Dos avisos que cuestan una tarde si no se
 * saben: dentro de una imagen NO viajan las clases CSS -hay que escribir el
 * color en cada trazo- y un SVG sin ancho ni alto explicitos puede rasterizarse
 * a cero pixeles, porque el viewBox solo dice proporciones.
 * ------------------------------------------------------------------- */
const PALETA_MAPA = { m0: "#E9EEEC", m1: "#CFE3E0", m2: "#93C6C0", m3: "#4E9A93",
                      m4: "#0E5C58", mp: "#F0D9AE", mf: "#DCD3C4" };

function svgAutonomo(sel, ancho){
  const svg = document.querySelector(sel);
  if (!svg) return null;
  const vb = (svg.getAttribute("viewBox") || "0 0 1000 1000").split(/\s+/).map(Number);
  const alto = Math.round(ancho * (vb[3] / vb[2]));
  const copia = svg.cloneNode(true);
  copia.querySelectorAll("path").forEach(p => {
    /* Siempre la paleta clara: el archivo se abre en Excel, sobre fondo blanco,
       y los tonos del modo oscuro alli no se leen. */
    p.setAttribute("fill", PALETA_MAPA[p.getAttribute("class")] || PALETA_MAPA.m0);
    p.setAttribute("stroke", "#FFFFFF");
    p.setAttribute("stroke-width", "0.8");
    p.removeAttribute("class");
  });
  /* Los textos tambien pierden el CSS: hay que escribirles el color, el halo y la
     fuente como atributos, o salen en negro, sin halo y con la serif del sistema. */
  copia.querySelectorAll("text").forEach(t => {
    t.setAttribute("fill", "#1A1A1A");
    t.setAttribute("stroke", "#FFFFFF");
    t.setAttribute("stroke-width", "3.5");
    t.setAttribute("stroke-linejoin", "round");
    t.setAttribute("paint-order", "stroke");
    t.setAttribute("text-anchor", "middle");
    t.setAttribute("dominant-baseline", "middle");
    t.setAttribute("font-family", "Arial, Helvetica, sans-serif");
    t.setAttribute("font-weight", t.classList.contains("con") ? "700" : "500");
    t.querySelectorAll(".cifra").forEach(c => {
      c.setAttribute("fill", "#0A403D");
      c.setAttribute("font-weight", "700");
    });
  });
  copia.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  copia.setAttribute("width", ancho);
  copia.setAttribute("height", alto);
  return { texto: new XMLSerializer().serializeToString(copia), ancho, alto };
}

async function pngDelMapa(sel, ancho){
  const s = svgAutonomo(sel, ancho);
  if (!s) return null;
  const img = new Image();
  await new Promise((listo, falla) => {
    img.onload = listo;
    img.onerror = () => falla(new Error("el navegador no pudo leer el SVG"));
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(s.texto);
  });
  /* Al doble de resolucion: en Excel la imagen se amplia al mirarla de cerca y a
     tamano natural se ve dentada. */
  const lienzo = document.createElement("canvas");
  lienzo.width = s.ancho * 2;
  lienzo.height = s.alto * 2;
  const ctx = lienzo.getContext("2d");
  ctx.fillStyle = "#FFFFFF";
  ctx.fillRect(0, 0, lienzo.width, lienzo.height);
  ctx.drawImage(img, 0, 0, lienzo.width, lienzo.height);
  const blob = await new Promise(r => lienzo.toBlob(r, "image/png"));
  if (!blob) throw new Error("el lienzo no devolvio imagen");
  return { bytes: new Uint8Array(await blob.arrayBuffer()), ancho: s.ancho, alto: s.alto };
}

/* Un pixel son 9.525 EMU, que es la unidad con la que Excel coloca los dibujos. */
const EMU = 9525;

function dibujoXml(imagenes){
  const anclas = imagenes.map((im, i) => {
    /* Una debajo de otra, dejando sitio a la tabla de la izquierda: columna 9,
       que empieza despues de la ultima con datos. */
    const fila = imagenes.slice(0, i).reduce((f, x) => f + Math.ceil(x.alto / 20) + 2, 1);
    return `<xdr:oneCellAnchor>
      <xdr:from><xdr:col>8</xdr:col><xdr:colOff>0</xdr:colOff>`
      + `<xdr:row>${fila}</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>
      <xdr:ext cx="${im.ancho * EMU}" cy="${im.alto * EMU}"/>
      <xdr:pic>
        <xdr:nvPicPr><xdr:cNvPr id="${i + 2}" name="${esc(im.nombre)}"/>
          <xdr:cNvPicPr/></xdr:nvPicPr>
        <xdr:blipFill><a:blip r:embed="rId${i + 1}"/><a:stretch><a:fillRect/></a:stretch></xdr:blipFill>
        <xdr:spPr><a:xfrm><a:off x="0" y="0"/>`
      + `<a:ext cx="${im.ancho * EMU}" cy="${im.alto * EMU}"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr>
      </xdr:pic><xdr:clientData/></xdr:oneCellAnchor>`;
  }).join("");
  return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    + '<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" '
    + 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    + 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    + anclas + '</xdr:wsDr>';
}

async function libroXlsx(){
  /* El mapa como imagen. Si el navegador no lo puede rasterizar, el libro sale
     igual con todas sus cifras: perder el dibujo no puede costar el archivo. */
  let imagenes = [];
  try{
    const a = await pngDelMapa("#mapa-valle svg", 520);
    const b = await pngDelMapa("#mapa-pais svg", 520);
    imagenes = [];
    if (a) imagenes.push(Object.assign(a, { nombre: "Valle del Cauca por municipio" }));
    if (b) imagenes.push(Object.assign(b, { nombre: "Colombia por departamento" }));
  }catch(e){
    console.warn("El mapa no se pudo incrustar en el Excel:", e.message);
    imagenes = [];
  }

  const ops = operacionesDeLaVista();
  const hojaOps = hojaXml(
    COLS_OPERACION.map(c => c[0]),
    ops.map(o => COLS_OPERACION.map(c => {
      const v = c[1](o);
      return v === null || v === undefined ? "" : v;
    })),
    [12, 12, 34, 26, 70, 16, 14, 34, 14, 26, 26, 14, 40, 18, 14, 24, 24, 20, 46]);

  const regs = registrosDeLaVista();
  const hojaRegs = hojaXml(
    COLS_REGISTRO,
    regs.map(r => COLS_REGISTRO.map(c => c === "valor"
      ? (Number(r[c]) || 0)
      : (r[c] === null || r[c] === undefined ? "" : String(r[c])))),
    COLS_REGISTRO.map(c => c === "objeto" ? 70 : c === "url" ? 46 : 20));

  /* Las mismas cifras que colorean el mapa. Un mapa en una hoja de calculo no se
     puede pivotar; estas filas si. */
  const hojaTerr = hojaXml(
    ["Ambito", "Codigo DANE", "Nombre", "Operaciones", "Valor firmado", "Sin contratar",
     "Situadas por el nombre de la entidad"],
    filasTerritorio(), [22, 14, 34, 14, 18, 14, 34], imagenes.length > 0);

  const hojaProc = hojaXml(["Que es esto", "Valor"], procedencia(), [30, 90]);

  const hojas = [["Operaciones", hojaOps], ["Registros", hojaRegs],
                 ["Territorio", hojaTerr], ["Procedencia", hojaProc]];

  const tipos = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    + '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    + '<Default Extension="xml" ContentType="application/xml"/>'
    + '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    + hojas.map((h, i) => `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" `
        + 'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>').join("")
    + '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
    + (imagenes.length
        ? '<Default Extension="png" ContentType="image/png"/>'
          + '<Override PartName="/xl/drawings/drawing1.xml" '
          + 'ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>'
        : "")
    + '</Types>';

  const libro = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    + '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
    + 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
    + hojas.map((h, i) => `<sheet name="${escXml(h[0])}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`).join("")
    + '</sheets></workbook>';

  const relsLibro = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    + hojas.map((h, i) => `<Relationship Id="rId${i + 1}" `
        + 'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        + `Target="worksheets/sheet${i + 1}.xml"/>`).join("")
    + `<Relationship Id="rId${hojas.length + 1}" `
    + 'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
    + 'Target="styles.xml"/></Relationships>';

  const raiz = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    + '<Relationship Id="rId1" '
    + 'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    + 'Target="xl/workbook.xml"/></Relationships>';

  const partes = [
    { nombre: "[Content_Types].xml", contenido: tipos },
    { nombre: "_rels/.rels", contenido: raiz },
    { nombre: "xl/workbook.xml", contenido: libro },
    { nombre: "xl/_rels/workbook.xml.rels", contenido: relsLibro },
    { nombre: "xl/styles.xml", contenido: ESTILOS_XLSX },
  ].concat(hojas.map((h, i) => ({ nombre: `xl/worksheets/sheet${i + 1}.xml`, contenido: h[1] })));

  if (imagenes.length){
    /* El dibujo cuelga de la hoja de Territorio, que es la tercera. Son cuatro
       piezas encadenadas -hoja -> dibujo -> imagen- y si falta un eslabon Excel
       abre el archivo pero sin la imagen y sin decir nada. */
    const nHoja = hojas.findIndex(h => h[0] === "Territorio") + 1;
    partes.push({
      nombre: `xl/worksheets/_rels/sheet${nHoja}.xml.rels`,
      contenido: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + '<Relationship Id="rId1" '
        + 'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" '
        + 'Target="../drawings/drawing1.xml"/></Relationships>',
    });
    partes.push({ nombre: "xl/drawings/drawing1.xml", contenido: dibujoXml(imagenes) });
    partes.push({
      nombre: "xl/drawings/_rels/drawing1.xml.rels",
      contenido: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + imagenes.map((im, i) => `<Relationship Id="rId${i + 1}" `
            + 'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            + `Target="../media/image${i + 1}.png"/>`).join("")
        + '</Relationships>',
    });
    imagenes.forEach((im, i) => partes.push({
      nombre: `xl/media/image${i + 1}.png`, contenido: im.bytes }));
  }
  return zip(partes);
}

async function descargarXlsx(){
  const boton = document.getElementById("btn-xlsx");
  const antes = boton ? boton.textContent : "";
  if (boton){ boton.disabled = true; boton.textContent = "Preparando…"; }
  try{
    bajarArchivo(
      new Blob([await libroXlsx()],
               { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }),
      "contratacion_urgencia_manifiesta_" + hoyArchivo() + ".xlsx");
  }catch(e){
    /* Un error aqui deja el boton muerto y sin explicacion; se dice. */
    alert("No se pudo generar el Excel: " + e.message);
  }finally{
    if (boton){ boton.disabled = false; boton.textContent = antes; }
  }
}

/* ---- Informe para papel y PDF --------------------------------------- *
 * Se arma en el momento y solo se ve al imprimir. No se usa una libreria de
 * PDF: obligaria a recortar el objeto para que la tabla cuadre, y el objeto es
 * el texto por el que se juzga si una contratacion tiene que ver con el sismo.
 * En papel salen TODAS las filas filtradas, no las 20 de la pagina.
 * ------------------------------------------------------------------- */
/* Los mapas para el papel. Se copian los SVG ya dibujados en vez de volver a
   generarlos: son los mismos, y duplicar el codigo de pintado es como se acaba
   teniendo dos mapas que no dicen lo mismo. */
function mapasParaPapel(){
  const valle = document.querySelector("#mapa-valle svg");
  const pais = document.querySelector("#mapa-pais svg");
  if (!valle && !pais) return "";
  const notas = document.getElementById("mapa-notas");
  const pie = document.getElementById("pie-pais");
  return `<div class="mapas-papel">
    ${valle ? `<figure><figcaption>Valle del Cauca · por municipio de la entidad que
        contrata</figcaption>${valle.outerHTML}
        <div class="leyenda-mapa">${document.getElementById("leyenda-valle").innerHTML}</div>
        </figure>` : ""}
    ${pais ? `<figure><figcaption>Colombia · por departamento (sin el filtro de
        territorio${pie && pie.textContent ? " · " + esc(pie.textContent) : ""})</figcaption>
        ${pais.outerHTML}
        <div class="leyenda-mapa">${document.getElementById("leyenda-pais").innerHTML}</div>
        </figure>` : ""}
    </div>

    ${notas ? `<p class="pie-inf">${notas.innerHTML}</p>` : ""}
    <p class="pie-inf">El municipio es el de la entidad que contrata; el lugar donde se
      ejecuta puede ser otro y, cuando consta, está dentro del objeto.</p>`;
}

function imprimirInforme(){
  const caja = document.getElementById("impresion");
  if (!caja) return;
  const filas = operacionesDeLaVista();
  const valor = filas.reduce((s, o) => s + (o.firmado ? o.valor : 0), 0);
  const abiertas = filas.filter(o => o.abierta).length;
  const datos = procedencia();
  const dato = clave => String((datos.find(l => l[0] === clave) || ["", ""])[1]);
  const aviso = document.getElementById("aviso-parcial");
  const vacio = document.getElementById("vacio");

  const porEntidad = agrupando() ? totalesPorEntidad(filas) : null;
  let enCurso = null;
  const cuerpo = filas.map(o => {
    /* En papel no hay paginacion propia, asi que la banda va una sola vez por
       entidad; el navegador ya repite la cabecera de la tabla en cada hoja. */
    let banda = "";
    if (porEntidad && o.entidad !== enCurso){
      const tot = porEntidad.get(o.entidad);
      banda = `<tr class="grupo-ent"><td colspan="5"><b>${esc(o.entidad)}</b> · `
        + `${frasePlural(tot.n, "operación", "operaciones")} · ${esc(pesos(tot.valor))} firmado`
        + `${tot.abiertas ? " · " + tot.abiertas + " sin contratar" : ""}</td></tr>`;
    }
    enCurso = o.entidad;
    const refs = [o.proceso, o.contrato].filter(Boolean)
      .map(r => esc(r.referencia || r.id)).join(" · ");
    return banda + `<tr>
      <td>${o.firmado ? "Contratada" : "Abierta"}<div class="menor">${esc(o.fecha)}</div></td>
      <td>${porEntidad ? "" : `<b>${esc(o.entidad)}</b>`}
        <div class="obj">${esc(o.objeto)}</div>
        <div class="menor">${esc(o.grupo)}${o.modalidad ? " · " + esc(o.modalidad) : ""}${
          refs ? " · " + refs : ""}</div></td>
      <td class="num">${esc(pesos(o.valor))}<div class="menor">${
        o.firmado ? "valor firmado" : "precio base"}</div></td>
      <td>${o.proveedor ? esc(o.proveedor) : '<span class="menor">aún sin contratista</span>'}</td>
      <td>${esc(nivelCorto(o.nivel))}${o.revisada ? '<div class="menor">✓ revisado</div>' : ""}
        <div class="menor">${esc(o.motivo)}</div></td>
    </tr>`;
  }).join("");

  caja.innerHTML = `
    <h1>Contratación asociada a la urgencia manifiesta · sismo del 10 de agosto de 2026</h1>
    <p class="pie-inf">Cali y Valle del Cauca · datos de la recolección del
      ${esc(dato("Datos de la recoleccion"))} · impreso el
      ${esc(new Date().toLocaleString("es-CO"))}</p>
    <table class="ficha"><tbody>
      <tr><th>Filtros aplicados</th><td>${esc(dato("Filtros aplicados"))}</td></tr>
      <tr><th>Lo que se lista</th><td>${frasePlural(filas.length, "operación", "operaciones")}
        · ${esc(pesos(valor))} firmado${abiertas ? " · " + abiertas + " aún sin contratar" : ""}</td></tr>
    </tbody></table>
    ${aviso && !aviso.hidden ? `<p class="ojo">${aviso.innerHTML}</p>` : ""}
    ${mapasParaPapel()}
    ${filas.length
      ? `<table class="listado"><thead><tr><th>Estado</th><th>Entidad y objeto</th>
           <th>Valor</th><th>Contratista</th><th>Relación</th></tr></thead>
         <tbody>${cuerpo}</tbody></table>`
      : `<p class="ojo">${esc(vacio ? vacio.textContent : "")}</p>`}
    <p class="pie-inf">Una operación es un proceso y el contrato que salió de él, contados una
      sola vez. El dato vivo está en
      https://jlzmontenegro.github.io/contratacion-urgencia-manifiesta-valle/</p>`;
  window.print();
}

function descargarCsv(){
  /* Antes salia de filtrados(), que ignoraba los filtros de estado y de revision:
     pidiendo "solo abiertas" el CSV traia tambien las contratadas y nadie lo veia
     hasta abrirlo. Ahora es lo mismo que hay en pantalla. */
  const filas = registrosDeLaVista();
  const cols = COLS_REGISTRO;
  const csv = [cols.join(";")].concat(filas.map(r =>
    cols.map(c => `"${String(r[c] ?? "").replace(/"/g, '""').replace(/\r?\n/g, " ")}"`).join(";")
  )).join("\r\n");
  bajarArchivo(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }),
               "contratacion_urgencia_manifiesta_" + hoyArchivo() + ".csv");
}

document.getElementById("btn-refrescar").addEventListener("click", cargar);
document.getElementById("btn-csv").addEventListener("click", descargarCsv);
document.getElementById("btn-xlsx").addEventListener("click", descargarXlsx);
document.getElementById("btn-pdf").addEventListener("click", imprimirInforme);
/* f-entidad ya no esta en esta lista: dejo de ser un <select> con un valor y paso a
   ser un panel de casillas. Ademas los eventos de su buscador burbujean hasta el
   <details>, asi que repintaria la tabla en cada tecla. */
["f-texto","f-grupo","f-nivel","f-tipo","f-revision","f-novedad","f-plataforma"].forEach(id =>
  document.getElementById(id).addEventListener("input",
    () => { paginas.tabla = 1; pintarTabla(); }));

/* Las casillas de entidad: una sola escucha en el contenedor, que se repinta entero
   al buscar. Marcar NO repinta la lista, para que las casillas no salten bajo el
   cursor mientras se eligen varias. */
document.getElementById("f-entidad-lista").addEventListener("change", ev => {
  const c = ev.target;
  if (!c || c.type !== "checkbox") return;
  if (c.checked) ENTIDADES_SEL.add(c.value); else ENTIDADES_SEL.delete(c.value);
  pintarResumenEntidades();
  paginas.tabla = 1;
  pintarTabla();
});
/* En pantalla estrecha la seccion del mapa arranca plegada: son dos mapas y ahi
   ocupan tres pantallas antes de llegar a la tabla. En el escritorio va abierta,
   que es lo que se pidio. El lector puede abrirla o cerrarla; esto solo decide
   como empieza. */
if ((window.innerWidth || 1024) < 700){
  const caja = document.querySelector(".mapa-caja");
  if (caja) caja.open = false;
}
["f-monto-min", "f-monto-max"].forEach(id =>
  document.getElementById(id).addEventListener("input", () => {
    pintarRangoMonto();
    paginas.tabla = 1;
    pintarTabla();
  }));
document.getElementById("f-monto-quitar").addEventListener("click", quitarFiltroMonto);
document.getElementById("f-mapa-metrica").addEventListener("change", pintarMapas);
document.getElementById("f-mapa-nombres").addEventListener("change", pintarMapas);
document.getElementById("f-agrupar").addEventListener("change", () => {
  paginas.tabla = 1;
  pintarTabla();
});
document.getElementById("f-entidad-buscar").addEventListener("input", llenarFiltroEntidades);
document.getElementById("f-entidad-limpiar").addEventListener("click", () => {
  ENTIDADES_SEL.clear();
  llenarFiltroEntidades();
  paginas.tabla = 1;
  pintarTabla();
});

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
