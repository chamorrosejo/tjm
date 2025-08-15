
import streamlit as st
import pandas as pd
import os, math
from datetime import datetime
from fpdf import FPDF

def _safe_float(val, default=0.0):
    try:
        if val is None: return default
        if isinstance(val, float) and pd.isna(val): return default
        if isinstance(val, str):
            s = val.strip().lower()
            if s in ("", "nan", "none"): return default
            # strip currency formatting
            s = s.replace("$","").replace(",","").strip()
            return float(s)
        return float(val)
    except Exception:
        return default

def ceil_to_even(x: float) -> int:
    n = math.ceil(x)
    return n if n % 2 == 0 else n + 1

def money(n): return f"${_safe_float(n):,.0f}"

SCRIPT_DIR = os.path.dirname(__file__) if "__file__" in globals() else os.getcwd()

_default_designs = os.path.join(SCRIPT_DIR, "data", "disenos_cortina.xlsx")
_default_bom     = os.path.join(SCRIPT_DIR, "data", "bom.xlsx")
_default_cat_ins = os.path.join(SCRIPT_DIR, "data", "catalogo_insumos.xlsx")
_default_cat_tel = os.path.join(SCRIPT_DIR, "data", "catalogo_telas.xlsx")

DESIGNS_XLSX_PATH      = os.environ.get("DESIGNS_XLSX_PATH")       or st.secrets.get("DESIGNS_XLSX_PATH", _default_designs)
BOM_XLSX_PATH          = os.environ.get("BOM_XLSX_PATH")           or st.secrets.get("BOM_XLSX_PATH", _default_bom)
CATALOG_XLSX_PATH      = os.environ.get("CATALOG_XLSX_PATH")       or st.secrets.get("CATALOG_XLSX_PATH", _default_cat_ins)
CATALOG_TELAS_XLSX_PATH= os.environ.get("CATALOG_TELAS_XLSX_PATH") or st.secrets.get("CATALOG_TELAS_XLSX_PATH", _default_cat_tel)

REQUIRED_DESIGNS_COLS = ["Diseño", "Tipo", "Multiplicador", "PVP M.O."]
REQUIRED_BOM_COLS     = ["Diseño", "Insumo", "Unidad", "ReglaCantidad", "Parametro", "DependeDeSeleccion", "Observaciones"]
REQUIRED_CAT_COLS     = ["Insumo", "Unidad", "Ref", "Color", "PVP"]
REQUIRED_TELAS_COLS   = ["TipoTela", "Referencia", "Color", "PVP/Metro ($)"]

ALLOWED_RULES = {"MT_ANCHO_X_MULT", "UND_OJALES_PAR", "UND_BOTON_PAR", "FIJO"}
IVA_PERCENT = 0.19
DISTANCIA_BOTON_DEF = 0.20
DISTANCIA_OJALES_DEF = 0.14

@st.cache_data
def load_excel(path, required):
    df = pd.read_excel(path, engine="openpyxl")
    faltantes = [c for c in required if c not in df.columns]
    if faltantes: raise RuntimeError(f"Faltan columnas {faltantes} en {os.path.basename(path)}")
    return df

def load_designs(df):
    tabla_disenos, tipos_cortina, precios_mo, disenos_a_tipos = {}, {}, {}, {}
    for _, row in df.iterrows():
        dis = str(row["Diseño"]).strip()
        tipos = [t.strip() for t in str(row["Tipo"]).split(",") if str(t).strip()]
        mult = _safe_float(row["Multiplicador"], 1.0)
        mo_val = _safe_float(row["PVP M.O."], 0.0)
        tabla_disenos[dis] = mult
        precios_mo[f"M.O: {dis}"] = {"unidad": "MT", "pvp": mo_val}
        disenos_a_tipos.setdefault(dis, [])
        for t in tipos:
            tipos_cortina.setdefault(t, [])
            if dis not in tipos_cortina[t]: tipos_cortina[t].append(dis)
            if t not in disenos_a_tipos[dis]: disenos_a_tipos[dis].append(t)
    return tabla_disenos, tipos_cortina, precios_mo, disenos_a_tipos

