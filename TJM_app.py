
import streamlit as st
import pandas as pd
import os
import math
from datetime import datetime
from fpdf import FPDF

# ================================
# CONFIG & CONSTANTS
# ================================
SCRIPT_DIR = os.path.dirname(__file__) if "__file__" in globals() else os.getcwd()

# Excel paths (with optional overrides via env or st.secrets)
def _get_secret(key):
    try:
        return st.secrets.get(key)
    except Exception:
        return None

DESIGNS_XLSX_PATH = os.environ.get("DESIGNS_XLSX_PATH") or _get_secret("DESIGNS_XLSX_PATH") or os.path.join(SCRIPT_DIR, "data", "disenos_cortina.xlsx")
BOM_XLSX_PATH     = os.environ.get("BOM_XLSX_PATH") or _get_secret("BOM_XLSX_PATH") or os.path.join(SCRIPT_DIR, "data", "bom.xlsx")
CATALOG_XLSX_PATH = os.environ.get("CATALOG_XLSX_PATH") or _get_secret("CATALOG_XLSX_PATH") or os.path.join(SCRIPT_DIR, "data", "catalogo_insumos.xlsx")

REQUIRED_DESIGNS_COLS = ["Diseño", "Tipo", "Multiplicador", "PVP M.O."]
REQUIRED_BOM_COLS = ["Diseño", "Insumo", "Unidad", "ReglaCantidad", "Parametro", "DependeDeSeleccion", "Observaciones"]
REQUIRED_CATALOG_COLS = ["Insumo", "Unidad", "Ref", "Color", "PVP"]  # "Notas" es opcional

ALLOWED_RULES = {"MT_ANCHO_X_MULT", "UND_OJALES_PAR", "UND_BOTON_PAR", "FIJO"}

IVA_PERCENT = 0.19
DISTANCIA_OJALES_DEF = 0.14
DISTANCIA_BOTON_DEF = 0.20

# ================================
# HELPER FUNCTIONS
# ================================
def ceil_to_even(x: float) -> int:
    n = math.ceil(x)
    return n if n % 2 == 0 else n + 1

def load_designs(path: str):
    if not os.path.exists(path):
        st.error(f"No se encontró el Excel de Diseños en: {path}")
        st.stop()
    try:
        df = pd.read_excel(path, engine="openpyxl")
    except Exception as e:
        st.error(f"No se pudo leer el Excel de Diseños: {e}")
        st.stop()

    missing = [c for c in REQUIRED_DESIGNS_COLS if c not in df.columns]
    if missing:
        st.error("El Excel de Diseños debe tener columnas: " + ", ".join(REQUIRED_DESIGNS_COLS) + f". Encontradas: {list(df.columns)}")
        st.stop()

    tabla_disenos = {}  # diseño -> multiplicador
    tipos_cortina = {}  # tipo -> [diseños]
    precios_mo = {}     # "M.O: DISEÑO" -> {unidad, pvp}
    for _, row in df.iterrows():
        dis = str(row["Diseño"]).strip()
        mult = float(row["Multiplicador"])
        mo = float(row["PVP M.O."])
        tabla_disenos[dis] = mult
        tipos = [t.strip() for t in str(row["Tipo"]).split(",") if t and str(t).strip()]
        for t in tipos:
            tipos_cortina.setdefault(t, [])
            if dis not in tipos_cortina[t]:
                tipos_cortina[t].append(dis)
        # registrar dos claves para tolerancia de formato
        precios_mo[f"M.O: {dis}"] = {"unidad": "MT", "pvp": mo}
        precios_mo[f"M.O. {dis}"] = {"unidad": "MT", "pvp": mo}
    return tabla_disenos, tipos_cortina, precios_mo, df

