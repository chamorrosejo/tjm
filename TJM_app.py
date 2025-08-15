import os
import math
from datetime import datetime

import pandas as pd
import streamlit as st
from fpdf import FPDF

# =============== Utilidades ===============

def _fmt_money0(x: float) -> str:
    try:
        return f"${float(x):,.0f}"
    except Exception:
        # intenta limpiar texto tipo "$6,500"
        if isinstance(x, str):
            x2 = x.replace("$", "").replace(",", "").strip()
            try:
                return f"${float(x2):,.0f}"
            except Exception:
                return "$0"
        return "$0"

def _to_float(val, default=0.0) -> float:
    # convierte valores de entrada a número de manera robusta
    try:
        if val is None:
            return default
        if isinstance(val, float) and pd.isna(val):
            return default
        if isinstance(val, str):
            s = val.strip()
            if s == "" or s.lower() in ("nan", "none", "null"):
                return default
            # limpia "$" y separadores
            s = s.replace("$", "").replace(",", "")
            return float(s)
        return float(val)
    except Exception:
        return default

def ceil_to_even(x: float) -> int:
    n = math.ceil(x)
    return n if n % 2 == 0 else n + 1

# =============== Rutas (repo ./data) + overrides ===============
SCRIPT_DIR = os.path.dirname(__file__) if "__file__" in globals() else os.getcwd()

_default_designs = os.path.join(SCRIPT_DIR, "data", "disenos_cortina.xlsx")
_default_bom     = os.path.join(SCRIPT_DIR, "data", "bom.xlsx")
_default_cat_ins = os.path.join(SCRIPT_DIR, "data", "catalogo_insumos.xlsx")
_default_cat_tel = os.path.join(SCRIPT_DIR, "data", "catalogo_telas.xlsx")

DESIGNS_XLSX_PATH       = os.environ.get("DESIGNS_XLSX_PATH")        or st.secrets.get("DESIGNS_XLSX_PATH", _default_designs)
BOM_XLSX_PATH           = os.environ.get("BOM_XLSX_PATH")            or st.secrets.get("BOM_XLSX_PATH", _default_bom)
CATALOG_XLSX_PATH       = os.environ.get("CATALOG_XLSX_PATH")        or st.secrets.get("CATALOG_XLSX_PATH", _default_cat_ins)
CATALOG_TELAS_XLSX_PATH = os.environ.get("CATALOG_TELAS_XLSX_PATH")  or st.secrets.get("CATALOG_TELAS_XLSX_PATH", _default_cat_tel)

IVA_PERCENT = 0.19
DISTANCIA_BOTON_DEF  = 0.20
DISTANCIA_OJALES_DEF = 0.14
ALLOWED_RULES = {"MT_ANCHO_X_MULT", "UND_OJALES_PAR", "UND_BOTON_PAR", "FIJO"}

# =============== Carga de datos ===============

def load_designs(path: str):
    df = pd.read_excel(path, engine="openpyxl")
    required = ["Diseño", "Tipo", "Multiplicador", "PVP M.O."]
    falt = [c for c in required if c not in df.columns]
    if falt:
        st.error(f"Faltan columnas en disenos_cortina.xlsx: {falt}")
        st.stop()

    tabla_mult = {}
    tipos_dict = {}           # Tipo → [Diseños]
    mo_dict = {}              # "M.O: DISEÑO" → {"unidad": "MT", "pvp": ...}
    diseno_a_tipo = {}        # DISEÑO → [Tipos]

    for _, row in df.iterrows():
        dis = str(row["Diseño"]).strip()
        tipos = [t.strip() for t in str(row["Tipo"]).split(",") if str(t).strip()]
        mult = _to_float(row["Multiplicador"], 1.0)
        pvp_mo = _to_float(row["PVP M.O."], 0.0)

        tabla_mult[dis] = mult
        mo_dict[f"M.O: {dis}"] = {"unidad": "MT", "pvp": pvp_mo}
        diseno_a_tipo[dis] = []
        for t in tipos:
            tipos_dict.setdefault(t, [])
            if dis not in tipos_dict[t]:
                tipos_dict[t].append(dis)
            diseno_a_tipo[dis].append(t)

    return tabla_mult, tipos_dict, mo_dict, diseno_a_tipo, df

