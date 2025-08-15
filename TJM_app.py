
import streamlit as st
import pandas as pd
import os
from fpdf import FPDF
from datetime import datetime
import math

# =========================================================
# CONFIG
# =========================================================
SCRIPT_DIR = os.path.dirname(__file__) if "__file__" in globals() else os.getcwd()

# 1) Ruta por defecto dentro del repo
_default_path = os.path.join(SCRIPT_DIR, "data", "disenos_cortina.xlsx")

# 2) Override opcional por variable de entorno o st.secrets
_excel_from_env = os.environ.get("DESIGNS_XLSX_PATH")
try:
    _excel_from_secrets = st.secrets.get("DESIGNS_XLSX_PATH")
except Exception:
    _excel_from_secrets = None

EXCEL_PATH = _excel_from_env or _excel_from_secrets or _default_path

# Columnas EXACTAS requeridas en el Excel
REQUIRED_COLUMNS = ["Diseño", "Tipo", "Multiplicador", "PVP M.O."]

# Impuestos y parámetros
IVA_PERCENT = 0.19
DISTANCIA_BOTON = 0.2
DISTANCIA_OJALES = 0.14
PASO_RODACHIN = 0.06

# =========================================================
# UTIL
# =========================================================
def ceil_to_even(x: float) -> int:
    n = math.ceil(x)
    return n if n % 2 == 0 else n + 1

def load_designs_from_excel(path: str):
    """Lee el Excel y construye:
      - TABLA_DISENOS: diseño -> multiplicador
      - TIPOS_CORTINA: tipo -> [diseños]
      - PRECIOS_MANO_DE_OBRA: "M.O: <DISEÑO>" -> {unidad,pvp}
      - DISENOS_A_TIPOS: diseño -> [tipos]
      - DF_DISENOS: dataframe original (para debug/uso futuro)
    """
    if not os.path.exists(path):
        st.error(f"No se encontró el archivo Excel requerido en: {path}")
        st.stop()

    try:
        df = pd.read_excel(path)
    except Exception as e:
        st.error(f"No se pudo leer el Excel en {path}. Error: {e}")
        st.stop()

    # Verificar columnas exactas
    faltantes = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if faltantes:
        st.error(
            "El Excel debe tener exactamente estas columnas:\n"
            + "\n".join(f"- {c}" for c in REQUIRED_COLUMNS)
            + f"\n\nColumnas encontradas: {list(df.columns)}"
        )
        st.stop()

    tabla_disenos = {}          # diseño -> multiplicador
    tipos_cortina = {}          # tipo -> [diseños]
    precios_mo = {}             # "M.O: DISEÑO" -> {unidad,pvp}
    disenos_a_tipos = {}        # diseño -> [tipos]

    for _, row in df.iterrows():
        dis = str(row["Diseño"]).strip()
        tipos = [t.strip() for t in str(row["Tipo"]).split(",") if t and str(t).strip()]
        try:
            mult = float(row["Multiplicador"])
        except Exception:
            st.error(f"Multiplicador inválido para el diseño '{dis}'. Verifica el Excel.")
            st.stop()
        try:
            mo_val = float(row["PVP M.O."])
        except Exception:
            st.error(f"PVP M.O. inválido para el diseño '{dis}'. Verifica el Excel.")
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
        st.error("El Excel no contiene filas válidas para diseños y tipos.")
        st.stop()

    return tabla_disenos, tipos_cortina, precios_mo, disenos_a_tipos, df

# =========================================================
# CARGA DE DISEÑOS (OBLIGATORIA)
# =========================================================
st.set_page_config(page_title="Megatex Cotizador", page_icon="Megatex.png", layout="wide")

TABLA_DISENOS, TIPOS_CORTINA, PRECIOS_MANO_DE_OBRA, DISENOS_A_TIPOS, DF_DISENOS = load_designs_from_excel(EXCEL_PATH)

# =========================================================
# CATÁLOGOS INDEPENDIENTES DEL EXCEL
# =========================================================
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

# BOM (por ahora estático; lo actualizaremos luego)
BOM = {
    "TUBULAR": ["TELA 1", "M.O: TUBULAR"], "PRESILLAS SIN BOTON": ["TELA 1", "M.O: PRESILLAS SIN BOTON"],
    "PRESILLAS CON BOTON": ["TELA 1", "BOTON", "M.O: PRESILLAS CON BOTON"], "REATA 3/4": ["TELA 1", "REATA 3/4", "M.O: REATA 3/4"],
    "ONDA MODERNA REATA BROCHES": ["TELA 1", "REATA DE REFUERZO", "REATA BROCHES", "RODACHINES REATA BROCHES", "M.O: ONDA MODERNA REATA BROCHES"],
    "ONDA MODERNA REATA ITALIANA": ["TELA 1", "REATA ITALIANA", "RODACHINES REATA ITALIANA", "UÑETA REATA ITALIANA", "M.O: ONDA MODERNA REATA ITALIANA"],
    "ARGOLLA PLASTICA": ["TELA 1", "REATA DE REFUERZO", "ARGOLLA PLASTICA", "M.O: ARGOLLA PLASTICA"],
    "ARGOLLA METALICA": ["TELA 1", "REATA DE REFUERZO", "ARGOLLA METALICA", "M.O: ARGOLLA METALICA"],
    "3 PLIEGUES": ["TELA 1", "M.O: 3 PLIEGUES"], "TUBULAR BOLERO RECTO": ["TELA 1", "M.O: TUBULAR BOLERO RECTO"],
    "TUBULAR BOLERO ONDAS": ["TELA 1", "M.O: TUBULAR BOLERO ONDAS"]
}

