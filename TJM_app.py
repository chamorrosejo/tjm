
import streamlit as st
import pandas as pd
import os
import math
from datetime import datetime
from fpdf import FPDF

# ---------- Helpers ----------
def _safe_float(val, default=0.0):
    try:
        if val is None:
            return default
        if isinstance(val, float):
            if pd.isna(val): return default
            return float(val)
        if isinstance(val, (int,)):
            return float(val)
        s = str(val).strip()
        if s == "" or s.lower() in ("nan","none"):
            return default
        # strip currency decoration if any
        s2 = s.replace("$","").replace(",","").replace(" ", "")
        return float(s2)
    except Exception:
        return default

def fmt_money(n):
    return f"${int(round(_safe_float(n,0))):,}"

def ceil_to_even(x: float) -> int:
    n = math.ceil(x)
    return n if n % 2 == 0 else n + 1

# ---------- Paths ----------
SCRIPT_DIR = os.path.dirname(__file__) if "__file__" in globals() else os.getcwd()
_default_designs = os.path.join(SCRIPT_DIR, "data", "disenos_cortina.xlsx")
_default_bom     = os.path.join(SCRIPT_DIR, "data", "bom.xlsx")
_default_cat_ins = os.path.join(SCRIPT_DIR, "data", "catalogo_insumos.xlsx")
_default_cat_tel = os.path.join(SCRIPT_DIR, "data", "catalogo_telas.xlsx")

DESIGNS_XLSX_PATH       = os.environ.get("DESIGNS_XLSX_PATH")       or st.secrets.get("DESIGNS_XLSX_PATH", _default_designs)
BOM_XLSX_PATH           = os.environ.get("BOM_XLSX_PATH")           or st.secrets.get("BOM_XLSX_PATH", _default_bom)
CATALOG_XLSX_PATH       = os.environ.get("CATALOG_XLSX_PATH")       or st.secrets.get("CATALOG_XLSX_PATH", _default_cat_ins)
CATALOG_TELAS_XLSX_PATH = os.environ.get("CATALOG_TELAS_XLSX_PATH") or st.secrets.get("CATALOG_TELAS_XLSX_PATH", _default_cat_tel)

REQUIRED_DESIGNS_COLS = ["Diseño","Tipo","Multiplicador","PVP M.O."]
REQUIRED_BOM_COLS     = ["Diseño","Insumo","Unidad","ReglaCantidad","Parametro","DependeDeSeleccion","Observaciones"]
REQUIRED_CAT_COLS     = ["Insumo","Unidad","Ref","Color","PVP"]
REQUIRED_TELAS_COLS   = ["TipoTela","Referencia","Color","PVP/Metro ($)"]

ALLOWED_RULES = {"MT_ANCHO_X_MULT","UND_OJALES_PAR","UND_BOTON_PAR","FIJO"}
IVA_PERCENT = 0.19
DISTANCIA_BOTON_DEF = 0.20
DISTANCIA_OJALES_DEF = 0.14

# ---------- Loaders ----------
@st.cache_data
def load_df(path):
    return pd.read_excel(path, engine="openpyxl")

def load_designs(path):
    df = load_df(path)
    falt = [c for c in REQUIRED_DESIGNS_COLS if c not in df.columns]
    if falt: st.stop()
    tabla, tipos, mo, d2t = {}, {}, {}, {}
    for _,r in df.iterrows():
        d = str(r["Diseño"]).strip()
        tlist = [t.strip() for t in str(r["Tipo"]).split(",") if str(t).strip()]
        tabla[d] = _safe_float(r["Multiplicador"], 1.0)
        mo[f"M.O: {d}"] = {"unidad":"MT","pvp":_safe_float(r["PVP M.O."],0)}
        d2t.setdefault(d,[])
        for t in tlist:
            tipos.setdefault(t,[])
            if d not in tipos[t]: tipos[t].append(d)
            if t not in d2t[d]: d2t[d].append(t)
    return tabla, tipos, mo, d2t, df