def load_bom(path: str):
    df = pd.read_excel(path, engine="openpyxl")
    required = ["Diseño", "Insumo", "Unidad", "ReglaCantidad", "Parametro", "DependeDeSeleccion", "Observaciones"]
    falt = [c for c in required if c not in df.columns]
    if falt:
        st.error(f"Faltan columnas en bom.xlsx: {falt}")
        st.stop()

    invalid = sorted(set(str(x).strip().upper() for x in df["ReglaCantidad"]) - ALLOWED_RULES)
    if invalid:
        st.error("Reglas no soportadas en el BOM: " + ", ".join(invalid))
        st.stop()

    bom = {}
    for _, row in df.iterrows():
        param_raw = row.get("Parametro", "")
        if pd.isna(param_raw) or (isinstance(param_raw, str) and param_raw.strip().lower() in ("", "nan", "none")):
            param = ""
        else:
            param = str(param_raw).strip()

        item = {
            "Insumo": str(row["Insumo"]).strip(),
            "Unidad": str(row["Unidad"]).strip().upper(),
            "ReglaCantidad": str(row["ReglaCantidad"]).strip().upper(),
            "Parametro": param,
            "DependeDeSeleccion": str(row["DependeDeSeleccion"]).strip().upper(),
            "Observaciones": "" if pd.isna(row.get("Observaciones", "")) else str(row.get("Observaciones", "")),
        }
        d = str(row["Diseño"]).strip()
        bom.setdefault(d, []).append(item)
    return bom, df

def load_catalog_insumos(path: str):
    if not os.path.exists(path):
        st.warning(f"No se encontró {path}. La app seguirá sin catálogo de insumos.")
        return {}
    df = pd.read_excel(path, engine="openpyxl")
    required = ["Insumo", "Unidad", "Ref", "Color", "PVP"]
    falt = [c for c in required if c not in df.columns]
    if falt:
        st.error(f"Faltan columnas en catalogo_insumos.xlsx: {falt}")
        st.stop()
    cat = {}
    for _, row in df.iterrows():
        ins = str(row["Insumo"]).strip()
        uni = str(row["Unidad"]).strip().upper()
        ref = str(row["Ref"]).strip()
        col = str(row["Color"]).strip()
        pvp = _to_float(row["PVP"], 0.0)
        cat.setdefault(ins, {"unidad": uni, "opciones": []})
        if not cat[ins].get("unidad"):
            cat[ins]["unidad"] = uni
        cat[ins]["opciones"].append({"ref": ref, "color": col, "pvp": pvp})
    return cat

def load_catalog_telas(path: str):
    if not os.path.exists(path):
        st.error(f"No se encontró {path} para el catálogo de telas.")
        st.stop()
    df = pd.read_excel(path, engine="openpyxl")
    required = ["TipoTela", "Referencia", "Color", "PVP/Metro ($)"]
    falt = [c for c in required if c not in df.columns]
    if falt:
        st.error(f"Faltan columnas en catalogo_telas.xlsx: {falt}")
        st.stop()

    # Estructura: {Tipo: {Referencia: [{"color":..., "pvp":...}, ...]}}
    telas = {}
    for _, row in df.iterrows():
        tipo = str(row["TipoTela"]).strip()
        ref  = str(row["Referencia"]).strip()
        col  = str(row["Color"]).strip()
        pvp  = _to_float(row["PVP/Metro ($)"], 0.0)
        telas.setdefault(tipo, {})
        telas[tipo].setdefault(ref, [])
        telas[tipo][ref].append({"color": col, "pvp": pvp})
    return telas

# =============== PDF (no cambiamos formato por ahora) ===============
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 20)
        self.set_text_color(0, 80, 180)
        self.cell(0, 10, 'Cotización', 0, 1, 'R')
        self.set_font('Arial', '', 10)
        self.set_text_color(128)
        self.cell(0, 5, f"Fecha: {datetime.now().strftime('%Y-%m-%d')}", 0, 1, 'R')
        self.cell(0, 5, f"Cotización #: {datetime.now().strftime('%Y%m%d%H%M')}", 0, 1, 'R')
        self.ln(10)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'R')

# =============== App ===============
st.set_page_config(page_title="Megatex Cotizador", layout="wide")

TABLA_DISENOS, TIPOS_CORTINA, PRECIOS_MO, DISENO_A_TIPO, DF_DES = load_designs(DESIGNS_XLSX_PATH)
BOM_DICT, DF_BOM = load_bom(BOM_XLSX_PATH)
CATALOGO_INSUMOS = load_catalog_insumos(CATALOG_XLSX_PATH)
CATALOGO_TELAS   = load_catalog_telas(CATALOG_TELAS_XLSX_PATH)

