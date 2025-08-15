
import streamlit as st
import pandas as pd
import os
from fpdf import FPDF
from datetime import datetime
import math

# =========================================
# CONFIG
# =========================================
SCRIPT_DIR = os.path.dirname(__file__) if "__file__" in globals() else os.getcwd()

# Excel paths with optional overrides
_default_designs = os.path.join(SCRIPT_DIR, "data", "disenos_cortina.xlsx")
_default_bom     = os.path.join(SCRIPT_DIR, "data", "bom.xlsx")
_default_catalog = os.path.join(SCRIPT_DIR, "data", "catalogo_insumos.xlsx")

DESIGNS_XLSX_PATH = os.environ.get("DESIGNS_XLSX_PATH") or \
                    (st.secrets.get("DESIGNS_XLSX_PATH") if hasattr(st, "secrets") else None) or \
                    _default_designs

BOM_XLSX_PATH = os.environ.get("BOM_XLSX_PATH") or \
                (st.secrets.get("BOM_XLSX_PATH") if hasattr(st, "secrets") else None) or \
                _default_bom

CATALOG_XLSX_PATH = os.environ.get("CATALOG_XLSX_PATH") or \
                    (st.secrets.get("CATALOG_XLSX_PATH") if hasattr(st, "secrets") else None) or \
                    _default_catalog

# Required columns
REQUIRED_DESIGNS_COLS = ["Diseño", "Tipo", "Multiplicador", "PVP M.O."]
REQUIRED_BOM_COLS     = ["Diseño", "Insumo", "Unidad", "ReglaCantidad", "Parametro", "DependeDeSeleccion", "Observaciones"]
REQUIRED_CATALOG_COLS = ["Insumo", "Unidad", "Ref", "Color", "PVP"]  # Notas es opcional

# Allowed rules
ALLOWED_RULES = {"MT_ANCHO_X_MULT", "UND_OJALES_PAR", "UND_BOTON_PAR", "FIJO"}

# Constants
IVA_PERCENT = 0.19
DISTANCIA_BOTON_DEF = 0.20
DISTANCIA_OJALES_DEF = 0.14

# =========================================
# FABRIC CATALOG (telas) - Static for now
# =========================================
CATALOGO_TELAS = {
    "Loneta": {
        "NATALIA": [{"color": "MARFIL", "pvp": 38000}, {"color": "CAMEL", "pvp": 38000}, {"color": "PLATA", "pvp": 38000}],
        "FINESTRA": [{"color": "BLANCO", "pvp": 24000}, {"color": "MARFIL", "pvp": 24000}, {"color": "CREMA", "pvp": 24000}, {"color": "LINO", "pvp": 24000}, {"color": "TAUPE", "pvp": 24000}, {"color": "ROSA", "pvp": 24000}, {"color": "PLATA", "pvp": 24000}, {"color": "GRIS", "pvp": 24000}, {"color": "INDIGO", "pvp": 24000}]
    },
    "Velo": {
        "CALMA": [{"color": "MARFIL", "pvp": 44000}, {"color": "NUEZ", "pvp": 44000}, {"color": "CAMEL", "pvp": 44000}, {"color": "PLATA", "pvp": 44000}, {"color": "GRIS", "pvp": 44000}],
        "LINK": [{"color": "BLANCO", "pvp": 26000}, {"color": "MARFIL", "pvp": 26000}, {"color": "SAHARA", "pvp": 26000}, {"color": "CAMEL", "pvp": 26000}, {"color": "TAUPE", "pvp": 26000}, {"color": "PLATA", "pvp": 26000}, {"color": "ACERO", "pvp": 26000}, {"color": "INDIGO", "pvp": 26000}]
    },
    "Pesada": {
        "ECLYPSE": [{"color": "MARFIL", "pvp": 46000}, {"color": "CAPUCHINO", "pvp": 46000}, {"color": "HOJA SECA", "pvp": 46000}, {"color": "AZUL", "pvp": 46000}, {"color": "PLATA", "pvp": 46000}, {"color": "GRIS", "pvp": 46000}],
        "POLYJACQUARD BITONO BILBAO": [{"color": "BEIGE", "pvp": 24000}, {"color": "TABACO", "pvp": 24000}, {"color": "AZUL", "pvp": 24000}, {"color": "ROSA", "pvp": 24000}, {"color": "PLATA", "pvp": 24000}, {"color": "GRIS", "pvp": 24000}]
    },
    "Blackout": {
        "UNITY": [{"color": "BLANCO", "pvp": 1}, {"color": "MARFIL", "pvp": 1}, {"color": "PERLA", "pvp": 1}, {"color": "PLATA", "pvp": 1}, {"color": "TAUPE", "pvp": 1}, {"color": "INDIGO", "pvp": 1}],
        "QUANTUM": [{"color": "BLANCO", "pvp": 26000}, {"color": "MARFIL", "pvp": 26000}, {"color": "PERLA", "pvp": 26000}, {"color": "PLATA", "pvp": 26000}, {"color": "TAUPE", "pvp": 26000}, {"color": "INDIGO", "pvp": 26000}],
        "OCASO": [{"color": "MARFIL", "pvp": 1}, {"color": "CAMEL", "pvp": 1}, {"color": "TAUPE", "pvp": 1}, {"color": "PLATA", "pvp": 1}, {"color": "AZUL", "pvp": 1}],
        "FLAT": [{"color": "BLANCO", "pvp": 1}, {"color": "MARFIL", "pvp": 1}, {"color": "BEIGE", "pvp": 1}, {"color": "TAUPE", "pvp": 1}, {"color": "CAMEL", "pvp": 1}, {"color": "PLATA", "pvp": 1}]
    }
}