def load_bom(path):
    df = load_df(path)
    falt = [c for c in REQUIRED_BOM_COLS if c not in df.columns]
    if falt: st.stop()
    bom = {}
    for _,r in df.iterrows():
        p = r.get("Parametro","")
        if pd.isna(p) or str(p).strip().lower() in ("","nan","none"): p=""
        item = {
            "Insumo": str(r["Insumo"]).strip(),
            "Unidad": str(r["Unidad"]).strip().upper(),
            "ReglaCantidad": str(r["ReglaCantidad"]).strip().upper(),
            "Parametro": str(p),
            "DependeDeSeleccion": str(r["DependeDeSeleccion"]).strip().upper(),
            "Observaciones": "" if pd.isna(r.get("Observaciones","")) else str(r.get("Observaciones",""))
        }
        bom.setdefault(str(r["Diseño"]).strip(), []).append(item)
    return bom, df

def load_catalog(path):
    if not os.path.exists(path): return {}
    df = load_df(path)
    falt = [c for c in REQUIRED_CAT_COLS if c not in df.columns]
    if falt: st.stop()
    cat = {}
    for _,r in df.iterrows():
        ins = str(r["Insumo"]).strip()
        uni = str(r["Unidad"]).strip().upper()
        ref = str(r["Ref"]).strip()
        col = str(r["Color"]).strip()
        pvp = _safe_float(r["PVP"],0)
        cat.setdefault(ins, {"unidad":uni, "opciones":[]})
        cat[ins]["opciones"].append({"ref":ref,"color":col,"pvp":pvp})
    return cat

def load_telas(path):
    df = load_df(path)
    falt = [c for c in REQUIRED_TELAS_COLS if c not in df.columns]
    if falt: st.stop()
    telas = {}
    for _,r in df.iterrows():
        tipo = str(r["TipoTela"]).strip()
        ref = str(r["Referencia"]).strip()
        col = str(r["Color"]).strip()
        pvp = _safe_float(r["PVP/Metro ($)"],0)
        telas.setdefault(tipo,{})
        telas[tipo].setdefault(ref, [])
        telas[tipo][ref].append({"color":col,"pvp":pvp})
    return telas

# ---------- App ----------
st.set_page_config(page_title="Megatex Cotizador", layout="wide")
TABLA_DISENOS, TIPOS_CORTINA, PRECIOS_MO, D2T, DF_DES = load_designs(DESIGNS_XLSX_PATH)
BOM, DF_BOM = load_bom(BOM_XLSX_PATH)
CAT_INS = load_catalog(CATALOG_XLSX_PATH)
CAT_TELAS = load_telas(CATALOG_TELAS_XLSX_PATH)

def init_state():
    for k,v in {"pagina_actual":"cotizador","cortina_calculada":None}.items():
        if k not in st.session_state: st.session_state[k]=v
init_state()

# CSS for red buttons
st.markdown("""
<style>
div.stButton > button:first-child {background:#c62828;color:white;border:0}
</style>
""", unsafe_allow_html=True)

def ui_tela(prefix):
    tipo = st.selectbox(f"Tipo de Tela {prefix}", options=list(CAT_TELAS.keys()), key=f"tipo_tela_sel_{prefix}")
    refs = list(CAT_TELAS[tipo].keys())
    ref = st.selectbox(f"Referencia {prefix}", options=refs, key=f"ref_tela_sel_{prefix}")
    colores = [x["color"] for x in CAT_TELAS[tipo][ref]]
    color = st.selectbox(f"Color {prefix}", options=colores, key=f"color_tela_sel_{prefix}")
    info = next(x for x in CAT_TELAS[tipo][ref] if x["color"]==color)
    # store numeric separately
    st.session_state[f"pvp_tela_{prefix}_num"] = info["pvp"]
    # show formatted PVP
    st.text_input(f"PVP/Metro TELA {prefix} ($)", value=fmt_money(info["pvp"]), disabled=True, key=f"pvp_tela_{prefix}_show")
    st.radio(f"Modo de confección {prefix}", options=["Entera","Partida","Semipartida"], horizontal=True, key=f"modo_conf_{prefix}")

