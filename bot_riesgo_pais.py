import tweepy
import requests
import time
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, firestore
import os
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import datetime, timedelta
import math
import random

# Definir las credenciales usando las variables de entorno
firebase_cred = {
    "type": os.environ.get('FIREBASE_TYPE'),
    "project_id": os.environ.get('FIREBASE_PROJECT_ID'),
    "private_key_id": os.environ.get('FIREBASE_PRIVATE_KEY_ID'),
    "private_key": os.environ.get('FIREBASE_PRIVATE_KEY').replace("\\n", "\n"),
    "client_email": os.environ.get('FIREBASE_CLIENT_EMAIL'),
    "client_id": os.environ.get('FIREBASE_CLIENT_ID'),
    "auth_uri": os.environ.get('FIREBASE_AUTH_URI'),
    "token_uri": os.environ.get('FIREBASE_TOKEN_URI'),
    "auth_provider_x509_cert_url": os.environ.get('FIREBASE_AUTH_PROVIDER_X509_CERT_URL'),
    "client_x509_cert_url": os.environ.get('FIREBASE_CLIENT_X509_CERT_URL'),
    "universe_domain": os.environ.get('FIREBASE_UNIVERSE_DOMAIN')
}

# Inicializa Firebase con las credenciales del diccionario
cred = credentials.Certificate(firebase_cred)
firebase_admin.initialize_app(cred)

# Inicializa el cliente de Firestore
db = firestore.client()

