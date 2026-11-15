(function () {
  "use strict";

  // Calendario de frutas y verduras de estación (AMBA). Fuente: Mercado Central
  // de Bs. As. / INTA y productoresymercados.com. Los meses son temporada pico
  // (1 = enero … 12 = diciembre); los bordes son aproximados (±1 mes).
  var MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
  var MESES_LARGO = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

  function rango(a, b) {
    var r = [];
    for (var m = a; m <= b; m++) r.push(m);
    return r;
  }

  var GRUPOS = [
    {
      titulo: "Frutas", emoji: "🍓", clase: "frutas",
      items: [
        ["Cítricos", "naranja, mandarina, pomelo, limón", rango(4, 10)],
        ["Pomáceas", "manzana, pera", rango(2, 7)],
        ["Membrillo, granada y caqui", "", rango(3, 5)],
        ["Uva", "", rango(1, 4)],
        ["Higo", "", rango(1, 3)],
        ["Kiwi", "", rango(6, 8)],
        ["Palta", "", rango(6, 10)],
        ["Frutilla", "", rango(8, 12)],
        ["Arándano", "", rango(9, 12)],
        ["Frambuesa y mora", "", [1, 2, 12]],
        ["Cereza y damasco", "", [11, 12]],
        ["Carozo", "durazno, pelón, ciruela", [1, 2, 11, 12]],
        ["Melón y sandía", "", [1, 2, 12]],
      ],
    },
    {
      titulo: "Verduras", emoji: "🥬", clase: "verduras",
      items: [
        ["Hortalizas de fruto", "tomate, morrón, berenjena, zapallito, pepino", [1, 2, 3, 11, 12]],
        ["Choclo", "", [1, 2, 3, 12]],
        ["Chaucha", "", [1, 2, 11, 12]],
        ["Zapallos", "calabaza, anco, criollo", rango(2, 6)],
        ["Hortalizas de hoja", "acelga, espinaca, rúcula, radicheta", rango(4, 10)],
        ["Crucíferas", "brócoli, coliflor, repollo, repollito de Bruselas, kale", rango(5, 9)],
        ["Hinojo, apio y puerro", "", rango(4, 7)],
        ["Alcaucil", "", rango(8, 11)],
        ["Espárrago", "", rango(9, 11)],
        ["Habas y arvejas", "", rango(9, 11)],
      ],
    },
  ];

  function el(tag, cls, texto) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (texto != null) e.textContent = texto;
    return e;
  }

  function render(container) {
    container.textContent = "";
    var mesActual = new Date().getMonth() + 1;
    var esPico = function (it) { return it[2].indexOf(mesActual) !== -1; };

    container.appendChild(el("h2", "estacion-titulo", "Frutas y verduras de estación"));
    container.appendChild(el("p", "estacion-sub",
      "Casilla pintada = temporada pico (mejor precio y calidad). Fuera de esos meses puede haber por cámara o importación, pero más caro y peor. Bordes aproximados (±1 mes)."));

    // Resumen: qué está en pico este mes, separado por tipo.
    var ahora = el("section", "estacion-ahora");
    ahora.appendChild(el("h3", "estacion-ahora-titulo", "En pico en " + MESES_LARGO[mesActual - 1]));
    var cols = el("div", "estacion-ahora-cols");
    GRUPOS.forEach(function (g) {
      var col = el("div", "estacion-ahora-col " + g.clase);
      col.appendChild(el("h4", null, g.emoji + " " + g.titulo));
      var chips = el("ul", "estacion-chips");
      var en = g.items.filter(esPico);
      en.forEach(function (it) { chips.appendChild(el("li", null, it[0])); });
      if (!en.length) chips.appendChild(el("li", "vacio", "Nada en pico este mes"));
      col.appendChild(chips);
      cols.appendChild(col);
    });
    ahora.appendChild(cols);
    container.appendChild(ahora);

    GRUPOS.forEach(function (g) {
      var bloque = el("section", "estacion-bloque " + g.clase);
      bloque.appendChild(el("h3", "estacion-bloque-titulo", g.emoji + " " + g.titulo));

      var wrap = el("div", "estacion-scroll");
      var tabla = el("table", "estacion-tabla");
      var thead = el("thead");
      var trh = el("tr");
      trh.appendChild(el("th", "estacion-nombre-col", ""));
      MESES.forEach(function (m, i) {
        var th = el("th", i + 1 === mesActual ? "mes-actual" : "", m);
        th.scope = "col";
        trh.appendChild(th);
      });
      thead.appendChild(trh);
      tabla.appendChild(thead);

      var tbody = el("tbody");
      g.items.forEach(function (it) {
        var tr = el("tr", esPico(it) ? "en-pico" : "");
        var th = el("th", "estacion-nombre");
        th.scope = "row";
        th.appendChild(document.createTextNode(it[0]));
        if (esPico(it)) th.appendChild(el("span", "estacion-ahora-tag", "ahora"));
        if (it[1]) th.appendChild(el("span", "estacion-detalle", it[1]));
        tr.appendChild(th);
        for (var m = 1; m <= 12; m++) {
          var pico = it[2].indexOf(m) !== -1;
          var td = el("td", (pico ? "pico" : "") + (m === mesActual ? " mes-actual" : ""));
          if (pico) {
            td.setAttribute("aria-label", "temporada en " + MESES_LARGO[m - 1]);
            td.title = it[0] + " — " + MESES_LARGO[m - 1];
          }
          tr.appendChild(td);
        }
        tbody.appendChild(tr);
      });
      tabla.appendChild(tbody);
      wrap.appendChild(tabla);
      bloque.appendChild(wrap);
      container.appendChild(bloque);
    });

    container.appendChild(el("p", "estacion-nota",
      "Todo el año (no figuran): papa, cebolla, zanahoria, batata, ajo, lechuga (cambia la variedad), limón y manzana de cámara."));
    var fuentes = el("p", "estacion-nota");
    fuentes.appendChild(document.createTextNode("Fuentes: "));
    var a1 = el("a", null, "Mercado Central de Bs. As. / INTA");
    a1.href = "https://www.mercadocentral.gob.ar/publicaciones/calendario-de-las-principales-frutas-y-hortalizas";
    var a2 = el("a", null, "productoresymercados.com");
    a2.href = "https://productoresymercados.com/calendario-de-frutas-y-verduras";
    [a1, a2].forEach(function (a) { a.target = "_blank"; a.rel = "noopener"; });
    fuentes.appendChild(a1);
    fuentes.appendChild(document.createTextNode(" · "));
    fuentes.appendChild(a2);
    container.appendChild(fuentes);
  }

  window.renderEstacion = render;
})();