CATALOGO_INSUMOS = {
    "BOTON": {"unidad": "UND", "opciones": [{"ref": "MADERA", "color": "CAOBA", "pvp": 1000}, {"ref": "MADERA", "color": "NATURAL", "pvp": 1000}, {"ref": "PLASTICO", "color": "BLANCO", "pvp": 500}, {"ref": "PLASTICO", "color": "NEGRO", "pvp": 500}]},
    "ARGOLLA PLASTICA": {"unidad": "UND", "opciones": [{"ref": "1 PULGADA", "color": "PLATA", "pvp": 2000}, {"ref": "1 PULGADA", "color": "DORADO", "pvp": 2200}, {"ref": "1.5 PULGADAS", "color": "PLATA", "pvp": 2500}]},
    "ARGOLLA METALICA": {"unidad": "UND", "opciones": [{"ref": "INOX 1 PULGADA", "color": "PLATA", "pvp": 3000}, {"ref": "INOX 1 PULGADA", "color": "NEGRO MATE", "pvp": 3500}, {"ref": "INOX 1.5 PULGADAS", "color": "PLATA", "pvp": 4000}]},
    "REATA 3/4": {"unidad": "MT", "opciones": [{"ref": "ALGODON", "color": "BLANCO", "pvp": 6000}, {"ref": "ALGODON", "color": "CRUDO", "pvp": 6000}, {"ref": "POLIESTER", "color": "BLANCO", "pvp": 5500}]},
    "REATA DE REFUERZO": {"unidad": "MT", "opciones": [{"ref": "ESTANDAR", "color": "TRANSPARENTE", "pvp": 2000}, {"ref": "PREMIUM", "color": "TRANSPARENTE", "pvp": 3000}]},
    "REATA BROCHES": {"unidad": "MT", "opciones": [{"ref": "PLASTICO", "color": "TRANSPARENTE", "pvp": 6000}, {"ref": "TELA", "color": "BLANCO", "pvp": 7000}]},
    "RODACHINES REATA BROCHES": {"unidad": "UND", "opciones": [{"ref": "PLASTICO", "color": "BLANCO", "pvp": 750}, {"ref": "SILICONA", "color": "TRANSPARENTE", "pvp": 900}]},
    "REATA ITALIANA": {"unidad": "MT", "opciones": [{"ref": "ESTANDAR", "color": "BLANCO", "pvp": 3500}, {"ref": "REFORZADA", "color": "BLANCO", "pvp": 4500}]},
    "RODACHINES REATA ITALIANA": {"unidad": "UND", "opciones": [{"ref": "ITALIANO", "color": "BLANCO", "pvp": 750}, {"ref": "PREMIUM", "color": "GRIS", "pvp": 1000}]},
    "UÑETA REATA ITALIANA": {"unidad": "UND", "opciones": [{"ref": "PLASTICA", "color": "BLANCO", "pvp": 500}, {"ref": "METALICA", "color": "CROMADO", "pvp": 800}]}
}

# =========================================================
# ESTADO
# =========================================================
def init_state():
    if 'pagina_actual' not in st.session_state:
        st.session_state.pagina_actual = 'cotizador'
    if 'datos_cotizacion' not in st.session_state:
        st.session_state.datos_cotizacion = {"cliente": {}, "vendedor": {}}
    if 'cortinas_resumen' not in st.session_state:
        st.session_state.cortinas_resumen = []
    if 'cortina_calculada' not in st.session_state:
        st.session_state.cortina_calculada = None
    if 'editando_index' not in st.session_state:
        st.session_state.editando_index = None
    if 'tipo_cortina_sel' not in st.session_state:
        st.session_state.tipo_cortina_sel = list(TIPOS_CORTINA.keys())[0]

# =========================================================
# PDF
# =========================================================
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

# =========================================================
# UI
# =========================================================
def sidebar():
    with st.sidebar:
        st.title("Megatex Cotizador")
        st.caption(f"Fuente de datos: {EXCEL_PATH}")
        if st.button("Recargar Excel"):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()
        st.markdown("---")
        if st.button("Crear Cotización", use_container_width=True):
            st.session_state.editando_index = None
            st.session_state.pagina_actual = 'cotizador'
            st.rerun()
        if st.button("Datos de la Cotización", use_container_width=True):
            st.session_state.pagina_actual = 'datos'
            st.rerun()
        if st.button("Ver Resumen Final", use_container_width=True):
            st.session_state.pagina_actual = 'resumen'
            st.rerun()

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

