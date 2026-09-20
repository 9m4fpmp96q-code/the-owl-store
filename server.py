import os, json, hmac, html, sqlite3, smtplib, stripe
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, redirect, Response
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = Flask(__name__, static_folder='.')
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

PRICES = {'Gen2':35,'Gen3':35,'Gen4':35,'Gen4 ANC':35,'Pro2':35,'Pro2 ANC':37,'Pro3':37,'Pro3 ANC':39}

# ── DATABASE ──────────────────────────────────────────────────────────────────
# En producción usa Postgres (DATABASE_URL). En local, SQLite.
# Render borra el disco del plan gratuito en cada reinicio: sin Postgres
# los pedidos se pierden.
DATABASE_URL = os.getenv('DATABASE_URL', '')
USE_PG = DATABASE_URL.startswith('postgres')

if USE_PG:
    import psycopg2
    from psycopg2.extras import RealDictCursor

def get_db():
    if USE_PG:
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    db = sqlite3.connect('orders.db')
    db.row_factory = sqlite3.Row
    return db

def init_db():
    schema_pg = '''CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY,
        session_id TEXT UNIQUE,
        model TEXT,
        qty INTEGER,
        price INTEGER,
        customer_name TEXT,
        customer_email TEXT,
        customer_address TEXT,
        status TEXT DEFAULT 'pagado',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )'''
    schema_sqlite = '''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT UNIQUE,
        model TEXT,
        qty INTEGER,
        price INTEGER,
        customer_name TEXT,
        customer_email TEXT,
        customer_address TEXT,
        status TEXT DEFAULT 'pagado',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )'''
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(schema_pg if USE_PG else schema_sqlite)
        conn.commit()
    finally:
        conn.close()

def save_order(o):
    """Guarda el pedido. Devuelve (id, es_nuevo).

    Stripe reintenta los webhooks: si el pedido ya existía devolvemos
    es_nuevo=False para no reenviar los emails por duplicado.
    """
    cols = (o['session_id'], o['model'], o['qty'], o['price'],
            o['customer_name'], o['customer_email'], o['customer_address'])
    conn = get_db()
    try:
        cur = conn.cursor()
        if USE_PG:
            cur.execute('''INSERT INTO orders
                (session_id,model,qty,price,customer_name,customer_email,customer_address)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (session_id) DO NOTHING RETURNING id''', cols)
            row = cur.fetchone()
            if row:
                conn.commit()
                return row['id'], True
            cur.execute('SELECT id FROM orders WHERE session_id = %s', (o['session_id'],))
            existing = cur.fetchone()
            conn.commit()
            return (existing['id'] if existing else 0), False
        cur.execute('''INSERT OR IGNORE INTO orders
            (session_id,model,qty,price,customer_name,customer_email,customer_address)
            VALUES (?,?,?,?,?,?,?)''', cols)
        conn.commit()
        if cur.rowcount:
            return cur.lastrowid, True
        cur.execute('SELECT id FROM orders WHERE session_id = ?', (o['session_id'],))
        existing = cur.fetchone()
        return (existing['id'] if existing else 0), False
    finally:
        conn.close()

def all_orders():
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute('SELECT * FROM orders ORDER BY created_at DESC')
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

init_db()

# ── AUTENTICACIÓN DEL PANEL ───────────────────────────────────────────────────
def require_admin(f):
    """Protege /admin. Sin ADMIN_PASSWORD el panel queda cerrado, nunca abierto."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        password = os.getenv('ADMIN_PASSWORD', '')
        if not password:
            return Response('Panel deshabilitado: falta configurar ADMIN_PASSWORD.', 503)
        auth = request.authorization
        ok = (auth and auth.username == 'owl'
              and hmac.compare_digest(auth.password or '', password))
        if not ok:
            return Response('Acceso restringido', 401,
                            {'WWW-Authenticate': 'Basic realm="OWL Admin"'})
        return f(*args, **kwargs)
    return wrapper

# ── EMAIL ─────────────────────────────────────────────────────────────────────
def send_email(to, subject, body_html):
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = os.getenv('GMAIL_USER')
        msg['To']      = to
        msg.attach(MIMEText(body_html, 'html'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(os.getenv('GMAIL_USER'), os.getenv('GMAIL_APP_PASSWORD'))
            server.sendmail(os.getenv('GMAIL_USER'), to, msg.as_string())
    except Exception as e:
        print(f'Email error: {e}')

EMAIL_BASE = """
<!DOCTYPE html><html><head><meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
</head><body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5;padding:40px 16px">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%">
  <!-- HEADER -->
  <tr><td style="background:#111;border-radius:16px 16px 0 0;padding:28px 40px;text-align:center">
    <span style="font-size:28px;font-weight:900;letter-spacing:0.12em;color:#fff">OWL</span>
  </td></tr>
  <!-- BODY -->
  <tr><td style="background:#fff;padding:40px;border-radius:0 0 16px 16px">
    {body}
  </td></tr>
  <!-- FOOTER -->
  <tr><td style="padding:24px;text-align:center;font-size:12px;color:#aaa">
    OWL Accessories · Envío gratis a Europa<br/>
    <a href="{store_url}" style="color:#aaa">{store_url}</a>
  </td></tr>