# =========================================
# UTILS
# =========================================
def ceil_to_even(x: float) -> int:
    n = math.ceil(x)
    return n if n % 2 == 0 else n + 1

def load_designs_from_excel(path: str):
    if not os.path.exists(path):
        st.error(f"No se encontró el archivo Excel de Diseños en: {path}")
        st.stop()
    try:
        df = pd.read_excel(path, engine="openpyxl")
    except Exception as e:
        st.error(f"No se pudo leer el Excel de Diseños: {e}")
        st.stop()

    faltantes = [c for c in REQUIRED_DESIGNS_COLS if c not in df.columns]
    if faltantes:
        st.error(
            "El Excel de Diseños debe tener exactamente estas columnas:\n"
            + "\n".join(f"- {c}" for c in REQUIRED_DESIGNS_COLS)
            + f"\n\nColumnas encontradas: {list(df.columns)}"
        )
        st.stop()

    tabla_disenos = {}
    tipos_cortina = {}
    precios_mo = {}
    disenos_a_tipos = {}

    for _, row in df.iterrows():
        dis = str(row["Diseño"]).strip()
        tipos = [t.strip() for t in str(row["Tipo"]).split(",") if t and str(t).strip()]
        try:
            mult = float(row["Multiplicador"])
        except Exception:
            st.error(f"Multiplicador inválido para el diseño '{dis}'.")
            st.stop()
        try:
            mo_val = float(row["PVP M.O."])
        except Exception:
            st.error(f"PVP M.O. inválido para el diseño '{dis}'.")
            st.stop()

        tabla_disenos[dis] = mult
        precios_mo[f"M.O. {dis}"] = {"unidad": "MT", "pvp": mo_val}  # nombre MO con "M.O. <Diseño>"
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
    try:
        df = pd.read_excel(path, engine="openpyxl")
    except Exception as e:
        st.error(f"No se pudo leer el Excel de BOM: {e}")
        st.stop()

    faltantes = [c for c in REQUIRED_BOM_COLS if c not in df.columns]
    if faltantes:
        st.error(
            "El Excel de BOM debe tener exactamente estas columnas:\n"
            + "\n".join(f"- {c}" for c in REQUIRED_BOM_COLS)
            + f"\n\nColumnas encontradas: {list(df.columns)}"
        )
        st.stop()

    reglas_invalidas = sorted(set(df["ReglaCantidad"].astype(str)) - ALLOWED_RULES)
    if reglas_invalidas:
        st.error("Se encontraron valores no soportados en 'ReglaCantidad'. "
                 "Permitidas: MT_ANCHO_X_MULT, UND_OJALES_PAR, UND_BOTON_PAR, FIJO.\n"
                 f"Inválidas: {reglas_invalidas}")
        st.stop()

    bom_dict = {}
    for _, row in df.iterrows():
        dis = str(row["Diseño"]).strip()
        item = {
            "Insumo": str(row["Insumo"]).strip(),
            "Unidad": str(row["Unidad"]).strip().upper(),
            "ReglaCantidad": str(row["ReglaCantidad"]).strip().upper(),
            "Parametro": ("" if pd.isna(row["Parametro"]) else str(row["Parametro"]).strip()),
            "DependeDeSeleccion": str(row["DependeDeSeleccion"]).strip().upper() if not pd.isna(row["DependeDeSeleccion"]) else "NO",
            "Observaciones": "" if pd.isna(row["Observaciones"]) else str(row["Observaciones"]).strip(),
        }
        bom_dict.setdefault(dis, []).append(item)
    return bom_dict, df

