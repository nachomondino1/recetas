(function () {
  "use strict";

  var DATA = window.RECETAS_DATA || { meta: { count: 0, warnings: [] }, recetas: [] };
  var RECETAS = DATA.recetas || [];

  var DIFICULTAD_ORDEN = ["baja", "media", "alta"];
  var TODAS = "__todas__";

  // Categoría y subcategoría son dinámicas: el valor es el texto del H1/H2
  // del Google Doc (ver src/doc_sync.py: normalizar_encabezado), sin lista
  // cerrada que mantener acá — ni de categorías ni de valores de subfiltro.
  // Lo único fijo es el NOMBRE del campo de subfiltro por categoría, igual
  // que schema.CAMPO_SUBCATEGORIA en el export (mismo motivo: no mezclar
  // ejes en un solo campo).
  var SUBFILTROS = {
    principales: { campo: "momento", label: "Momento" },
    meriendas: { campo: "tipo_merienda", label: "Tipo" },
    bebidas: { campo: "tipo_bebida", label: "Tipo de bebida" },
    postres: { campo: "tipo_postre", label: "Tipo" },
  };
  var PLACEHOLDER_EMOJI = "🍲";
  var EMOJI_TODAS = "🍽️"; // concepto de UI ("todas las categorías"), no viene del Doc

  // Emoji fijo por tipo de sección (coincidencia por texto normalizado, en orden:
  // la primera regla que matchea gana). Secciones que no matchean ninguna regla
  // quedan sin emoji, para no forzar uno arbitrario en encabezados puntuales.
  var EMOJI_SECCIONES = [
    [/donde no comprarlo/, "🚫"],
    [/donde comprarlo/, "🛒"],
    [/^ingrediente/, "🥕"],
    [/^paso a paso/, "👩‍🍳"],
    [/^material/, "🧰"],
  ];

  function normalizarTexto(s) {
    return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  }

  function emojiDeSeccion(texto) {
    var norm = normalizarTexto(texto);
    for (var i = 0; i < EMOJI_SECCIONES.length; i++) {
      if (EMOJI_SECCIONES[i][0].test(norm)) return EMOJI_SECCIONES[i][1];
    }
    return null;
  }

  var state = {
    categoria: null, // null = "Todas"; si no, un único valor (navbar = selección simple)
    dificultades: new Set(),
    subfiltro: new Set(), // valores del campo de SUBFILTROS[state.categoria]
    orden: "tiempo-asc",
  };

  // Categorías con al menos una receta, orden alfabético. Se calcula una vez
  // en init() y la reusan renderNavCategorias/onCambioCategoria.
  var categoriasDisponibles = [];

  var els = {
    grid: document.getElementById("grid"),
    resultadoCount: document.getElementById("resultado-count"),
    estadoVacio: document.getElementById("estado-vacio"),
    categoriasNav: document.getElementById("categorias-nav"),
    chipsDificultad: document.getElementById("chips-dificultad"),
    grupoSubfiltro: document.getElementById("grupo-subfiltro"),
    subfiltroLabel: document.getElementById("subfiltro-label"),
    chipsSubfiltro: document.getElementById("chips-subfiltro"),
    ordenSelect: document.getElementById("orden-select"),
    limpiarFiltros: document.getElementById("limpiar-filtros"),
    filtrosToggle: document.getElementById("filtros-toggle"),
    filtrosPanel: document.getElementById("filtros-panel"),
    filtrosBadge: document.getElementById("filtros-badge"),
    vistaGrid: document.getElementById("vista-grid"),
    vistaDetalle: document.getElementById("vista-detalle"),
    detalleContenido: document.getElementById("detalle-contenido"),
  };

  // Mayúscula en la primera LETRA (no en la posición 0): los valores de
  // subcategoría pueden traer un emoji adelante tal cual lo escribió el
  // usuario en el Doc (ej. "🍰 budines"), y no hay que tocarlo.
  function capitalize(s) {
    if (!s) return s;
    var i = 0;
    while (i < s.length && !/[a-zA-ZÀ-ÿ]/.test(s[i])) i++;
    if (i >= s.length) return s;
    return s.slice(0, i) + s[i].toUpperCase() + s.slice(i + 1);
  }

  // Clave de lookup en SUBFILTROS sin el emoji/símbolo decorativo que el
  // usuario le puso al H1 de categoría en el Doc (ej. "🍰 meriendas" ->
  // "meriendas") — mismo motivo que schema.clave_categoria en Python: el
  // emoji puede cambiar sin romper el mapeo de campo de subfiltro.
  function quitarEmojiInicial(s) {
    var i = 0;
    while (i < s.length && !/[a-zA-ZÀ-ÿ]/.test(s[i])) i++;
    return s.slice(i);
  }

  function formatTiempo(min, max) {
    if (min == null) return "Sin dato";
    var fmt = function (m) {
      if (m < 60) return m + " min";
      var h = Math.floor(m / 60), r = m % 60;
      return r === 0 ? h + " h" : h + " h " + r + " min";
    };
    if (max != null && max !== min) return fmt(min) + " – " + fmt(max);
    return fmt(min);
  }

  // `orden` es un hint de orden preferido, opcional y nunca bloqueante: un
  // valor que no está ahí (ej. una subcategoría nueva agregada en el Doc)
  // simplemente cae en los "extras", ordenado alfabéticamente.
  function ordenarValores(valores, orden) {
    orden = orden || [];
    var presentes = new Set(valores);
    var ordenados = orden.filter(function (v) { return presentes.has(v); });
    var extras = valores.filter(function (v) { return orden.indexOf(v) === -1; }).sort();
    return ordenados.concat(extras);
  }

  function valoresUnicos(campoFn) {
    var vals = [];
    RECETAS.forEach(function (r) {
      var v = campoFn(r);
      if (Array.isArray(v)) {
        v.forEach(function (x) { if (x && vals.indexOf(x) === -1) vals.push(x); });
      } else if (v && vals.indexOf(v) === -1) {
        vals.push(v);
      }
    });
    return vals;
  }

  function renderChips(container, valores, activeSet) {
    container.innerHTML = "";
    valores.forEach(function (valor) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chip" + (activeSet.has(valor) ? " activo" : "");
      btn.textContent = capitalize(valor);
      btn.setAttribute("aria-pressed", activeSet.has(valor) ? "true" : "false");
      btn.addEventListener("click", function () {
        if (activeSet.has(valor)) activeSet.delete(valor);
        else activeSet.add(valor);
        var activo = activeSet.has(valor);
        btn.classList.toggle("activo", activo);
        btn.setAttribute("aria-pressed", activo ? "true" : "false");
        renderTodo();
      });
      container.appendChild(btn);
    });
  }

  // Navbar de categorías: navegación primaria, selección única (a diferencia
  // de los chips de abajo, que son filtros secundarios combinables). "Todas"
  // es la pestaña por default. Una receta con varias categorias aparece en
  // cada pestaña que le corresponda.
  function renderNavCategorias(valores) {
    els.categoriasNav.innerHTML = "";

    function crearPestana(valor, texto) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chip" + (state.categoria === valor ? " activo" : "");
      btn.textContent = texto;
      btn.setAttribute("role", "tab");
      btn.setAttribute("aria-selected", state.categoria === valor ? "true" : "false");
      btn.addEventListener("click", function () {
        state.categoria = valor === TODAS ? null : valor;
        onCambioCategoria();
      });
      els.categoriasNav.appendChild(btn);
    }

    crearPestana(TODAS, EMOJI_TODAS + " Todas");
    valores.forEach(function (valor) { crearPestana(valor, capitalize(valor)); });
  }

  function onCambioCategoria() {
    state.subfiltro.clear();
    renderNavCategorias(categoriasDisponibles);
    renderGrupoSubfiltro();
    renderTodo();
  }

  function renderGrupoSubfiltro() {
    var sf = SUBFILTROS[quitarEmojiInicial(state.categoria || "")];
    var disponibles = sf
      ? ordenarValores(valoresUnicos(function (r) {
          return r.categorias.indexOf(state.categoria) !== -1 ? r[sf.campo] : null;
        }))
      : [];
    els.grupoSubfiltro.hidden = disponibles.length === 0;
    els.subfiltroLabel.textContent = sf ? sf.label : "";
    renderChips(els.chipsSubfiltro, disponibles, state.subfiltro);
  }

  // Valores de los sub-filtros presentes en una receta (una por categoría a
  // la que pertenezca), para mostrarlos como chips en la card/detalle sin
  // depender de la pestaña activa.
  function valoresSubfiltro(receta) {
    var valores = [];
    (receta.categorias || []).forEach(function (categoria) {
      var sf = SUBFILTROS[quitarEmojiInicial(categoria)];
      var valor = sf ? receta[sf.campo] : null;
      if (valor && valores.indexOf(valor) === -1) {
        valores.push(valor);
      }
    });
    return valores;
  }

  function fotoHTML(foto, claseContenedor) {
    if (foto) {
      var img = document.createElement("img");
      img.src = foto;
      img.alt = "";
      img.loading = "lazy";
      return img;
    }
    var span = document.createElement("span");
    span.setAttribute("aria-hidden", "true");
    span.textContent = PLACEHOLDER_EMOJI;
    return span;
  }

  function recetasFiltradas() {
    return RECETAS.filter(function (r) {
      if (state.categoria && r.categorias.indexOf(state.categoria) === -1) return false;
      if (state.dificultades.size > 0) {
        if (!r.dificultad || !state.dificultades.has(r.dificultad)) return false;
      }
      if (state.subfiltro.size > 0) {
        var sf = SUBFILTROS[quitarEmojiInicial(state.categoria || "")];
        var valor = sf ? r[sf.campo] : null;
        if (!valor || !state.subfiltro.has(valor)) return false;
      }
      return true;
    });
  }

  function ordenarRecetas(lista) {
    var copia = lista.slice();
    if (state.orden === "alfabetico") {
      copia.sort(function (a, b) { return a.titulo.localeCompare(b.titulo, "es"); });
    } else {
      var signo = state.orden === "tiempo-desc" ? -1 : 1;
      copia.sort(function (a, b) {
        var ta = a.tiempo_minutos, tb = b.tiempo_minutos;
        if (ta == null && tb == null) return a.titulo.localeCompare(b.titulo, "es");
        if (ta == null) return 1;
        if (tb == null) return -1;
        return signo * (ta - tb);
      });
    }
    return copia;
  }

  function crearCard(receta) {
    var card = document.createElement("article");
    card.className = "card";
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", "Ver receta: " + receta.titulo);

    var foto = document.createElement("div");
    foto.className = "card-foto";
    foto.appendChild(fotoHTML(receta.foto));
    card.appendChild(foto);

    var body = document.createElement("div");
    body.className = "card-body";

    var titulo = document.createElement("h3");
    titulo.className = "card-titulo";
    titulo.textContent = receta.titulo;
    body.appendChild(titulo);

    var meta = document.createElement("div");
    meta.className = "card-meta";

    var badge = document.createElement("span");
    badge.className = "badge-dificultad " + (receta.dificultad || "sin-dato");
    badge.textContent = receta.dificultad ? capitalize(receta.dificultad) : "Sin dato";
    meta.appendChild(badge);

    var tiempo = document.createElement("span");
    tiempo.className = "pill-tiempo";
    tiempo.textContent = formatTiempo(receta.tiempo_minutos, receta.tiempo_minutos_max);
    meta.appendChild(tiempo);

    body.appendChild(meta);

    var chips = document.createElement("div");
    chips.className = "card-chips";
    receta.categorias.forEach(function (c) {
      var chip = document.createElement("span");
      chip.className = "chip-categoria";
      chip.textContent = capitalize(c);
      chips.appendChild(chip);
    });
    valoresSubfiltro(receta).forEach(function (valor) {
      var chipTipo = document.createElement("span");
      chipTipo.className = "chip-categoria";
      chipTipo.textContent = capitalize(valor);
      chips.appendChild(chipTipo);
    });
    body.appendChild(chips);

    card.appendChild(body);

    function abrir() { location.hash = "#/receta/" + receta.id; }
    card.addEventListener("click", abrir);
    card.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); abrir(); }
    });

    return card;
  }

  function haySeleccionActiva() {
    return !!state.categoria || state.dificultades.size > 0 || state.subfiltro.size > 0;
  }

  function renderGrid() {
    var lista = ordenarRecetas(recetasFiltradas());
    els.grid.innerHTML = "";
    lista.forEach(function (r) { els.grid.appendChild(crearCard(r)); });

    if (haySeleccionActiva()) {
      els.resultadoCount.textContent = lista.length + " de " + RECETAS.length + " receta(s)";
    } else {
      els.resultadoCount.textContent = RECETAS.length + " receta(s)";
    }

    els.grid.hidden = lista.length === 0;
    els.estadoVacio.hidden = lista.length !== 0;
  }

  // El badge y "Limpiar filtros" solo cuentan los filtros SECUNDARIOS
  // (dificultad, sub-filtro de categoría): la categoría ahora es navegación
  // primaria (navbar), no un filtro que se "limpia".
  function renderFiltrosEstado() {
    var totalActivos = state.dificultades.size + state.subfiltro.size;
    els.filtrosBadge.hidden = totalActivos === 0;
    els.filtrosBadge.textContent = String(totalActivos);
    els.limpiarFiltros.hidden = totalActivos === 0;
  }

  function renderTodo() {
    renderGrid();
    renderFiltrosEstado();
  }

  function slugify(texto) {
    return (texto || "")
      .normalize("NFD").replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "seccion";
  }

  // Los links externos del cuerpo (ej. URLs a YouTube linkificadas por
  // export_data.py) deben abrir en una pestaña nueva. Los links internos
  // "ver foto" (#/receta/<slug>/foto-<id>) tienen que navegar en la misma
  // pestaña: son parte del router hash-based, no una salida del sitio.
  function abrirLinksEnNuevaPestana(cuerpo) {
    cuerpo.querySelectorAll('a[href^="http://"], a[href^="https://"]').forEach(function (link) {
      link.setAttribute("target", "_blank");
      link.setAttribute("rel", "noopener noreferrer");
    });
  }

  // Envuelve cada sección (desde un <h2> hasta el próximo <h2>) en su propio
  // <details> colapsable. El h3 (ej. cada paso del paso a paso) queda como
  // contenido normal adentro de la sección, no se colapsa por separado.
  function agruparSecciones(cuerpo) {
    var nodos = Array.prototype.slice.call(cuerpo.childNodes);
    var fragmento = document.createDocumentFragment();
    var seccionActual = null;

    nodos.forEach(function (nodo) {
      if (nodo.nodeType === 1 && nodo.tagName === "H2") {
        var emoji = emojiDeSeccion(nodo.textContent);
        if (emoji) nodo.textContent = emoji + " " + nodo.textContent;

        var detalle = document.createElement("details");
        detalle.className = "detalle-seccion";
        detalle.open = true;

        var resumen = document.createElement("summary");
        resumen.appendChild(nodo);
        detalle.appendChild(resumen);

        fragmento.appendChild(detalle);
        seccionActual = detalle;
      } else if (seccionActual) {
        seccionActual.appendChild(nodo);
      } else {
        fragmento.appendChild(nodo);
      }
    });

    cuerpo.innerHTML = "";
    cuerpo.appendChild(fragmento);
  }

  // Índice de las secciones: los <h2> y, debajo de cada uno, sus <h3>
  // (ej. cada paso del paso a paso) anidados como sub-ítems.
  function crearIndice(cuerpo) {
    var headings = Array.prototype.filter.call(cuerpo.querySelectorAll("h2, h3"), function (h) {
      return h.textContent.trim() !== "";
    });
    var totalH2 = headings.filter(function (h) { return h.tagName === "H2"; }).length;
    if (totalH2 < 2) return null;

    var reducirMovimiento = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var idsUsados = {};

    function asignarId(h) {
      var texto = h.textContent.trim();
      var base = slugify(texto);
      var id = base, i = 2;
      while (idsUsados[id]) { id = base + "-" + i; i++; }
      idsUsados[id] = true;
      h.id = id;
      return texto;
    }

    function crearBoton(h, texto, claseExtra) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "detalle-indice-item" + (claseExtra ? " " + claseExtra : "");
      btn.textContent = texto;
      btn.addEventListener("click", function () {
        var seccion = h.closest("details.detalle-seccion");
        if (seccion && !seccion.open) seccion.open = true;
        h.scrollIntoView({ behavior: reducirMovimiento ? "auto" : "smooth", block: "start" });
      });
      return btn;
    }

    var detalle = document.createElement("details");
    detalle.className = "detalle-indice";
    detalle.open = true;

    var resumen = document.createElement("summary");
    resumen.textContent = "En esta receta";
    detalle.appendChild(resumen);

    var lista = document.createElement("ul");
    lista.className = "detalle-indice-lista";

    var subLista = null;

    headings.forEach(function (h) {
      var texto = asignarId(h);
      var li = document.createElement("li");

      if (h.tagName === "H2") {
        li.appendChild(crearBoton(h, texto));
        lista.appendChild(li);
        subLista = document.createElement("ul");
        subLista.className = "detalle-indice-lista detalle-indice-sublista";
        li.appendChild(subLista);
      } else if (subLista) {
        li.appendChild(crearBoton(h, texto, "detalle-indice-subitem"));
        subLista.appendChild(li);
      }
    });

    detalle.appendChild(lista);
    return detalle;
  }

  function renderDetalle(id) {
    var receta = RECETAS.find(function (r) { return r.id === id; });
    els.detalleContenido.innerHTML = "";

    if (!receta) {
      var p = document.createElement("p");
      p.className = "estado-vacio";
      p.textContent = "No encontramos esa receta.";
      els.detalleContenido.appendChild(p);
      return;
    }

    var foto = document.createElement("div");
    foto.className = "detalle-foto";
    foto.appendChild(fotoHTML(receta.foto));
    els.detalleContenido.appendChild(foto);

    var header = document.createElement("div");
    header.className = "detalle-header";

    var titulo = document.createElement("h2");
    titulo.className = "detalle-titulo";
    titulo.textContent = receta.titulo;
    header.appendChild(titulo);

    var meta = document.createElement("div");
    meta.className = "detalle-meta";

    var badge = document.createElement("span");
    badge.className = "badge-dificultad " + (receta.dificultad || "sin-dato");
    badge.textContent = receta.dificultad ? capitalize(receta.dificultad) : "Sin dato";
    meta.appendChild(badge);

    var tiempo = document.createElement("span");
    tiempo.className = "pill-tiempo";
    tiempo.textContent = formatTiempo(receta.tiempo_minutos, receta.tiempo_minutos_max);
    meta.appendChild(tiempo);

    if (receta.porciones) {
      var porciones = document.createElement("span");
      porciones.className = "pill-tiempo";
      porciones.textContent = receta.porciones + " porciones";
      meta.appendChild(porciones);
    }

    receta.categorias.forEach(function (c) {
      var chip = document.createElement("span");
      chip.className = "chip-categoria";
      chip.textContent = capitalize(c);
      meta.appendChild(chip);
    });
    valoresSubfiltro(receta).forEach(function (valor) {
      var chipTipo = document.createElement("span");
      chipTipo.className = "chip-categoria";
      chipTipo.textContent = capitalize(valor);
      meta.appendChild(chipTipo);
    });

    header.appendChild(meta);
    els.detalleContenido.appendChild(header);

    var cuerpo = document.createElement("div");
    cuerpo.className = "detalle-cuerpo";
    cuerpo.innerHTML = receta.body_html || "";
    abrirLinksEnNuevaPestana(cuerpo);
    agruparSecciones(cuerpo);

    var indice = crearIndice(cuerpo);
    if (indice) els.detalleContenido.appendChild(indice);

    els.detalleContenido.appendChild(cuerpo);

    if (receta.fuente) {
      var fuente = document.createElement("p");
      fuente.className = "detalle-fuente";
      fuente.textContent = "Fuente: " + receta.fuente;
      els.detalleContenido.appendChild(fuente);
    }

    document.title = receta.titulo + " — Recetas";
  }

  // El router es hash-based (#/receta/<slug>), así que un <a href="#foto-1">
  // normal rompería la navegación (route() lo interpretaría como "no hay
  // receta, mostrar la grilla"). Los links "ver foto" del cuerpo usan en vez
  // /foto-<id> como sufijo de la misma ruta (#/receta/<slug>/foto-<id>): no
  // cambia de receta, solo le pide a route() hacer scroll a esa imagen.
  function route() {
    var hash = location.hash || "#/";
    var match = hash.match(/^#\/receta\/([^/]+)(?:\/foto-(.+))?$/);
    if (match) {
      renderDetalle(decodeURIComponent(match[1]));
      els.vistaGrid.hidden = true;
      els.vistaDetalle.hidden = false;
      var fotoId = match[2] && "foto-" + decodeURIComponent(match[2]);
      var fotoEl = fotoId && document.getElementById(fotoId);
      if (fotoEl) {
        var seccion = fotoEl.closest("details.detalle-seccion");
        if (seccion && !seccion.open) seccion.open = true;
        var reducirMovimiento = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        fotoEl.scrollIntoView({ behavior: reducirMovimiento ? "auto" : "smooth", block: "center" });
      } else {
        window.scrollTo(0, 0);
      }
    } else {
      els.vistaGrid.hidden = false;
      els.vistaDetalle.hidden = true;
      document.title = "Recetas";
    }
  }

  function init() {
    categoriasDisponibles = ordenarValores(valoresUnicos(function (r) { return r.categorias; }));
    var dificultadesDisponibles = ordenarValores(valoresUnicos(function (r) { return r.dificultad; }), DIFICULTAD_ORDEN);

    renderNavCategorias(categoriasDisponibles);
    renderChips(els.chipsDificultad, dificultadesDisponibles, state.dificultades);
    renderGrupoSubfiltro();

    els.ordenSelect.addEventListener("change", function () {
      state.orden = els.ordenSelect.value;
      renderGrid();
    });

    els.limpiarFiltros.addEventListener("click", function (e) {
      e.preventDefault();
      state.dificultades.clear();
      state.subfiltro.clear();
      renderChips(els.chipsDificultad, dificultadesDisponibles, state.dificultades);
      renderGrupoSubfiltro();
      renderTodo();
    });

    els.filtrosToggle.addEventListener("click", function () {
      var abierto = els.filtrosPanel.classList.toggle("abierto");
      els.filtrosToggle.setAttribute("aria-expanded", abierto ? "true" : "false");
    });

    renderTodo();
    route();
    window.addEventListener("hashchange", route);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