def load_bom(path: str):
    if not os.path.exists(path):
        st.error(f"No se encontró el Excel de BOM en: {path}")
        st.stop()
    try:
        df = pd.read_excel(path, engine="openpyxl")
    except Exception as e:
        st.error(f"No se pudo leer el Excel de BOM: {e}")
        st.stop()

    missing = [c for c in REQUIRED_BOM_COLS if c not in df.columns]
    if missing:
        st.error("El Excel de BOM debe tener columnas: " + ", ".join(REQUIRED_BOM_COLS) + f". Encontradas: {list(df.columns)}")
        st.stop()

    # validar reglas
    reglas = set(str(x).strip().upper() for x in df["ReglaCantidad"])
    invalid = sorted(reglas - ALLOWED_RULES)
    if invalid:
        st.error("Reglas no soportadas en BOM: " + ", ".join(invalid) + ". Permitidas: " + ", ".join(sorted(ALLOWED_RULES)))
        st.stop()

    bom_dict = {}
    for _, row in df.iterrows():
        item = {
            "Diseño": str(row["Diseño"]).strip(),
            "Insumo": str(row["Insumo"]).strip(),
            "Unidad": str(row["Unidad"]).strip().upper(),
            "ReglaCantidad": str(row["ReglaCantidad"]).strip().upper(),
            "Parametro": ("" if pd.isna(row["Parametro"]) else str(row["Parametro"]).strip()),
            "DependeDeSeleccion": str(row["DependeDeSeleccion"]).strip().upper(),
            "Observaciones": ("" if pd.isna(row["Observaciones"]) else str(row["Observaciones"]).strip()),
        }
        bom_dict.setdefault(item["Diseño"], []).append(item)
    return bom_dict, df

def load_catalog(path: str):
    if not os.path.exists(path):
        st.error(f"No se encontró el Excel de Catálogo de Insumos en: {path}")
        st.stop()
    try:
        df = pd.read_excel(path, engine="openpyxl")
    except Exception as e:
        st.error(f"No se pudo leer el Excel de Catálogo: {e}")
        st.stop()

    missing = [c for c in REQUIRED_CATALOG_COLS if c not in df.columns]
    if missing:
        st.error("El Excel de Catálogo debe tener columnas: " + ", ".join(REQUIRED_CATALOG_COLS) + f". Encontradas: {list(df.columns)}")
        st.stop()

    # construir estructura: insumo -> {"unidad": unit, "opciones":[{ref,color,pvp}]}
    catalog = {}
    for _, row in df.iterrows():
        ins = str(row["Insumo"]).strip()
        unidad = str(row["Unidad"]).strip().upper()
        ref = str(row["Ref"]).strip()
        color = str(row["Color"]).strip()
        try:
            pvp = float(row["PVP"])
        except Exception:
            pvp = 0.0
        catalog.setdefault(ins, {"unidad": unidad, "opciones": []})
        catalog[ins]["opciones"].append({"ref": ref, "color": color, "pvp": pvp})
    return catalog, df

# ================================
# STATIC CATALOG OF FABRICS (for UI)
# ================================
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

# ================================
# LOAD DATA
# ================================
st.set_page_config(page_title="Megatex Cotizador", page_icon="🧵", layout="wide")

TABLA_DISENOS, TIPOS_CORTINA, PRECIOS_MANO_DE_OBRA, DF_DISENOS = load_designs(DESIGNS_XLSX_PATH)
BOM_DICT, DF_BOM = load_bom(BOM_XLSX_PATH)
CATALOGO_INSUMOS, DF_CATALOG = load_catalog(CATALOG_XLSX_PATH)

# ================================
# STATE
# ================================
def init_state():
    if 'pagina_actual' not in st.session_state:
        st.session_state.pagina_actual = 'cotizador'
    if 'datos_cotizacion' not in st.session_state:
        st.session_state.datos_cotizacion = {"cliente": {}, "vendedor": {}}
    if 'cortinas_resumen' not in st.session_state:
        st.session_state.cortinas_resumen = []
    if 'cortina_calculada' not in st.session_state:
        st.session_state.cortina_calculada = None
    if 'insumos_seleccion' not in st.session_state:
        st.session_state.insumos_seleccion = {}
    if 'tipo_cortina_sel' not in st.session_state:
        st.session_state.tipo_cortina_sel = list(TIPOS_CORTINA.keys())[0]

