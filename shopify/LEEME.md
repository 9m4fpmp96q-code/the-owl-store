# OWL en Shopify — guía de migración

Todo lo necesario para pasar OWL Store de la web Flask a una tienda Shopify
con el mismo diseño. La web actual sigue funcionando en Render hasta el
último paso: en ningún momento te quedas sin tienda.

## Qué hay en esta carpeta

| Archivo | Para qué |
|---|---|
| `tema-owl.zip` | El tema de Shopify con el diseño OWL. Se sube tal cual. |
| `tema-owl/` | El código del tema (lo mismo que el .zip, sin comprimir). |
| `productos.csv` | Los 3 productos para importar: el pack (activo) y las fundas (borrador). |
| `imagenes/pack-owl.png` | Imagen del pack (la ilustración, 2048 × 2048) para la ficha del producto. |
| `politicas/` | Textos legales adaptados a Shopify, listos para pegar. |

## Lo que hace el tema

Revisado con **Theme Check**, el revisor oficial de Shopify: 0 errores y 0 avisos.
La fuente (Inter) se sirve desde el CDN de Shopify, no desde Google: carga
más rápido y no envía la IP de los visitantes a Google.

- Portada, ficha de producto, carrito lateral y barra de compra en el móvil,
  idénticos a la web actual. Modo oscuro incluido (y arreglado: en la web
  actual los botones negros quedaban ilegibles en modo oscuro).
- Mientras no haya fotos reales se muestra la ilustración del pack, con la
  nota «Las fotos reales llegan con la primera producción». Nunca fotos de
  otro producto.
- Reseñas: el estado vacío honesto («Todavía no hay ninguna») hasta que
  instales una app de reseñas verificadas y añadas su bloque.
- Ficha técnica: el texto de «Todavía no la publicamos» hasta que la fábrica
  confirme las características.
- Todos los textos se cambian desde **Tienda online → Personalizar**, sin
  tocar código.
- Página «Próximamente» para mientras la tienda tenga contraseña, que recoge
  emails para avisar de la apertura.

## Pasos

Los marcados con 👤 los tienes que hacer tú (crear cuentas, aceptar
condiciones o meter datos bancarios no lo puedo hacer yo). El resto lo
puedo hacer yo en cuanto conectes el conector de Shopify en Claude.

### 1. 👤 Crear la tienda
1. Ve a shopify.com y crea la tienda (hay prueba gratis).
2. País: España · Moneda: euro · Idioma: español.
3. En Claude, pulsa **Connect** en el conector de Shopify y autoriza tu tienda.

### 2. Datos de la tienda
**Configuración → Datos de la tienda**
- Nombre: `OWL` · Email de contacto: `theowlstore26@gmail.com`.
- Formato de moneda (**Configuración → Mercados → Monedas**, o en «Datos de la
  tienda» según tu versión): usa `{{amount_with_comma_separator}} €` para que
  los precios salgan como `39,95 €`.

### 3. Subir el tema
**Tienda online → Temas → Añadir tema → Subir archivo zip** → `tema-owl.zip`.
Pulsa **Personalizar** para revisarlo y **Publicar** cuando esté listo.

### 4. Productos
1. **Productos → Importar** → `productos.csv`.
2. Abre «Pack OWL — OWL Buds» y arrastra `imagenes/pack-owl.png` a Multimedia.
3. Comprueba que el identificador (handle) es `pack-owl`: la portada lo usa.
4. **Peso**: pon el peso real de cada producto (el CSV lo deja a 0).
5. **Inventario**: el CSV lo deja a 0 unidades, así que el pack aparece
   «Agotado» hasta que tengas stock. Cuando llegue, pon la cantidad real.
   *Si quieres vender antes de tener stock* (preventa), marca «Seguir vendiendo
   cuando no haya stock» **y cambia los textos de «48 h»**: prometer una
   entrega que no puedes cumplir es lo que la ley y los clientes no perdonan.
6. Las fundas quedan en **borrador**: publícalas cuando quieras venderlas.

### 5. Textos legales
**Configuración → Políticas**. Abre cada archivo de `politicas/` en el
navegador, selecciona todo, copia y pega:

| Archivo | Política de Shopify |
|---|---|
| `devoluciones.html` | Política de reembolso |
| `privacidad.html` | Política de privacidad |
| `condiciones.html` | Términos del servicio |
| `envios.html` | Política de envío |
| `aviso-legal.html` | Aviso legal |

⚠️ **Sustituye cada `[PENDIENTE: …]`** (nombre o razón social, NIF, domicilio
y dominio). La LSSI obliga a publicarlos antes de vender a distancia: no
abras la tienda sin ellos. Los textos son una base razonable, pero no
sustituyen el consejo de un profesional.

### 6. Página de contacto
**Tienda online → Páginas → Añadir página**
- Título: `Contacto` · Contenido: pega `politicas/contacto.html`.
- Plantilla: `page.contact` (añade el formulario debajo del texto).
- Comprueba que la URL queda en `/pages/contacto` (el pie de página enlaza ahí).

### 7. Envíos
**Configuración → Envío y entrega** → crea dos zonas con tarifa **gratis (0 €)**:
- España (incluye Baleares; Canarias, Ceuta y Melilla, solo si las vas a atender).
- Europa: Portugal, Francia, Alemania, Italia, Bélgica, Países Bajos, Austria,
  Polonia y Reino Unido.

### 8. Impuestos
**Configuración → Impuestos y aranceles** → marca **«Incluir impuestos en los
precios»** (los precios de OWL ya llevan IVA). Si vas a vender bastante a
otros países de la UE, pregunta a tu gestor por el régimen de ventanilla
única (OSS).

### 9. 👤 Pagos
**Configuración → Pagos** → activa **Shopify Payments** con tus datos y tu
cuenta bancaria. Comisión en el plan Basic: 2,1 % + 0,30 € por tarjeta
europea (1,14 € por pack). Actualiza `STRIPE_PCT` y `STRIPE_FIJO` en
`catalogo.py` a `0.021` y `0.30` para que los márgenes cuadren.

### 10. Cookies y privacidad
**Configuración → Privacidad de los clientes** → activa el **aviso de
cookies** para la UE/EEE y Reino Unido. La política de privacidad ya lo explica.

### 11. Pantalla de pago y emails
- **Configuración → Pantalla de pago**: sube el logo (usa `assets/favicon.svg`
  convertido a PNG) y pon el negro `#111111` como color principal.
- **Configuración → Notificaciones**: revisa el email de confirmación de pedido
  (Shopify ya lo trae en español).

### 12. Apps (opcionales)
- **Reseñas verificadas** (p. ej. Judge.me, con plan gratuito): después añade su
  bloque a la sección «Reseñas» en Personalizar.
- **Proveedor / almacén**: si usas CJ Dropshipping, su app oficial sustituye a
  `cj.py`. Si fabricas y guardas el stock en un almacén, busca la app de ese
  almacén; si envías tú, no hace falta nada.

### 13. Antes de abrir
- [ ] Todos los `[PENDIENTE]` de las políticas sustituidos.
- [ ] Stock real cargado (o preventa con los textos de entrega corregidos).
- [ ] Pedido de prueba hecho (Configuración → Pagos → modo de prueba) y reembolsado.
- [ ] Revisado en el móvil.
- [ ] **Tienda online → Preferencias → Protección con contraseña**: desactivar.

### 14. 👤 Cambiar el dominio y apagar Render
1. **Configuración → Dominios**: conecta tu dominio (cambias los DNS donde lo compraste).
2. Exporta los pedidos antiguos del panel de la web Flask si quieres conservarlos.
3. Cuando el dominio ya apunte a Shopify, suspende el servicio y la base de
   datos de Render para dejar de pagarlos.

## Qué pasa con el código Flask

| Archivo | En Shopify |
|---|---|
| `server.py` (checkout, webhook, panel, emails) | Lo hace Shopify. |
| `cj.py` | Lo hace la app del proveedor, si la usas. |
| Reseñas propias | App de reseñas verificadas. |
| `catalogo.py` | **Se queda**: sigue siendo tu calculadora de precios y márgenes. |

Nada de esto se borra: el repositorio queda como estaba.