def init_state():
    ss = st.session_state
    ss.setdefault("pagina_actual", "cotizador")
    ss.setdefault("datos_cotizacion", {"cliente": {}, "vendedor": {}})
    ss.setdefault("cortinas_resumen", [])
    ss.setdefault("cortina_calculada", None)
    # default tipo cortina
    if "tipo_cortina_sel" not in ss:
        ss["tipo_cortina_sel"] = list(TIPOS_CORTINA.keys())[0]

def sidebar():
    with st.sidebar:
        st.title("Megatex Cotizador")
        st.caption(f"📄 Diseños: {DESIGNS_XLSX_PATH}")
        st.caption(f"📄 BOM: {BOM_XLSX_PATH}")
        st.caption(f"📄 Cat. insumos: {CATALOG_XLSX_PATH}")
        st.caption(f"📄 Cat. telas: {CATALOG_TELAS_XLSX_PATH}")
        if st.button("Recargar datos"):
            st.cache_data.clear(); st.cache_resource.clear(); st.rerun()
        st.divider()
        st.button("Crear Cotización", use_container_width=True, on_click=lambda: set_page("cotizador"))
        st.button("Datos de la Cotización", use_container_width=True, on_click=lambda: set_page("datos"))
        st.button("Ver Resumen Final", use_container_width=True, on_click=lambda: set_page("resumen"))

def set_page(name: str):
    st.session_state.pagina_actual = name
    st.experimental_rerun()

