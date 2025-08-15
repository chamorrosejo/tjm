
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

DESIGNS_XLSX_PATH = os.environ.get("DESIGNS_XLSX_PATH", None) or (st.secrets.get("DESIGNS_XLSX_PATH") if hasattr(st, "secrets") else None) or _default_designs
BOM_XLSX_PATH     = os.environ.get("BOM_XLSX_PATH", None) or (st.secrets.get("BOM_XLSX_PATH") if hasattr(st, "secrets") else None) or _default_bom
CATALOG_XLSX_PATH = os.environ.get("CATALOG_XLSX_PATH", None) or (st.secrets.get("CATALOG_XLSX_PATH") if hasattr(st, "secrets") else None) or _default_catalog

# Required columns
REQUIRED_DESIGNS_COLS = ["Diseño", "Tipo", "Multiplicador", "PVP M.O."]
REQUIRED_BOM_COLS     = ["Diseño", "Insumo", "Unidad", "ReglaCantidad", "Parametro", "DependeDeSeleccion", "Observaciones"]
REQUIRED_CATALOG_COLS = ["Insumo", "Unidad", "Ref", "Color", "PVP"]

# Allowed rules
ALLOWED_RULES = {"MT_ANCHO_X_MULT", "UND_OJALES_PAR", "UND_BOTON_PAR", "FIJO"}

# Constants
IVA_PERCENT = 0.19
DISTANCIA_BOTON_DEF = 0.20
DISTANCIA_OJALES_DEF = 0.14

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
        precios_mo[f"M.O: {dis}"] = {"unidad": "MT", "pvp": mo_val}
        disenos_a_tipos.setdefault(dis, [])
        for t in tipos:
            tipos_cortina.setdefault(t, [])
            if dis not in tipos_cortina[t]:
                tipos_cortina[t].append(dis)
            if t not in disenos_a_tipos[dis]:
                disenos_a_tipos[dis].append(t)

    if not tabla_disenos or not tipos_cortina:
        st.error("El Excel de Diseños no contiene filas válidas.")
        st.stop()

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

    # Validar reglas
    reglas_invalidas = sorted(set(df["ReglaCantidad"].astype(str)) - ALLOWED_RULES)
    if reglas_invalidas:
        st.error(
            "Se encontraron valores no soportados en 'ReglaCantidad'. "
            "Reglas permitidas: MT_ANCHO_X_MULT, UND_OJALES_PAR, UND_BOTON_PAR, FIJO.\n\n"
            f"Valores inválidos detectados: {reglas_invalidas}"
        )
        st.stop()

    # Dict por diseño
    bom_dict = {}
    for _, row in df.iterrows():
        dis = str(row["Diseño"]).strip()
        item = {
            "Insumo": str(row["Insumo"]).strip(),
            "Unidad": str(row["Unidad"]).strip().upper(),
            "ReglaCantidad": str(row["ReglaCantidad"]).strip().upper(),
            "Parametro": str(row["Parametro"]).strip(),
            "DependeDeSeleccion": str(row["DependeDeSeleccion"]).strip().upper(),
            "Observaciones": str(row["Observaciones"]).strip(),
        }
        bom_dict.setdefault(dis, []).append(item)
    return bom_dict, df

def load_catalog_from_excel(path: str):
    if not os.path.exists(path):
        st.error(f"No se encontró el archivo Excel de Catálogo en: {path}")
        st.stop()
    try:
        df = pd.read_excel(path, engine="openpyxl")
    except Exception as e:
        st.error(f"No se pudo leer el Excel de Catálogo: {e}")
        st.stop()
    faltantes = [c for c in REQUIRED_CATALOG_COLS if c not in df.columns]
    if faltantes:
        st.error(
            "El Catálogo debe tener al menos estas columnas:\n"
            + "\n".join(f"- {c}" for c in REQUIRED_CATALOG_COLS)
            + f"\n\nColumnas encontradas: {list(df.columns)}"
        )
        st.stop()

    # construir estructura: CATALOGO_INSUMOS[insumo] = {"unidad":..., "opciones":[{ref,color,pvp}]}
    res = {}
    for _, row in df.iterrows():
        insumo = str(row["Insumo"]).strip()
        unidad = str(row["Unidad"]).strip().upper()
        ref = str(row["Ref"]).strip()
        color = str(row["Color"]).strip()
        try:
            pvp = float(row["PVP"])
        except Exception:
            pvp = 0.0
        if insumo not in res:
            res[insumo] = {"unidad": unidad, "opciones": []}
        res[insumo]["opciones"].append({"ref": ref, "color": color, "pvp": pvp})
    return res, df

