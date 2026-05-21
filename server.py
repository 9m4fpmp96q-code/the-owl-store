import os, json, sqlite3, smtplib, stripe
from flask import Flask, request, jsonify, send_from_directory, redirect
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = Flask(__name__, static_folder='.')
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

PRICES = {'Gen2':35,'Gen3':35,'Gen4':35,'Gen4 ANC':35,'Pro2':35,'Pro2 ANC':37,'Pro3':37,'Pro3 ANC':39}

# ── DATABASE ──────────────────────────────────────────────────────────────────
def get_db():
    db = sqlite3.connect('orders.db')
    db.row_factory = sqlite3.Row
    return db

def init_db():
    with get_db() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS orders (
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
        )''')

init_db()

# ── EMAIL ─────────────────────────────────────────────────────────────────────
def send_email(to, subject, html):
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = os.getenv('GMAIL_USER')
        msg['To']      = to
        msg.attach(MIMEText(html, 'html'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(os.getenv('GMAIL_USER'), os.getenv('GMAIL_APP_PASSWORD'))
            server.sendmail(os.getenv('GMAIL_USER'), to, msg.as_string())
    except Exception as e:
        print(f'Email error: {e}')

def notify_owner(order):
    html = f"""
    <h2>🛒 Nuevo pedido OWL #{order['id']}</h2>
    <table style="font-family:sans-serif;font-size:14px">
      <tr><td><b>Modelo</b></td><td>{order['model']} x{order['qty']}</td></tr>
      <tr><td><b>Total</b></td><td>{order['price']}€</td></tr>
      <tr><td><b>Cliente</b></td><td>{order['customer_name']}</td></tr>
      <tr><td><b>Email</b></td><td>{order['customer_email']}</td></tr>
      <tr><td><b>Dirección</b></td><td>{order['customer_address']}</td></tr>
    </table>
    <p style="margin-top:20px">
      <b>Acción:</b> Entra en Alibaba y haz el pedido con esta dirección de envío.
    </p>
    """
    send_email(os.getenv('OWNER_EMAIL'), f'Nuevo pedido #{order["id"]} — {order["model"]}', html)

def notify_supplier(order):
    html = f"""
    <p>Hola,</p>
    <p>Por favor envía el siguiente pedido:</p>
    <table style="font-family:sans-serif;font-size:14px">
      <tr><td><b>Producto</b></td><td>AirPods {order['model']} + funda silicona OWL</td></tr>
      <tr><td><b>Cantidad</b></td><td>{order['qty']}</td></tr>
      <tr><td><b>Enviar a</b></td><td>{order['customer_name']}<br>{order['customer_address']}</td></tr>
    </table>
    <p>Gracias.</p>
    """
    send_email(os.getenv('SUPPLIER_EMAIL'), f'Pedido nuevo — {order["model"]} x{order["qty"]}', html)

def notify_customer(order):
    html = f"""
    <h2>¡Gracias por tu compra, {order['customer_name'].split()[0]}! 🦉</h2>
    <p>Hemos recibido tu pedido:</p>
    <table style="font-family:sans-serif;font-size:14px">
      <tr><td><b>Producto</b></td><td>AirPods {order['model']} + Cover OWL</td></tr>
      <tr><td><b>Total</b></td><td>{order['price']}€</td></tr>
      <tr><td><b>Enviamos a</b></td><td>{order['customer_address']}</td></tr>
    </table>
    <p>Te avisaremos cuando tu pedido esté en camino. Tiempo estimado: 7-14 días.</p>
    <p>— El equipo OWL 🦉</p>
    """
    send_email(order['customer_email'], '¡Pedido confirmado! — OWL Store', html)

# ── STRIPE CHECKOUT ───────────────────────────────────────────────────────────
@app.route('/create-checkout', methods=['POST'])
def create_checkout():
    data  = request.json
    model = data.get('model', 'Gen4 ANC')
    qty   = int(data.get('qty', 1))
    price = PRICES.get(model, 35)

    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
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
        }],
        mode='payment',
        shipping_address_collection={'allowed_countries': ['ES','FR','DE','IT','PT','BE','NL','AT','PL','GB']},
        customer_email=data.get('email'),
        metadata={'model': model, 'qty': str(qty)},
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

        order = {
            'session_id':       s['id'],
            'model':            s['metadata'].get('model','Gen4 ANC'),
            'qty':              int(s['metadata'].get('qty', 1)),
            'price':            s['amount_total'] // 100,
            'customer_name':    shipping.get('name', s.get('customer_details',{}).get('name','')),
            'customer_email':   s.get('customer_email',''),
            'customer_address': address,
        }

        with get_db() as db:
            cur = db.execute(
                'INSERT OR IGNORE INTO orders (session_id,model,qty,price,customer_name,customer_email,customer_address) VALUES (?,?,?,?,?,?,?)',
                (order['session_id'],order['model'],order['qty'],order['price'],order['customer_name'],order['customer_email'],order['customer_address'])
            )
            order['id'] = cur.lastrowid

        notify_owner(order)
        notify_supplier(order)
        notify_customer(order)

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
def admin():
    with get_db() as db:
        orders = db.execute('SELECT * FROM orders ORDER BY created_at DESC').fetchall()
    rows = ''.join(f'''<tr>
        <td>#{o["id"]}</td>
        <td>{o["model"]} x{o["qty"]}</td>
        <td><b>{o["price"]}€</b></td>
        <td>{o["customer_name"]}</td>
        <td>{o["customer_email"]}</td>
        <td style="font-size:12px">{o["customer_address"]}</td>
        <td><span style="background:{"#d4edda" if o["status"]=="pagado" else "#fff3cd"};padding:3px 10px;border-radius:20px;font-size:12px">{o["status"]}</span></td>
        <td style="font-size:12px;color:#888">{o["created_at"][:16]}</td>
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

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5003))
    debug = os.environ.get('RENDER') is None  # debug solo en local
    print(f'🦉 OWL Store running on port {port}')
    print(f'   Admin: http://localhost:{port}/admin')
    app.run(host='0.0.0.0', port=port, debug=debug)