def load_catalog_from_excel(path: str):
    if not os.path.exists(path):
        # If missing, fallback to empty
        return {}
    try:
        df = pd.read_excel(path, engine="openpyxl")
    except Exception as e:
        st.error(f"No se pudo leer el Excel de Catálogo: {e}")
        st.stop()
    faltantes = [c for c in REQUIRED_CATALOG_COLS if c not in df.columns]
    if faltantes:
        st.error("El Excel de Catálogo de Insumos debe tener columnas: "
                 + ", ".join(REQUIRED_CATALOG_COLS))
        st.stop()
    # Build structure: name -> {"unidad": unit, "opciones": [ {ref,color,pvp} ]}
    catalog = {}
    for _, row in df.iterrows():
        ins = str(row["Insumo"]).strip()
        uni = str(row["Unidad"]).strip().upper()
        ref = "" if pd.isna(row["Ref"]) else str(row["Ref"]).strip()
        color = "" if pd.isna(row["Color"]) else str(row["Color"]).strip()
        try:
            pvp = float(row["PVP"])
        except Exception:
            pvp = 0.0
        catalog.setdefault(ins, {"unidad": uni, "opciones": []})
        catalog[ins]["opciones"].append({"ref": ref, "color": color, "pvp": pvp})
        # keep unidad consistent
        catalog[ins]["unidad"] = uni
    return catalog

# =========================================
# LOAD
# =========================================
st.set_page_config(page_title="Megatex Cotizador", page_icon="Megatex.png", layout="wide")

TABLA_DISENOS, TIPOS_CORTINA, PRECIOS_MANO_DE_OBRA, DISENOS_A_TIPOS, DF_DISENOS = load_designs_from_excel(DESIGNS_XLSX_PATH)
BOM_DICT, DF_BOM = load_bom_from_excel(BOM_XLSX_PATH)
CATALOGO_INSUMOS = load_catalog_from_excel(CATALOG_XLSX_PATH)

# =========================================
# UI helpers
# =========================================
def sidebar():
    with st.sidebar:
        st.title("Megatex Cotizador")
        st.caption(f"Diseños: {DESIGNS_XLSX_PATH}")
        st.caption(f"BOM: {BOM_XLSX_PATH}")
        st.caption(f"Catálogo insumos: {CATALOG_XLSX_PATH}")
        if st.button("Recargar datos"):
            st.cache_data.clear(); st.cache_resource.clear(); st.rerun()
        st.markdown("---")
        if st.button("Crear Cotización", use_container_width=True):
            st.session_state.pagina_actual = 'cotizador'; st.rerun()
        if st.button("Datos de la Cotización", use_container_width=True):
            st.session_state.pagina_actual = 'datos'; st.rerun()
        if st.button("Ver Resumen Final", use_container_width=True):
            st.session_state.pagina_actual = 'resumen'; st.rerun()

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

