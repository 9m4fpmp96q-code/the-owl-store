"""Solo se envia a Espana y Portugal, y se hace cumplir en el pago.

Ejecutar con:  python3 tests/test_envios.py
"""
import os, sys, tempfile, shutil
from pathlib import Path

RAIZ = str(Path(__file__).resolve().parent.parent)
os.environ['ADMIN_PASSWORD']='clave'; os.environ['BASE_URL']='https://owl.test'
os.environ['GMAIL_USER']='t@owl.test'; os.environ['OWNER_EMAIL']='d@owl.test'
w=tempfile.mkdtemp()
for f in ('server.py','cj.py','catalogo.py'): shutil.copy(f'{RAIZ}/{f}', w)
os.chdir(w); sys.path.insert(0,w)
import server, catalogo
fails=[]
def check(n,c,e=''):
    print(('  OK   ' if c else '  FALLO')+f' {n} {e}')
    if not c: fails.append(n)

print('\n[1] El catalogo manda')
check('solo ES y PT', catalogo.PAISES_ENVIO == ['ES','PT'], f'({catalogo.PAISES_ENVIO})')
check('coste por pais', set(catalogo.COSTE_ENVIO_POR_PAIS) == {'ES','PT'})
check('referencia = el peor', catalogo.COSTE_ENVIO == 5.90, f'({catalogo.COSTE_ENVIO})')

print('\n[2] Stripe no deja elegir otro pais')
capt={}
class S:
    class checkout:
        class Session:
            @staticmethod
            def create(**kw):
                capt.update(kw); return type('o',(),{'url':'https://s.test','id':'cs_1'})()
server.stripe=S
c=server.app.test_client()
c.post('/create-checkout', json={'items':[{'model':'OWL Buds','qty':1}]})
paises=capt['shipping_address_collection']['allowed_countries']
check('la pasarela solo ofrece ES y PT', paises == ['ES','PT'], f'({paises})')
for fuera in ('DE','FR','GB','PL','IT'):
    check(f'{fuera} fuera', fuera not in paises)

print('\n[3] La web no promete lo que no hace')
import io
for ruta, prohibidas in (('index.html', ['Resto de Europa','para Europa']),
                         ('envios.html', ['Reino Unido','Polonia','Alemania','Francia']),
                         ('terminos.html', ['Reino Unido'])):
    t = io.open(f'{RAIZ}/{ruta}', encoding='utf-8').read()
    for p in prohibidas:
        check(f'{ruta} sin "{p}"', p not in t)

print('\n[4] Margen con el envio real')
coste = catalogo.AURICULARES['OWL Buds']['coste_compra'] + catalogo.FUNDA['coste_compra']
d = catalogo.desglose(coste, 39.95)
check('sigue siendo positivo', d['beneficio'] > 0, f"({d['beneficio']} EUR, {d['margen_pct']}%)")

print('\n'+('TODO CORRECTO' if not fails else f'FALLOS: {fails}'))
sys.exit(1 if fails else 0)