def ui_insumo_catalogo(nombre, cat):
    refs = sorted({opt['ref'] for opt in cat['opciones']})
    ref_key = f"ref_{nombre}"
    color_key = f"color_{nombre}"
    ref_sel = st.selectbox(f"Referencia {nombre}", options=refs, key=ref_key)
    colores = sorted({opt['color'] for opt in cat['opciones'] if opt.get('ref') == ref_sel}) or ["No disponible"]
    color_sel = st.selectbox(f"Color {nombre}", options=colores, key=color_key)
    info = next((opt for opt in cat['opciones'] if opt.get('ref')==ref_sel and opt.get('color')==color_sel), None)
    pvp_num = _safe_float(info["pvp"],0) if info else 0.0
    st.text_input(f"P.V.P {nombre} ({cat['unidad']})", value=fmt_money(pvp_num), disabled=True, key=f"pvp_{nombre}_show")
    st.session_state.setdefault("insumos_seleccion",{})
    st.session_state.insumos_seleccion[nombre] = {"ref":ref_sel,"color":color_sel,"pvp_num":pvp_num,"unidad":cat["unidad"]}

def calcular(detalle=True):
    dis = st.session_state.diseno_sel
    ancho = _safe_float(st.session_state.ancho,0)
    mult = _safe_float(st.session_state.multiplicador,1)
    n = int(st.session_state.cantidad)
    detalle_rows = []
    subtotal = 0.0
    for it in BOM.get(dis, []):
        nameU = it["Insumo"].strip().upper()
        unidad = it["Unidad"].upper()
        regla = it["ReglaCantidad"].upper()
        param = it["Parametro"]
        if regla=="MT_ANCHO_X_MULT":
            factor = _safe_float(param,1.0)
            cant = ancho*mult*factor
        elif regla=="UND_OJALES_PAR":
            paso = _safe_float(param, DISTANCIA_OJALES_DEF)
            cant = ceil_to_even((ancho*mult)/paso)
        elif regla=="UND_BOTON_PAR":
            paso = _safe_float(param, DISTANCIA_BOTON_DEF)
            cant = ceil_to_even((ancho*mult)/paso)
        elif regla=="FIJO":
            cant = _safe_float(param,0)
        else:
            cant = 0
        cant_total = cant*n
        if nameU=="TELA 1":
            pvp = _safe_float(st.session_state.get("pvp_tela_1_num"),0)
            ref = st.session_state.get("ref_tela_sel_1","")
            color = st.session_state.get("color_tela_sel_1","")
            nombre = f"TELA 1: {ref} - {color} [{st.session_state.get('modo_conf_1','')}]"
            uni="MT"
        elif nameU=="TELA 2":
            pvp = _safe_float(st.session_state.get("pvp_tela_2_num"),0)
            ref = st.session_state.get("ref_tela_sel_2","")
            color = st.session_state.get("color_tela_sel_2","")
            nombre = f"TELA 2: {ref} - {color} [{st.session_state.get('modo_conf_2','')}]"
            uni="MT"
        elif nameU.startswith("M.O"):
            continue
        else:
            sel = st.session_state.get("insumos_seleccion",{}).get(it["Insumo"],{})
            pvp = _safe_float(sel.get("pvp_num"),0)
            uni = sel.get("unidad", unidad)
            nombre = it["Insumo"]
        precio = pvp*cant_total
        subtotal += precio
        detalle_rows.append({
            "Insumo": nombre,
            "Unidad": uni,
            "Cantidad": round(cant_total,2) if uni!="UND" else int(round(cant_total)),
            "P.V.P/Unit ($)": fmt_money(pvp),
            "Precio ($)": fmt_money(precio)
        })
    # Mano de obra
    mo_key = next((k for k in (f"M.O: {dis}", f"M.O. {dis}") if k in PRECIOS_MO), None)
    if mo_key and _safe_float(PRECIOS_MO[mo_key]["pvp"],0)>0:
        pvp_mo = _safe_float(PRECIOS_MO[mo_key]["pvp"],0)
        cant_mo = ancho*mult*n
        precio_mo = pvp_mo*cant_mo
        subtotal += precio_mo
        detalle_rows.append({
            "Insumo": mo_key,
            "Unidad": PRECIOS_MO[mo_key].get("unidad","MT"),
            "Cantidad": round(cant_mo,2),
            "P.V.P/Unit ($)": fmt_money(pvp_mo),
            "Precio ($)": fmt_money(precio_mo)
        })
    iva = subtotal*IVA_PERCENT
    total = subtotal
    return detalle_rows, subtotal, iva, total

