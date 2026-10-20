"""
menu.py — Sistema completo (Portable + Exportación Excel + Intervalos de Confianza)
"""
import os, sys, json, webbrowser
from urllib.parse import urlencode
import numpy as np
import pandas as pd
import statsmodels.api as sm

# --- Solucion para colores del IDLE---
in_idle = 'idlelib' in sys.modules
if in_idle:
    HAS_COLOR = False
else:
    try:
        import colorama
        colorama.init(autoreset=True)
        HAS_COLOR = True
    except ImportError:
        HAS_COLOR = False

# --- Librerias del agente para las preguntas a google, no puede hacer preguntas de dias anteriores, esto para mejora ---
try:
    import feedparser
    from groq import Groq
    AGENTE_LIBS = True
except Exception as _e:
    AGENTE_LIBS = False
    _AGENTE_LIB_ERR = str(_e)

# ---------------------------------------------------------------
# CONFIGURACIÓN PORTABLE para la creacion de la carpeta, leer historico, creacion del dashboard para las gráficas, ventana de dias y proyecciones, groq key para el agente
#                           tambien la toma de las variables de entorno.
# ---------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CARPETA = os.path.join(BASE_DIR, "dn")
if not os.path.exists(CARPETA):
    os.makedirs(CARPETA)
    print(f"📁 Carpeta creada automáticamente: {CARPETA}")

EXCEL  = os.path.join(CARPETA, "historico_equipos.xlsx")
SALIDA = os.path.join(CARPETA, "dashboard.html")

MM_VENTANA  = 90
HORIZONTE_D = 30
HORIZONTE_5A = 1260

# Busca la API Key en las variables de entorno. Si no está, se deja vacía para pedirla luego.
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# ---------------------------------------------------------------
# COLORES para las graficas 
# ---------------------------------------------------------------
class C:
    if HAS_COLOR:
        BOLD="\033[1m"; END="\033[0m"
        CY="\033[96m"; G="\033[92m"; W="\033[93m"; R="\033[91m"; M="\033[95m"
    else:
        BOLD=""; END=""; CY=""; G=""; W=""; R=""; M=""

def hdr(t):
    print(f"\n{C.BOLD}{C.CY}{'═'*80}{C.END}")
    print(f"{C.BOLD}{C.CY}  {t}{C.END}")
    print(f"{C.BOLD}{C.CY}{'═'*80}{C.END}")
def ok(t):   print(f"{C.G}✓ {t}{C.END}")
def warn(t): print(f"{C.W}⚠ {t}{C.END}")
def err(t):  print(f"{C.R}✗ {t}{C.END}")

# ---------------------------------------------------------------
# Estado de memoria para las x,y,z y cambios de pregunta del agente
# ---------------------------------------------------------------
class E:
    df = None
    ultima_fecha = None
    m1_z = None; m1_xy = None
    m2_xz = None; m2_xyz = None
    met = {}
    agente_resp = None
    factores = {"X": 1.0, "Y": 1.0, "Z": 1.0}
    horizonte = HORIZONTE_D

# ---------------------------------------------------------------
# 1) Cargar datos del historico
# ---------------------------------------------------------------
def _procesar_df(df):
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    return df[df["Price_Z"] < 5000].reset_index(drop=True)

def cargar_datos(ruta=None):
    hdr("1. CARGAR DATOS HISTÓRICOS")
    ruta = ruta or EXCEL
    if not os.path.exists(ruta):
        err(f"No se encontró el archivo: {ruta}")
        warn("Por favor, coloca tu archivo 'historico_equipos.xlsx' dentro de la carpeta 'dn'.")
        return False
    try:
        df = pd.read_excel(ruta)
        df = _procesar_df(df)
        E.df = df
        E.ultima_fecha = df["Date"].max()
        ok(f"{len(df)} filas cargadas desde {os.path.basename(ruta)}")
        print(f"   {df['Date'].min().date()} → {E.ultima_fecha.date()}")
        return True
    except Exception as e:
        err(f"Error: {e}")
        return False

def agregar_datos():
    hdr("1b. AGREGAR DATOS AL HISTÓRICO ACTUAL")
    if E.df is None:
        warn("Primero debes cargar un archivo base (opción 1).")
        return False
    print("Selecciona el nuevo archivo Excel a agregar (o presiona Enter para usar el default).")
    ruta = input(f"Ruta [{EXCEL}]: ").strip() or EXCEL
    if not os.path.exists(ruta):
        err(f"No existe: {ruta}")
        return False
    try:
        df_nuevo = pd.read_excel(ruta)
        df_nuevo = _procesar_df(df_nuevo)
        filas_antes = len(E.df)
        E.df = pd.concat([E.df, df_nuevo]).drop_duplicates(subset=["Date"], keep="last").sort_values("Date").reset_index(drop=True)
        E.ultima_fecha = E.df["Date"].max()
        ok(f"Agregadas {len(E.df) - filas_antes} filas nuevas. Total actual: {len(E.df)}")
        if E.m1_z is not None:
            warn("Los datos cambiaron. Por favor, vuelve a entrenar los modelos (Opción 2).")
            E.m1_z = None
        return True
    except Exception as e:
        err(f"Error al agregar: {e}")
        return False

# ---------------------------------------------------------------
# 2) Entrenamieto por medio de los datos del historico, para sacar las rubricas, unas con z otras con xy por el modelo propio 
# ---------------------------------------------------------------
def _metricas(m, y):
    resid = m.resid.values
    return {"r2": float(m.rsquared), "mape": float(np.abs(resid / y).mean() * 100),
            "sigma": float(np.std(resid, ddof=1))}

def entrenar_modelos():
    hdr("2. ENTRENAR MODELOS (4 variantes)")
    if E.df is None:
        warn("Carga datos primero (opción 1)."); return False
    df = E.df

    E.m1_z  = sm.OLS(df["Price_Equipo1"], sm.add_constant(df[["Price_Z"]])).fit()
    E.m1_xy = sm.OLS(df["Price_Equipo1"], sm.add_constant(df[["Price_X","Price_Y"]])).fit()
    E.m2_xz  = sm.OLS(df["Price_Equipo2"], sm.add_constant(df[["Price_X","Price_Z"]])).fit()
    E.m2_xyz = sm.OLS(df["Price_Equipo2"], sm.add_constant(df[["Price_X","Price_Y","Price_Z"]])).fit()

    E.met = {
        "Eq1_Z":   _metricas(E.m1_z,   df["Price_Equipo1"]),
        "Eq1_XY":  _metricas(E.m1_xy,  df["Price_Equipo1"]),
        "Eq2_XZ":  _metricas(E.m2_xz,  df["Price_Equipo2"]),
        "Eq2_XYZ": _metricas(E.m2_xyz, df["Price_Equipo2"]),
    }

    print(f"\n  {C.BOLD}{'Modelo':<12}{'R²':>10}{'MAPE':>10}{'σ':>12}   Coeficientes{C.END}")
    print("  " + "-" * 78)
    for k, m in [("Eq1_Z",E.m1_z),("Eq1_XY",E.m1_xy),("Eq2_XZ",E.m2_xz),("Eq2_XYZ",E.m2_xyz)]:
        mt = E.met[k]
        cstr = "  ".join(f"{n}={v:.2f}" for n,v in m.params.items())
        print(f"  {k:<12}{mt['r2']:>10.4f}{mt['mape']:>9.2f}%{mt['sigma']:>12.2f}   {cstr}")

    print(f"\n  {C.BOLD}🔍 Comparativa Eq1:{C.END}")
    d_r2   = E.met['Eq1_Z']['r2']   - E.met['Eq1_XY']['r2']
    d_mape = E.met['Eq1_XY']['mape'] - E.met['Eq1_Z']['mape']
    print(f"   R²:      {C.G}{d_r2:+.4f}{C.END} a favor de Eq1~Z")
    print(f"   MAPE:    {C.G}{-d_mape:+.2f}%{C.END} de error a favor de Eq1~Z")
    ok("Modelos listos.")
    return True