def load_bom(df):
    bom = {}
    for _, row in df.iterrows():
        p_raw = row.get("Parametro","")
        if pd.isna(p_raw) or (isinstance(p_raw,str) and p_raw.strip().lower() in ("","nan","none")): param_norm=""
        else: param_norm=str(p_raw).strip()
        item = {
            "Insumo": str(row["Insumo"]).strip(),
            "Unidad": str(row["Unidad"]).strip().upper(),
            "ReglaCantidad": str(row["ReglaCantidad"]).strip().upper(),
            "Parametro": param_norm,
            "DependeDeSeleccion": str(row["DependeDeSeleccion"]).strip().upper(),
            "Observaciones": "" if pd.isna(row.get("Observaciones","")) else str(row.get("Observaciones",""))
        }
        bom.setdefault(str(row["Diseño"]).strip(), []).append(item)
    return bom

def load_catalog(df):
    catalog = {}
    for _, row in df.iterrows():
        insumo = str(row["Insumo"]).strip()
        unidad = str(row["Unidad"]).strip().upper()
        ref = str(row["Ref"]).strip()
        color = str(row["Color"]).strip()
        pvp = _safe_float(row["PVP"], 0.0)
        catalog.setdefault(insumo, {"unidad": unidad, "opciones": []})
        if not catalog[insumo].get("unidad"): catalog[insumo]["unidad"] = unidad
        catalog[insumo]["opciones"].append({"ref": ref, "color": color, "pvp": pvp})
    return catalog

def load_telas(df):
    telas = {}
    for _, row in df.iterrows():
        tipo = str(row["TipoTela"]).strip()
        ref = str(row["Referencia"]).strip()
        color = str(row["Color"]).strip()
        pvp = _safe_float(row["PVP/Metro ($)"], 0.0)
        telas.setdefault(tipo,{}); telas[tipo].setdefault(ref,[])
        telas[tipo][ref].append({"color": color, "pvp": pvp})
    return telas

st.set_page_config(page_title="Megatex Cotizador", page_icon="🧵", layout="wide")

# Load all data
try:
    df_dis = load_excel(DESIGNS_XLSX_PATH, REQUIRED_DESIGNS_COLS)
    df_bom = load_excel(BOM_XLSX_PATH, REQUIRED_BOM_COLS)
    df_cat = load_excel(CATALOG_XLSX_PATH, REQUIRED_CAT_COLS)
    df_tel = load_excel(CATALOG_TELAS_XLSX_PATH, REQUIRED_TELAS_COLS)
except Exception as e:
    st.error(str(e)); st.stop()

TABLA_DISENOS, TIPOS_CORTINA, PRECIOS_MANO_DE_OBRA, DISENOS_A_TIPOS = load_designs(df_dis)
BOM_DICT = load_bom(df_bom)
CATALOGO_INSUMOS = load_catalog(df_cat)
CATALOGO_TELAS = load_telas(df_tel)

def init_state():
    st.session_state.setdefault("pagina_actual","cotizador")
    st.session_state.setdefault("datos_cotizacion", {"cliente": {}, "vendedor": {}})
    st.session_state.setdefault("cortinas_resumen", [])
    st.session_state.setdefault("cortina_calculada", None)
    st.session_state.setdefault("tipo_cortina_sel", list(TIPOS_CORTINA.keys())[0])

init_state()

# Top navigation (ensures pages are reachable even if sidebar is hidden)
tab_map = {"Configurar":"cotizador","Datos":"datos","Resumen":"resumen"}
tabs = st.tabs(list(tab_map.keys()))
# We'll render after setting page variable