# =========================================
# LOAD DATA
# =========================================
st.set_page_config(page_title="Megatex Cotizador", page_icon="Megatex.png", layout="wide")

TABLA_DISENOS, TIPOS_CORTINA, PRECIOS_MANO_DE_OBRA, DISENOS_A_TIPOS, DF_DISENOS = load_designs_from_excel(DESIGNS_XLSX_PATH)
BOM_DICT, DF_BOM = load_bom_from_excel(BOM_XLSX_PATH)
CATALOGO_INSUMOS, DF_CATALOG = load_catalog_from_excel(CATALOG_XLSX_PATH)

# =========================================
# STATE
# =========================================
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

# =========================================
# PDF (unchanged)
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

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'R')

# =========================================
# UI
# =========================================
def sidebar():
    with st.sidebar:
        st.title("Megatex Cotizador")
        st.caption(f"Diseños: {DESIGNS_XLSX_PATH}")
        st.caption(f"BOM: {BOM_XLSX_PATH}")
        st.caption(f"Catálogo: {CATALOG_XLSX_PATH}")
        if st.button("Recargar datos"):
            st.cache_data.clear(); st.cache_resource.clear(); st.rerun()
        st.markdown("---")
        if st.button("Crear Cotización", use_container_width=True):
            st.session_state.editando_index = None
            st.session_state.pagina_actual = 'cotizador'; st.rerun()
        if st.button("Datos de la Cotización", use_container_width=True):
            st.session_state.pagina_actual = 'datos'; st.rerun()
        if st.button("Ver Resumen Final", use_container_width=True):
            st.session_state.pagina_actual = 'resumen'; st.rerun()

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