# Credenciales OAuth 2.0
BEARER_TOKEN = os.environ.get('BEARER_TOKEN')
CONSUMER_KEY = os.environ.get('CONSUMER_KEY')
CONSUMER_SECRET = os.environ.get('CONSUMER_SECRET')
ACCESS_TOKEN = os.environ.get('ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.environ.get('ACCESS_TOKEN_SECRET')

# Inicializa el cliente de Tweepy con el Bearer Token
client = tweepy.Client(BEARER_TOKEN, CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)

auth = tweepy.OAuth1UserHandler(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)

# URL y cabeceras de la API de RapidAPI para riesgo país
url_riesgo_pais = "https://riesgo-pais.p.rapidapi.com/api/riesgopais"
headers = {
    "x-rapidapi-key": "a2df4bf8demsh97afe8342a3d223p118bd5jsn7414c6a2d7b7",
    "x-rapidapi-host": "riesgo-pais.p.rapidapi.com"
}

def leer_ultimo_valor_guardado():
    doc_ref = db.collection('riesgo_pais').document('ultimo_valor')
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get('valor')
    return None

def leer_valor_dia_anterior():
    doc_ref = db.collection('riesgo_pais').document('valor_dia_anterior')
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get('valor')
    return None

def leer_historico_riesgo_pais():
    historico = []
    docs = db.collection('historico_riesgo_pais').stream()
    for doc in docs:
        data = doc.to_dict()
        fecha = data.get('fecha')
        valor = data.get('valor')
        historico.append((datetime.strptime(fecha, '%d-%m-%Y'), valor))
    return historico

def guardar_valor_riesgo_pais(valor):
    doc_ref = db.collection('riesgo_pais').document('ultimo_valor')
    doc_ref.set({'valor': valor})

def actualizar_valor_dia_anterior():
    """Actualizar el valor del día anterior al final del día."""
    valor_actual = leer_ultimo_valor_guardado()
    if valor_actual is not None:
        guardar_valor_dia_anterior(valor_actual)

def guardar_valor_dia_anterior(valor):
    doc_ref = db.collection('riesgo_pais').document('valor_dia_anterior')
    doc_ref.set({'valor': valor})

def guardar_historico_riesgo_pais(valor):
    """Guarda el valor del riesgo país para la fecha actual en Firestore."""
    # Obtener la fecha actual en el formato requerido
    fecha_actual = datetime.now(pytz.timezone('America/Argentina/Buenos_Aires')).strftime('%d-%m-%Y')
    
    # Referencia al documento usando la fecha como ID
    doc_ref = db.collection('historico_riesgo_pais').document(fecha_actual)
    
    # Escritura del valor sin verificar si ya existe (asumimos que se ejecuta solo una vez al día)
    doc_ref.set({'fecha': fecha_actual, 'valor': valor})
    print(f"Valor del riesgo país guardado para la fecha {fecha_actual}: {valor}")

def obtener_riesgo_pais():
    """Obtiene el valor del riesgo país de la API de RapidAPI."""
    response = requests.get(url_riesgo_pais, headers=headers)
    if response.status_code == 200:
        datos = response.json()
        return int(datos['ultimo'])
    return None

def calcular_porcentaje_cambio(nuevo_valor, ultimo_valor):
    """Calcula el porcentaje de cambio entre el nuevo valor y el último valor."""
    if ultimo_valor is None or ultimo_valor == 0:
        return 0
    return ((nuevo_valor - ultimo_valor) / ultimo_valor) * 100

def calcular_porcentaje_cambio_diario(nuevo_valor, valor_dia_anterior):
    """Calcula el porcentaje de cambio diario en base al valor del día anterior."""
    if valor_dia_anterior is None or valor_dia_anterior == 0:
        return 0
    return ((nuevo_valor - valor_dia_anterior) / valor_dia_anterior) * 100

def obtener_mejor_valor_desde_fecha(valor_actual, historico):
    """Determina la fecha más reciente con un valor inferior al valor actual."""
    mejor_fecha = None
    mejor_valor = None
    for fecha, valor in sorted(historico, key=lambda x: x[0], reverse=True):
        if valor < valor_actual:
            mejor_fecha = fecha
            mejor_valor = valor
            break
    return mejor_fecha, mejor_valor

def traducir_fecha(fecha):
    """Traduce el nombre del mes en una fecha."""
    meses = {
        "January": "Enero", "February": "Febrero", "March": "Marzo", "April": "Abril",
        "May": "Mayo", "June": "Junio", "July": "Julio", "August": "Agosto",
        "September": "Septiembre", "October": "Octubre", "November": "Noviembre", "December": "Diciembre"
    }
    # Formatear la fecha y traducir el mes
    fecha_str = fecha.strftime("%d de %B")
    for mes_ing, mes_esp in meses.items():
        fecha_str = fecha_str.replace(mes_ing, mes_esp)
    return fecha_str

def generar_grafico_en_memoria(datos):
    """Genera un gráfico visualmente moderno para los últimos 10 años de riesgo país."""
    
    # Lista de presidentes por año (ajusta según los datos reales)
    presidentes = {
        1998: "Carlos Menem",
        1999: "Carlos Menem",
        2000: "Fernando de la Rúa",
        2001: "Fernando de la Rúa",
        2002: "Eduardo Duhalde",
        2003: "Eduardo Duhalde",
        2004: "Néstor Kirchner",
        2005: "Néstor Kirchner",
        2006: "Néstor Kirchner",
        2007: "Néstor Kirchner",
        2008: "Cristina Fernández",
        2009: "Cristina Fernández",
        2010: "Cristina Fernández",
        2011: "Cristina Fernández",
        2012: "Cristina Fernández",
        2013: "Cristina Fernández",
        2014: "Cristina Fernández",
        2015: "Cristina Fernández",
        2016: "Mauricio Macri",
        2017: "Mauricio Macri",
        2018: "Mauricio Macri",
        2019: "Mauricio Macri",
        2020: "Alberto Fernández",
        2021: "Alberto Fernández",
        2022: "Alberto Fernández",
        2023: "Alberto Fernández",
        2024: "Javier Milei",
        2025: "Javier Milei",
        2026: "Javier Milei",
        2027: "Javier Milei",
    }

    # Ordenar los datos por año
    datos_ordenados = sorted(datos, key=lambda x: x[0])
    años = [d[0].year for d in datos_ordenados]
    valores = [d[1] for d in datos_ordenados]

    # Obtener la fecha actual para mostrarla en el título
    hoy = datetime.now()
    fecha_actual = traducir_fecha(hoy)
    año_actual = hoy.year
    rango_años = f"{min(años)}-{max(años)}"  # Determinar el rango dinámico de años

    # Determinar el valor mínimo y máximo de los datos
    min_valor = min(valores)
    max_valor = max(valores)

    # Agregar un margen para que los puntos no estén pegados al borde
    margen = (max_valor - min_valor) * 0.1  # 10% del rango de datos
    rango_min = max(0, min_valor - margen)  # Asegurar que el rango mínimo no sea negativo
    rango_max = max_valor + margen

    # Ajuste dinámico del paso de los ticks del eje Y
    rango_total = rango_max - rango_min
    if rango_total <= 1000:
        step = 50
    elif rango_total <= 5000:
        step = 250
    else:
        step = 500

    # Crear el gráfico
    plt.figure(figsize=(12, 8))
    ax = plt.gca()

    # Fondo moderno
    ax.set_facecolor('#2b2b2b')  # Fondo oscuro
    plt.gcf().set_facecolor('#2b2b2b')  # Fondo completo

    # Línea de riesgo país
    plt.plot(años, valores, marker='o', color='#FF5733', linestyle='-', linewidth=3, label="Riesgo País")

    # Sombreado suave debajo de la línea
    plt.fill_between(años, valores, color='#FF5733', alpha=0.1)

    # Título moderno
    plt.title(f"Riesgo País ({rango_años})\n({fecha_actual} de cada año)",
              fontsize=18, fontweight='bold', color='white')

    # Etiquetas del eje Y
    plt.ylabel("Valor Riesgo País", fontsize=14, fontweight='bold', color='white')

    # Establecer los límites del eje Y
    plt.ylim(rango_min, rango_max)

    # Configurar los ticks del eje Y dinámicamente
    tick_inicio = math.floor(rango_min / step) * step
    tick_fin = math.ceil(rango_max / step) * step
    ticks_y = range(int(tick_inicio), int(tick_fin + step), int(step))
    plt.yticks(ticks_y, fontsize=12, color='white')

    # Configurar los ticks del eje X (años en negrita)
    plt.xticks(años, fontsize=12, fontweight='bold', color='white')
    ax.xaxis.label.set_visible(False)  # Ocultar texto del eje X

    # Posición fija para los nombres de presidentes debajo del gráfico
    posicion_presidentes = rango_min - (margen * 0.8)  # Mayor separación

    # Agregar nombres de presidentes debajo de cada año
    for año in años:
        presidente = presidentes.get(año, "N/A")
        nombre, apellido = presidente.split(" ", 1) if " " in presidente else (presidente, "")
        plt.text(año, posicion_presidentes, f"{nombre}\n{apellido}", 
                 fontsize=10, color='white', ha='center', va='top')

    # Rejilla
    plt.grid(color='gray', linestyle='--', linewidth=0.5, alpha=0.5)

    # Agregar etiquetas con los valores en cada punto
    for i, (año, valor) in enumerate(zip(años, valores)):
        if año == año_actual:
            plt.annotate(f"{valor}", (años[i], valores[i]),
                         textcoords="offset points", xytext=(0, 10), ha='center',
                         fontsize=14, color='#FFC300',  # Resaltar en amarillo brillante
                         bbox=dict(boxstyle="round,pad=0.3", edgecolor='#FF5733', facecolor='#2b2b2b', alpha=0.9))
        else:
            plt.annotate(f"{valor}", (años[i], valores[i]),
                         textcoords="offset points", xytext=(0, 10), ha='center',
                         fontsize=12, color='white',
                         bbox=dict(boxstyle="round,pad=0.3", edgecolor='gray', facecolor='#2b2b2b', alpha=0.8))

    # Leyenda moderna
    plt.legend(fontsize=12, loc='upper left', facecolor='#2b2b2b', edgecolor='white', labelcolor='white')

    # Guardar la imagen en un objeto BytesIO
    buffer = BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight', dpi=100)
    plt.close()
    buffer.seek(0)  # Volver al inicio del buffer
    return buffer
    
def obtener_datos_historicos_para_grafico():
    """Obtiene los datos históricos necesarios para el gráfico."""
    historico = leer_historico_riesgo_pais()
    hoy = datetime.now(pytz.timezone('America/Argentina/Buenos_Aires'))
    
    datos = []
    for año in range(hoy.year - 10, hoy.year + 1):
        fecha_objetivo = datetime(hoy.year, hoy.month, hoy.day)
        while fecha_objetivo.year == año:
            # Buscar el valor más cercano para la fecha
            valor = next((v for f, v in historico if f.date() == fecha_objetivo.date()), None)
            if valor is not None:
                datos.append((fecha_objetivo, valor))
                break
            fecha_objetivo -= timedelta(days=1)
    
    return datos

def obtener_datos_historicos_simulados_para_grafico():
    """Simula datos históricos del riesgo país desde 1999 hasta 2024."""
    hoy = datetime.now()
    años = range(2014, 2025)  # Desde 2014 hasta 2024

    # Generar valores simulados entre 50 y 6000
    valores_simulados = [random.randint(50, 6000) for _ in años]

    # Crear datos ficticios con fechas
    datos = [(datetime(año, hoy.month, hoy.day), valor) for año, valor in zip(años, valores_simulados)]
    return datos

def postear_grafico():
    """Genera y postea un gráfico con los datos históricos de riesgo país."""
    # datos = obtener_datos_historicos_para_grafico()
    datos = obtener_datos_historicos_simulados_para_grafico()
    if not datos:
        print("No hay suficientes datos para generar el gráfico.")
        return

    # Generar gráfico en memoria
    imagen_buffer = generar_grafico_en_memoria(datos)

    # Subir la imagen con `api`
    media = api.media_upload(filename="grafico.png", file=imagen_buffer)

    # Obtener la fecha actual y los rangos de años
    hoy = datetime.now()
    fecha_actual = traducir_fecha(hoy)
    años = [dato[0].year for dato in datos]  # Extraer los años de los datos
    rango_años = f"{min(años)}-{max(años)}"  # Determinar el rango dinámicamente
    
    texto = (
        f"📊 #RiesgoPaís: {rango_años}\n"
        f"📅 Fecha: {fecha_actual}\n"
        "🇦🇷 #Argentina #Economía"
    )
    
    client.create_tweet(text=texto, media_ids=[media.media_id])
    print("Tweet con gráfico enviado.")    

def postear_tweet(nuevo_valor, ultimo_valor):
    """Postea un tweet indicando si el riesgo país subió o bajó."""
    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    fecha_hora = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    
    if ultimo_valor is not None:
        diferencia = nuevo_valor - ultimo_valor
        # Calcular porcentaje respecto al valor del día anterior
        valor_dia_anterior = leer_valor_dia_anterior()
        porcentaje_cambio_diario = calcular_porcentaje_cambio_diario(nuevo_valor, valor_dia_anterior)
        # Determinar si usar "punto" o "puntos"
        puntos_texto = "punto" if abs(diferencia) == 1 else "puntos"
        if diferencia > 0:
            movimiento = f"😭 El riesgo país subió {diferencia} {puntos_texto} ⬆️"
        else:
            movimiento = f"💪 El riesgo país bajó {abs(diferencia)} {puntos_texto} ⬇️"
    else:
        movimiento = "ℹ️ No tiene un valor previo registrado"
        porcentaje_cambio_diario = 0  # Para evitar errores si no hay valor previo
    
    tweet = (
        f"{movimiento}\n"
        f"⚠️ Ahora es de {nuevo_valor} ({porcentaje_cambio_diario:.2f}%)\n"
        f"🇦🇷 #RiesgoPaís #Argentina\n"
        f"🕒 {fecha_hora}"
    )
    client.create_tweet(text=tweet)
    print(f"Tweet enviado: {tweet}")

    # Guardar el nuevo valor del riesgo país después de postear el tweet
    guardar_valor_riesgo_pais(nuevo_valor)

def postear_resumen_diario():
    """Postea un tweet con el resumen diario del cambio del riesgo país."""
    valor_actual = leer_ultimo_valor_guardado()
    valor_dia_anterior = leer_valor_dia_anterior()
    historico = leer_historico_riesgo_pais()
    if valor_actual is not None and valor_dia_anterior is not None:
        diferencia = valor_actual - valor_dia_anterior
        puntos_texto = "punto" if abs(diferencia) == 1 else "puntos"
        porcentaje_cambio_diario = calcular_porcentaje_cambio_diario(valor_actual, valor_dia_anterior)
        if diferencia > 0:
            movimiento = f"😭 Subió {diferencia} {puntos_texto} hoy. ⬆️"
        elif diferencia < 0:
            movimiento = f"💪 Bajó {abs(diferencia)} {puntos_texto} hoy. ⬇️"
        else:
            movimiento = "ℹ️ El riesgo país no cambió hoy."
        
        fecha_actual = datetime.now(pytz.timezone('America/Argentina/Buenos_Aires')).strftime('%d/%m')
        tweet = (
            f"🔔 RESUMEN DEL DÍA {fecha_actual} 🔔\n"
            f"\n"
            f"📉 Riesgo País: {valor_actual}\n"
            f"{movimiento}\n"
            f"📊 Variación porcentual: {porcentaje_cambio_diario:.2f}%\n"
        )

        mejor_fecha, mejor_valor = obtener_mejor_valor_desde_fecha(valor_actual, historico)
        if mejor_fecha:
            mejor_fecha_str = mejor_fecha.strftime('%d/%m/%Y')
            tweet += f"🏆 Mejor desde {mejor_fecha_str} ({mejor_valor:.0f})\n"
        
        tweet += f"🇦🇷 #RiesgoPaís #Argentina"
        client.create_tweet(text=tweet)
        print(f"Tweet resumen diario enviado: {tweet}")

# Bucle principal
actualizado_hoy = False
resumen_diario_posteado = False
grafico_posteado = False

while True:
    # Obtener la hora y día actual en la zona horaria de Buenos Aires
    ahora = datetime.now(pytz.timezone('America/Argentina/Buenos_Aires'))
    hora_actual = ahora.time()
    dia_actual = ahora.weekday()  # 0 = Lunes, 6 = Domingo

    # Publicar gráfico los sábados a las 19:30
    if dia_actual == 5 and hora_actual.hour == 16 and 33 <= hora_actual.minute <= 38 and not grafico_posteado:
        postear_grafico()
        grafico_posteado = True
        
    # Verificar si está dentro del horario permitido
    if dia_actual < 5 and (hora_actual >= datetime.strptime("08:00", "%H:%M").time() or hora_actual <= datetime.strptime("01:00", "%H:%M").time()):
        nuevo_valor = obtener_riesgo_pais()
        
        if nuevo_valor is not None:
            ultimo_valor = leer_ultimo_valor_guardado()
            if ultimo_valor is None or abs(nuevo_valor - ultimo_valor) != 0:
                postear_tweet(nuevo_valor, ultimo_valor)
            else:
                print(f"El riesgo país no cambió. Valor actual: {nuevo_valor}")
        
        # Verificar si la hora está entre 23:50 y 23:55 para actualizar el valor del día anterior
        if hora_actual.hour == 23 and 50 <= hora_actual.minute <= 55 and not actualizado_hoy:
            actualizar_valor_dia_anterior()
            guardar_historico_riesgo_pais(nuevo_valor)
            actualizado_hoy = True
            resumen_diario_posteado = False  # Permitir que se postee el resumen al día siguiente
            print("Valor del día anterior actualizado y Valor historico agregado.")
        
        # Postear el resumen diario a las 22:00
        if hora_actual.hour == 22 and not resumen_diario_posteado:
            postear_resumen_diario()
            resumen_diario_posteado = True
        
        # Resetear el indicador al inicio de un nuevo día
        if hora_actual.hour == 0:
            actualizado_hoy = False
            resumen_diario_posteado = False
            grafico_posteado = False
    else:
        print("Fuera del horario permitido. Bot en espera...")

    # Esperar 5 minutos antes de la próxima verificación
    time.sleep(300)  # 5 minutos = 300 segundos
