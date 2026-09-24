"""Catálogo con costes reales y cálculo de precio de venta.

Aquí se toca UN sitio y se actualiza toda la tienda. Cada modelo lleva lo que
cuesta de verdad; el precio de venta sale de aplicar el margen objetivo y
redondear al siguiente x9,90, que es como se fija precio en retail.

Los costes marcados ESTIMADO hay que sustituirlos por los reales cuando
se cierre proveedor.
"""

# ── COSTES FIJOS POR PEDIDO ───────────────────────────────────────────────────
COSTE_PACKAGING   = 0.80   # caja + etiqueta
COSTE_ENVIO       = 3.50   # envío nacional desde almacén España
STRIPE_PCT        = 0.015  # 1,5 % tarjetas del EEE
STRIPE_FIJO       = 0.25
TASA_DEVOLUCIONES = 0.08   # 8 % de pedidos que vuelven o fallan

# Margen objetivo sobre el precio de venta (no sobre el coste).
# 0.50 = la mitad de lo que cobras es tuyo antes de publicidad.
MARGEN_OBJETIVO = 0.50

# ── COSTES DE COMPRA ──────────────────────────────────────────────────────────
# coste_compra: lo que pagas al proveedor por la unidad, puesto en almacén.
# cj_pid: id del producto en CJ Dropshipping. Sin él, el pedido no se
#         automatiza y cae al aviso por email (nunca se pierde).
FUNDA = {
    'nombre':       'Funda OWL + mosquetón',
    'coste_compra': 3.00,   # ESTIMADO — pendiente del coste real
    'cj_pid':       None,
}

# Producto decidido el 2026-09-24: auriculares de marca propia.
#
# Se deja de revender marca ajena y se fabrican con el logo OWL. Es lo que
# hace que el precio funcione: unos auriculares de otra marca los compara
# el cliente en Amazon en diez segundos; los tuyos no los tiene nadie.
#
# OJO con el coste: es ESTIMADO hasta que vuelvan los presupuestos de
# fábrica. En cuanto tengas el precio real, se cambia aquí y toda la tienda
# se recalcula sola. No publiques ficha técnica hasta que la fábrica
# confirme las características: prometer ANC que la unidad no trae es la
# forma más rápida de comerse las devoluciones.
AURICULARES = {
    'OWL Buds': {'coste_compra': 11.00, 'cj_pid': None},   # ESTIMADO 8-14 €
}

# Precio fijado por el dueño el 2026-09-24. Con marca propia el precio deja
# de estar atado al de nadie: no hay referencia con la que compararte.
PRECIO_PACK_FIJO = 39.95


def _redondea_comercial(precio):
    """Redondea al siguiente escalón de retail: x4,90 o x9,90.

    Con solo x9,90 un céntimo de más en el coste disparaba el precio 10 €.
    Los medios escalones mantienen el margen pegado al objetivo.
    """
    decenas = int(precio // 10)
    for candidato in (decenas * 10 + 4.90, decenas * 10 + 9.90,
                      (decenas + 1) * 10 + 4.90, (decenas + 1) * 10 + 9.90):
        if precio <= candidato:
            return round(candidato, 2)
    return round((decenas + 1) * 10 + 9.90, 2)


def coste_total(coste_compra, con_envio=True):
    """Lo que te cuesta servir una unidad, sin contar la comisión de pago."""
    base = coste_compra + COSTE_PACKAGING + (COSTE_ENVIO if con_envio else 0)
    return round(base * (1 + TASA_DEVOLUCIONES), 2)


def precio_sugerido(coste_compra, con_envio=True, margen=None):
    """Precio de venta que deja el margen objetivo, ya redondeado."""
    m = MARGEN_OBJETIVO if margen is None else margen
    bruto = (coste_total(coste_compra, con_envio) + STRIPE_FIJO) / (1 - m - STRIPE_PCT)
    return _redondea_comercial(bruto)


def desglose(coste_compra, precio_venta, con_envio=True):
    """Qué se lleva cada uno en una venta. Para el panel de pedidos."""
    coste   = coste_total(coste_compra, con_envio)
    comision = round(precio_venta * STRIPE_PCT + STRIPE_FIJO, 2)
    neto    = round(precio_venta - coste - comision, 2)
    return {
        'precio_venta': round(precio_venta, 2),
        'coste':        coste,
        'comision':     comision,
        'beneficio':    neto,
        'margen_pct':   round(neto / precio_venta * 100, 1) if precio_venta else 0.0,
    }


# ── PRECIOS DE VENTA ──────────────────────────────────────────────────────────
# El pack lleva auriculares + funda. La funda sola va sin coste de auriculares
# y con envío de sobre, mucho más barato.
COSTE_ENVIO_SOBRE = 1.80

# Fijado a mano por el dueño el 2026-09-24. No sale de precio_sugerido():
# es precio de entrada, pensado para que comprar la funda no se piense.
PRECIO_FUNDA_SOLA = 12.95

PRECIO_PACK_2_FUNDAS = 21.90   # dos fundas: descuento real sobre 2 x 12,95

PRECIOS_PACK = {modelo: PRECIO_PACK_FIJO for modelo in AURICULARES}


def resumen():
    """Imprime la tabla de precios y márgenes. Para revisarlo de un vistazo."""
    filas = []
    for modelo, datos in AURICULARES.items():
        coste = datos['coste_compra'] + FUNDA['coste_compra']
        d = desglose(coste, PRECIOS_PACK[modelo])
        filas.append((modelo, coste, d['precio_venta'], d['beneficio'], d['margen_pct']))
    return filas


if __name__ == '__main__':
    print(f"{'MODELO':<12} {'COSTE':>8} {'VENTA':>8} {'TUYO':>8} {'MARGEN':>8}")
    print('-' * 48)
    for modelo, coste, venta, benef, pct in resumen():
        print(f'{modelo:<12} {coste:>7.2f}€ {venta:>7.2f}€ {benef:>7.2f}€ {pct:>7.1f}%')
    fs = desglose(FUNDA['coste_compra'] - 0.50, PRECIO_FUNDA_SOLA, con_envio=False)
    fs['coste'] = round(fs['coste'] + COSTE_ENVIO_SOBRE, 2)
    fs['beneficio'] = round(PRECIO_FUNDA_SOLA - fs['coste'] - fs['comision'], 2)
    print('-' * 48)
    print(f"{'Funda sola':<12} {fs['coste']:>7.2f}€ {PRECIO_FUNDA_SOLA:>7.2f}€ "
          f"{fs['beneficio']:>7.2f}€ {fs['beneficio']/PRECIO_FUNDA_SOLA*100:>7.1f}%")
