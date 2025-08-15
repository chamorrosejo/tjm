
import streamlit as st
import pandas as pd
import os
from fpdf import FPDF
from datetime import datetime
import math

# =======================
# Helpers
# =======================
def _safe_float(val, default=0.0):
    try:
        if val is None:
            return default
        if isinstance(val, float) and (pd.isna(val)):
            return default
        if isinstance(val, str) and val.strip().lower() in ("", "nan", "none"):
            return default
        return float(val)
    except Exception:
        return default

def ceil_to_even(x: float) -> int:
    n = math.ceil(x)
    return n if n % 2 == 0 else n + 1

def money(n: float) -> str:
    try:
        return f"${int(round(float(n))):,}".replace(",", ".") if False else f"${int(round(float(n))):,}"
    except Exception:
        return "$0"

# =======================
# Paths & constants
# =======================
SCRIPT_DIR = os.path.dirname(__file__) if "__file__" in globals() else os.getcwd()

_default_designs = os.path.join(SCRIPT_DIR, "data", "disenos_cortina.xlsx")
_default_bom     = os.path.join(SCRIPT_DIR, "data", "bom.xlsx")
_default_cat_ins = os.path.join(SCRIPT_DIR, "data", "catalogo_insumos.xlsx")
_default_cat_tel = os.path.join(SCRIPT_DIR, "data", "catalogo_telas.xlsx")

DESIGNS_XLSX_PATH       = os.environ.get("DESIGNS_XLSX_PATH")       or st.secrets.get("DESIGNS_XLSX_PATH", _default_designs)
BOM_XLSX_PATH           = os.environ.get("BOM_XLSX_PATH")           or st.secrets.get("BOM_XLSX_PATH", _default_bom)
CATALOG_XLSX_PATH       = os.environ.get("CATALOG_XLSX_PATH")       or st.secrets.get("CATALOG_XLSX_PATH", _default_cat_ins)
CATALOG_TELAS_XLSX_PATH = os.environ.get("CATALOG_TELAS_XLSX_PATH") or st.secrets.get("CATALOG_TELAS_XLSX_PATH", _default_cat_tel)

REQUIRED_DESIGNS_COLS = ["Diseño", "Tipo", "Multiplicador", "PVP M.O."]
REQUIRED_BOM_COLS     = ["Diseño", "Insumo", "Unidad", "ReglaCantidad", "Parametro", "DependeDeSeleccion", "Observaciones"]
REQUIRED_CAT_COLS     = ["Insumo", "Unidad", "Ref", "Color", "PVP"]
REQUIRED_TELAS_COLS   = ["TipoTela", "Referencia", "Color", "PVP/Metro ($)"]

ALLOWED_RULES = {"MT_ANCHO_X_MULT", "UND_OJALES_PAR", "UND_BOTON_PAR", "FIJO"}

IVA_PERCENT = 0.19
DISTANCIA_BOTON_DEF = 0.20
DISTANCIA_OJALES_DEF = 0.14

# =======================
# Loading
# =======================
def load_designs_from_excel(path: str):
    if not os.path.exists(path):
        st.error(f"No se encontró el archivo Excel de Diseños en: {path}")
        st.stop()
    df = pd.read_excel(path, engine="openpyxl")
    faltantes = [c for c in REQUIRED_DESIGNS_COLS if c not in df.columns]
    if faltantes:
        st.error(f"El Excel de Diseños debe tener columnas: {REQUIRED_DESIGNS_COLS}. Encontradas: {list(df.columns)}")
        st.stop()

    tabla_disenos = {}
    tipos_cortina = {}
    precios_mo = {}
    disenos_a_tipos = {}

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
            if dis not in tipos_cortina[t]:
                tipos_cortina[t].append(dis)
            if t not in disenos_a_tipos[dis]:
                disenos_a_tipos[dis].append(t)

    return tabla_disenos, tipos_cortina, precios_mo, disenos_a_tipos, df