# =========================================
# PANTALLA COTIZADOR
# =========================================
def pantalla_cotizador():
    st.header("Configurar Cortina")
    st.subheader("1. Medidas y Opciones Finales")
    ancho = st.number_input("Ancho de la Ventana (m)", min_value=0.1, value=1.0, step=0.1, key="ancho")
    alto = st.number_input("Alto de la Cortina (m)", min_value=0.1, value=1.0, step=0.1, key="alto")
    cantidad_cortinas = st.number_input("Cantidad (und)", min_value=1, value=1, step=1, key="cantidad")
    partida = st.radio("¿Cortina partida?", ("SI", "NO"), horizontal=True, key="partida")
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
    multiplicador = st.number_input("Multiplicador", min_value=1.0, value=valor_multiplicador, step=0.1, key="multiplicador")

    ancho_cortina = st.session_state.ancho * multiplicador
    st.number_input("Ancho Cortina (m)", value=float(ancho_cortina), step=0.1, disabled=True, key="ancho_cortina_info")

    st.markdown("---")
    st.subheader("3. Selecciona la Tela")
    # Aquí asumes catálogo de telas separado; para simplificar omitimos y el PVP se puede ingresar o tomar de un catálogo fijo.
    # Para mantener compatibilidad con versiones previas, dejamos una entrada de precio editable.
    pvp_tela_val = st.number_input("Precio por Metro de la TELA seleccionada ($)", min_value=0, value=38000, step=1000, key="pvp_tela")

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
# INSUMOS UI (BOM-driven) -- with display filter
# =========================================
def mostrar_insumos_bom(diseno_sel: str):
    # Reset dict for a fresh rendering
    st.session_state.insumos_seleccion = {}

    items_all = BOM_DICT.get(diseno_sel, [])
    if not items_all:
        st.info("Este diseño no requiere insumos adicionales.")
        return

    # Only display items where DependeDeSeleccion == "SI"
    items_display = [it for it in items_all if it["DependeDeSeleccion"] == "SI"]

    if not items_display:
        st.info("Este diseño no requiere insumos adicionales para seleccionar.")
        return

    for item in items_display:
        nombre = item["Insumo"]
        unidad  = item["Unidad"]

        with st.container(border=True):
            st.markdown(f"**Insumo:** {nombre} • **Unidad:** {unidad}")
            if nombre in CATALOGO_INSUMOS:
                cat = CATALOGO_INSUMOS[nombre]
                refs = sorted(list(set(opt['ref'] for opt in cat['opciones'])))
                ref_key = f"ref_{nombre}"
                color_key = f"color_{nombre}"

                ref_sel = st.selectbox(f"Referencia {nombre}", options=refs, key=ref_key)
                colores = sorted(list(set(opt['color'] for opt in cat['opciones'] if opt['ref'] == ref_sel)))
                color_sel = st.selectbox(f"Color {nombre}", options=colores, key=color_key)

                insumo_info = next(opt for opt in cat['opciones'] if opt['ref'] == ref_sel and opt['color'] == color_sel)
                st.session_state.insumos_seleccion[nombre] = {
                    "ref": ref_sel, "color": color_sel, "pvp": insumo_info["pvp"], "unidad": cat["unidad"]
                }
                st.number_input(f"P.V.P {nombre} ({cat['unidad']})", value=float(insumo_info["pvp"]), disabled=True, key=f"pvp_{nombre}")
            else:
                # If not in catalog, default pvp=0
                st.session_state.insumos_seleccion[nombre] = {"ref":"", "color":"", "pvp":0.0, "unidad": unidad}
                st.number_input(f"P.V.P {nombre} ({unidad})", value=0.0, disabled=True, key=f"pvp_{nombre}")

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

    # Recorremos TODOS los items del BOM (aunque no se muestren)
    for item in BOM_DICT.get(diseno, []):
        nombre = item["Insumo"]
        unidad = item["Unidad"].upper()
        regla  = item["ReglaCantidad"].upper()
        param  = item["Parametro"].strip()

        # Cantidad por cortina
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

        # Precio unitario
        if nombre == "TELA 1":
            pvp = float(st.session_state.pvp_tela)
            uni = "MT"
            nombre_mostrado = "TELA (seleccionada)"
        elif item["DependeDeSeleccion"] == "SI":
            sel = st.session_state.insumos_seleccion.get(nombre, {"pvp":0.0, "unidad":unidad, "ref":"", "color":""})
            pvp = float(sel["pvp"]); uni = sel["unidad"]; nombre_mostrado = nombre
        else:
            # No depende: tomar del catálogo si existe, si no 0
            if nombre in CATALOGO_INSUMOS:
                opt0 = CATALOGO_INSUMOS[nombre]["opciones"][0]
                pvp = float(opt0["pvp"]); uni = CATALOGO_INSUMOS[nombre]["unidad"]
            else:
                pvp = 0.0; uni = unidad
            nombre_mostrado = nombre

        precio_total = pvp * cantidad_total
        subtotal += precio_total

        detalle_insumos.append({
            "Insumo": nombre_mostrado,
            "Cantidad": f"{int(cantidad_total)}" if uni == "UND" else f"{cantidad_total:.2f}",
            "Unidad": uni,
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
        "tela": {"pvp": float(st.session_state.pvp_tela)},
        "insumos_seleccion": st.session_state.insumos_seleccion,
        "detalle_insumos": detalle_insumos, "subtotal": subtotal_sin_iva, "iva": iva, "total": total
    }

# =========================================
# MAIN
# =========================================
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