# ---------- UI ----------
st.header("Configurar Cortina")
c1,c2,c3 = st.columns(3)
ancho = c1.number_input("Ancho de la Ventana (m)", min_value=0.1, value=2.0, step=0.1, key="ancho")
alto = c2.number_input("Alto de la Cortina (m)", min_value=0.1, value=2.0, step=0.1, key="alto")
cant = c3.number_input("Cantidad (und)", min_value=1, value=1, step=1, key="cantidad")

st.subheader("2. Selecciona el Diseño")
tipo_opts = list(TIPOS_CORTINA.keys())
tipo = st.selectbox("Tipo de Cortina", options=tipo_opts, key="tipo_cortina_sel")
disenos = TIPOS_CORTINA.get(tipo, [])
dis = st.selectbox("Diseño", options=disenos, key="diseno_sel")
mult_ini = float(TABLA_DISENOS.get(dis,2.0))
mult = st.number_input("Multiplicador", min_value=1.0, value=mult_ini, step=0.1, key="multiplicador")
st.number_input("Ancho Cortina (m)", value=float(ancho*mult), disabled=True, key="ancho_cortina_info")

st.subheader("3. Selecciona la(s) Tela(s)")
# TELA 1
ui_tela("1")
# TELA 2 según BOM
usa_tela2 = any(i["Insumo"].strip().upper()=="TELA 2" for i in BOM.get(dis,[]))
if usa_tela2:
    st.markdown("—")
    ui_tela("2")

st.subheader("4. Insumos según BOM")
items_sel = [it for it in BOM.get(dis,[]) if it["DependeDeSeleccion"]=="SI"]
if not items_sel:
    st.info("Este diseño no requiere insumos adicionales para seleccionar.")
else:
    for it in items_sel:
        nombre = it["Insumo"]
        with st.container(border=True):
            st.markdown(f"**Insumo:** {nombre}  •  **Unidad:** {it['Unidad']}")
            if nombre in CAT_INS:
                ui_insumo_catalogo(nombre, CAT_INS[nombre])
            else:
                st.warning(f"{nombre}: marcado como 'DependeDeSeleccion' pero no está en Catálogo de Insumos.")

# Calculate & show
if st.button("Calcular cotización"):
    det, sub, iva, total = calcular()
    st.session_state.cortina_calculada = {
        "diseno": dis, "multiplicador": mult, "ancho": ancho, "alto": alto,
        "cantidad": int(cant),
        "detalle_insumos": det,
        "subtotal": sub, "iva": iva, "total": total,
        "telas": {
            "tela1": {
                "referencia": st.session_state.get("ref_tela_sel_1",""),
                "color": st.session_state.get("color_tela_sel_1",""),
                "modo_confeccion": st.session_state.get("modo_conf_1","")
            },
            "tela2": {
                "referencia": st.session_state.get("ref_tela_sel_2",""),
                "color": st.session_state.get("color_tela_sel_2",""),
                "modo_confeccion": st.session_state.get("modo_conf_2","")
            } if usa_tela2 else None
        }
    }

if st.session_state.cortina_calculada:
    df = pd.DataFrame(st.session_state.cortina_calculada["detalle_insumos"])
    st.dataframe(df, use_container_width=True, hide_index=True)
    c1,c2,c3 = st.columns(3)
    c1.metric("Subtotal Cortina", fmt_money(st.session_state.cortina_calculada["subtotal"]))
    c2.metric("IVA Cortina", fmt_money(st.session_state.cortina_calculada["iva"]))
    c3.metric("Total Cortina", fmt_money(st.session_state.cortina_calculada["total"]))
    if st.button("Guardar cortina"):
        st.success("Cortina guardada en la cotización.")