def load_bom_from_excel(path: str):
    if not os.path.exists(path):
        st.error(f"No se encontró el archivo Excel de BOM en: {path}")
        st.stop()
    df = pd.read_excel(path, engine="openpyxl")
    faltantes = [c for c in REQUIRED_BOM_COLS if c not in df.columns]
    if faltantes:
        st.error(f"El Excel de BOM debe tener columnas: {REQUIRED_BOM_COLS}. Encontradas: {list(df.columns)}")
        st.stop()

    reglas_invalidas = sorted(set(str(x).strip().upper() for x in df["ReglaCantidad"]) - ALLOWED_RULES)
    if reglas_invalidas:
        st.error("Reglas no soportadas en 'ReglaCantidad': " + ", ".join(reglas_invalidas))
        st.stop()

    bom_dict = {}
    for _, row in df.iterrows():
        p_raw = row.get("Parametro", "")
        if pd.isna(p_raw) or (isinstance(p_raw, str) and p_raw.strip().lower() in ("", "nan", "none")):
            param_norm = ""
        else:
            param_norm = str(p_raw).strip()

        item = {
            "Insumo": str(row["Insumo"]).strip(),
            "Unidad": str(row["Unidad"]).strip().upper(),
            "ReglaCantidad": str(row["ReglaCantidad"]).strip().upper(),
            "Parametro": param_norm,
            "DependeDeSeleccion": str(row["DependeDeSeleccion"]).strip().upper(),
            "Observaciones": "" if pd.isna(row.get("Observaciones", "")) else str(row.get("Observaciones", "")),
        }
        dis = str(row["Diseño"]).strip()
        bom_dict.setdefault(dis, []).append(item)
    return bom_dict, df

def load_catalog_from_excel(path: str):
    if not os.path.exists(path):
        return {}
    df = pd.read_excel(path, engine="openpyxl")
    faltantes = [c for c in REQUIRED_CAT_COLS if c not in df.columns]
    if faltantes:
        st.error(f"El catálogo de insumos debe tener columnas: {REQUIRED_CAT_COLS}. Encontradas: {list(df.columns)}")
        st.stop()

    catalog = {}
    for _, row in df.iterrows():
        insumo = str(row["Insumo"]).strip()
        unidad = str(row["Unidad"]).strip().upper()
        ref = str(row["Ref"]).strip()
        color = str(row["Color"]).strip()
        pvp = _safe_float(row["PVP"], 0.0)
        catalog.setdefault(insumo, {"unidad": unidad, "opciones": []})
        if not catalog[insumo].get("unidad"):
            catalog[insumo]["unidad"] = unidad
        catalog[insumo]["opciones"].append({"ref": ref, "color": color, "pvp": pvp})
    return catalog

def load_telas_from_excel(path: str):
    if not os.path.exists(path):
        st.error(f"No se encontró el catálogo de telas en: {path}")
        st.stop()
    df = pd.read_excel(path, engine="openpyxl")
    faltantes = [c for c in REQUIRED_TELAS_COLS if c not in df.columns]
    if faltantes:
        st.error(f"El catálogo de telas debe tener columnas: {REQUIRED_TELAS_COLS}. Encontradas: {list(df.columns)}")
        st.stop()

    telas = {}  # {TipoTela: {Referencia: [{"color":..., "pvp":...}, ...]}}
    for _, row in df.iterrows():
        tipo = str(row["TipoTela"]).strip()
        ref = str(row["Referencia"]).strip()
        color = str(row["Color"]).strip()
        pvp = _safe_float(row["PVP/Metro ($)"], 0.0)
        telas.setdefault(tipo, {})
        telas[tipo].setdefault(ref, [])
        telas[tipo][ref].append({"color": color, "pvp": pvp})
    return telas

# =======================
# App state & UI
# =======================
st.set_page_config(page_title="Megatex Cotizador", page_icon="🧵", layout="wide")

# CSS botones rojos
st.markdown("""
<style>
div.stButton > button:first-child {
  background-color: #d92828 !important;
  color: white !important;
  border: 0;
}
</style>
""", unsafe_allow_html=True)

TABLA_DISENOS, TIPOS_CORTINA, PRECIOS_MANO_DE_OBRA, DISENOS_A_TIPOS, DF_DISENOS = load_designs_from_excel(DESIGNS_XLSX_PATH)
BOM_DICT, DF_BOM = load_bom_from_excel(BOM_XLSX_PATH)
CATALOGO_INSUMOS = load_catalog_from_excel(CATALOG_XLSX_PATH)
CATALOGO_TELAS = load_telas_from_excel(CATALOG_TELAS_XLSX_PATH)