def pantalla_cotizador():
    st.header("Configurar Cortina")
    c1,c2,c3 = st.columns(3)
    ancho = c1.number_input("Ancho de la Ventana (m)", min_value=0.1, value=2.0, step=0.1, key="ancho")
    alto  = c2.number_input("Alto de la Cortina (m)", min_value=0.1, value=2.0, step=0.1, key="alto")
    cant  = c3.number_input("Cantidad (und)", min_value=1, value=1, step=1, key="cantidad")
    st.markdown("---")
    st.subheader("2. Selecciona el Diseño")
    tipo_opciones = list(TIPOS_CORTINA.keys()); tipo_default = st.session_state.get("tipo_cortina_sel", tipo_opciones[0])
    tipo_sel = st.selectbox("Tipo de Cortina", options=tipo_opciones, index=tipo_opciones.index(tipo_default), key="tipo_cortina_sel")
    disenos = TIPOS_CORTINA.get(tipo_sel, [])
    dis_prev = st.session_state.get("diseno_sel", disenos[0] if disenos else "")
    if dis_prev not in disenos and disenos: dis_prev = disenos[0]
    st.selectbox("Diseño", options=disenos, index=(disenos.index(dis_prev) if disenos else 0), key="diseno_sel")
    multip = st.number_input("Multiplicador", min_value=1.0, value=float(TABLA_DISENOS.get(st.session_state.diseno_sel,2.0)), step=0.1, key="multiplicador")
    st.number_input("Ancho Cortina (m)", value=float(st.session_state.ancho * multip), step=0.1, disabled=True, key="ancho_cortina_info")

    st.markdown("---"); st.subheader("3. Selecciona la(s) Tela(s)")
    def ui_tela(prefix):
        tipo = st.selectbox(f"Tipo de Tela {prefix}", options=list(CATALOGO_TELAS.keys()), key=f"tipo_tela_sel_{prefix}")
        referencias = list(CATALOGO_TELAS[tipo].keys())
        ref_sel = st.selectbox(f"Referencia {prefix}", options=referencias, key=f"ref_tela_sel_{prefix}")
        colores = sorted({opt['color'] for opt in CATALOGO_TELAS[tipo][ref_sel]}) or ["No disponible"]
        color_sel = st.selectbox(f"Color {prefix}", options=colores, key=f"color_tela_sel_{prefix}")
        info = next((x for x in CATALOGO_TELAS[tipo][ref_sel] if x["color"]==color_sel), {"pvp":0})
        # keep numeric & show formatted
        st.session_state[f"pvp_tela_{prefix}_num"] = _safe_float(info["pvp"],0.0)
        st.number_input(f"PVP/Metro TELA {prefix} ($)", value=_safe_float(info["pvp"]), disabled=True, key=f"pvp_tela_{prefix}_show", format="%d")
        st.radio(f"Modo de confección {prefix}", options=["Entera","Partida","Semipartida"], horizontal=True, key=f"modo_conf_{prefix}")
    ui_tela("1")
    usa_tela2 = any(i["Insumo"].strip().upper()=="TELA 2" for i in BOM_DICT.get(st.session_state.diseno_sel,[]))
    if usa_tela2:
        st.markdown("—")
        ui_tela("2")

    st.markdown("---"); st.subheader("4. Insumos según BOM")
    items = [it for it in BOM_DICT.get(st.session_state.diseno_sel, []) if it["DependeDeSeleccion"]=="SI"]
    if not items:
        st.info("Este diseño no requiere insumos adicionales para seleccionar.")
    for it in items:
        nombre = it["Insumo"]
        if nombre in CATALOGO_INSUMOS:
            cat = CATALOGO_INSUMOS[nombre]
            refs = sorted({opt['ref'] for opt in cat['opciones']})
            ref_sel = st.selectbox(f"Referencia {nombre}", options=refs, key=f"ref_{nombre}")
            colores = sorted({opt['color'] for opt in cat['opciones'] if opt.get('ref')==ref_sel}) or ["No disponible"]
            color_sel = st.selectbox(f"Color {nombre}", options=colores, key=f"color_{nombre}")
            info = next((o for o in cat['opciones'] if o['ref']==ref_sel and o['color']==color_sel), {"pvp":0})
            st.session_state.setdefault("insumos_seleccion",{})
            st.session_state["insumos_seleccion"][nombre] = {"ref": ref_sel, "color": color_sel, "pvp": _safe_float(info["pvp"]), "unidad": cat["unidad"]}
            st.number_input(f"P.V.P {nombre} ({cat['unidad']})", value=_safe_float(info["pvp"]), disabled=True, key=f"pvp_{nombre}_show", format="%d")
        else:
            st.warning(f"{nombre}: marcado como 'DependeDeSeleccion' pero no está en el Catálogo de Insumos.")

    # Buttons
    st.markdown("""<style> div.stButton > button {background:#c1121f;color:white;} </style>""", unsafe_allow_html=True)
    if st.button("Calcular cotización"):
        calcular_cotizacion()
    if st.session_state.get("cortina_calculada"):
        mostrar_detalle()
        if st.button("Guardar cortina"):
            guardar_cortina()
            st.success("Cortina guardada en la cotización. Ve a 'Resumen' para verla.")