# ---------------------------------------------------------------
# 3) Proyecciones de 1 a 5 anos.
# ---------------------------------------------------------------
def _mm3(serie, n, ventana=MM_VENTANA):
    vals = list(serie.tail(ventana).values)
    out = []
    for _ in range(n):
        m = float(np.mean(vals[-ventana:]))
        out.append(m); vals.append(m)
    return np.array(out)

def proyectar(horizonte=None):
    hdr("3. PROYECCIÓN BASE (Línea Recta)")
    if E.m1_z is None:
        warn("Entrena modelos primero (opción 2)."); return None
        
    if horizonte is None:
        try:
            h = input(f"Días a proyectar (1 a 1260) [{E.horizonte}]: ").strip()
            horizonte = int(h) if h else E.horizonte
            # Validación para no salir de los límites
            horizonte = max(1, min(horizonte, 1260))
        except ValueError:
            horizonte = E.horizonte
    E.horizonte = horizonte

    df = E.df
    Xp, Yp, Zp = (_mm3(df[f"Price_{s}"], horizonte) for s in "XYZ")
    
    p1z, p1xy = E.m1_z.params, E.m1_xy.params
    p2xz, p2xyz = E.m2_xz.params, E.m2_xyz.params

    eq1_z_base  = p1z["const"]  + p1z["Price_Z"] * Zp
    eq1_xy_base = p1xy["const"] + p1xy["Price_X"] * Xp + p1xy["Price_Y"] * Yp
    eq2_xz_base  = p2xz["const"]  + p2xz["Price_X"] * Xp + p2xz["Price_Z"] * Zp
    eq2_xyz_base = p2xyz["const"] + p2xyz["Price_X"] * Xp + p2xyz["Price_Y"] * Yp + p2xyz["Price_Z"] * Zp

    fX, fY, fZ = E.factores["X"], E.factores["Y"], E.factores["Z"]
    Xa, Ya, Za = Xp*fX, Yp*fY, Zp*fZ

    eq1_z_ag  = p1z["const"]  + p1z["Price_Z"] * Za
    eq1_xy_ag = p1xy["const"] + p1xy["Price_X"] * Xa + p1xy["Price_Y"] * Ya
    eq2_xz_ag  = p2xz["const"]  + p2xz["Price_X"] * Xa + p2xz["Price_Z"] * Za
    eq2_xyz_ag = p2xyz["const"] + p2xyz["Price_X"] * Xa + p2xyz["Price_Y"] * Ya + p2xyz["Price_Z"] * Za

    ic = lambda k: 1.96 * E.met[k]["sigma"]
    E.proy = dict(
        horizonte=horizonte, X=Xp, Y=Yp, Z=Zp, X_ag=Xa, Y_ag=Ya, Z_ag=Za,
        eq1_z_base=eq1_z_base, eq1_xy_base=eq1_xy_base,
        eq2_xz_base=eq2_xz_base, eq2_xyz_base=eq2_xyz_base,
        eq1_z_ag=eq1_z_ag, eq1_xy_ag=eq1_xy_ag,
        eq2_xz_ag=eq2_xz_ag, eq2_xyz_ag=eq2_xyz_ag,
        ic1_z=ic("Eq1_Z"), ic1_xy=ic("Eq1_XY"),
        ic2_xz=ic("Eq2_XZ"), ic2_xyz=ic("Eq2_XYZ"),
    )

    # --- CREACIÓN DEL EXCEL CON TODOS LOS DÍAS ---
    fechas_fut = pd.bdate_range(start=E.ultima_fecha + pd.Timedelta(days=1), periods=horizonte)
    df_export = pd.DataFrame({
        "Fecha": fechas_fut.strftime("%Y-%m-%d"),
        "Precio_X_Base": Xp.round(2),
        "Precio_Y_Base": Yp.round(2),
        "Precio_Z_Base": Zp.round(2),
        "Precio_X_Ajustado": Xa.round(2),
        "Precio_Y_Ajustado": Ya.round(2),
        "Precio_Z_Ajustado": Za.round(2),
        "Eq1_Base(Z)": eq1_z_base.round(2),
        "Eq1_Base(X+Y)": eq1_xy_base.round(2),
        "Eq1_Ajustado(Z)": eq1_z_ag.round(2),
        "Eq1_Ajustado(X+Y)": eq1_xy_ag.round(2),
        "Eq2_Base(X+Z)": eq2_xz_base.round(2),
        "Eq2_Base(X+Y+Z)": eq2_xyz_base.round(2),
        "Eq2_Ajustado(X+Z)": eq2_xz_ag.round(2),
        "Eq2_Ajustado(X+Y+Z)": eq2_xyz_ag.round(2),
    })
    
    ruta_excel = os.path.join(CARPETA, f"proyeccion_base_{horizonte}dias.xlsx")
    df_export.to_excel(ruta_excel, index=False)
    ok(f"Archivo Excel generado con los {horizonte} días: {os.path.basename(ruta_excel)}")

    # --- IMPRESIÓN EN CONSOLA (Solo primeros 30 días) ---
    mostrar = min(30, horizonte)
    print(f"\n  Mostrando los primeros {mostrar} días en consola (el Excel tiene los {horizonte} días):")
    print(f"  {C.BOLD}Factores aplicados: X={fX:.2f}, Y={fY:.2f}, Z={fZ:.2f}{C.END}")
    print(f"  {'Fecha':<12} | {'Eq1~Z (Base)':>15} | {'Eq1~X+Y (Base)':>15} | {'Eq2~X+Z (Base)':>15} | {'Eq2~X+Y+Z (Base)':>15}")
    print("  " + "-"*85)
    
    fechas_str = [d.strftime("%Y-%m-%d") for d in fechas_fut]
    for i in range(0, mostrar, 3): # Imprime cada 3 días para no saturar
        print(f"  {fechas_str[i]:<12} | {eq1_z_base[i]:>15.2f} | {eq1_xy_base[i]:>15.2f} | {eq2_xz_base[i]:>15.2f} | {eq2_xyz_base[i]:>15.2f}")
    print(f"  {fechas_str[mostrar-1]:<12} | {eq1_z_base[mostrar-1]:>15.2f} | {eq1_xy_base[mostrar-1]:>15.2f} | {eq2_xz_base[mostrar-1]:>15.2f} | {eq2_xyz_base[mostrar-1]:>15.2f}")
    
    ok("Proyección base calculada.")
    return E.proy

def simular_proyeccion(horizonte):
    np.random.seed(42) 
    def _simular_caminata(serie):
        ret = serie.pct_change().dropna()
        media, std = ret.mean(), ret.std()
        sims = np.random.normal(media, std, horizonte)
        precios = [serie.iloc[-1]]
        for i in range(horizonte):
            precios.append(precios[-1] * (1 + sims[i]))
        return np.array(precios[1:])

    X_base = _simular_caminata(E.df["Price_X"])
    Y_base = _simular_caminata(E.df["Price_Y"])
    Z_base = _simular_caminata(E.df["Price_Z"])

    fX, fY, fZ = E.factores["X"], E.factores["Y"], E.factores["Z"]
    X_ajust = X_base * fX
    Y_ajust = Y_base * fY
    Z_ajust = Z_base * fZ

    p1z = E.m1_z.params
    p1xy = E.m1_xy.params
    p2xz = E.m2_xz.params
    p2xyz = E.m2_xyz.params

    eq1_z = p1z["const"] + p1z["Price_Z"] * Z_ajust
    eq1_xy = p1xy["const"] + p1xy["Price_X"] * X_ajust + p1xy["Price_Y"] * Y_ajust
    eq2_xz = p2xz["const"] + p2xz["Price_X"] * X_ajust + p2xz["Price_Z"] * Z_ajust
    eq2_xyz = p2xyz["const"] + p2xyz["Price_X"] * X_ajust + p2xyz["Price_Y"] * Y_ajust + p2xyz["Price_Z"] * Z_ajust

    return X_ajust, Y_ajust, Z_ajust, eq1_z, eq1_xy, eq2_xz, eq2_xyz