def pantalla_cotizador():
    st.header("Configurar Cortina")

    # =========== 1. Medidas ===========
    st.subheader("1. Medidas")
    c1, c2, c3 = st.columns(3)
    ancho = c1.number_input("Ancho de la Ventana (m)", min_value=0.1, value=2.0, step=0.1, key="ancho")
    alto  = c2.number_input("Alto de la Cortina (m)", min_value=0.1, value=2.0, step=0.1, key="alto")
    cant  = c3.number_input("Cantidad (und)", min_value=1, value=1, step=1, key="cantidad")

    st.markdown("---")

    # =========== 2. Diseño ===========
    st.subheader("2. Selecciona el Diseño")
    tipo_opts = list(TIPOS_CORTINA.keys())
    tipo_prev = st.session_state.get("tipo_cortina_sel", tipo_opts[0])
    tipo_sel  = st.selectbox("Tipo de Cortina", options=tipo_opts, index=tipo_opts.index(tipo_prev), key="tipo_cortina_sel")

    disenos = TIPOS_CORTINA.get(tipo_sel, [])
    if not disenos:
        st.error("No hay diseños para este tipo.")
        st.stop()

    dis_prev = st.session_state.get("diseno_sel", disenos[0])
    if dis_prev not in disenos:
        dis_prev = disenos[0]
    diseno_sel = st.selectbox("Diseño", options=disenos, index=disenos.index(dis_prev), key="diseno_sel")

    mult_default = float(TABLA_DISENOS.get(diseno_sel, 2.0))
    multiplicador = st.number_input("Multiplicador", min_value=1.0, step=0.1, value=mult_default, key="multiplicador")

    ancho_cortina = ancho * multiplicador
    st.number_input("Ancho Cortina (m)", value=float(ancho_cortina), step=0.1, disabled=True, key="ancho_cortina_info")

    st.markdown("---")

    # =========== 3. Telas ===========
    st.subheader("3. Selecciona la(s) Tela(s)")

    def ui_tela(prefijo: str):
        tipo_key  = f"tipo_tela_sel_{prefijo}"
        ref_key   = f"ref_tela_sel_{prefijo}"
        color_key = f"color_tela_sel_{prefijo}"
        pvp_num_key = f"pvp_tela_{prefijo}_num"   # numérico para cálculo
        modo_key  = f"modo_conf_{prefijo}"

        tipo = st.selectbox(f"Tipo de Tela {prefijo}", options=list(CATALOGO_TELAS.keys()), key=tipo_key)
        refs = sorted(CATALOGO_TELAS[tipo].keys())
        ref  = st.selectbox(f"Referencia {prefijo}", options=refs, key=ref_key)
        colores = sorted({x["color"] for x in CATALOGO_TELAS[tipo][ref]}) or ["No disponible"]
        color = st.selectbox(f"Color {prefijo}", options=colores, key=color_key)
        info = next((x for x in CATALOGO_TELAS[tipo][ref] if x["color"] == color), CATALOGO_TELAS[tipo][ref][0])
        # guardamos numérico, mostramos formateado
        st.session_state[pvp_num_key] = _to_float(info["pvp"], 0.0)
        st.number_input(f"PVP/Metro TELA {prefijo} ($)", value=float(info["pvp"]), disabled=True, key=f"pvp_tela_{prefijo}_show", format="%d")

        # Modo de confección (solo informativo)
        st.radio(f"Modo de confección {prefijo}", options=["Entera", "Partida", "Semipartida"], horizontal=True, key=modo_key)

    items_d = BOM_DICT.get(diseno_sel, [])
    usa_tela2 = any(i["Insumo"].strip().upper() == "TELA 2" for i in items_d)

    ui_tela("1")
    if usa_tela2:
        st.markdown("—")
        ui_tela("2")

    st.markdown("---")

    # =========== 4. Insumos que dependen de selección ===========
    st.subheader("4. Insumos según BOM")
    items_si = [it for it in items_d if it["DependeDeSeleccion"] == "SI"]
    if not items_si:
        st.info("Este diseño no requiere insumos adicionales para seleccionar.")
    else:
        for item in items_si:
            nombre = item["Insumo"]
            unidad = item["Unidad"]
            with st.container(border=True):
                st.markdown(f"**Insumo:** {nombre}  •  **Unidad:** {unidad}")
                if nombre in CATALOGO_INSUMOS:
                    cat = CATALOGO_INSUMOS[nombre]
                    refs = sorted({opt["ref"] for opt in cat["opciones"]})
                    ref_key = f"ref_{nombre}"
                    color_key = f"color_{nombre}"
                    ref_sel = st.selectbox(f"Referencia {nombre}", options=refs, key=ref_key)
                    colores = sorted({opt["color"] for opt in cat["opciones"] if opt.get("ref") == ref_sel}) or ["No disponible"]
                    color_sel = st.selectbox(f"Color {nombre}", options=colores, key=color_key)
                    info = next((opt for opt in cat["opciones"] if opt["ref"] == ref_sel and opt["color"] == color_sel), None)
                    pvp_num = _to_float(info["pvp"], 0.0) if info else 0.0
                    st.number_input(f"P.V.P {nombre} ({cat['unidad']})", value=float(pvp_num), disabled=True, key=f"pvp_{nombre}_show", format="%d")
                    st.session_state.setdefault("insumos_seleccion", {})
                    st.session_state.insumos_seleccion[nombre] = {"ref": ref_sel, "color": color_sel, "pvp": pvp_num, "unidad": cat["unidad"]}
                else:
                    st.warning(f"{nombre}: marcado como 'DependeDeSeleccion' pero no está en CATALOGO_INSUMOS.")

    # Botón calcular (rojo)
    st.markdown("""
        <style>
        div.stButton > button.kirby-red {background-color:#d11a2a; color:white; border:0; }
        div.stButton > button.kirby-red:hover {filter: brightness(0.95);}
        </style>
    """, unsafe_allow_html=True)

    if st.button("Calcular cotización", key="calc_btn", type="primary", help="Calcula totales", use_container_width=False):
        calcular_y_mostrar_cotizacion()

    # Mostrar resultado si existe
    if st.session_state.get("cortina_calculada"):
        st.success("Cálculo realizado. Revisa los detalles a continuación.")
        df = pd.DataFrame(st.session_state.cortina_calculada["detalle_insumos"])
        # formateo visual $ sin decimales
        if not df.empty:
            if "P.V.P/Unit ($)" in df.columns:
                df["P.V.P/Unit ($)"] = df["P.V.P/Unit ($)"].apply(_fmt_money0)
            if "Precio ($)" in df.columns:
                df["Precio ($)"] = df["Precio ($)"].apply(_fmt_money0)
        st.dataframe(df, use_container_width=True, hide_index=True)

        c1, c2, c3 = st.columns(3)
        c1.metric("Subtotal Cortina", _fmt_money0(st.session_state.cortina_calculada["subtotal"]))
        c2.metric("IVA Cortina", _fmt_money0(st.session_state.cortina_calculada["iva"]))
        c3.metric("Total Cortina", _fmt_money0(st.session_state.cortina_calculada["total"]))

        # Botón Guardar (rojo)
        if st.button("Guardar cortina", key="save_btn"):
            st.session_state.cortinas_resumen.append(st.session_state.cortina_calculada.copy())
            st.success("✅ Cortina guardada en la cotización. Ve a 'Ver Resumen Final' para verla en el listado.")

