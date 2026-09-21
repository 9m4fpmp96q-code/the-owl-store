"""Integración con CJ Dropshipping.

Manda el pedido al proveedor cuando Stripe confirma el pago, y recupera el
número de seguimiento cuando sale del almacén.

REGLA DE ORO: esto nunca puede tumbar un pedido. Cada función devuelve
(ok, datos_o_motivo) en lugar de lanzar excepciones. Si CJ está caído o las
credenciales faltan, el pedido se guarda igual y al dueño le llega el aviso
por email para hacerlo a mano.

Escrito contra la API v2 documentada de CJ. Sin credenciales reales no se ha
podido probar contra el servidor: la primera venta real hay que vigilarla.
"""

import os, json, time, urllib.request, urllib.error

API = 'https://developers.cjdropshipping.com/api2.0/v1'

_token = {'valor': None, 'expira': 0}


def configurado():
    return bool(os.getenv('CJ_EMAIL') and os.getenv('CJ_API_KEY'))


def _peticion(metodo, ruta, cuerpo=None, token=None, timeout=20):
    url = API + ruta
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(url, data=datos, method=metodo)
    req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('CJ-Access-Token', token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detalle = e.read().decode(errors='replace')[:300]
        return False, f'HTTP {e.code}: {detalle}'
    except Exception as e:
        return False, f'{type(e).__name__}: {e}'


def _access_token():
    """Token de CJ, cacheado. Dura 15 días; lo renovamos a los 12."""
    if _token['valor'] and time.time() < _token['expira']:
        return True, _token['valor']
    if not configurado():
        return False, 'Faltan CJ_EMAIL o CJ_API_KEY'

    ok, resp = _peticion('POST', '/authentication/getAccessToken', {
        'email':    os.getenv('CJ_EMAIL'),
        'password': os.getenv('CJ_API_KEY'),
    })
    if not ok:
        return False, f'Login CJ falló: {resp}'
    if not resp.get('result'):
        return False, f'Login CJ rechazado: {resp.get("message", resp)}'

    valor = (resp.get('data') or {}).get('accessToken')
    if not valor:
        return False, f'Login CJ sin token: {resp}'
    _token['valor']  = valor
    _token['expira'] = time.time() + 12 * 24 * 3600
    return True, valor


def _trocea_direccion(order):
    """La dirección llega de Stripe en una sola línea; CJ la quiere por partes."""
    return {
        'nombre':   (order.get('customer_name') or 'Cliente').strip(),
        'direccion': (order.get('customer_address') or '').strip(),
        'cp':        (order.get('customer_zip') or '').strip(),
        'ciudad':    (order.get('customer_city') or '').strip(),
        'provincia': (order.get('customer_state') or '').strip(),
        'pais':      (order.get('customer_country') or 'ES').strip().upper(),
        'telefono':  (order.get('customer_phone') or '').strip(),
    }


def crear_pedido(order, productos):
    """Envía el pedido a CJ.

    productos: lista de {'vid': <variante CJ>, 'quantity': n}
    Devuelve (ok, id_pedido_cj) o (False, motivo).
    """
    if not productos:
        return False, 'Ningún producto tiene id de CJ asignado'

    ok, token = _access_token()
    if not ok:
        return False, token

    d = _trocea_direccion(order)
    cuerpo = {
        'orderNumber':          f"OWL-{order.get('id')}",
        'shippingCountryCode':  d['pais'],
        'shippingProvince':     d['provincia'],
        'shippingCity':         d['ciudad'],
        'shippingAddress':      d['direccion'],
        'shippingZip':          d['cp'],
        'shippingCustomerName': d['nombre'],
        'shippingPhone':        d['telefono'],
        'remark':               'OWL Store',
        'fromCountryCode':      os.getenv('CJ_ALMACEN', 'ES'),
        'logisticName':         os.getenv('CJ_LOGISTICA', 'CJPacket Sensitive'),
        'products':             productos,
    }

    ok, resp = _peticion('POST', '/shopping/order/createOrderV2', cuerpo, token)
    if not ok:
        return False, f'CJ no aceptó el pedido: {resp}'
    if not resp.get('result'):
        return False, f'CJ rechazó el pedido: {resp.get("message", resp)}'

    datos = resp.get('data') or {}
    cj_id = datos.get('orderId') or datos.get('orderNumber')
    if not cj_id:
        return False, f'CJ respondió sin id de pedido: {resp}'
    return True, str(cj_id)


def estado_pedido(cj_order_id):
    """Consulta el estado y el número de seguimiento de un pedido ya enviado."""
    ok, token = _access_token()
    if not ok:
        return False, token

    ok, resp = _peticion('GET', f'/shopping/order/getOrderDetail?orderId={cj_order_id}',
                         token=token)
    if not ok:
        return False, f'No se pudo consultar CJ: {resp}'
    if not resp.get('result'):
        return False, f'CJ rechazó la consulta: {resp.get("message", resp)}'

    datos = resp.get('data') or {}
    return True, {
        'estado':     datos.get('orderStatus') or '',
        'seguimiento': datos.get('trackNumber') or '',
        'transportista': datos.get('logisticName') or '',
    }