# =========================================================
# PANTALLA COTIZADOR
# =========================================================
def pantalla_cotizador():
    st.header("Configurar Cortina")
    st.subheader("1. Medidas y Opciones Finales")
    ancho = st.number_input("Ancho de la Ventana (m)", min_value=0.1, value=1.0, step=0.1, key="ancho")
    alto = st.number_input("Alto de la Cortina (m)", min_value=0.1, value=1.0, step=0.1, key="alto")
    cantidad_cortinas = st.number_input("Cantidad (und)", min_value=1, value=1, step=1, key="cantidad")
    partida = st.radio("¿Cortina partida?", ("SI", "NO"), horizontal=True, key="partida")
    st.markdown("---")
    st.subheader("2. Selecciona el Diseño")

    # 2.1 Tipo de Cortina
    tipo_opciones = list(TIPOS_CORTINA.keys())
    tipo_default = st.session_state.get("tipo_cortina_sel", tipo_opciones[0])
    tipo_cortina_sel = st.selectbox("Tipo de Cortina", options=tipo_opciones, index=tipo_opciones.index(tipo_default), key="tipo_cortina_sel")

    # 2.2 Diseño filtrado por el tipo seleccionado
    disenos_disponibles = TIPOS_CORTINA.get(tipo_cortina_sel, [])
    if not disenos_disponibles:
        st.error("No hay diseños disponibles para el tipo seleccionado. Verifica el Excel.")
        st.stop()

    diseno_previo = st.session_state.get("diseno_sel", disenos_disponibles[0])
    if diseno_previo not in disenos_disponibles:
        diseno_previo = disenos_disponibles[0]

    diseno_sel = st.selectbox("Diseño", options=disenos_disponibles, index=disenos_disponibles.index(diseno_previo), key="diseno_sel")

    # 2.3 Multiplicador
    valor_multiplicador = float(TABLA_DISENOS.get(diseno_sel, 2.0))
    multiplicador = st.number_input("Multiplicador", min_value=1.0, value=valor_multiplicador, step=0.1, key="multiplicador")

    # 2.4 Ancho Cortina (informativo: ancho ventana * multiplicador)
    ancho_cortina = st.session_state.ancho * multiplicador
    st.number_input("Ancho Cortina (m)", value=float(ancho_cortina), step=0.1, disabled=True, key="ancho_cortina_info")

    st.markdown("---")
    st.subheader("3. Selecciona la Tela")
    tipo_tela_sel = st.selectbox("Tipo de Tela", options=list(CATALOGO_TELAS.keys()), key="tipo_tela_sel")
    referencias = list(CATALOGO_TELAS[tipo_tela_sel].keys())
    ref_tela_sel = st.selectbox("Referencia", options=referencias, key="ref_tela_sel")
    colores = [item['color'] for item in CATALOGO_TELAS[tipo_tela_sel][ref_tela_sel]]
    color_tela_sel = st.selectbox("Color", options=colores, key="color_tela_sel")
    tela_info = next(item for item in CATALOGO_TELAS[tipo_tela_sel][ref_tela_sel] if item['color'] == color_tela_sel)
    st.number_input("Precio por Metro ($)", value=tela_info['pvp'], disabled=True, key="pvp_tela")

    st.markdown("---")
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

# =========================================================
# LÓGICA
# =========================================================
def calcular_y_mostrar_cotizacion():
    diseno = st.session_state.diseno_sel
    ancho = st.session_state.ancho
    alto = st.session_state.alto
    multiplicador = st.session_state.multiplicador
    num_cortinas = st.session_state.cantidad

    detalle_insumos = []
    subtotal = 0

    # Mano de obra según el diseño (obligatoria desde Excel)
    mo_key = f"M.O: {diseno}"
    mo_info = PRECIOS_MANO_DE_OBRA.get(mo_key, {"unidad": "MT", "pvp": 0})
    pvp_mo = mo_info["pvp"]

    # TELA 1
    cant_tela = ancho * multiplicador * num_cortinas
    pvp_tela = st.session_state.pvp_tela
    precio_tela = cant_tela * pvp_tela
    subtotal += precio_tela
    detalle_insumos.append({
        "Insumo": f"TELA: {st.session_state.ref_tela_sel} - {st.session_state.color_tela_sel}",
        "Cantidad": f"{cant_tela:.2f}", "Unidad": "MT",
        "P.V.P/Unit ($)": f"${pvp_tela:,.2f}", "Precio ($)": f"${precio_tela:,.2f}"
    })

    # Mano de obra (por metro)
    cant_mo = ancho * multiplicador * num_cortinas
    precio_mo = cant_mo * pvp_mo
    subtotal += precio_mo
    detalle_insumos.append({
        "Insumo": mo_key, "Cantidad": f"{cant_mo:.2f}", "Unidad": "MT",
        "P.V.P/Unit ($)": f"${pvp_mo:,.2f}", "Precio ($)": f"${precio_mo:,.2f}"
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
        "insumos_seleccion": {},
        "detalle_insumos": detalle_insumos, "subtotal": subtotal_sin_iva, "iva": iva, "total": total
    }

# =========================================================
# MAIN
# =========================================================
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