def proyectar_con_volatilidad():
    hdr("3d. PROYECCIÓN CON VOLATILIDAD (Simulación combinada)")
    if E.m1_xy is None: return
    print("  Generando simulación de 30 días con volatilidad...")
    _, _, _, eq1_z, eq1_xy, eq2_xz, eq2_xyz = simular_proyeccion(30)
    ok("Simulación generada. Ve a la opción 6 o 7 para ver el Dashboard.")

# ---------------------------------------------------------------
# 4) AGENTE IA
# ---------------------------------------------------------------
def _noticias(query):
    if not AGENTE_LIBS: return "—"
    try:
        params = urlencode({"q": query, "hl":"es-419","gl":"MX","ceid":"MX:es-419"})
        feed = feedparser.parse(f"https://news.google.com/rss/search?{params}")
        return "\n".join([f"- {e.title}" for e in feed.entries[:4]]) or "Sin noticias."
    except Exception: return "(error noticias)"

def consultar_agente():
    global GROQ_API_KEY
    hdr("4. CONSULTAR AGENTE IA")
    
    if not AGENTE_LIBS:
        err("Librerías del agente no instaladas.")
        return
        
    if not GROQ_API_KEY:
        warn("No se detectó la GROQ_API_KEY.")
        GROQ_API_KEY = input("Por favor, ingresa tu API Key de Groq: ").strip()
        if not GROQ_API_KEY:
            err("Sin API Key no se puede consultar al agente.")
            return

    print("  🌐 Buscando noticias…")
    nx = _noticias("precio acero mercado")
    ny = _noticias("precio aluminio mercado")
    nz = _noticias("precio cobre mineria")
    ctx = f"ACERO (X):\n{nx}\n\nALUMINIO (Y):\n{ny}\n\nCOBRE (Z):\n{nz}"
    prompt = """
Eres un analista experto en proyectos de construccion y costos de equipos.
Analiza las noticias y devuelve EXCLUSIVAMENTE un JSON:
{
  "factores_ajuste": {"X": float, "Y": float, "Z": float},
  "analisis": "Explicación breve del impacto."
}
Reglas: Rango [-10%, +10%] -> [0.90, 1.10]. Y estable: cercano a 1.0.
"""
    try:
        client = Groq(api_key=GROQ_API_KEY)
        resp = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role":"system","content":prompt}, {"role":"user","content":ctx}],
            response_format={"type":"json_object"}, temperature=0.2
        )
        data = json.loads(resp.choices[0].message.content)
        fa = data.get("factores_ajuste", {})
        E.factores = {k: float(fa.get(k, 1.0)) for k in ("X","Y","Z")}
        E.agente_resp = data
        print(f"\n  {C.BOLD}Análisis:{C.END} {data.get('analisis','')}")
        print(f"  Factores → X={E.factores['X']:.2f}  Y={E.factores['Y']:.2f}  Z={E.factores['Z']:.2f}")
        ok("Agente consultado. (Los factores se aplicarán sobre la volatilidad).")
    except Exception as e:
        err(f"Error Groq: {e}")

def override_factores():
    hdr("4b. FACTORES MANUALES")
    try:
        for k in ("X","Y","Z"):
            v = input(f"  {k} [{E.factores[k]}]: ").strip()
            if v: E.factores[k] = float(v)
        ok(f"X={E.factores['X']}  Y={E.factores['Y']}  Z={E.factores['Z']}")
    except ValueError: err("Valor inválido.")

def chat_interactivo():
    global GROQ_API_KEY
    hdr("4c. CHAT CON EL AGENTE IA")
    
    if not AGENTE_LIBS or E.m1_z is None:
        return

    # SOLICITUD DINÁMICA DE LA API KEY
    if not GROQ_API_KEY:
        warn("No se detectó la GROQ_API_KEY.")
        GROQ_API_KEY = input("Por favor, ingresa tu API Key de Groq: ").strip()
        if not GROQ_API_KEY:
            err("Sin API Key no se puede usar el chat.")
            return

    print("  🌐 El agente está analizando el contexto actual y los datos del dashboard...")
    nx = _noticias("precio acero mercado")
    ny = _noticias("precio aluminio mercado")
    nz = _noticias("precio cobre mineria")
    
    ult_hist = E.df.tail(5)
    hist_txt = "\n".join([f"Fecha: {r['Date'].strftime('%Y-%m-%d')} | Eq1: {r['Price_Equipo1']:.2f} | Eq2: {r['Price_Equipo2']:.2f}" for _, r in ult_hist.iterrows()])
    
    # Extraemos los datos futuros de TODOS los modelos
    _, _, _, eq1_z_30, eq1_xy_30, eq2_xz_30, eq2_xyz_30 = simular_proyeccion(30)
    fechas_30 = [d.strftime("%Y-%m-%d") for d in pd.bdate_range(start=E.ultima_fecha + pd.Timedelta(days=1), periods=30)]
    
    fut_txt = ""
    for i in range(30):
        fut_txt += f"Fecha: {fechas_30[i]} | Eq1 (Principal ~Z): {eq1_z_30[i]:.2f} | Eq1 (Alt ~X+Y): {eq1_xy_30[i]:.2f} | Eq2 (Principal ~X+Z): {eq2_xz_30[i]:.2f} | Eq2 (Alt ~X+Y+Z): {eq2_xyz_30[i]:.2f}\n"

    contexto_sistema = f"""
    Eres un Agente de IA experto en análisis de costos de materias primas.
    Estás asistiendo a un gerente que está viendo un Dashboard con 10 gráficas, las cuales
    te indican los datos de los equipos 1 y equipo2 los cuales tienen relacion con x,y,z nuestra tarea
    es analizar los datos para poder dar un contexto correcto de las proyecciones a futuro
    
    TUS DATOS Y MODELOS (Tienes acceso a las métricas de los 4 modelos):
    - Equipo 1 (Principal ~Z): R²={E.met['Eq1_Z']['r2']:.4f}, MAPE={E.met['Eq1_Z']['mape']:.2f}%
    - Equipo 1 (Alternativo ~X+Y): R²={E.met['Eq1_XY']['r2']:.4f}, MAPE={E.met['Eq1_XY']['mape']:.2f}%
    - Equipo 2 (Principal ~X+Z): R²={E.met['Eq2_XZ']['r2']:.4f}, MAPE={E.met['Eq2_XZ']['mape']:.2f}%
    - Equipo 2 (Alternativo ~X+Y+Z): R²={E.met['Eq2_XYZ']['r2']:.4f}, MAPE={E.met['Eq2_XYZ']['mape']:.2f}%
    
    - Factores macro actuales aplicados: X={E.factores['X']}, Y={E.factores['Y']}, Z={E.factores['Z']}

    DATOS HISTÓRICOS RECIENTES:
    {hist_txt}

    PROYECCIÓN FUTURA A 30 DÍAS (Esta es la tabla exacta que el usuario ve en el Dashboard):
    {fut_txt}

    NOTICIAS RECIENTES:
    - Acero (X): {nx}
    - Aluminio (Y): {ny}
    - Cobre (Z): {nz}
    
    INSTRUCCIONES ESTRICTAS:
    1. Tienes los datos exactos de la tabla (histórico y futuro). Si te preguntan por una fecha, busca en la tabla.
    2. El Equipo 1 SÍ tiene un modelo que usa solo Z (Principal ~Z). Tienes sus datos futuros en la tabla de arriba.
    3. ACLARACIÓN: Eres un modelo de lenguaje. No puedes "ver" los gráficos visuales (como los de Plotly en el dashboard), pero SÍ tienes los datos numéricos que los componen, así que úsalos para responder.
    4. Si te preguntan por el dashboard, explica que no lo ves visualmente pero conoces todos los datos y métricas.
    5. Si el usuario te pregunta algo fuera de este contexto,tu deber es saber sobre construccion y el programa desarrollado, sobre los datos contenidos en este programa, niégate amablemente.

    Debes responder SIEMPRE en formato JSON con la siguiente estructura exacta:
    {{
      "respuesta": "Tu respuesta aquí.",
      "actualizar_factores": false,
      "nuevos_factores": {{"X": 1.0, "Y": 1.0, "Z": 1.0}}
    }}
    """
    mensajes = [{"role": "system", "content": contexto_sistema}]
    client = Groq(api_key=GROQ_API_KEY)
    
    print("\n" + "="*60)
    print("  🤖 AGENTE ESPECIALIZADO ACTIVO. Escribe 'salir' para volver.")
    print("="*60)

    while True:
        try:
            pregunta = input(f"\n{C.BOLD}👨‍💼 Tú: {C.END}").strip()
            if not pregunta: continue
            if pregunta.lower() in ["salir", "exit", "quit"]: break
            
            mensajes.append({"role": "user", "content": pregunta})
            print("  🤖 Pensando...")
            
            completion = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=mensajes,
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            data = json.loads(completion.choices[0].message.content)
            respuesta_texto = data.get("respuesta", "No pude procesar la respuesta.")
            
            print(f"\n{C.CY}{C.BOLD}🤖 Agente: {C.END}{respuesta_texto}")
            
            if data.get("actualizar_factores"):
                nuevos = data.get("nuevos_factores", {})
                E.factores = {k: float(nuevos.get(k, E.factores[k])) for k in ("X","Y","Z")}
                print(f"\n{C.G}🔄 EL AGENTE ACTUALIZÓ LOS FACTORES:{C.END}")
                print(f"   X={E.factores['X']}  Y={E.factores['Y']}  Z={E.factores['Z']}")
            
            mensajes.append({"role": "assistant", "content": respuesta_texto})
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            err(f"Error: {e}")