def calcular_y_mostrar_cotizacion():
    d = st.session_state.diseno_sel
    ancho = _to_float(st.session_state.ancho, 0.0)
    alto  = _to_float(st.session_state.alto, 0.0)
    mult  = _to_float(st.session_state.multiplicador, 1.0)
    n     = int(st.session_state.cantidad)

    detalle = []
    subtotal = 0.0

    for it in BOM_DICT.get(d, []):
        nombre = it["Insumo"].strip().upper()
        unidad = it["Unidad"].upper()
        regla  = it["ReglaCantidad"].upper()
        param  = it["Parametro"]

        # cantidad por cortina
        if regla == "MT_ANCHO_X_MULT":
            factor = _to_float(param, 1.0)
            cantidad = ancho * mult * factor
        elif regla == "UND_OJALES_PAR":
            paso = _to_float(param, DISTANCIA_OJALES_DEF)
            cantidad = ceil_to_even((ancho * mult) / paso)
        elif regla == "UND_BOTON_PAR":
            paso = _to_float(param, DISTANCIA_BOTON_DEF)
            cantidad = ceil_to_even((ancho * mult) / paso)
        elif regla == "FIJO":
            cantidad = _to_float(param, 0.0)
        else:
            st.error(f"ReglaCantidad no soportada: {regla}")
            st.stop()

        cant_total = cantidad * n

        # PVP
        if nombre == "TELA 1":
            pvp = _to_float(st.session_state.get("pvp_tela_1_num"), 0.0)
            ref = st.session_state.get("ref_tela_sel_1", "")
            col = st.session_state.get("color_tela_sel_1", "")
            nombre_mostrar = f"TELA 1: {ref} – {col}"
            uni = "MT"
        elif nombre == "TELA 2":
            pvp = _to_float(st.session_state.get("pvp_tela_2_num"), 0.0)
            ref = st.session_state.get("ref_tela_sel_2", "")
            col = st.session_state.get("color_tela_sel_2", "")
            nombre_mostrar = f"TELA 2: {ref} – {col}"
            uni = "MT"
        elif nombre.startswith("M.O"):
            # M.O. va como línea aparte al final (para no duplicar)
            continue
        else:
            sel = st.session_state.get("insumos_seleccion", {}).get(it["Insumo"], {})
            pvp = _to_float(sel.get("pvp"), 0.0)
            uni = sel.get("unidad", unidad)
            nombre_mostrar = it["Insumo"]

        total_item = pvp * cant_total
        subtotal += total_item
        detalle.append({
            "Insumo": nombre_mostrar,
            "Unidad": uni,
            "Cantidad": round(cant_total, 2) if uni != "UND" else int(round(cant_total)),
            "P.V.P/Unit ($)": pvp,
            "Precio ($)": round(total_item, 2),
        })

    # Mano de Obra (línea independiente)
    mo_key = next((k for k in (f"M.O: {d}", f"M.O. {d}") if k in PRECIOS_MO), None)
    if mo_key and _to_float(PRECIOS_MO[mo_key]["pvp"], 0) > 0:
        cant_mo = ancho * mult * n
        pvp_mo = _to_float(PRECIOS_MO[mo_key]["pvp"], 0.0)
        precio_mo = round(cant_mo * pvp_mo, 2)
        subtotal += precio_mo
        detalle.append({
            "Insumo": mo_key,
            "Unidad": PRECIOS_MO[mo_key].get("unidad", "MT"),
            "Cantidad": round(cant_mo, 2),
            "P.V.P/Unit ($)": pvp_mo,
            "Precio ($)": precio_mo,
        })

    iva = round(subtotal * IVA_PERCENT, 2)
    total = round(subtotal, 2)
    subtotal_sin_iva = round(total - iva, 2)

    # Adjuntar info de telas (con modo de confección)
    telas_info = {
        "tela1": {
            "tipo": st.session_state.get("tipo_tela_sel_1", ""),
            "referencia": st.session_state.get("ref_tela_sel_1", ""),
            "color": st.session_state.get("color_tela_sel_1", ""),
            "modo_confeccion": st.session_state.get("modo_conf_1", ""),
        }
    }
    if st.session_state.get("pvp_tela_2_num") is not None:
        telas_info["tela2"] = {
            "tipo": st.session_state.get("tipo_tela_sel_2", ""),
            "referencia": st.session_state.get("ref_tela_sel_2", ""),
            "color": st.session_state.get("color_tela_sel_2", ""),
            "modo_confeccion": st.session_state.get("modo_conf_2", ""),
        }
    else:
        telas_info["tela2"] = None

    st.session_state.cortina_calculada = {
        "tipo": st.session_state.tipo_cortina_sel,
        "diseno": d, "multiplicador": mult, "ancho": ancho, "alto": alto,
        "cantidad": n,
        "telas": telas_info,
        "detalle_insumos": detalle,
        "subtotal": subtotal_sin_iva, "iva": iva, "total": total
    }