</table>
</td></tr></table>
</body></html>
"""

def render_email(body):
    """Monta el email con la URL real de la tienda (no una fija que caduca)."""
    return EMAIL_BASE.format(body=body, store_url=os.getenv('BASE_URL', ''))

def support_email():
    return os.getenv('OWNER_EMAIL') or os.getenv('GMAIL_USER') or ''

def _row(label, value):
    return f'<tr><td style="padding:10px 0;border-bottom:1px solid #f0f0f0;font-size:14px;color:#888;width:120px;vertical-align:top">{label}</td><td style="padding:10px 0;border-bottom:1px solid #f0f0f0;font-size:14px;color:#111;font-weight:600">{value}</td></tr>'

def notify_owner(order):
    body = f"""
    <h2 style="margin:0 0 8px;font-size:22px;font-weight:800;letter-spacing:-0.02em;color:#111">🛒 Nuevo pedido #{order['id']}</h2>
    <p style="margin:0 0 28px;color:#888;font-size:14px">Acción requerida: hacer el pedido al proveedor con la dirección de abajo.</p>
    <table width="100%" cellpadding="0" cellspacing="0">
      {_row('Pedido', f"#{order['id']}")}
      {_row('Modelo', f"{order['model']} x{order['qty']}")}
      {_row('Total', f"<span style='color:#111;font-size:18px;font-weight:900'>{order['price']} €</span>")}
      {_row('Cliente', order['customer_name'])}
      {_row('Email', f"<a href='mailto:{order['customer_email']}' style='color:#111'>{order['customer_email']}</a>")}
      {_row('Dirección', order['customer_address'])}
    </table>
    <div style="margin-top:28px;background:#f5f5f5;border-radius:10px;padding:16px">
      <p style="margin:0;font-size:13px;color:#555"><strong>Próximo paso:</strong> Entra en Alibaba/proveedor y realiza el pedido enviando a la dirección del cliente indicada arriba.</p>
    </div>
    """
    send_email(os.getenv('OWNER_EMAIL'), f'🛒 Nuevo pedido #{order["id"]} — {order["model"]} ({order["price"]}€)', render_email(body))

def notify_supplier(order):
    body = f"""
    <h2 style="margin:0 0 8px;font-size:22px;font-weight:800;letter-spacing:-0.02em;color:#111">Nuevo pedido</h2>
    <p style="margin:0 0 28px;color:#888;font-size:14px">Por favor, prepara y envía el siguiente pedido a la dirección indicada.</p>
    <table width="100%" cellpadding="0" cellspacing="0">
      {_row('Producto', f"AirPods {order['model']} + Funda silicona OWL")}
      {_row('Cantidad', str(order['qty']))}
      {_row('Destinatario', order['customer_name'])}
      {_row('Dirección envío', order['customer_address'])}
    </table>
    <p style="margin-top:28px;font-size:14px;color:#555">Gracias por tu colaboración.</p>
    """
    send_email(os.getenv('SUPPLIER_EMAIL'), f'Pedido — {order["model"]} x{order["qty"]}', render_email(body))

def notify_customer(order):
    # Stripe puede devolver el nombre vacío: sin este guardo el email reventaba.
    parts = (order['customer_name'] or '').split()
    first_name = parts[0] if parts else 'de nuevo'
    body = f"""
    <div style="text-align:center;margin-bottom:32px">
      <div style="font-size:48px;margin-bottom:12px">🦉</div>
      <h2 style="margin:0 0 8px;font-size:24px;font-weight:900;letter-spacing:-0.02em;color:#111">¡Gracias, {first_name}!</h2>
      <p style="margin:0;color:#888;font-size:15px">Tu pedido ha sido confirmado y está en proceso.</p>
    </div>
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px">
      {_row('Producto', f"AirPods {order['model']} + Cover OWL + Mosquetón")}
      {_row('Total', f"<span style='color:#111;font-size:18px;font-weight:900'>{order['price']} €</span>")}
      {_row('Envío', 'Gratis')}
      {_row('Dirección', order['customer_address'])}
      {_row('Entrega estimada', '7–14 días hábiles')}
    </table>
    <div style="background:#f5f5f5;border-radius:10px;padding:20px;text-align:center;margin-bottom:28px">
      <p style="margin:0;font-size:14px;color:#555">Te enviaremos otro email cuando tu pedido esté en camino con el número de seguimiento.</p>
    </div>
    <p style="text-align:center;font-size:13px;color:#aaa;margin:0">¿Alguna duda? Escríbenos a <a href="mailto:{support_email()}" style="color:#111">{support_email()}</a></p>
    """
    send_email(order['customer_email'], f'¡Pedido confirmado! 🦉 — OWL Store', render_email(body))

# ── STRIPE CHECKOUT ───────────────────────────────────────────────────────────
@app.route('/create-checkout', methods=['POST'])
def create_checkout():
    data = request.json

    # Soporta tanto items[] (carrito completo) como model/qty (legado)
    raw_items = data.get('items')
    if not raw_items:
        raw_items = [{'model': data.get('model', 'Gen4 ANC'), 'qty': int(data.get('qty', 1))}]

    line_items = []
    for item in raw_items:
        model = item.get('model', 'Gen4 ANC')
        qty   = int(item.get('qty', 1))
        price = PRICES.get(model, 35)
        line_items.append({
            'price_data': {
                'currency': 'eur',
                'product_data': {
                    'name': f'AirPods {model} + Cover OWL',
                    'description': 'Auriculares inalámbricos + funda personalizada OWL + mosquetón de acero',
                    'images': [],
                },
                'unit_amount': price * 100,
            },
            'quantity': qty,
        })

    # Metadata: serializa todos los modelos para el webhook
    meta_models = ','.join(f"{i['model']}x{i['qty']}" for i in raw_items)

    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=line_items,
        mode='payment',
        shipping_address_collection={'allowed_countries': ['ES','FR','DE','IT','PT','BE','NL','AT','PL','GB']},
        customer_email=data.get('email'),
        metadata={'items': meta_models},
        success_url=os.getenv('BASE_URL') + '/success?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=os.getenv('BASE_URL') + '/',
    )
    return jsonify({'url': session.url})

# ── STRIPE WEBHOOK ────────────────────────────────────────────────────────────
@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.data
    sig     = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig, os.getenv('STRIPE_WEBHOOK_SECRET'))
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    if event['type'] == 'checkout.session.completed':
        s       = event['data']['object']
        shipping = s.get('shipping_details') or {}
        addr    = shipping.get('address', {})
        address = f"{addr.get('line1','')} {addr.get('line2','')} {addr.get('postal_code','')} {addr.get('city','')} {addr.get('country','')}".strip()

        # Soporta metadata nueva (items) y legada (model/qty)
        meta_items = s['metadata'].get('items')
        if meta_items:
            model_label = meta_items
            qty_total   = sum(int(p.split('x')[1]) for p in meta_items.split(','))
        else:
            model_label = s['metadata'].get('model', 'Gen4 ANC')
            qty_total   = int(s['metadata'].get('qty', 1))

        # Stripe Checkout solo rellena customer_email si se pre-cargó al crear
        # la sesión. El email que escribe el comprador llega en customer_details.
        details = s.get('customer_details') or {}
        email   = details.get('email') or s.get('customer_email') or ''
        name    = shipping.get('name') or details.get('name') or ''

        order = {
            'session_id':       s['id'],
            'model':            model_label,
            'qty':              qty_total,
            'price':            s['amount_total'] // 100,
            'customer_name':    name,
            'customer_email':   email,
            'customer_address': address,
        }

        order['id'], is_new = save_order(order)

        if is_new:
            notify_owner(order)
            notify_supplier(order)
            if email:
                notify_customer(order)
            else:
                print('Aviso: pedido sin email de cliente, no se envía confirmación.')

    return jsonify({'ok': True})

# ── SUCCESS PAGE ──────────────────────────────────────────────────────────────
@app.route('/success')
def success():
    return '''<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>Pedido confirmado — OWL</title>
<style>
  body{font-family:-apple-system,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#f5f5f7}
  .box{text-align:center;max-width:480px;padding:48px 32px;background:#fff;border-radius:24px;box-shadow:0 4px 40px rgba(0,0,0,0.08)}
  .icon{font-size:64px;margin-bottom:16px}
  h1{font-size:28px;font-weight:800;margin:0 0 12px}
  p{color:#666;line-height:1.6}
  a{display:inline-block;margin-top:24px;padding:14px 32px;background:#111;color:#fff;border-radius:100px;text-decoration:none;font-weight:600}
</style></head>
<body><div class="box">
  <div class="icon">🦉</div>
  <h1>¡Pedido confirmado!</h1>
  <p>Hemos recibido tu pedido y te hemos enviado un email de confirmación.<br>
  Tu pack llegará en <strong>7-14 días</strong>.</p>
  <a href="/">Volver a la tienda</a>
</div></body></html>'''

# ── ADMIN PANEL ───────────────────────────────────────────────────────────────
@app.route('/admin')
@require_admin
def admin():
    orders = all_orders()
    def esc(v):
        # El nombre y la dirección los escribe el comprador: nunca se
        # insertan crudos en el HTML.
        return html.escape(str(v if v is not None else ''))
    rows = ''.join(f'''<tr>
        <td>#{esc(o["id"])}</td>
        <td>{esc(o["model"])} x{esc(o["qty"])}</td>
        <td><b>{esc(o["price"])}€</b></td>
        <td>{esc(o["customer_name"])}</td>
        <td>{esc(o["customer_email"])}</td>
        <td style="font-size:12px">{esc(o["customer_address"])}</td>
        <td><span style="background:{"#d4edda" if o["status"]=="pagado" else "#fff3cd"};padding:3px 10px;border-radius:20px;font-size:12px">{esc(o["status"])}</span></td>
        <td style="font-size:12px;color:#888">{esc(o["created_at"])[:16]}</td>
    </tr>''' for o in orders)
    total = sum(o['price'] for o in orders)
    return f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Admin — OWL Store</title>
<style>
  body{{font-family:-apple-system,sans-serif;margin:0;background:#f5f5f7}}
  .header{{background:#111;color:#fff;padding:20px 40px;display:flex;align-items:center;gap:16px}}
  .header h1{{margin:0;font-size:20px}}
  .stats{{display:flex;gap:16px;padding:24px 40px}}
  .stat{{background:#fff;border-radius:16px;padding:20px 28px;flex:1}}
  .stat .n{{font-size:32px;font-weight:800}}
  .stat .l{{font-size:13px;color:#888;margin-top:4px}}
  table{{width:calc(100% - 80px);margin:0 40px;border-collapse:collapse;background:#fff;border-radius:16px;overflow:hidden}}
  th{{background:#f5f5f7;padding:12px 16px;text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:#888}}
  td{{padding:14px 16px;border-top:1px solid #f0f0f0;font-size:14px}}
  tr:hover td{{background:#fafafa}}
</style></head>
<body>
<div class="header"><span style="font-size:28px">🦉</span><h1>OWL Store — Panel de pedidos</h1></div>
<div class="stats">
  <div class="stat"><div class="n">{len(orders)}</div><div class="l">Pedidos totales</div></div>
  <div class="stat"><div class="n">{total}€</div><div class="l">Ingresos totales</div></div>
  <div class="stat"><div class="n">{sum(1 for o in orders if o["status"]=="pagado")}</div><div class="l">Pendientes de enviar</div></div>
</div>
<table>
  <tr><th>#</th><th>Modelo</th><th>Precio</th><th>Cliente</th><th>Email</th><th>Dirección</th><th>Estado</th><th>Fecha</th></tr>
  {rows or '<tr><td colspan="8" style="text-align:center;padding:40px;color:#888">No hay pedidos aún</td></tr>'}
</table>
</body></html>'''

# ── STATIC FILES ──────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/envios')
def envios():
    return send_from_directory('.', 'envios.html')

@app.route('/devoluciones')
def devoluciones():
    return send_from_directory('.', 'devoluciones.html')

@app.route('/contacto')
def contacto():
    return send_from_directory('.', 'contacto.html')

@app.route('/privacidad')
def privacidad():
    return send_from_directory('.', 'privacidad.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)

@app.errorhandler(404)
def not_found(e):
    return send_from_directory('.', '404.html'), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5003))
    debug = os.environ.get('RENDER') is None  # debug solo en local
    print(f'🦉 OWL Store running on port {port}')
    print(f'   Admin: http://localhost:{port}/admin')
    app.run(host='0.0.0.0', port=port, debug=debug)