def calcular_cotizacion():
    diseno = st.session_state.diseno_sel
    ancho = _safe_float(st.session_state.ancho,0.0)
    multip = _safe_float(st.session_state.multiplicador,1.0)
    cant = int(st.session_state.cantidad)
    detalle, subtotal = [], 0.0
    for it in BOM_DICT.get(diseno, []):
        nombre = it["Insumo"].strip().upper()
        regla = it["ReglaCantidad"].upper()
        param = it["Parametro"]
        unidad = it["Unidad"].upper()
        if regla=="MT_ANCHO_X_MULT":
            factor=_safe_float(param,1.0); cantidad=ancho*multip*factor
        elif regla=="UND_OJALES_PAR":
            paso=_safe_float(param,0.14); cantidad=ceil_to_even((ancho*multip)/paso)
        elif regla=="UND_BOTON_PAR":
            paso=_safe_float(param,0.20); cantidad=ceil_to_even((ancho*multip)/paso)
        elif regla=="FIJO":
            cantidad=_safe_float(param,0.0)
        else:
            st.error(f"ReglaCantidad no soportada: {regla}"); return
        cantidad_total = cantidad*cant
        if nombre=="TELA 1":
            pvp = _safe_float(st.session_state.get("pvp_tela_1_num"),0.0)
            ref = st.session_state.get("ref_tela_sel_1",""); color = st.session_state.get("color_tela_sel_1","")
            nombre_mostrar = f"TELA 1: {ref} - {color}"
            uni="MT"
        elif nombre=="TELA 2":
            pvp = _safe_float(st.session_state.get("pvp_tela_2_num"),0.0)
            ref = st.session_state.get("ref_tela_sel_2",""); color = st.session_state.get("color_tela_sel_2","")
            nombre_mostrar = f"TELA 2: {ref} - {color}"
            uni="MT"
        elif nombre.startswith("M.O"):
            continue
        else:
            sel = st.session_state.get("insumos_seleccion",{}).get(it["Insumo"],{})
            pvp = _safe_float(sel.get("pvp"),0.0)
            uni = sel.get("unidad", unidad)
            nombre_mostrar = it["Insumo"]
        precio = pvp * cantidad_total; subtotal += precio
        detalle.append({"Insumo": nombre_mostrar, "Unidad": uni,
                        "Cantidad": round(cantidad_total,2) if uni!="UND" else int(round(cantidad_total)),
                        "P.V.P/Unit ($)": pvp, "Precio ($)": precio})
    mo_key = f"M.O: {diseno}"
    if mo_key in PRECIOS_MANO_DE_OBRA and _safe_float(PRECIOS_MANO_DE_OBRA[mo_key]["pvp"])>0:
        cant_mo = ancho*multip*cant; pvp_mo=_safe_float(PRECIOS_MANO_DE_OBRA[mo_key]["pvp"],0.0)
        precio_mo = cant_mo*pvp_mo; subtotal += precio_mo
        detalle.append({"Insumo": mo_key, "Unidad":"MT","Cantidad":round(cant_mo,2),
                        "P.V.P/Unit ($)": pvp_mo, "Precio ($)": precio_mo})
    iva = subtotal*IVA_PERCENT; total=subtotal
    st.session_state.cortina_calculada = {"diseno": diseno, "ancho": ancho, "alto": _safe_float(st.session_state.alto),
        "multiplicador": multip, "cantidad": cant, "detalle": detalle, "subtotal": subtotal-iva, "iva": iva, "total": total,
        "telas": {"tela1":{"modo": st.session_state.get("modo_conf_1","")},
                  "tela2":{"modo": st.session_state.get("modo_conf_2","")} if st.session_state.get("pvp_tela_2_num") is not None else None}}