def pantalla_datos():
    st.header("Datos de la Cotización")
    with st.expander("Datos del Cliente", expanded=True):
        cliente = st.session_state.datos_cotizacion["cliente"]
        cliente["nombre"]    = st.text_input("Nombre:", value=cliente.get("nombre", ""))
        c1, c2 = st.columns(2)
        cliente["cedula"]    = c1.text_input("Cédula/NIT:", value=cliente.get("cedula", ""))
        cliente["telefono"]  = c2.text_input("Teléfono:", value=cliente.get("telefono", ""))
        cliente["direccion"] = st.text_input("Dirección:", value=cliente.get("direccion", ""))
        cliente["correo"]    = st.text_input("Correo:", value=cliente.get("correo", ""))

    with st.expander("Datos del Vendedor", expanded=True):
        vendedor = st.session_state.datos_cotizacion["vendedor"]
        vendedor["nombre"]   = st.text_input("Nombre Vendedor:", value=vendedor.get("nombre", ""))
        vendedor["telefono"] = st.text_input("Teléfono Vendedor:", value=vendedor.get("telefono", ""))

def pantalla_resumen():
    st.header("Resumen de la Cotización")
    items = st.session_state.cortinas_resumen
    if not items:
        st.info("Aún no has añadido ninguna cortina a la cotización.")
        return

    for i, c in enumerate(items, start=1):
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([0.6, 2.6, 3.0, 1.2])
            # 1) índice
            col1.markdown(f"**{i}**")
            # 2) diseño + bullets de insumos
            col2.markdown(f"**{c['diseno']}**")
            bullets = []
            # Telas (si existen, con [modo])
            t1 = c.get("telas", {}).get("tela1")
            if t1:
                modo = f" [{t1.get('modo_confeccion','')}]" if t1.get("modo_confeccion") else ""
                # buscar cantidad de TELA 1 en detalle
                cant_t1 = next((x["Cantidad"] for x in c["detalle_insumos"] if x["Insumo"].startswith("TELA 1")), None)
                bullets.append(f"- **TELA 1:** {t1.get('referencia','')} – {t1.get('color','')}{modo} — {cant_t1} MT")
            t2 = c.get("telas", {}).get("tela2")
            if t2:
                modo = f" [{t2.get('modo_confeccion','')}]" if t2.get("modo_confeccion") else ""
                cant_t2 = next((x["Cantidad"] for x in c["detalle_insumos"] if x["Insumo"].startswith("TELA 2")), None)
                bullets.append(f"- **TELA 2:** {t2.get('referencia','')} – {t2.get('color','')}{modo} — {cant_t2} MT")
            # Otros insumos (incluye M.O.)
            for it in c["detalle_insumos"]:
                if it["Insumo"].startswith("TELA"):
                    continue
                bullets.append(f"- **{it['Insumo']}** — {it['Cantidad']} {it['Unidad']}")
            if bullets:
                col2.markdown("\n".join(bullets))
            # 3) dimensiones + cantidad
            col3.write(f"Dimensiones: {c['ancho'] * c['multiplicador']:.2f} × {c['alto']:.2f} m • Cant: {c['cantidad']}")
            # 4) total
            col4.markdown(f"**{_fmt_money0(c['total'])}**")

    total_final = sum(x["total"] for x in items)
    iva = total_final * IVA_PERCENT
    subtotal = total_final - iva
    st.markdown("---")
    a, b, c = st.columns(3)
    a.metric("Subtotal", _fmt_money0(subtotal))
    b.metric(f"IVA ({int(IVA_PERCENT*100)}%)", _fmt_money0(iva))
    c.metric("Total Cotización", _fmt_money0(total_final))

# =============== Router principal ===============
def main():
    init_state()
    sidebar()
    page = st.session_state.get("pagina_actual", "cotizador")
    if page == "datos":
        pantalla_datos()
    elif page == "resumen":
        pantalla_resumen()
    else:
        pantalla_cotizador()

if __name__ == "__main__":
    main()