def init_state():
    if 'pagina_actual' not in st.session_state:
        st.session_state.pagina_actual = 'cotizador'
    if 'datos_cotizacion' not in st.session_state:
        st.session_state.datos_cotizacion = {"cliente": {}, "vendedor": {}}
    if 'cortinas_resumen' not in st.session_state:
        st.session_state.cortinas_resumen = []
    if 'cortina_calculada' not in st.session_state:
        st.session_state.cortina_calculada = None
    if 'tipo_cortina_sel' not in st.session_state:
        st.session_state.tipo_cortina_sel = list(TIPOS_CORTINA.keys())[0]

def sidebar():
    st.title("Megatex Cotizador")
    st.caption(f"Diseños: {DESIGNS_XLSX_PATH}")
    st.caption(f"BOM: {BOM_XLSX_PATH}")
    st.caption(f"Catálogo insumos: {CATALOG_XLSX_PATH or '—'}")
    st.caption(f"Catálogo telas: {CATALOG_TELAS_XLSX_PATH}")
    st.divider()
    if st.button("Crear Cotización", use_container_width=True):
        st.session_state.editando_index = None
        st.session_state.pagina_actual = 'cotizador'; st.rerun()
    if st.button("Datos de la Cotización", use_container_width=True):
        st.session_state.pagina_actual = 'datos'; st.rerun()
    if st.button("Ver Resumen Final", use_container_width=True):
        st.session_state.pagina_actual = 'resumen'; st.rerun()