def mostrar_detalle():
    det = st.session_state.cortina_calculada["detalle"]
    df = pd.DataFrame(det)
    df["P.V.P/Unit ($)"] = df["P.V.P/Unit ($)"].apply(money)
    df["Precio ($)"] = df["Precio ($)"].apply(money)
    st.dataframe(df, use_container_width=True, hide_index=True)
    c1,c2,c3 = st.columns(3)
    c1.metric("Subtotal Cortina", money(st.session_state.cortina_calculada["subtotal"]))
    c2.metric("IVA Cortina", money(st.session_state.cortina_calculada["iva"]))
    c3.metric("Total Cortina", money(st.session_state.cortina_calculada["total"]))

def guardar_cortina():
    st.session_state.cortinas_resumen.append(st.session_state.cortina_calculada)

def pantalla_datos():
    st.header("Datos de la Cotización")
    st.write("Formulario de datos del cliente/vendedor (placeholder).")

def pantalla_resumen():
    st.header("Resumen de la Cotización")
    if not st.session_state.cortinas_resumen:
        st.info("Aún no has añadido ninguna cortina a la cotización.")
        return
    for i, c in enumerate(st.session_state.cortinas_resumen, start=1):
        with st.container(border=True):
            col1,col2,col3,col4 = st.columns([0.5, 2.5, 2.5, 1])
            col1.markdown(f"**{i}**")
            # Col2: Diseño + bullets de insumos
            bullets = []
            for it in c["detalle"]:
                nm = it["Insumo"]
                cant = it["Cantidad"]; uni = it["Unidad"]
                if nm.startswith("TELA 1"):
                    modo = st.session_state.get("modo_conf_1","")
                    bullets.append(f"- {nm} [{' '+modo+' ' if modo else ''}]. — {cant} {uni}".replace("  ", " ").replace("[ ]","").replace("[]",""))
                elif nm.startswith("TELA 2"):
                    modo = st.session_state.get("modo_conf_2","")
                    bullets.append(f"- {nm} [{' '+modo+' ' if modo else ''}]. — {cant} {uni}".replace("  ", " ").replace("[ ]","").replace("[]",""))
                else:
                    bullets.append(f"- {nm} — {cant} {uni}")
            col2.markdown(f"**{c['diseno']}**\n\n" + "\n".join(bullets))
            col3.write(f"Dimensiones: {c['ancho']*c['multiplicador']:.2f} × {c['alto']:.2f} m • Cant: {c['cantidad']}")
            col4.markdown(f"**{money(c['total'])}**")

# Render tabs
with tabs[0]:
    st.session_state.pagina_actual = "cotizador"
    pantalla_cotizador()
with tabs[1]:
    st.session_state.pagina_actual = "datos"
    pantalla_datos()
with tabs[2]:
    st.session_state.pagina_actual = "resumen"
    pantalla_resumen()