# ================================
# UI HELPERS
# ================================
def sidebar():
    with st.sidebar:
        st.title("Megatex Cotizador")
        st.caption(f"🗂 Diseños: {DESIGNS_XLSX_PATH}")
        st.caption(f"🗂 BOM: {BOM_XLSX_PATH}")
        st.caption(f"🗂 Catálogo insumos: {CATALOG_XLSX_PATH}")
        if st.button("Recargar datos"):
            st.cache_data.clear(); st.cache_resource.clear(); st.rerun()
        st.markdown("---")
        if st.button("Crear Cotización", use_container_width=True):
            st.session_state.pagina_actual = 'cotizador'; st.session_state.cortina_calculada = None; st.rerun()
        if st.button("Datos de la Cotización", use_container_width=True):
            st.session_state.pagina_actual = 'datos'; st.rerun()
        if st.button("Ver Resumen Final", use_container_width=True):
            st.session_state.pagina_actual = 'resumen'; st.rerun()

def pantalla_datos():
    st.header("Datos de la Cotización")
    with st.expander("Cliente", expanded=True):
        c = st.session_state.datos_cotizacion['cliente']
        c['nombre'] = st.text_input("Nombre", value=c.get('nombre', ''))
        c1, c2 = st.columns(2)
        c['cedula'] = c1.text_input("Cédula/NIT", value=c.get('cedula', ''))
        c['telefono'] = c2.text_input("Teléfono", value=c.get('telefono', ''))
        c['direccion'] = st.text_input("Dirección", value=c.get('direccion', ''))
        c['correo'] = st.text_input("Correo", value=c.get('correo', ''))

    with st.expander("Vendedor", expanded=True):
        v = st.session_state.datos_cotizacion['vendedor']
        v['nombre'] = st.text_input("Nombre Vendedor", value=v.get('nombre', ''))
        v['telefono'] = st.text_input("Teléfono Vendedor", value=v.get('telefono', ''))

def pantalla_resumen():
    st.header("Resumen de la Cotización")
    if not st.session_state.cortinas_resumen:
        st.info("Aún no has añadido cortinas.")
        return
    for i, c in enumerate(st.session_state.cortinas_resumen):
        with st.container(border=True):
            st.markdown(f"**{i+1}. {c['diseno']}** — {c['ancho']*c['multiplicador']:.2f} × {c['alto']:.2f} m × {c['cantidad']} und")
            st.write(f"Total: ${c['total']:,.2f}")