# ---------------------------------------------------------------
# 5) Simulador de eventos cambiando x:80.1 y z Y 6) DASHBOARD con graficas
# ---------------------------------------------------------------
def simulador():
    hdr("5. SIMULADOR WHAT-IF")
    if E.m1_z is None: return
    df = E.df
    lx, ly, lz = (float(df[f"Price_{s}"].iloc[-1]) for s in "XYZ")
    print(f"Último → X={lx:.2f}  Y={ly:.2f}  Z={lz:.2f}")
    try:
        dx = float(input("Δ% X [0]: ") or 0); dy = float(input("Δ% Y [0]: ") or 0); dz = float(input("Δ% Z [0]: ") or 0)
    except ValueError: return
    nx, ny, nz = lx*(1+dx/100), ly*(1+dy/100), lz*(1+dz/100)

    p1z, p1xy, p2xz, p2xyz = E.m1_z.params, E.m1_xy.params, E.m2_xz.params, E.m2_xyz.params
    def calc(p, **kw):
        s = p["const"]
        for k, v in kw.items(): s += p[f"Price_{k}"]*v
        return s

    print(f"\n  {'Modelo':<14}{'Base':>12}{'Escenario':>14}{'Δ%':>10}")
    print("  " + "-"*52)
    for n,b,v in [("Eq1~Z",calc(p1z,Z=lz),calc(p1z,Z=nz)), ("Eq1~X+Y",calc(p1xy,X=lx,Y=ly),calc(p1xy,X=nx,Y=ny)),
                  ("Eq2~X+Z",calc(p2xz,X=lx,Z=lz),calc(p2xz,X=nx,Z=nz)), ("Eq2~X+Y+Z",calc(p2xyz,X=lx,Y=ly,Z=lz),calc(p2xyz,X=nx,Y=ny,Z=nz))]:
        print(f"  {n:<14}{b:>12.2f}{v:>14.2f}{((v-b)/b*100 if b else 0):>9.2f}%")

def generar_html(abrir=False):
    hdr("6. GENERAR DASHBOARD HTML")
    if E.m1_z is None: return
    
    print("  (Generando proyecciones con volatilidad y factores macro...)")
    
    X_30, Y_30, Z_30, eq1_z_30, eq1_xy_30, eq2_xz_30, eq2_xyz_30 = simular_proyeccion(30)
    fechas_30 = [d.strftime("%Y-%m-%d") for d in pd.bdate_range(start=E.ultima_fecha + pd.Timedelta(days=1), periods=30)]

    X_5A, Y_5A, Z_5A, eq1_z_5A, eq1_xy_5A, eq2_xz_5A, eq2_xyz_5A = simular_proyeccion(HORIZONTE_5A)
    fechas_5A = [d.strftime("%Y-%m-%d") for d in pd.bdate_range(start=E.ultima_fecha + pd.Timedelta(days=1), periods=HORIZONTE_5A)]

    df = E.df

    eq1_z_fit = E.m1_z.predict(sm.add_constant(df[["Price_Z"]]))
    eq1_xy_fit = E.m1_xy.predict(sm.add_constant(df[["Price_X", "Price_Y"]]))
    eq2_xz_fit = E.m2_xz.predict(sm.add_constant(df[["Price_X", "Price_Z"]]))
    eq2_xyz_fit = E.m2_xyz.predict(sm.add_constant(df[["Price_X", "Price_Y", "Price_Z"]]))

    p1, p1xy, p2, p2xyz = E.m1_z.params, E.m1_xy.params, E.m2_xz.params, E.m2_xyz.params
    fX, fY, fZ = E.factores["X"], E.factores["Y"], E.factores["Z"]

    # Calculo MM3 (linea recta pura) para la Seccion 10
    X5_mm3 = _mm3(df["Price_X"], HORIZONTE_5A) * fX
    Y5_mm3 = _mm3(df["Price_Y"], HORIZONTE_5A) * fY
    eq1_mm3_fut = p1xy["const"] + p1xy["Price_X"] * X5_mm3 + p1xy["Price_Y"] * Y5_mm3

    # Unir datos para la Seccion 10 (Historico + Futuro)
    hist_dates_str = df["Date"].dt.strftime("%Y-%m-%d").tolist()
    all_dates = hist_dates_str + fechas_5A
    
    # Rellenar con None para que la grafica no una el historico con el futuro con una linea diagonal
    eq1_hist_full = df["Price_Equipo1"].round(2).tolist() + [None] * HORIZONTE_5A
    eq2_hist_full = df["Price_Equipo2"].round(2).tolist() + [None] * HORIZONTE_5A
    
    eq1_model_complete = eq1_xy_fit.round(2).tolist() + eq1_xy_5A.round(2).tolist()
    eq2_model_complete = eq2_xyz_fit.round(2).tolist() + eq2_xyz_5A.round(2).tolist()
    
    eq1_z_complete = eq1_z_fit.round(2).tolist() + eq1_z_5A.round(2).tolist()
    eq2_xz_complete = eq2_xz_fit.round(2).tolist() + eq2_xz_5A.round(2).tolist()
    
    eq1_mm3_complete = [None] * len(hist_dates_str) + eq1_mm3_fut.round(2).tolist()
    eq2_mm3_complete = [None] * len(hist_dates_str) + (p2xyz["const"] + p2xyz["Price_X"]*X5_mm3 + p2xyz["Price_Y"]*Y5_mm3 + p2xyz["Price_Z"]*_mm3(df["Price_Z"], HORIZONTE_5A)*fZ).round(2).tolist()

    eq1_mc_complete = [None] * len(hist_dates_str) + eq1_xy_5A.round(2).tolist()
    eq2_mc_complete = [None] * len(hist_dates_str) + eq2_xyz_5A.round(2).tolist()

    # --- CALCULO DE INTERVALOS DE CONFIANZA PARA 30 DIAS ---
    ic1_z_val = 1.96 * E.met["Eq1_Z"]["sigma"]
    ic1_xy_val = 1.96 * E.met["Eq1_XY"]["sigma"]
    ic2_xz_val = 1.96 * E.met["Eq2_XZ"]["sigma"]
    ic2_xyz_val = 1.96 * E.met["Eq2_XYZ"]["sigma"]

    eq1_xy_30_lo = eq1_xy_30 - ic1_xy_val
    eq1_xy_30_hi = eq1_xy_30 + ic1_xy_val
    eq2_xyz_30_lo = eq2_xyz_30 - ic2_xyz_val
    eq2_xyz_30_hi = eq2_xyz_30 + ic2_xyz_val

    coef = {
        "eq1_z": dict(const=float(p1["const"]), Z=float(p1["Price_Z"]), r2=E.met["Eq1_Z"]["r2"], mape=E.met["Eq1_Z"]["mape"]),
        "eq1_xy": dict(const=float(p1xy["const"]), X=float(p1xy["Price_X"]), Y=float(p1xy["Price_Y"]), r2=E.met["Eq1_XY"]["r2"], mape=E.met["Eq1_XY"]["mape"]),
        "eq2_xz": dict(const=float(p2["const"]), X=float(p2["Price_X"]), Z=float(p2["Price_Z"]), r2=E.met["Eq2_XZ"]["r2"], mape=E.met["Eq2_XZ"]["mape"]),
        "eq2_xyz": dict(const=float(p2xyz["const"]), X=float(p2xyz["Price_X"]), Y=float(p2xyz["Price_Y"]), Z=float(p2xyz["Price_Z"]), r2=E.met["Eq2_XYZ"]["r2"], mape=E.met["Eq2_XYZ"]["mape"]),
    }
    
    data = dict(
        hist_dates=hist_dates_str, 
        eq1_hist=eq1_hist_full[:-HORIZONTE_5A], eq1_z_fit=eq1_z_fit.round(2).tolist(), eq1_xy_fit=eq1_xy_fit.round(2).tolist(),
        eq2_hist=eq2_hist_full[:-HORIZONTE_5A], eq2_xz_fit=eq2_xz_fit.round(2).tolist(), eq2_xyz_fit=eq2_xyz_fit.round(2).tolist(),
        fut30_dates=fechas_30,
        eq1_z_30=eq1_z_30.round(2).tolist(), eq1_xy_30=eq1_xy_30.round(2).tolist(),
        eq2_xz_30=eq2_xz_30.round(2).tolist(), eq2_xyz_30=eq2_xyz_30.round(2).tolist(),
        
        # Datos de los intervalos de confianza
        eq1_xy_30_lo=eq1_xy_30_lo.round(2).tolist(),
        eq1_xy_30_hi=eq1_xy_30_hi.round(2).tolist(),
        eq2_xyz_30_lo=eq2_xyz_30_lo.round(2).tolist(),
        eq2_xyz_30_hi=eq2_xyz_30_hi.round(2).tolist(),

        fut5A_dates=fechas_5A,
        eq1_5A=eq1_xy_5A.round(2).tolist(), eq2_5A=eq2_xyz_5A.round(2).tolist(),
        X_5A=X_5A.round(2).tolist(), Y_5A=Y_5A.round(2).tolist(), Z_5A=Z_5A.round(2).tolist(),
        all_dates=all_dates,
        eq1_hist_full=eq1_hist_full, eq2_hist_full=eq2_hist_full,
        eq1_model_complete=eq1_model_complete, eq2_model_complete=eq2_model_complete,
        eq1_z_complete=eq1_z_complete, eq2_xz_complete=eq2_xz_complete,
        eq1_mm3_complete=eq1_mm3_complete, eq2_mm3_complete=eq2_mm3_complete,
        eq1_mc_complete=eq1_mc_complete, eq2_mc_complete=eq2_mc_complete
    )
    
    html = _HTML.replace("__COEF__", json.dumps(coef)).replace("__AG__", json.dumps((E.agente_resp or {}).get("analisis","No consultado."))).replace("__FACT__", json.dumps(E.factores)).replace("__DATA__", json.dumps(data)).replace("__HOR__", str(E.horizonte))
    
    with open(SALIDA, "w", encoding="utf-8") as f: f.write(html)
    ok(f"Guardado: {SALIDA}")
    if abrir:
        webbrowser.open(f"file:///{SALIDA}")
        ok("Abierto en el navegador.")