# =========================================
# PDF (unchanged minimal)
# =========================================
class PDF(FPDF):
    def header(self):
        try:
            logo_path = os.path.join(SCRIPT_DIR, "Megatex.png")
            self.image(logo_path, 10, 8, 33)
        except Exception:
            pass
        self.set_font('Arial', 'B', 20)
        self.set_text_color(0, 80, 180)
        self.cell(0, 10, 'Cotización', 0, 1, 'R')
        self.set_font('Arial', '', 10)
        self.set_text_color(128)
        self.cell(0, 5, f"Fecha: {datetime.now().strftime('%Y-%m-%d')}", 0, 1, 'R')
        self.cell(0, 5, f"Cotización #: {datetime.now().strftime('%Y%m%d%H%M')}", 0, 1, 'R')
        self.ln(10)

# =========================================
# PAGES
# =========================================
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
    st.subheader("Productos Añadidos")
    if not st.session_state.cortinas_resumen:
        st.info("Aún no has añadido ninguna cortina a la cotización.")
    else:
        for i, cortina in enumerate(st.session_state.cortinas_resumen):
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([0.6, 2.2, 3.2, 1])
                c1.markdown(f"**{i+1}**")
                c2.markdown(f"**{cortina['diseno']}**")
                c3.write(f"Dimensiones: {cortina['ancho'] * cortina['multiplicador']:.2f} × {cortina['alto']:.2f} m  •  Cant: {cortina['cantidad']}")
                c4.markdown(f"**${cortina['total']:,.2f}**")

    total_final = sum(c['total'] for c in st.session_state.cortinas_resumen)
    iva = total_final * IVA_PERCENT
    subtotal = total_final - iva
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("Subtotal", f"${subtotal:,.2f}")
    c2.metric(f"IVA ({IVA_PERCENT:.0%})", f"${iva:,.2f}")
    c3.metric("Total Cotización", f"${total_final:,.2f}")