def pantalla_cotizador():
    st.header("Configurar Cortina")

    # Sección 1: Medidas
    st.subheader("1. Medidas")
    ancho = st.number_input("Ancho de la Ventana (m)", min_value=0.1, value=1.0, step=0.1, key="ancho")
    alto = st.number_input("Alto de la Cortina (m)", min_value=0.1, value=1.0, step=0.1, key="alto")
    cantidad = st.number_input("Cantidad (und)", min_value=1, value=1, step=1, key="cantidad")
    st.session_state.partida = st.radio("¿Cortina partida?", ("SI", "NO"), horizontal=True)

    st.markdown("---")
    # Sección 2: tipo y diseño
    st.subheader("2. Selecciona el Diseño")
    tipo_opciones = list(TIPOS_CORTINA.keys())
    tipo_sel = st.selectbox("Tipo de Cortina", options=tipo_opciones, index=tipo_opciones.index(st.session_state.tipo_cortina_sel) if st.session_state.tipo_cortina_sel in tipo_opciones else 0, key="tipo_cortina_sel")
    disenos = TIPOS_CORTINA.get(tipo_sel, [])
    if not disenos:
        st.error("No hay diseños para el tipo seleccionado.")
        st.stop()
    diseno_sel = st.selectbox("Diseño", options=disenos, key="diseno_sel")
    multiplicador = float(TABLA_DISENOS.get(diseno_sel, 2.0))
    st.number_input("Multiplicador", value=multiplicador, min_value=1.0, step=0.1, key="multiplicador")
    # informativo
    ancho_cortina = st.session_state.ancho * st.session_state.multiplicador
    st.number_input("Ancho Cortina (m)", value=float(ancho_cortina), step=0.1, disabled=True, key="ancho_cortina_info")

    st.markdown("---")
    # Sección 3: Tela
    st.subheader("3. Selecciona la Tela")
    tipo_tela = st.selectbox("Tipo de Tela", options=list(CATALOGO_TELAS.keys()), key="tipo_tela_sel")
    refs = list(CATALOGO_TELAS[tipo_tela].keys())
    ref_tela = st.selectbox("Referencia", options=refs, key="ref_tela_sel")
    colores = [x["color"] for x in CATALOGO_TELAS[tipo_tela][ref_tela]]
    color_tela = st.selectbox("Color", options=colores, key="color_tela_sel")
    pvp_tela = next(x["pvp"] for x in CATALOGO_TELAS[tipo_tela][ref_tela] if x["color"] == color_tela)
    st.number_input("Precio por Metro de la TELA seleccionada ($)", value=pvp_tela, disabled=True, key="pvp_tela")

    st.markdown("---")
    # Sección 4: Insumos según BOM (solo los SI)
    st.subheader("4. Insumos según BOM")
    mostrar_insumos_bom(diseno_sel)
    st.markdown("---")

    if st.button("Calcular Cotización", type="primary"):
        calcular_y_mostrar_cotizacion()
    if st.session_state.get("cortina_calculada"):
        st.success("Cálculo realizado.")
        st.subheader("Detalle de Insumos Calculados")
        df = pd.DataFrame(st.session_state.cortina_calculada["detalle_insumos"])
        st.dataframe(df, use_container_width=True, hide_index=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Subtotal Cortina", f"${st.session_state.cortina_calculada['subtotal']:,.2f}")
        c2.metric("IVA Cortina", f"${st.session_state.cortina_calculada['iva']:,.2f}")
        c3.metric("Total Cortina", f"${st.session_state.cortina_calculada['total']:,.2f}")

def mostrar_insumos_bom(diseno_sel: str):
    items_all = BOM_DICT.get(diseno_sel, [])
    items_display = [it for it in items_all if it["DependeDeSeleccion"] == "SI" and it["Insumo"] != "TELA 1"]
    if not items_display:
        st.info("Este diseño no requiere insumos adicionales para seleccionar.")
        return

    for item in items_display:
        nombre = item["Insumo"]
        if nombre not in CATALOGO_INSUMOS:
            st.warning(f"{nombre}: marcado como 'DependeDeSeleccion' pero no está en el catálogo de insumos.")
            continue
        cat = CATALOGO_INSUMOS[nombre]
        refs = sorted(list(set(opt["ref"] for opt in cat["opciones"])))
        ref_key = f"ref_{nombre}"
        color_key = f"color_{nombre}"
        ref_sel = st.selectbox(f"Referencia {nombre}", options=refs, key=ref_key)
        colores = sorted(list(set(opt["color"] for opt in cat["opciones"] if opt["ref"] == ref_sel)))
        color_sel = st.selectbox(f"Color {nombre}", options=colores, key=color_key)
        insumo_info = next(opt for opt in cat["opciones"] if opt["ref"] == ref_sel and opt["color"] == color_sel)
        st.session_state.insumos_seleccion[nombre] = {"ref": ref_sel, "color": color_sel, "pvp": insumo_info["pvp"], "unidad": cat["unidad"]}
        st.number_input(f"P.V.P {nombre} ({cat['unidad']})", value=insumo_info["pvp"], disabled=True, key=f"pvp_{nombre}")

# ================================
# CORE CALC
# ================================
def calcular_y_mostrar_cotizacion():
    diseno = st.session_state.diseno_sel
    ancho = st.session_state.ancho
    alto = st.session_state.alto
    multiplicador = st.session_state.multiplicador
    num_cortinas = st.session_state.cantidad

    detalle = []
    subtotal = 0.0

    for item in BOM_DICT.get(diseno, []):
        nombre = item["Insumo"]
        unidad = item["Unidad"]
        regla = item["ReglaCantidad"]
        param = item["Parametro"]
        depende = item["DependeDeSeleccion"] == "SI"

        # Cantidad por cortina según regla
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
                st.error(f"Cantidad FIJA inválida para '{nombre}' en BOM.")
                st.stop()
        else:
            st.error(f"ReglaCantidad '{regla}' no soportada.")
            st.stop()

        cantidad_total = cantidad * num_cortinas

        # Precio unitario
        if nombre == "TELA 1":
            pvp = float(st.session_state.pvp_tela)
            uni = "MT"
            nombre_mostrar = f"TELA: {st.session_state.ref_tela_sel} - {st.session_state.color_tela_sel}"
        else:
            if depende and nombre in st.session_state.insumos_seleccion:
                sel = st.session_state.insumos_seleccion[nombre]
                pvp = float(sel["pvp"]); uni = sel.get("unidad", unidad); nombre_mostrar = nombre
            elif nombre in CATALOGO_INSUMOS:
                # tomar primer precio del catálogo si no depende de selección
                cat = CATALOGO_INSUMOS[nombre]
                pvp = float(cat["opciones"][0]["pvp"]) if cat["opciones"] else 0.0
                uni = cat["unidad"]
                nombre_mostrar = nombre
            else:
                pvp = 0.0; uni = unidad; nombre_mostrar = nombre

        precio_total = pvp * cantidad_total
        subtotal += precio_total
        detalle.append({
            "Insumo": nombre_mostrar,
            "Unidad": uni,
            "Cantidad": f"{int(cantidad_total)}" if uni == "UND" else f"{cantidad_total:.2f}",
            "P.V.P/Unit ($)": f"${pvp:,.2f}",
            "Precio ($)": f"${precio_total:,.2f}"
        })

    # --- Mano de Obra (desde diseños) -------------------------
    mo_key = None
    mo_info = None
    for k in (f"M.O: {diseno}", f"M.O. {diseno}"):
        if k in PRECIOS_MANO_DE_OBRA:
            mo_key = k
            mo_info = PRECIOS_MANO_DE_OBRA[k]
            break

    if mo_info and float(mo_info.get("pvp", 0)) > 0:
        cant_mo = ancho * multiplicador * num_cortinas  # por ahora: ancho ventana × multiplicador × cantidad
        pvp_mo = float(mo_info["pvp"])
        precio_mo = cant_mo * pvp_mo
        subtotal += precio_mo
        detalle.append({
            "Insumo": mo_key,
            "Unidad": mo_info.get("unidad", "MT"),
            "Cantidad": f"{cant_mo:.2f}",
            "P.V.P/Unit ($)": f"${pvp_mo:,.2f}",
            "Precio ($)": f"${precio_mo:,.2f}"
        })

    total = subtotal
    iva = total * IVA_PERCENT
    subtotal_sin_iva = total - iva

    st.session_state.cortina_calculada = {
        "tipo": st.session_state.tipo_cortina_sel,
        "diseno": diseno,
        "multiplicador": multiplicador,
        "ancho": ancho,
        "alto": alto,
        "cantidad": num_cortinas,
        "detalle_insumos": detalle,
        "subtotal": subtotal_sin_iva,
        "iva": iva,
        "total": total
    }

# ================================
# MAIN
# ================================
def main():
    init_state()
    sidebar()
    if st.session_state.pagina_actual == 'datos':
        pantalla_datos()
    elif st.session_state.pagina_actual == 'resumen':
        pantalla_resumen()
    else:
        pantalla_cotizador()

if __name__ == "__main__":
    main()
