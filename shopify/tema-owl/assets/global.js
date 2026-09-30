/**
 * global.js — Comportamiento del tema OWL en Shopify.
 *
 * Portado de la web original y adaptado a Shopify:
 *   - El carrito ya no vive en localStorage: se guarda en Shopify y se
 *     maneja con su API de carrito (/cart.js, /cart/add.js, /cart/change.js).
 *     Así el precio que ve el cliente es siempre el que cobra Shopify.
 *   - El pago lo hace el checkout de Shopify (ya no hay /create-checkout).
 *
 * window.OWL lo rellena theme.liquid: carrito inicial, formato de moneda,
 * rutas y textos traducidos.
 */
(function () {
  'use strict';

  var OWL = window.OWL || {};
  var textos = OWL.textos || {};
  document.documentElement.classList.add('js');

  // ── UTILIDADES ───────────────────────────────────────────────────
  /**
   * Formatea céntimos con el formato de moneda de la tienda
   * (Configuración → Datos de la tienda), p. ej. "{{amount_with_comma_separator}} €".
   */
  function formatoDinero(centimos, formato) {
    formato = formato || OWL.formatoDinero || '{{amount_with_comma_separator}} €';
    var valor = (typeof centimos === 'string' ? parseInt(centimos, 10) : centimos) || 0;

    function conSeparadores(numero, decimales, miles, decimal) {
      var fijo = (numero / 100).toFixed(decimales);
      var partes = fijo.split('.');
      var entero = partes[0].replace(/\B(?=(\d{3})+(?!\d))/g, miles);
      return partes[1] ? entero + decimal + partes[1] : entero;
    }

    var marcador = /\{\{\s*(\w+)\s*\}\}/;
    var tipo = (formato.match(marcador) || [])[1];
    var texto;
    switch (tipo) {
      case 'amount_no_decimals': texto = conSeparadores(valor, 0, ',', '.'); break;
      case 'amount_with_comma_separator': texto = conSeparadores(valor, 2, '.', ','); break;
      case 'amount_no_decimals_with_comma_separator': texto = conSeparadores(valor, 0, '.', ','); break;
      case 'amount_with_apostrophe_separator': texto = conSeparadores(valor, 2, "'", '.'); break;
      case 'amount_with_space_separator': texto = conSeparadores(valor, 2, ' ', ','); break;
      default: texto = conSeparadores(valor, 2, ',', '.');
    }
    // El formato puede traer HTML (p. ej. "<span>€</span>"): se queda solo el texto.
    var tmp = document.createElement('div');
    tmp.innerHTML = formato.replace(marcador, texto);
    return tmp.textContent;
  }
  OWL.formatoDinero = OWL.formatoDinero || '{{amount_with_comma_separator}} €';
  OWL.formatear = formatoDinero;

  function peticionJSON(url, datos) {
    var opciones = datos
      ? { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify(datos) }
      : { headers: { Accept: 'application/json' } };
    return fetch(url, opciones).then(function (r) {
      return r.json().then(function (json) {
        if (!r.ok) {
          var error = new Error(json.description || json.message || textos.errorCarrito);
          error.datos = json;
          throw error;
        }
        return json;
      });
    });
  }

  // ── MODO OSCURO ──────────────────────────────────────────────────
  // El tema guardado se aplica en <head> (theme.liquid) antes de pintar,
  // para que no haya un destello blanco al cargar en modo oscuro.
  var botonesTema = document.querySelectorAll('.js-theme-toggle');
  function pintaBotonTema() {
    var oscuro = document.documentElement.getAttribute('data-theme') === 'dark';
    botonesTema.forEach(function (b) {
      b.textContent = oscuro ? '☀️' : '🌙';
      b.setAttribute('aria-pressed', oscuro ? 'true' : 'false');
    });
  }
  botonesTema.forEach(function (boton) {
    boton.addEventListener('click', function () {
      var oscuro = document.documentElement.getAttribute('data-theme') === 'dark';
      if (oscuro) document.documentElement.removeAttribute('data-theme');
      else document.documentElement.setAttribute('data-theme', 'dark');
      try { localStorage.setItem('owl-theme', oscuro ? 'light' : 'dark'); } catch (e) { /* modo privado */ }
      pintaBotonTema();
    });
  });
  pintaBotonTema();

  // ── APARICIÓN AL HACER SCROLL ────────────────────────────────────
  var elementosReveal = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    var observador = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('visible'); observador.unobserve(e.target); }
      });
    }, { threshold: 0.1 });
    elementosReveal.forEach(function (el) { observador.observe(el); });
  } else {
    elementosReveal.forEach(function (el) { el.classList.add('visible'); });
  }

  // ── CABECERA Y BARRA DE COMPRA MÓVIL ─────────────────────────────
  var nav = document.querySelector('.js-nav');
  var barraMovil = document.querySelector('.js-barra-movil');
  var heroe = document.querySelector('.hero');
  var botonPrincipal = document.querySelector('.js-add-to-cart');

  // window.scrollY se queda a 0 en algunos visores embebidos aunque la
  // página esté desplazada: se toma el mayor de los valores disponibles.
  function desplazamiento() {
    return Math.max(window.scrollY || 0, document.documentElement.scrollTop || 0, document.body.scrollTop || 0);
  }

  function alDesplazar() {
    var y = desplazamiento();
    if (nav) nav.classList.toggle('scrolled', y > 40);
    if (!barraMovil) return;
    var visible;
    if (heroe) {
      // Portada: aparece al pasar la mayor parte del héroe.
      visible = y > heroe.offsetHeight * 0.75;
    } else if (botonPrincipal) {
      // Ficha de producto: aparece cuando el botón de comprar ya ha subido.
      visible = botonPrincipal.getBoundingClientRect().bottom < 0;
    } else {
      visible = y > 400;
    }
    barraMovil.classList.toggle('visible', visible);
  }
  window.addEventListener('scroll', alDesplazar, { passive: true });
  alDesplazar();

  // ── ENLACES A SECCIONES DE LA PORTADA ────────────────────────────
  // "#producto" o "/#producto": si la sección está en esta página, se
  // desplaza con suavidad en lugar de recargar.
  document.querySelectorAll('a[href^="#"], a[href^="/#"]').forEach(function (a) {
    a.addEventListener('click', function (e) {
      var href = a.getAttribute('href');
      var id = href.slice(href.indexOf('#') + 1);
      if (!id) return;
      var destino = document.getElementById(id);
      if (destino) {
        e.preventDefault();
        destino.scrollIntoView({ behavior: 'smooth' });
        if (history.replaceState) history.replaceState(null, '', '#' + id);
      }
    });
  });

  // ── MINIATURAS DE LA FICHA ───────────────────────────────────────
  document.querySelectorAll('.js-thumbs').forEach(function (tira) {
    var contenedor = tira.closest('.product-images');
    var principal = contenedor && contenedor.querySelector('.js-main-img img');
    tira.querySelectorAll('.product-thumb').forEach(function (miniatura) {
      miniatura.addEventListener('click', function () {
        tira.querySelectorAll('.product-thumb').forEach(function (t) { t.classList.remove('active'); });
        miniatura.classList.add('active');
        if (!principal) return;
        principal.classList.add('fade');
        setTimeout(function () {
          principal.removeAttribute('srcset');
          principal.src = miniatura.dataset.src;
          principal.alt = miniatura.dataset.alt || principal.alt;
          principal.classList.remove('fade');
        }, 200);
      });
    });
  });

  // ── CARRITO LATERAL ──────────────────────────────────────────────
  var cajon = document.querySelector('.js-cart-drawer');
  var capa = document.querySelector('.js-cart-overlay');
  var listaCarrito = document.querySelector('.js-cart-items');
  var vacioCarrito = document.querySelector('.js-cart-empty');
  var ultimoFoco = null;

  function abrirCarrito() {
    if (!cajon) { window.location.href = OWL.rutas.carrito; return; }
    ultimoFoco = document.activeElement;
    cajon.classList.add('open');
    cajon.setAttribute('aria-hidden', 'false');
    if (capa) capa.classList.add('open');
    document.body.style.overflow = 'hidden';
    var cerrar = cajon.querySelector('.js-cart-close');
    if (cerrar) cerrar.focus();
  }

  function cerrarCarrito() {
    if (!cajon) return;
    cajon.classList.remove('open');
    cajon.setAttribute('aria-hidden', 'true');
    if (capa) capa.classList.remove('open');
    document.body.style.overflow = '';
    if (ultimoFoco && ultimoFoco.focus) ultimoFoco.focus();
  }

  document.querySelectorAll('.js-cart-open').forEach(function (b) {
    b.addEventListener('click', function (e) {
      if (!cajon) return;       // sin cajón, el enlace lleva a /cart
      e.preventDefault();
      abrirCarrito();
    });
  });
  document.querySelectorAll('.js-cart-close').forEach(function (b) { b.addEventListener('click', cerrarCarrito); });
  if (capa) capa.addEventListener('click', cerrarCarrito);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && cajon && cajon.classList.contains('open')) cerrarCarrito();
  });

  function crear(etiqueta, clase, texto) {
    var el = document.createElement(etiqueta);
    if (clase) el.className = clase;
    if (texto !== undefined) el.textContent = texto;   // textContent: nunca HTML de datos
    return el;
  }

  function pintaCarrito(carrito) {
    OWL.carrito = carrito;
    document.querySelectorAll('.js-cart-count').forEach(function (c) { c.textContent = carrito.item_count; });
    if (!cajon) return;

    cajon.querySelectorAll('.js-cart-subtotal').forEach(function (el) {
      el.textContent = formatoDinero(carrito.items_subtotal_price);
    });
    cajon.querySelectorAll('.js-cart-total').forEach(function (el) {
      el.textContent = formatoDinero(carrito.total_price);
    });
    cajon.querySelectorAll('.js-checkout').forEach(function (b) { b.disabled = carrito.item_count === 0; });

    listaCarrito.querySelectorAll('.cart-item').forEach(function (el) { el.remove(); });
    if (vacioCarrito) vacioCarrito.style.display = carrito.item_count === 0 ? 'flex' : 'none';

    carrito.items.forEach(function (linea) {
      var fila = crear('div', 'cart-item');

      var foto = crear('div', 'cart-item-img');
      if (linea.image) {
        var img = document.createElement('img');
        img.src = linea.image + (linea.image.indexOf('?') > -1 ? '&' : '?') + 'width=160';
        img.alt = linea.product_title;
        img.loading = 'lazy';
        foto.appendChild(img);
      } else {
        foto.textContent = '🦉';
      }

      var info = crear('div', 'cart-item-info');
      var nombre = crear('div', 'cart-item-name');
      var enlace = crear('a', '', linea.product_title);
      enlace.href = linea.url;
      nombre.appendChild(enlace);
      info.appendChild(nombre);
      if (linea.variant_title && linea.variant_title !== 'Default Title') {
        info.appendChild(crear('div', 'cart-item-sub', linea.variant_title));
      }

      var controles = crear('div', 'cart-item-controls');
      var menos = crear('button', 'qty-btn', '−');
      menos.type = 'button';
      menos.setAttribute('aria-label', textos.reducir);
      var cantidad = crear('span', 'qty-val', String(linea.quantity));
      var mas = crear('button', 'qty-btn', '+');
      mas.type = 'button';
      mas.setAttribute('aria-label', textos.aumentar);
      menos.addEventListener('click', function () { cambiaLinea(linea.key, linea.quantity - 1); });
      mas.addEventListener('click', function () { cambiaLinea(linea.key, linea.quantity + 1); });
      controles.append(menos, cantidad, mas);
      info.appendChild(controles);

      var lado = crear('div', 'cart-item-lado');
      var quitar = crear('button', 'cart-remove', '✕');
      quitar.type = 'button';
      quitar.setAttribute('aria-label', textos.quitar + ' ' + linea.product_title);
      quitar.addEventListener('click', function () { cambiaLinea(linea.key, 0); });
      lado.append(quitar, crear('span', 'cart-item-price', formatoDinero(linea.final_line_price)));

      fila.append(foto, info, lado);
      listaCarrito.appendChild(fila);
    });
  }

  function cambiaLinea(clave, cantidad) {
    listaCarrito.classList.add('cargando');
    peticionJSON(OWL.rutas.carritoCambiar + '.js', { id: clave, quantity: Math.max(0, cantidad) })
      .then(pintaCarrito)
      .catch(function (err) { alert(err.message || textos.errorCarrito); })
      .then(function () { listaCarrito.classList.remove('cargando'); });
  }

  function refrescaCarrito() {
    return peticionJSON(OWL.rutas.carrito + '.js').then(pintaCarrito);
  }
  OWL.refrescaCarrito = refrescaCarrito;

  if (OWL.carrito) pintaCarrito(OWL.carrito);
  // Al volver con el botón "atrás" del navegador la página sale de la
  // caché con el carrito viejo: se vuelve a pedir.
  window.addEventListener('pageshow', function (e) { if (e.persisted) refrescaCarrito(); });

  // ── FORMULARIO DE COMPRA ─────────────────────────────────────────
  function variantesDe(formulario) {
    var seccion = formulario.closest('[data-section]');
    var json = seccion && seccion.querySelector('.js-variants-json');
    try { return json ? JSON.parse(json.textContent) : []; } catch (e) { return []; }
  }

  function actualizaVariante(formulario, variante) {
    var seccion = formulario.closest('[data-section]') || document;
    var boton = formulario.querySelector('.js-add-to-cart');
    var precio = formatoDinero(variante.price);
    seccion.querySelectorAll('.js-precio').forEach(function (el) { el.textContent = precio; });
    seccion.querySelectorAll('.js-precio-antes').forEach(function (el) {
      var hayOferta = variante.compare_at_price && variante.compare_at_price > variante.price;
      el.textContent = hayOferta ? formatoDinero(variante.compare_at_price) : '';
      el.hidden = !hayOferta;
    });
    if (boton) {
      boton.disabled = !variante.available;
      var etiqueta = boton.querySelector('.js-etiqueta-boton');
      if (etiqueta) etiqueta.textContent = variante.available ? boton.dataset.textoComprar + ' — ' + precio : textos.agotado;
    }
    seccion.querySelectorAll('.js-barra-comprar').forEach(function (b) { b.disabled = !variante.available; });
    if (formulario.dataset.actualizaUrl === 'true' && history.replaceState) {
      var url = new URL(window.location.href);
      url.searchParams.set('variant', variante.id);
      history.replaceState(null, '', url.toString());
    }
  }

  document.querySelectorAll('.js-product-form').forEach(function (formulario) {
    var boton = formulario.querySelector('.js-add-to-cart');
    var error = formulario.querySelector('.js-form-error');
    var selector = formulario.querySelector('.js-variant-select');

    if (selector) {
      selector.addEventListener('change', function () {
        var id = parseInt(selector.value, 10);
        var variante = variantesDe(formulario).filter(function (v) { return v.id === id; })[0];
        if (variante) actualizaVariante(formulario, variante);
      });
    }

    formulario.addEventListener('submit', function (e) {
      if (!window.fetch) return;           // navegador muy antiguo: envío normal
      e.preventDefault();
      if (!boton || boton.disabled) return;
      if (error) { error.hidden = true; error.textContent = ''; }
      boton.disabled = true;
      boton.setAttribute('aria-busy', 'true');

      var datos = new FormData(formulario);
      var id = parseInt(datos.get('id'), 10);
      var cantidad = parseInt(datos.get('quantity'), 10) || 1;

      peticionJSON(OWL.rutas.carritoAnadir + '.js', { items: [{ id: id, quantity: cantidad }] })
        .then(function () { return refrescaCarrito(); })
        .then(function () {
          abrirCarrito();
          var etiqueta = boton.querySelector('.js-etiqueta-boton');
          var original = etiqueta ? etiqueta.textContent : '';
          if (etiqueta) etiqueta.textContent = textos.anadido;
          boton.classList.add('anadido');
          setTimeout(function () {
            if (etiqueta) etiqueta.textContent = original;
            boton.classList.remove('anadido');
          }, 1800);
          document.querySelectorAll('.js-cart-count').forEach(function (c) {
            c.classList.add('bump');
            setTimeout(function () { c.classList.remove('bump'); }, 300);
          });
        })
        .catch(function (err) {
          if (error) { error.textContent = err.message || textos.errorCarrito; error.hidden = false; }
        })
        .then(function () {
          boton.disabled = false;
          boton.removeAttribute('aria-busy');
        });
    });
  });

  // El botón de la barra móvil compra con el formulario principal.
  document.querySelectorAll('.js-barra-comprar').forEach(function (b) {
    b.addEventListener('click', function () {
      var seccion = b.closest('[data-section]');
      var formulario = (seccion && seccion.querySelector('.js-product-form')) || document.querySelector('.js-product-form');
      if (!formulario) return;
      if (formulario.requestSubmit) formulario.requestSubmit();
      else formulario.dispatchEvent(new Event('submit', { cancelable: true }));
    });
  });

  window.OWL = OWL;
})();