def pantalla_cotizador():
    st.header("Configurar Cortina")
    st.subheader("1. Medidas y Opciones Finales")
    st.number_input("Ancho de la Ventana (m)", min_value=0.1, value=1.0, step=0.1, key="ancho")
    st.number_input("Alto de la Cortina (m)", min_value=0.1, value=1.0, step=0.1, key="alto")
    st.number_input("Cantidad (und)", min_value=1, value=1, step=1, key="cantidad")
    st.radio("¿Cortina partida?", ("SI", "NO"), horizontal=True, key="partida")
    st.markdown("---")
    st.subheader("2. Selecciona el Diseño")

    tipo_opciones = list(TIPOS_CORTINA.keys())
    tipo_default = st.session_state.get("tipo_cortina_sel", tipo_opciones[0])
    tipo_cortina_sel = st.selectbox("Tipo de Cortina", options=tipo_opciones, index=tipo_opciones.index(tipo_default), key="tipo_cortina_sel")

    disenos_disponibles = TIPOS_CORTINA.get(tipo_cortina_sel, [])
    if not disenos_disponibles:
        st.error("No hay diseños disponibles para el tipo seleccionado. Verifica el Excel de Diseños.")
        st.stop()

    diseno_previo = st.session_state.get("diseno_sel", disenos_disponibles[0])
    if diseno_previo not in disenos_disponibles:
        diseno_previo = disenos_disponibles[0]

    diseno_sel = st.selectbox("Diseño", options=disenos_disponibles, index=disenos_disponibles.index(diseno_previo), key="diseno_sel")

    valor_multiplicador = float(TABLA_DISENOS.get(diseno_sel, 2.0))
    st.number_input("Multiplicador", min_value=1.0, value=valor_multiplicador, step=0.1, key="multiplicador")

    ancho_cortina = st.session_state.ancho * st.session_state.multiplicador
    st.number_input("Ancho Cortina (m)", value=float(ancho_cortina), step=0.1, disabled=True, key="ancho_cortina_info")

    st.markdown("---")
    st.subheader("3. Selecciona la Tela")
    # Restored cascading selectors using CATALOGO_TELAS
    tipo_tela_sel = st.selectbox("Tipo de Tela", options=list(CATALOGO_TELAS.keys()), key="tipo_tela_sel")
    refs = list(CATALOGO_TELAS[tipo_tela_sel].keys())
    ref_tela_sel = st.selectbox("Referencia", options=refs, key="ref_tela_sel")
    colores = [item['color'] for item in CATALOGO_TELAS[tipo_tela_sel][ref_tela_sel]]
    color_tela_sel = st.selectbox("Color", options=colores, key="color_tela_sel")
    tela_info = next(item for item in CATALOGO_TELAS[tipo_tela_sel][ref_tela_sel] if item['color'] == color_tela_sel)
    st.number_input("Precio por Metro de la TELA seleccionada ($)", value=tela_info['pvp'], disabled=True, key="pvp_tela")

    st.markdown("---")
    st.subheader("4. Insumos según BOM")
    mostrar_insumos_bom(diseno_sel)

    if st.button("Calcular Cotización", type="primary"):
        calcular_y_mostrar_cotizacion()

    if st.session_state.get('cortina_calculada'):
        st.success("Cálculo realizado. Revisa los detalles a continuación.")
        st.subheader("Detalle de Insumos Calculados")
        df_detalle = pd.DataFrame(st.session_state.cortina_calculada['detalle_insumos'])
        st.dataframe(df_detalle, use_container_width=True, hide_index=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Subtotal Cortina", f"${st.session_state.cortina_calculada['subtotal']:,.2f}")
        c2.metric("IVA Cortina", f"${st.session_state.cortina_calculada['iva']:,.2f}")
        c3.metric("Total Cortina", f"${st.session_state.cortina_calculada['total']:,.2f}")
        if st.button("Añadir al Resumen", type="primary", use_container_width=True):
            st.session_state.cortinas_resumen.append(st.session_state.cortina_calculada)
            st.session_state.cortina_calculada = None
            st.session_state.pagina_actual = 'resumen'
            st.rerun()

# =========================================
# INSUMOS UI
# =========================================
def mostrar_insumos_bom(diseno_sel: str):
    # Seleccionados por el usuario (solo DependeDeSeleccion = SI)
    if 'insumos_seleccion' not in st.session_state:
        st.session_state.insumos_seleccion = {}

    items_all = BOM_DICT.get(diseno_sel, [])
    items_display = [it for it in items_all if it["DependeDeSeleccion"] == "SI"]

    if not items_display:
        st.info("Este diseño no requiere insumos adicionales para seleccionar.")
        return

    for item in items_display:
        nombre = item["Insumo"]
        unidad  = item["Unidad"]
        with st.container(border=True):
            st.markdown(f"**Insumo:** {nombre} • **Unidad:** {unidad}")
            # For TELA 1, we always use the selected fabric price from Section 3, not catalog
            if nombre == "TELA 1":
                pvp = st.session_state.get("pvp_tela", 0)
                st.session_state.insumos_seleccion[nombre] = {"ref": st.session_state.get("ref_tela_sel",""), "color": st.session_state.get("color_tela_sel",""), "pvp": pvp, "unidad": "MT"}
                st.number_input(f"P.V.P {nombre} (MT)", value=float(pvp), disabled=True, key=f"pvp_{nombre}")
            else:
                # find in catalog
                if nombre not in CATALOGO_INSUMOS or not CATALOGO_INSUMOS[nombre]["opciones"]:
                    st.warning(f"{nombre}: marcado como 'DependeDeSeleccion' pero no está en el catálogo de insumos.")
                    continue
                cat = CATALOGO_INSUMOS[nombre]
                refs = sorted(list(set(opt['ref'] for opt in cat['opciones'])))
                ref_key = f"ref_{nombre}"
                color_key = f"color_{nombre}"
                ref_sel = st.selectbox(f"Referencia {nombre}", options=refs, key=ref_key)
                colores = sorted(list(set(opt['color'] for opt in cat['opciones'] if opt['ref'] == ref_sel)))
                color_sel = st.selectbox(f"Color {nombre}", options=colores, key=color_key)
                insumo_info = next(opt for opt in cat['opciones'] if opt['ref'] == ref_sel and opt['color'] == color_sel)
                st.session_state.insumos_seleccion[nombre] = {"ref": ref_sel, "color": color_sel, "pvp": insumo_info["pvp"], "unidad": cat["unidad"]}
                st.number_input(f"P.V.P {nombre} ({cat['unidad']})", value=float(insumo_info["pvp"]), disabled=True, key=f"pvp_{nombre}")

# =========================================
# CALC
# =========================================
def calcular_y_mostrar_cotizacion():
    diseno = st.session_state.diseno_sel
    ancho = st.session_state.ancho
    alto = st.session_state.alto
    multiplicador = st.session_state.multiplicador
    num_cortinas = st.session_state.cantidad

    detalle_insumos = []
    subtotal = 0.0

    # iterate all BOM items (SI + NO) for total
    for item in BOM_DICT.get(diseno, []):
        nombre = item["Insumo"]
        unidad = item["Unidad"].upper()
        regla  = item["ReglaCantidad"].upper()
        param  = item["Parametro"]

        # Qty per curtain
        if regla == "MT_ANCHO_X_MULT":
            factor = float(param) if param else 1.0
            cantidad = ancho * multiplicador * factor
        elif regla == "UND_OJALES_PAR":
            paso = float(param) if param else DISTANCIA_OJALES_DEF
            cantidad = ceil_to_even((ancho * multiplicador) / paso)
        elif regla == "UND_BOTON_PAR":
            paso = float(param) if param else DISTANCIA_BOTON_DEF
            cantidad = ceil_to_even((ancho * multiplicador) / paso)
        elif regla == "FIJO":
            try:
                cantidad = float(param)
            except Exception:
                st.error(f"Cantidad FIJA inválida para insumo '{nombre}'. Revisa 'Parametro' en el BOM.")
                st.stop()
        else:
            st.error(f"ReglaCantidad '{regla}' no soportada (BOM).")
            st.stop()

        cantidad_total = cantidad * num_cortinas

        # price
        if nombre == "TELA 1":
            pvp = float(st.session_state.get("pvp_tela", 0))
            uni = "MT"
            nombre_mostrado = f"TELA: {st.session_state.get('ref_tela_sel','')} - {st.session_state.get('color_tela_sel','')}"
        else:
            sel = st.session_state.insumos_seleccion.get(nombre)
            if sel:
                pvp = float(sel["pvp"]); uni = sel["unidad"]
            else:
                # fallback to catalog first option if exists else 0
                if nombre in CATALOGO_INSUMOS and CATALOGO_INSUMOS[nombre]["opciones"]:
                    pvp = float(CATALOGO_INSUMOS[nombre]["opciones"][0]["pvp"])
                    uni = CATALOGO_INSUMOS[nombre]["unidad"]
                else:
                    pvp = 0.0; uni = unidad
            nombre_mostrado = nombre

        precio_total = pvp * cantidad_total
        subtotal += precio_total

        detalle_insumos.append({
            "Insumo": nombre_mostrado,
            "Unidad": uni,
            "Cantidad": f"{int(cantidad_total)}" if uni == "UND" else f"{cantidad_total:.2f}",
            "P.V.P/Unit ($)": f"${pvp:,.2f}",
            "Precio ($)": f"${precio_total:,.2f}"
        })

    total = subtotal
    iva = total * IVA_PERCENT
    subtotal_sin_iva = total - iva

    st.session_state.cortina_calculada = {
        "tipo": st.session_state.tipo_cortina_sel,
        "diseno": diseno, "multiplicador": multiplicador, "ancho": ancho, "alto": alto,
        "cantidad": num_cortinas,
        "partida": st.session_state.partida,
        "tela": {"tipo": st.session_state.tipo_tela_sel, "referencia": st.session_state.ref_tela_sel, "color": st.session_state.color_tela_sel},
        "insumos_seleccion": st.session_state.insumos_seleccion,
        "detalle_insumos": detalle_insumos, "subtotal": subtotal_sin_iva, "iva": iva, "total": total
    }

# =========================================
# MAIN
# =========================================
def main():
    init_state()
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