def pantalla_cotizador():
    st.header("Configurar Cortina")
    st.subheader("1. Medidas")
    ancho = st.number_input("Ancho de la Ventana (m)", min_value=0.1, value=2.0, step=0.1, key="ancho")
    alto = st.number_input("Alto de la Cortina (m)", min_value=0.1, value=2.0, step=0.1, key="alto")
    cantidad_cortinas = st.number_input("Cantidad (und)", min_value=1, value=1, step=1, key="cantidad")
    st.markdown("---")
    st.subheader("2. Selecciona el Diseño")

    tipo_opciones = list(TIPOS_CORTINA.keys())
    tipo_default = st.session_state.get("tipo_cortina_sel", tipo_opciones[0])
    tipo_cortina_sel = st.selectbox("Tipo de Cortina", options=tipo_opciones, index=tipo_opciones.index(tipo_default), key="tipo_cortina_sel")

    disenos_disponibles = TIPOS_CORTINA.get(tipo_cortina_sel, [])
    if not disenos_disponibles:
        st.error("No hay diseños disponibles para el tipo seleccionado.")
        st.stop()

    diseno_previo = st.session_state.get("diseno_sel", disenos_disponibles[0])
    if diseno_previo not in disenos_disponibles:
        diseno_previo = disenos_disponibles[0]
    diseno_sel = st.selectbox("Diseño", options=disenos_disponibles, index=disenos_disponibles.index(diseno_previo), key="diseno_sel")

    valor_multiplicador = float(TABLA_DISENOS.get(diseno_sel, 2.0))
    multiplicador = st.number_input("Multiplicador", min_value=1.0, value=valor_multiplicador, step=0.1, key="multiplicador")

    ancho_cortina = st.session_state.ancho * multiplicador
    st.number_input("Ancho Cortina (m)", value=float(ancho_cortina), step=0.1, disabled=True, key="ancho_cortina_info")

    st.markdown("---")
    st.subheader("3. Selecciona la(s) Tela(s)")

    def ui_tela(prefix: str):
        tipo_key = f"tipo_tela_sel_{prefix}"
        ref_key  = f"ref_tela_sel_{prefix}"
        color_key= f"color_tela_sel_{prefix}"
        pvp_key  = f"pvp_tela_{prefix}"
        modo_key = f"modo_conf_{prefix}"

        tipo = st.selectbox(f"Tipo de Tela {prefix}", options=list(CATALOGO_TELAS.keys()), key=tipo_key)
        referencias = list(CATALOGO_TELAS[tipo].keys())
        ref = st.selectbox(f"Referencia {prefix}", options=referencias, key=ref_key)
        colores = [x["color"] for x in CATALOGO_TELAS[tipo][ref]]
        color = st.selectbox(f"Color {prefix}", options=colores, key=color_key)
        info = next(x for x in CATALOGO_TELAS[tipo][ref] if x["color"] == color)
        st.text_input(f"PVP/Metro TELA {prefix}", value=money(info["pvp"]), disabled=True, key=pvp_key)

        # Modo de confección por tela
        st.radio(f"Modo de confección {prefix}", options=["Entera", "Partida", "Semipartida"], horizontal=True, key=modo_key)

    items_d = BOM_DICT.get(diseno_sel, [])
    usa_tela2 = any(i["Insumo"].strip().upper() == "TELA 2" for i in items_d)

    ui_tela("1")
    if usa_tela2:
        st.markdown("—")
        ui_tela("2")

    st.markdown("---")
    st.subheader("4. Insumos según BOM")
    mostrar_insumos_bom(diseno_sel)

    if st.button("Calcular cotización"):
        calcular_y_mostrar_cotizacion()

    if st.session_state.get('cortina_calculada'):
        st.success("Cálculo realizado. Revisa los detalles a continuación.")
        df_detalle = pd.DataFrame(st.session_state.cortina_calculada['detalle_insumos'])

        # Formateo $ en tabla
        if not df_detalle.empty:
            if "P.V.P/Unit ($)" in df_detalle.columns:
                df_detalle["P.V.P/Unit ($)"] = df_detalle["P.V.P/Unit ($)"].apply(money)
            if "Precio ($)" in df_detalle.columns:
                df_detalle["Precio ($)"] = df_detalle["Precio ($)"].apply(money)

        st.dataframe(df_detalle, use_container_width=True, hide_index=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Subtotal Cortina", money(st.session_state.cortina_calculada['subtotal']))
        c2.metric("IVA Cortina", money(st.session_state.cortina_calculada['iva']))
        c3.metric("Total Cortina", money(st.session_state.cortina_calculada['total']))

        if st.button("Guardar cortina"):
            # Guardar copia inmutable de la cortina
            st.session_state.cortinas_resumen.append(st.session_state.cortina_calculada.copy())
            st.success("✅ Cortina guardada en la cotización. Ve a 'Ver Resumen Final'.")

def mostrar_insumos_bom(diseno_sel: str):
    # Sólo mostrar los que requieren selección
    items = [it for it in BOM_DICT.get(diseno_sel, []) if it["DependeDeSeleccion"] == "SI"]
    if not items:
        st.info("Este diseño no requiere insumos adicionales para seleccionar.")
        return

    for item in items:
        nombre = item["Insumo"]
        unidad  = item["Unidad"]
        with st.container(border=True):
            st.markdown(f"**Insumo:** {nombre}  •  **Unidad:** {unidad}")
            if nombre in CATALOGO_INSUMOS:
                cat = CATALOGO_INSUMOS[nombre]
                refs = sorted({opt['ref'] for opt in cat['opciones']})
                ref_key = f"ref_{nombre}"
                color_key = f"color_{nombre}"
                ref_sel = st.selectbox(f"Referencia {nombre}", options=refs, key=ref_key)
                colores = sorted({opt['color'] for opt in cat['opciones'] if opt.get('ref') == ref_sel}) or ["No disponible"]
                color_sel = st.selectbox(f"Color {nombre}", options=colores, key=color_key)
                match = [opt for opt in cat['opciones'] if opt.get('ref') == ref_sel and opt.get('color') == color_sel]
                pvp_val = match[0]["pvp"] if match else 0.0
                st.text_input(f"P.V.P {nombre} ({cat['unidad']})", value=money(pvp_val), disabled=True, key=f"pvp_{nombre}")
                # Guardar selección
                st.session_state.setdefault("insumos_seleccion", {})
                st.session_state.insumos_seleccion[nombre] = {"ref": ref_sel, "color": color_sel, "pvp": pvp_val, "unidad": cat["unidad"]}
            else:
                st.warning(f"{nombre}: marcado como 'DependeDeSeleccion' pero no está en el Catálogo de Insumos.")

def calcular_y_mostrar_cotizacion():
    diseno = st.session_state.diseno_sel
    ancho = _safe_float(st.session_state.ancho, 0.0)
    alto = _safe_float(st.session_state.alto, 0.0)
    multiplicador = _safe_float(st.session_state.multiplicador, 1.0)
    num_cortinas = int(st.session_state.cantidad)

    detalle_insumos = []
    subtotal = 0.0

    # Recorrer TODOS los ítems del BOM (SI y NO) para cálculo
    for item in BOM_DICT.get(diseno, []):
        nombre = item["Insumo"].strip().upper()
        unidad = item["Unidad"].upper()
        regla  = item["ReglaCantidad"].upper()
        param  = item["Parametro"]

        # Cantidad por cortina
        if regla == "MT_ANCHO_X_MULT":
            factor = _safe_float(param, 1.0)
            cantidad = ancho * multiplicador * factor
        elif regla == "UND_OJALES_PAR":
            paso = _safe_float(param, DISTANCIA_OJALES_DEF)
            cantidad = ceil_to_even((ancho * multiplicador) / paso)
        elif regla == "UND_BOTON_PAR":
            paso = _safe_float(param, DISTANCIA_BOTON_DEF)
            cantidad = ceil_to_even((ancho * multiplicador) / paso)
        elif regla == "FIJO":
            cantidad = _safe_float(param, 0.0)
        else:
            st.error(f"ReglaCantidad '{regla}' no soportada.")
            st.stop()

        cantidad_total = cantidad * num_cortinas

        # PVP según insumo
        if nombre == "TELA 1":
            pvp = _safe_float(st.session_state.get("pvp_tela_1"), 0.0)
            ref = st.session_state.get("ref_tela_sel_1", "")
            color = st.session_state.get("color_tela_sel_1", "")
            nombre_mostrado = f"TELA 1: {ref} - {color}"
            uni = "MT"
        elif nombre == "TELA 2":
            pvp = _safe_float(st.session_state.get("pvp_tela_2"), 0.0)
            ref = st.session_state.get("ref_tela_sel_2", "")
            color = st.session_state.get("color_tela_sel_2", "")
            nombre_mostrado = f"TELA 2: {ref} - {color}"
            uni = "MT"
        elif nombre.startswith("M.O"):
            continue
        else:
            sel = st.session_state.get("insumos_seleccion", {}).get(item["Insumo"], {})
            pvp = _safe_float(sel.get("pvp"), 0.0)
            uni = sel.get("unidad", unidad)
            nombre_mostrado = item["Insumo"]

        precio_total = pvp * cantidad_total
        subtotal += precio_total

        detalle_insumos.append({
            "Insumo": nombre_mostrado,
            "Unidad": uni,
            "Cantidad": round(cantidad_total, 2) if uni != "UND" else int(round(cantidad_total)),
            "P.V.P/Unit ($)": pvp,
            "Precio ($)": round(precio_total, 2),
        })

    # Mano de Obra (línea independiente)
    mo_key_candidates = [f"M.O: {diseno}", f"M.O. {diseno}"]
    mo_info = None
    mo_key = None
    for k in mo_key_candidates:
        if k in PRECIOS_MANO_DE_OBRA:
            mo_key = k; mo_info = PRECIOS_MANO_DE_OBRA[k]; break
    if mo_info and _safe_float(mo_info.get("pvp"), 0) > 0:
        cant_mo = ancho * multiplicador * num_cortinas
        pvp_mo = _safe_float(mo_info["pvp"], 0.0)
        precio_mo = round(cant_mo * pvp_mo, 2)
        subtotal += precio_mo
        detalle_insumos.append({
            "Insumo": mo_key,
            "Unidad": mo_info.get("unidad", "MT"),
            "Cantidad": round(cant_mo, 2),
            "P.V.P/Unit ($)": pvp_mo,
            "Precio ($)": precio_mo,
        })

    iva = round(subtotal * IVA_PERCENT, 2)
    total = round(subtotal, 2)
    subtotal_sin_iva = round(total - iva, 2)

    tela_info = {
        "tela1": {
            "tipo": st.session_state.get("tipo_tela_sel_1", ""),
            "referencia": st.session_state.get("ref_tela_sel_1", ""),
            "color": st.session_state.get("color_tela_sel_1", ""),
            "pvp": _safe_float(st.session_state.get("pvp_tela_1"), 0.0),
            "modo_confeccion": st.session_state.get("modo_conf_1", ""),
        }
    }
    if st.session_state.get("pvp_tela_2") is not None:
        tela_info["tela2"] = {
            "tipo": st.session_state.get("tipo_tela_sel_2", ""),
            "referencia": st.session_state.get("ref_tela_sel_2", ""),
            "color": st.session_state.get("color_tela_sel_2", ""),
            "pvp": _safe_float(st.session_state.get("pvp_tela_2"), 0.0),
            "modo_confeccion": st.session_state.get("modo_conf_2", ""),
        }
    else:
        tela_info["tela2"] = None

    st.session_state.cortina_calculada = {
        "tipo": st.session_state.tipo_cortina_sel,
        "diseno": diseno, "multiplicador": multiplicador, "ancho": ancho, "alto": alto,
        "cantidad": num_cortinas,
        "telas": tela_info,
        "detalle_insumos": detalle_insumos, "subtotal": subtotal_sin_iva, "iva": iva, "total": total
    }

def pantalla_datos():
    st.header("Datos de la Cotización")
    with st.expander("Datos del Cliente", expanded=True):
        cliente = st.session_state.datos_cotizacion['cliente']
        cliente['nombre'] = st.text_input("Nombre:", value=cliente.get('nombre', ''))
        c1, c2 = st.columns(2)
        cliente['cedula'] = c1.text_input("Cédula/NIT:", value=cliente.get('cedula', ''))
        cliente['telefono'] = c2.text_input("Teléfono:", value=cliente.get('telefono', ''))
        cliente['direccion'] = st.text_input("Dirección:", value=cliente.get('direccion', ''))
        cliente['correo'] = st.text_input("Correo:", value=cliente.get('correo', ''))

    with st.expander("Datos del Vendedor", expanded=True):
        vendedor = st.session_state.datos_cotizacion['vendedor']
        vendedor['nombre'] = st.text_input("Nombre Vendedor:", value=vendedor.get('nombre', ''))
        vendedor['telefono'] = st.text_input("Teléfono Vendedor:", value=vendedor.get('telefono', ''))

def pantalla_resumen():
    st.header("Resumen de la Cotización")
    cliente = st.session_state.datos_cotizacion['cliente']
    vendedor = st.session_state.datos_cotizacion['vendedor']
    if any(cliente.values()) or any(vendedor.values()):
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Cliente")
            st.text(f"Nombre: {cliente.get('nombre', 'N/A')}")
            st.text(f"Teléfono: {cliente.get('telefono', 'N/A')}")
            st.text(f"Correo: {cliente.get('correo', 'N/A')}")
        with c2:
            st.subheader("Vendedor")
            st.text(f"Nombre: {vendedor.get('nombre', 'N/A')}")
            st.text(f"Teléfono: {vendedor.get('telefono', 'N/A')}")

    st.subheader("Productos Añadidos")
    if not st.session_state.cortinas_resumen:
        st.info("Aún no has añadido ninguna cortina a la cotización.")
    else:
        for i, cortina in enumerate(st.session_state.cortinas_resumen):
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([0.6, 3.0, 2.8, 1.2])
                c1.markdown(f"**{i+1}**")
                # Columna 2: diseño + bullets de insumos
                bullets = []
                # Enriquecer TELAS con [modo] si existe
                tela1_modo = cortina.get("telas", {}).get("tela1", {}).get("modo_confeccion", "")
                tela2_modo = cortina.get("telas", {}).get("tela2", {}).get("modo_confeccion", "") if cortina.get("telas", {}).get("tela2") else ""
                for item in cortina["detalle_insumos"]:
                    nombre = item["Insumo"]
                    cantidad = item["Cantidad"]
                    unidad = item["Unidad"]
                    if nombre.startswith("TELA 1:"):
                        suf = f" [{tela1_modo}]" if tela1_modo else ""
                        bullets.append(f"- **{nombre}**{suf} — {cantidad} {unidad}")
                    elif nombre.startswith("TELA 2:"):
                        suf = f" [{tela2_modo}]" if tela2_modo else ""
                        bullets.append(f"- **{nombre}**{suf} — {cantidad} {unidad}")
                    else:
                        bullets.append(f"- **{nombre}** — {cantidad} {unidad}")
                c2.markdown(f"**{cortina['diseno']}**\n\n" + ("\n".join(bullets) if bullets else ""))
                # Columna 3: dimensiones y cantidad
                c3.write(f"Dimensiones: {cortina['ancho'] * cortina['multiplicador']:.2f} × {cortina['alto']:.2f} m  •  Cant: {cortina['cantidad']}")
                # Columna 4: precio
                c4.markdown(f"**{money(cortina['total'])}**")

    total_final = sum(c['total'] for c in st.session_state.cortinas_resumen)
    iva = total_final * IVA_PERCENT
    subtotal = total_final - iva
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("Subtotal", money(subtotal))
    c2.metric(f"IVA ({IVA_PERCENT:.0%})", money(iva))
    c3.metric("Total Cotización", money(total_final))

# =======================
# MAIN
# =======================
def main():
    init_state()
    with st.sidebar:
        sidebar()
    page = st.session_state.pagina_actual
    if page == 'datos':
        pantalla_datos()
    elif page == 'resumen':
        pantalla_resumen()
    else:
        pantalla_cotizador()

if __name__ == "__main__":
    main()