def ver_resumen():
    hdr("RESUMEN DEL ESTADO ACTUAL")
    if E.df is not None: print(f"  Datos:    {C.G}✓ {len(E.df)} filas{C.END} ({E.df['Date'].min().date()} a {E.ultima_fecha.date()})")
    else: print(f"  Datos:    {C.R}✗ Sin cargar{C.END}")
    if E.m1_z is not None: print(f"  Modelos:  {C.G}✓ Entrenados{C.END}")
    else: print(f"  Modelos:  {C.W}⚠ No entrenados{C.END}")
    print(f"  Agente:   {'✓' if E.agente_resp else '✗'}")
    print(f"  Factores: X={E.factores['X']} Y={E.factores['Y']} Z={E.factores['Z']}")

# ---------------------------------------------------------------
# HTML TEMPLATE
# ---------------------------------------------------------------
_HTML = r"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><title>Dashboard Equipos</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  *{box-sizing:border-box}
  body{font-family:system-ui,-apple-system,sans-serif;margin:0;padding:20px;background:#f0f4f8;color:#1f2937}
  h1{color:#1e40af;margin:0 0 4px}
  h3{color:#1e40af;margin:0 0 12px;border-bottom:2px solid #dbeafe;padding-bottom:6px}
  h4{color:#374151;margin:6px 0}
  .panel{background:#fff;border-radius:12px;padding:18px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.1)}
  .p-model{border-top:4px solid #3b82f6}
  .p-cmp{border-top:4px solid #f59e0b;background:#fffbeb}
  .p-agent{border-top:4px solid #a855f7;background:#faf5ff}
  .p-chart{border-top:4px solid #10b981}
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
  @media(max-width:900px){.grid2{grid-template-columns:1fr}}
  .formula{font-family:ui-monospace,monospace;background:#eff6ff;padding:6px 10px;border-radius:6px;font-size:12px;display:inline-block;margin:4px 0;line-height:1.5}
  .badge{display:inline-block;padding:3px 8px;border-radius:999px;font-size:12px;font-weight:700;margin-right:6px}
  .bg-g{background:#d1fae5;color:#065f46}.bg-b{background:#dbeafe;color:#1e40af}
  .bg-r{background:#fee2e2;color:#991b1b}.bg-p{background:#f3e8ff;color:#6b21a8}
  .bg-y{background:#fef3c7;color:#92400e}
  
  .table-container{max-height:600px; overflow-y:auto; overflow-x:auto; border:1px solid #e2e8f0; border-radius:8px; position:relative;}
  table{width:100%;border-collapse:collapse;font-size:12px;white-space:nowrap}
  td{padding:6px 8px;text-align:right;border-bottom:1px solid #f1f5f9;font-family:ui-monospace,monospace}
  td:first-child{text-align:left;font-family:inherit;font-weight:600}
  tr:hover{background:#f8fafc}
  
  th{background:#eff6ff;padding:10px 8px;text-align:right;color:#1e40af;box-shadow:0 1px 0 #cbd5e1}
  th:first-child{text-align:left}
  thead tr:nth-child(1) th { position: sticky; top: 0; z-index: 10; background: #dbeafe; }
  thead tr:nth-child(1) th:first-child { z-index: 12; background: #eff6ff; }
  thead tr:nth-child(2) th { position: sticky; top: 35px; z-index: 9; }

  .info{background:#f0fdf4;border-left:4px solid #22c55e;padding:10px 14px;border-radius:6px;margin-bottom:12px;font-size:13px;line-height:1.5}
  .info-warn{background:#fef3c7;border-left:4px solid #f59e0b;padding:10px 14px;border-radius:6px;margin-bottom:12px;font-size:13px}
  
  .err-hi { color:#ef4444; font-weight:bold; }
  .err-lo { color:#10b981; }
</style></head><body>

<h1>📊 Dashboard de Costos — Equipos 1 &amp; 2</h1>
<p style="color:#6b7280;margin:0 0 16px">Horizonte de proyección: <b>Simulación Volátil (Tendencia del Agente + Movimientos Diarios)</b></p>

<div class="panel p-model">
  <h3>Modelos entrenados</h3>
  <div class="grid2">
    <div><h4>Equipo 1 <span class="badge bg-b">Principal: ~ Z</span></h4>
      <div class="formula" id="f1z"></div><br>
      <span class="badge bg-g" id="r1z"></span><span class="badge bg-r" id="m1z"></span>
      <h4 style="margin-top:14px">Equipo 1 <span class="badge bg-y">Alternativo: ~ X + Y</span></h4>
      <div class="formula" id="f1xy"></div><br>
      <span class="badge bg-g" id="r1xy"></span><span class="badge bg-r" id="m1xy"></span>
    </div>
    <div><h4>Equipo 2 <span class="badge bg-b">Principal: ~ X + Z</span></h4>
      <div class="formula" id="f2xz"></div><br>
      <span class="badge bg-g" id="r2xz"></span><span class="badge bg-r" id="m2xz"></span>
      <h4 style="margin-top:14px">Equipo 2 <span class="badge bg-y">Alternativo: ~ X + Y + Z</span></h4>
      <div class="formula" id="f2xyz"></div><br>
      <span class="badge bg-g" id="r2xyz"></span><span class="badge bg-r" id="m2xyz"></span>
    </div>
  </div>
</div>

<div class="panel p-cmp">
  <h3>🔍 Conclusión de la comparativa</h3>
  <div class="info-warn">
    El modelo <b>principal</b> (impuesto por el caso) excluye Y. El <b>alternativo</b> es tu modelo original.<br>
    <b>Revisa la tabla y la gráfica del final:</b> Ahí podrás comprobar cómo el modelo alternativo predice con muchísima más precisión los datos reales (menor % de error), demostrando que la variable Y sí tiene un impacto significativo en la realidad.
  </div>
</div>

<div class="panel p-agent">
  <h3>🧠 Análisis del Agente IA</h3>
  <div class="info" id="ag"></div>
  <p>Factores aplicados a la volatilidad futura: <span class="badge bg-p" id="fx"></span>
    <span class="badge bg-p" id="fy"></span>
    <span class="badge bg-p" id="fz"></span></p>
</div>

<div class="panel p-chart">
  <h3>1. Histórico completo + Proyección a 5 Años (Simulación con Volatilidad)</h3>
  <div class="info">
    Línea oscura: Histórico Real. <br>
    Línea de color: Proyección simulada con volatilidad diaria y tendencia macro del Agente.
  </div>
  <div id="g5"></div>
</div>

<div class="panel p-chart">
  <h3>2. Equipo 1 — Proyección 30 Días (Con Intervalo de Confianza 95%)</h3>
  <div id="gEq1"></div>
</div>

<div class="panel p-chart">
  <h3>3. Equipo 2 — Proyección 30 Días (Con Intervalo de Confianza 95%)</h3>
  <div id="gEq2"></div>
</div>

<div class="panel p-chart" style="border-top-color: #8e44ad;">
  <h3>4. Demostración Visual Histórica (El ajuste de los modelos)</h3>
  <div class="grid2">
    <div>
      <h4>Equipo 1: Real vs Modelos</h4>
      <div id="gHistEq1"></div>
    </div>
    <div>
      <h4>Equipo 2: Real vs Modelos</h4>
      <div id="gHistEq2"></div>
    </div>
  </div>
</div>

<div class="panel">
  <h3>5. Tabla Histórica de Datos + Futuro Proyectado (30 días)</h3>
  <div class="table-container">
    <table>
      <thead>
        <tr>
          <th rowspan="2">Fecha</th>
          <th colspan="3" style="text-align:center; border-bottom:1px solid #bfdbfe; background:#dbeafe;">EQUIPO 1</th>
          <th colspan="3" style="text-align:center; border-bottom:1px solid #bfdbfe; background:#dbeafe;">EQUIPO 2</th>
        </tr>
        <tr>
          <th>Precio Real</th>
          <th>Principal (~Z)</th>
          <th>Alt (~X+Y)</th>
          <th>Precio Real</th>
          <th>Principal (~X+Z)</th>
          <th>Alt (~X+Y+Z)</th>
        </tr>
      </thead>
      <tbody id="tb"></tbody>
    </table>
  </div>
</div>

<div class="panel p-chart" style="border-top-color: #6366f1;">
  <h3>6. Transición: Últimos 3 meses + Próximos 30 días</h3>
  <div id="gHist30"></div>
</div>

<div class="panel p-chart" style="border-top-color: #ff9800; background: #fffaf0;">
  <h3>7. Verificación del Ajuste del Modelo (Histórico Completo)</h3>
  <div style="margin-bottom: 20px;">
    <h4>Equipo 1: Histórico Real vs Predicción de los Modelos</h4>
    <div id="gFullHistEq1"></div>
  </div>
  <div>
    <h4>Equipo 2: Histórico Real vs Predicción de los Modelos</h4>
    <div id="gFullHistEq2"></div>
  </div>
</div>

<div class="panel p-chart" id="seccion-variables" style="border-top-color: #10b981; background: #ecfdf5;">
  <h3>8. Simulación de Variables del Mercado (X, Y, Z) a 5 Años</h3>
  <div class="info" style="background: #d1fae5; border-left-color: #059669; color: #065f46;">
    Puedes ver cómo las variables fluctúan día a día. Esta volatilidad es la que genera los "picos y valles" en las gráficas de costos.
  </div>
  <div id="gVariables5A"></div>
</div>

<div class="panel p-chart" id="seccion-larga-volatilidad" style="border-top-color: #8b5cf6; background: #f5f3ff;">
  <h3>9. Proyección a 5 Años con Volatilidad Detallada</h3>
  <div class="info" style="background: #ede9fe; border-left-color: #8b5cf6; color: #4c1d95;">
    Aquí puedes ver únicamente las líneas de costos a 5 años para analizar la tendencia del serrucho sin la interferencia del histórico.
  </div>
  <div id="gVolatilidad5A"></div>
</div>

<div class="panel p-chart" style="border-top-color: #e11d48; background: #fff1f2;">
  <h3>10. Comparación Total (Histórico vs Simulación Pura vs MM3 vs Agente)</h3>
  <div class="info" style="background: #ffe4e6; border-left-color: #e11d48; color: #881337;">
    Esta gráfica maestra une todo en una sola línea de tiempo. Muestra el pasado real y las distintas formas de proyectar el futuro para que compares cuál se adapta mejor.
  </div>
  <div id="gComparacionTotalEq1"></div>
  <div id="gComparacionTotalEq2"></div>
</div>

<script>
const COEF=__COEF__, AG=__AG__, F=__FACT__, D=__DATA__;

const f1z = COEF.eq1_z;
document.getElementById("f1z").textContent = `Eq1 = ${f1z.const.toFixed(2)} + ${f1z.Z.toFixed(4)}·Z`;
document.getElementById("r1z").textContent = `R² = ${f1z.r2.toFixed(4)}`;
document.getElementById("m1z").textContent = `MAPE = ${f1z.mape.toFixed(2)}%`;

const f1xy = COEF.eq1_xy;
document.getElementById("f1xy").textContent = `Eq1 = ${f1xy.const.toFixed(2)} + ${f1xy.X.toFixed(4)}·X + ${f1xy.Y.toFixed(4)}·Y`;
document.getElementById("r1xy").textContent = `R² = ${f1xy.r2.toFixed(4)}`;
document.getElementById("m1xy").textContent = `MAPE = ${f1xy.mape.toFixed(2)}%`;

const f2xz = COEF.eq2_xz;
document.getElementById("f2xz").textContent = `Eq2 = ${f2xz.const.toFixed(2)} + ${f2xz.X.toFixed(4)}·X + ${f2xz.Z.toFixed(4)}·Z`;
document.getElementById("r2xz").textContent = `R² = ${f2xz.r2.toFixed(4)}`;
document.getElementById("m2xz").textContent = `MAPE = ${f2xz.mape.toFixed(2)}%`;

const f2xyz = COEF.eq2_xyz;
document.getElementById("f2xyz").textContent = `Eq2 = ${f2xyz.const.toFixed(2)} + ${f2xyz.X.toFixed(4)}·X + ${f2xyz.Y.toFixed(4)}·Y + ${f2xyz.Z.toFixed(4)}·Z`;
document.getElementById("r2xyz").textContent = `R² = ${f2xyz.r2.toFixed(4)}`;
document.getElementById("m2xyz").textContent = `MAPE = ${f2xyz.mape.toFixed(2)}%`;

document.getElementById("ag").textContent = AG || "No consultado.";
document.getElementById("fx").textContent = `X × ${F.X.toFixed(2)}`;
document.getElementById("fy").textContent = `Y × ${F.Y.toFixed(2)}`;
document.getElementById("fz").textContent = `Z × ${F.Z.toFixed(2)}`;

Plotly.newPlot("g5",[
  {x:D.hist_dates, y:D.eq1_hist, mode:"lines", name:"Eq1 Histórico Real", line:{color:"#111",width:1.5}},
  {x:D.hist_dates, y:D.eq2_hist, mode:"lines", name:"Eq2 Histórico Real", line:{color:"#922b21",width:1.5}},
  {x:D.fut5A_dates, y:D.eq1_5A, mode:"lines", name:"Eq1 Simulación Volátil", line:{color:"#3b82f6",width:2}},
  {x:D.fut5A_dates, y:D.eq2_5A, mode:"lines", name:"Eq2 Simulación Volátil", line:{color:"#ef4444",width:2}}
],{margin:{l:60,r:20,t:20,b:60},xaxis:{title:"Fecha",gridcolor:"#eee"},yaxis:{title:"Precio"},height:500,legend:{x:0.02,y:0.98}},{responsive:true});

// GRAFICA 2: Eq1 con IC 95%
Plotly.newPlot("gEq1",[
  {x:D.hist_dates.slice(-90), y:D.eq1_hist.slice(-90), mode:"lines", name:"Histórico Real", line:{color:"#111",width:2}},
  {x:D.fut30_dates, y:D.eq1_xy_30_hi, mode:"lines", line:{width:0}, showlegend:false, hoverinfo:"skip"},
  {x:D.fut30_dates, y:D.eq1_xy_30_lo, mode:"lines", name:"IC 95%", fill:"tonexty", fillcolor:"rgba(59, 130, 246, 0.2)", line:{width:0}},
  {x:D.fut30_dates, y:D.eq1_xy_30, mode:"lines+markers", name:"Simulación Eq1 (Alt)", line:{color:"#f59e0b",width:2.5}}
],{margin:{l:60,r:20,t:20,b:60},xaxis:{gridcolor:"#eee",tickangle:-45},yaxis:{title:"Precio Eq1"},height:400},{responsive:true});

// GRAFICA 3: Eq2 con IC 95%
Plotly.newPlot("gEq2",[
  {x:D.hist_dates.slice(-90), y:D.eq2_hist.slice(-90), mode:"lines", name:"Histórico Real", line:{color:"#111",width:2}},
  {x:D.fut30_dates, y:D.eq2_xyz_30_hi, mode:"lines", line:{width:0}, showlegend:false, hoverinfo:"skip"},
  {x:D.fut30_dates, y:D.eq2_xyz_30_lo, mode:"lines", name:"IC 95%", fill:"tonexty", fillcolor:"rgba(168, 85, 247, 0.2)", line:{width:0}},
  {x:D.fut30_dates, y:D.eq2_xyz_30, mode:"lines+markers", name:"Simulación Eq2 (Alt)", line:{color:"#a855f7",width:2.5}}
],{margin:{l:60,r:20,t:20,b:60},xaxis:{gridcolor:"#eee",tickangle:-45},yaxis:{title:"Precio Eq2"},height:400},{responsive:true});

Plotly.newPlot("gHistEq1",[
  {x:D.hist_dates, y:D.eq1_hist, mode:"lines", name:"Real", line:{color:"#111",width:1.5}},
  {x:D.hist_dates, y:D.eq1_xy_fit, mode:"lines", name:"Modelo Alt (~X+Y)", line:{color:"#f59e0b",width:1.5}}
],{margin:{l:60,r:20,t:20,b:40},xaxis:{gridcolor:"#eee"},yaxis:{title:"Precio Eq1"},height:350},{responsive:true});

Plotly.newPlot("gHistEq2",[
  {x:D.hist_dates, y:D.eq2_hist, mode:"lines", name:"Real", line:{color:"#111",width:1.5}},
  {x:D.hist_dates, y:D.eq2_xyz_fit, mode:"lines", name:"Modelo Alt (~X+Y+Z)", line:{color:"#a855f7",width:1.5}}
],{margin:{l:60,r:20,t:20,b:40},xaxis:{gridcolor:"#eee"},yaxis:{title:"Precio Eq2"},height:350},{responsive:true});

Plotly.newPlot("gHist30",[
  {x: D.hist_dates.slice(-90), y: D.eq1_hist.slice(-90), mode:"lines", name:"Eq1 Histórico", line:{color:"#111",width:2}},
  {x: D.fut30_dates, y: D.eq1_xy_30, mode:"lines+markers", name:"Eq1 Simulado", line:{color:"#f59e0b",width:2.5}},
  
  {x: D.hist_dates.slice(-90), y: D.eq2_hist.slice(-90), mode:"lines", name:"Eq2 Histórico", line:{color:"#922b21",width:2}},
  {x: D.fut30_dates, y: D.eq2_xyz_30, mode:"lines+markers", name:"Eq2 Simulado", line:{color:"#a855f7",width:2.5}}
],{margin:{l:60,r:20,t:20,b:60},xaxis:{gridcolor:"#eee",tickangle:-45},yaxis:{title:"Precio"},height:400},{responsive:true});

Plotly.newPlot("gFullHistEq1",[
  {x:D.hist_dates, y:D.eq1_hist, mode:"lines", name:"Real", line:{color:"#111",width:1.5}},
  {x:D.hist_dates, y:D.eq1_xy_fit, mode:"lines", name:"Predicción", line:{color:"#f59e0b",width:2}}
],{margin:{l:60,r:20,t:20,b:40},xaxis:{gridcolor:"#eee"},yaxis:{title:"Precio Eq1"},height:350},{responsive:true});

Plotly.newPlot("gFullHistEq2",[
  {x:D.hist_dates, y:D.eq2_hist, mode:"lines", name:"Real", line:{color:"#111",width:1.5}},
  {x:D.hist_dates, y:D.eq2_xyz_fit, mode:"lines", name:"Predicción", line:{color:"#a855f7",width:2}}
],{margin:{l:60,r:20,t:20,b:40},xaxis:{gridcolor:"#eee"},yaxis:{title:"Precio Eq2"},height:350},{responsive:true});

Plotly.newPlot("gVariables5A",[
  {x:D.fut5A_dates, y:D.X_5A, mode:"lines", name:"Acero (X)", line:{color:"#3b82f6",width:1}},
  {x:D.fut5A_dates, y:D.Y_5A, mode:"lines", name:"Aluminio (Y)", line:{color:"#f59e0b",width:1}},
  {x:D.fut5A_dates, y:D.Z_5A, mode:"lines", name:"Cobre (Z)", line:{color:"#ef4444",width:1}}
],{margin:{l:60,r:20,t:20,b:40},xaxis:{gridcolor:"#eee"},yaxis:{title:"Precio Materia Prima"},height:400,legend:{x:0.02,y:0.98}},{responsive:true});

Plotly.newPlot("gVolatilidad5A",[
  {x:D.fut5A_dates, y:D.eq1_5A, mode:"lines", name:"Eq1 Simulación 5 Años", line:{color:"#f59e0b",width:2}},
  {x:D.fut5A_dates, y:D.eq2_5A, mode:"lines", name:"Eq2 Simulación 5 Años", line:{color:"#a855f7",width:2}}
],{margin:{l:60,r:20,t:20,b:60},xaxis:{title:"Fecha",gridcolor:"#eee"},yaxis:{title:"Costo"},height:450},{responsive:true});

Plotly.newPlot("gComparacionTotalEq1",[
  {x:D.all_dates, y:D.eq1_hist_full, mode:"lines", name:"Histórico Real", line:{color:"#111",width:1.5}},
  {x:D.all_dates, y:D.eq1_model_complete, mode:"lines", name:"Modelo Puro (Fit + Futuro)", line:{color:"#f59e0b",width:2}},
  {x:D.all_dates, y:D.eq1_z_complete, mode:"lines", name:"Modelo de la Prueba (~Z)", line:{color:"#8b5cf6",width:2, dash:"dashdot"}},
  {x:D.all_dates, y:D.eq1_mm3_complete, mode:"lines", name:"Proyección MM3 (Lineal)", line:{color:"#ef4444",width:2, dash:"dot"}},
  {x:D.all_dates, y:D.eq1_mc_complete, mode:"lines", name:"Monte Carlo + Agente", line:{color:"#3b82f6",width:2, dash:"dash"}}
],{margin:{l:60,r:20,t:20,b:60},xaxis:{title:"Fecha",gridcolor:"#eee"},yaxis:{title:"Precio Eq1"},height:450,legend:{x:0.02,y:0.98}},{responsive:true});

Plotly.newPlot("gComparacionTotalEq2",[
  {x:D.all_dates, y:D.eq2_hist_full, mode:"lines", name:"Histórico Real", line:{color:"#111",width:1.5}},
  {x:D.all_dates, y:D.eq2_model_complete, mode:"lines", name:"Modelo Puro (Fit + Futuro)", line:{color:"#a855f7",width:2}},
  {x:D.all_dates, y:D.eq2_xz_complete, mode:"lines", name:"Modelo de la Prueba (~X+Z)", line:{color:"#8b5cf6",width:2, dash:"dashdot"}},
  {x:D.all_dates, y:D.eq2_mm3_complete, mode:"lines", name:"Proyección MM3 (Lineal)", line:{color:"#ef4444",width:2, dash:"dot"}},
  {x:D.all_dates, y:D.eq2_mc_complete, mode:"lines", name:"Monte Carlo + Agente", line:{color:"#3b82f6",width:2, dash:"dash"}}
],{margin:{l:60,r:20,t:20,b:60},xaxis:{title:"Fecha",gridcolor:"#eee"},yaxis:{title:"Precio Eq2"},height:450,legend:{x:0.02,y:0.98}},{responsive:true});

const tb=document.getElementById("tb");
tb.innerHTML = "";

for(let i = D.fut30_dates.length - 1; i >= 0; i--){
  const r=document.createElement("tr");
  r.style.backgroundColor = "#fcf4ff";
  r.innerHTML = `
    <td style="color:#8e44ad;"><b>${D.fut30_dates[i]}</b> (Futuro)</td>
    <td>-</td>
    <td style="color:#8e44ad;">${D.eq1_z_30[i].toFixed(2)}</td>
    <td style="color:#8e44ad;">${D.eq1_xy_30[i].toFixed(2)}</td>
    <td>-</td>
    <td style="color:#8e44ad;">${D.eq2_xz_30[i].toFixed(2)}</td>
    <td style="color:#8e44ad;">${D.eq2_xyz_30[i].toFixed(2)}</td>
  `;
  tb.appendChild(r);
}

if (D.fut30_dates.length > 0) {
  const sep = document.createElement("tr");
  sep.innerHTML = `<td colspan="7" style="text-align:center; font-weight:bold; background:#e2e8f0; color:#475569;">▲ FUTURO / ▼ HISTÓRICO REAL</td>`;
  tb.appendChild(sep);
}

for(let i = D.hist_dates.length - 1; i >= 0; i--){
  const real1 = D.eq1_hist[i];
  const pred1_z = D.eq1_z_fit[i];
  const pred1_xy = D.eq1_xy_fit[i];
  
  const real2 = D.eq2_hist[i];
  const pred2_xz = D.eq2_xz_fit[i];
  const pred2_xyz = D.eq2_xyz_fit[i];
  
  const err1_z = Math.abs(real1 - pred1_z) / real1 * 100;
  const err1_xy = Math.abs(real1 - pred1_xy) / real1 * 100;
  const err2_xz = Math.abs(real2 - pred2_xz) / real2 * 100;
  const err2_xyz = Math.abs(real2 - pred2_xyz) / real2 * 100;
  
  const colorErr = (err) => err > 5 ? 'err-hi' : 'err-lo';
  
  const r=document.createElement("tr");
  r.innerHTML = `
    <td>${D.hist_dates[i]}</td>
    <td><b>${real1.toFixed(2)}</b></td>
    <td>${pred1_z.toFixed(2)} <br><span class="${colorErr(err1_z)}">(${err1_z.toFixed(1)}%)</span></td>
    <td>${pred1_xy.toFixed(2)} <br><span class="${colorErr(err1_xy)}">(${err1_xy.toFixed(1)}%)</span></td>
    
    <td><b>${real2.toFixed(2)}</b></td>
    <td>${pred2_xz.toFixed(2)} <br><span class="${colorErr(err2_xz)}">(${err2_xz.toFixed(1)}%)</span></td>
    <td>${pred2_xyz.toFixed(2)} <br><span class="${colorErr(err2_xyz)}">(${err2_xyz.toFixed(1)}%)</span></td>
  `;
  tb.appendChild(r);
}
</script></body></html>"""

# ---------------------------------------------------------------
# MENÚ PRINCIPAL
# ---------------------------------------------------------------
def menu():
    while True:
        datos = f"{len(E.df)} filas" if E.df is not None else "Sin cargar"
        mods = "Entrenados" if E.m1_z is not None else "No entrenados"
        
        print(f"\n{C.BOLD}{C.CY}{'─'*66}{C.END}")
        print(f"{C.BOLD}  GESTOR DE COSTOS{C.END}  |  Datos: {C.G}{datos}{C.END}  |  Modelos: {C.G}{mods}{C.END}")
        print(f"{C.BOLD}{C.CY}{'─'*66}{C.END}")
        print("  1) Cargar datos históricos (Reinicia)")
        print("  1b) AGREGAR más datos al histórico actual")
        print("  2) Entrenar modelos (4 variantes y comparar)")
        print("  3) Generar proyección base (Línea Recta) + Guardar Excel")
        print("  3d) Simular volatilidad (Ver picos en consola)")
        print("  4) Consultar Agente IA (Calcula factores de ajuste)")
        print("  4b) Sobrescribir factores manualmente")
        print("  4c) CHAT interactivo con el Agente IA (Preguntas)")
        print("  5) Simulador what-if")
        print("  6) Generar dashboard HTML")
        print("  7) Generar + abrir en navegador")
        print("  8) Ver resumen")
        print("  0) Salir")
        
        opt = input(f"\n  {C.BOLD}Opción → {C.END}").strip().lower()

        if   opt == "1":  cargar_datos()
        elif opt == "1b": agregar_datos()
        elif opt == "2":  entrenar_modelos()
        elif opt == "3":  proyectar()
        elif opt == "3d": proyectar_con_volatilidad()
        elif opt == "4":  consultar_agente()
        elif opt == "4b": override_factores()
        elif opt == "4c": chat_interactivo()
        elif opt == "5":  simulador()
        elif opt == "6":  generar_html()
        elif opt == "7":  generar_html(abrir=True)
        elif opt == "8":  ver_resumen()
        elif opt == "0":
            print(f"\n{C.G}👋 Hasta luego.{C.END}\n"); break
        else: warn("Opción no válida.")

if __name__ == "__main__":
    print(f"\n{C.BOLD}🚀 Sistema interactivo de costos{C.END}")
    if os.path.exists(EXCEL):
        if cargar_datos():
            entrenar_modelos()
    menu()
