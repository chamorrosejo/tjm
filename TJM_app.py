import streamlit as st
import pandas as pd
import os
from fpdf import FPDF
from datetime import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Megatex Cotizador",
    page_icon="Megatex.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DATOS DE NEGOCIO (CATÁLOGOS Y PRECIOS) ---
IVA_PERCENT = 0.19
DISTANCIA_BOTON = 0.2
DISTANCIA_OJALES = 0.14
PASO_RODACHIN = 0.06

TABLA_DISENOS = {
    "TUBULAR": 2, "PRESILLAS SIN BOTON": 2, "PRESILLAS CON BOTON": 2, "REATA 3/4": 2,
    "ONDA MODERNA REATA BROCHES": 2.8, "ONDA MODERNA REATA ITALIANA": 2.5,
    "ARGOLLA PLASTICA": 2.5, "ARGOLLA METALICA": 2.5, "TUBULAR BOLERO RECTO": 2,
    "TUBULAR BOLERO ONDAS": 2, "3 PLIEGUES": 2.5
}

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

PRECIOS_MANO_DE_OBRA = {
    "M.O: TUBULAR": {"unidad": "MT", "pvp": 5000}, "M.O: PRESILLAS SIN BOTON": {"unidad": "MT", "pvp": 7000},
    "M.O: PRESILLAS CON BOTON": {"unidad": "MT", "pvp": 8000}, "M.O: REATA 3/4": {"unidad": "MT", "pvp": 6000},
    "M.O: ONDA MODERNA REATA BROCHES": {"unidad": "MT", "pvp": 10000}, "M.O: ONDA MODERNA REATA ITALIANA": {"unidad": "MT", "pvp": 10000},
    "M.O: ARGOLLA PLASTICA": {"unidad": "MT", "pvp": 8000}, "M.O: ARGOLLA METALICA": {"unidad": "MT", "pvp": 8000},
    "M.O: 3 PLIEGUES": {"unidad": "MT", "pvp": 10000}, "M.O: TUBULAR BOLERO RECTO": {"unidad": "MT", "pvp": 8000},
    "M.O: TUBULAR BOLERO ONDAS": {"unidad": "MT", "pvp": 8000}
}

# --- INICIALIZACIÓN DEL ESTADO DE LA SESIÓN ---
def inicializar_estado():
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

# --- CLASE PARA GENERACIÓN DE PDF ---
class PDF(FPDF):
    def header(self):
        try:
            script_dir = os.path.dirname(__file__)
            logo_path = os.path.join(script_dir, "Megatex.png")
            self.image(logo_path, 10, 8, 33)
        except Exception:
            self.set_font('Arial', 'B', 12)
            self.cell(40, 10, 'Megatex Logo')

        self.set_font('Arial', 'B', 20)
        self.set_text_color(0, 80, 180)
        self.cell(0, 10, 'Cotización', 0, 1, 'R')
        self.set_font('Arial', '', 10)
        self.set_text_color(128)
        self.cell(0, 5, f"Fecha: {datetime.now().strftime('%Y-%m-%d')}", 0, 1, 'R')
        self.cell(0, 5, f"Cotización #: {datetime.now().strftime('%Y%m%d%H%M')}", 0, 1, 'R')
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, 'Gracias por su preferencia.', 0, 0, 'C')
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'R')

# --- FUNCIONES DE LA INTERFAZ DE USUARIO (UI) ---
def mostrar_sidebar():
    with st.sidebar:
        try:
            script_dir = os.path.dirname(__file__)
            logo_path = os.path.join(script_dir, "Megatex.png")
            st.image(logo_path, width=150)
        except Exception:
            st.warning("No se pudo cargar el logo 'Megatex.png'.")

        st.title("Megatex Cotizador")
        
        if st.button("Crear Cotización", icon="✍️", use_container_width=True):
            st.session_state.editando_index = None
            st.session_state.pagina_actual = 'cotizador'
            st.rerun()
        
        st.markdown("---")
        if st.button("Datos de la Cotización", use_container_width=True):
            st.session_state.pagina_actual = 'datos'
            st.rerun()
        if st.button("Ver Resumen Final", use_container_width=True):
            st.session_state.pagina_actual = 'resumen'
            st.rerun()
        st.markdown("---")

def mostrar_pantalla_datos():
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

    if st.button("Guardar Datos", type="primary"):
        st.session_state.pagina_actual = 'resumen'
        st.success("Datos guardados correctamente.")
        st.rerun()

def mostrar_pantalla_resumen():
    st.header("Resumen de la Cotización")
    cliente = st.session_state.datos_cotizacion['cliente']
    vendedor = st.session_state.datos_cotizacion['vendedor']
    if any(cliente.values()) or any(vendedor.values()):
        with st.container(border=True):
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
        col_header = st.columns((0.5, 2, 3, 1))
        headers = ["Línea", "Nombre", "Características", "Precio"]
        for col, header in zip(col_header, headers):
            col.markdown(f"**{header}**")

        for i, cortina in enumerate(st.session_state.cortinas_resumen):
            with st.container(border=True):
                col_data = st.columns((0.5, 2, 3, 1))
                col_data[0].markdown(f"**{i+1}**")
                with col_data[1]:
                    st.markdown(f"**{cortina['diseno']}**")
                    st.markdown(f"Dimensiones: {cortina['ancho']:.2f} mts x {cortina['alto']:.2f} mts")
                    st.markdown(f"Cantidad: 1 und")
                    partida_texto = "Sí" if cortina['partida'] == "SI" else "No"
                    st.markdown(f"Partida: {partida_texto}")
                with col_data[2]:
                    caracteristicas_md = f"- **Tela:** {cortina['tela']['referencia']} {cortina['tela']['color']}\n"
                    for nombre, sel in cortina.get('insumos_seleccion', {}).items():
                         caracteristicas_md += f"- **{nombre}:** {sel['ref']} {sel['color']}\n"
                    st.markdown(caracteristicas_md)
                col_data[3].markdown(f"**${cortina['total']:,.2f}**")
        
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            cortina_a_editar_idx = st.selectbox(
                "Selecciona una cortina para editar:", 
                options=[(f"Línea {i+1}: {cortina['diseno']}", i) for i, cortina in enumerate(st.session_state.cortinas_resumen)],
                index=None, placeholder="Seleccionar...", format_func=lambda x: x[0], key="edit_select"
            )
            if st.button("Editar Cortina Seleccionada") and cortina_a_editar_idx is not None:
                iniciar_edicion(cortina_a_editar_idx[1])
        with c2:
            cortina_a_eliminar_idx = st.selectbox(
                "Selecciona una cortina para eliminar:", 
                options=[(f"Línea {i+1}: {cortina['diseno']}", i) for i, cortina in enumerate(st.session_state.cortinas_resumen)],
                index=None, placeholder="Seleccionar...", format_func=lambda x: x[0], key="delete_select"
            )
            if st.button("Eliminar Cortina Seleccionada", type="primary") and cortina_a_eliminar_idx is not None:
                del st.session_state.cortinas_resumen[cortina_a_eliminar_idx[1]]
                st.success("Cortina eliminada.")
                st.rerun()

    total_final = sum(c['total'] for c in st.session_state.cortinas_resumen)
    iva = total_final * IVA_PERCENT
    subtotal = total_final - iva
    
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("Subtotal", f"${subtotal:,.2f}")
    c2.metric(f"IVA ({IVA_PERCENT:.0%})", f"${iva:,.2f}")
    c3.metric("Total Cotización", f"${total_final:,.2f}")

    if st.session_state.cortinas_resumen:
        pdf_bytes = generar_pdf(st.session_state.datos_cotizacion, st.session_state.cortinas_resumen)
        st.download_button(
            label="Descargar PDF",
            data=pdf_bytes,
            file_name=f"cotizacion_megatex_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

def mostrar_pantalla_cotizador():
    header_text = "Editando Cortina" if st.session_state.editando_index is not None else "Configurar Cortina"
    st.header(header_text)
    st.subheader("1. Medidas y Opciones Finales")
    ancho = st.number_input("Ancho de la Ventana (m)", min_value=0.1, value=1.0, step=0.1, key="ancho")
    alto = st.number_input("Alto de la Cortina (m)", min_value=0.1, value=1.0, step=0.1, key="alto")
    partida = st.radio("¿Cortina partida?", ("SI", "NO"), horizontal=True, key="partida")
    st.markdown("---")
    st.subheader("2. Selecciona el Diseño")
    diseno_sel = st.selectbox("Diseño", options=list(TABLA_DISENOS.keys()), key="diseno_sel")
    valor_multiplicador = float(TABLA_DISENOS.get(diseno_sel, 2.0))
    multiplicador = st.number_input("Multiplicador", min_value=1.0, value=valor_multiplicador, step=0.1, key="multiplicador")
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
    st.subheader("4. Selecciona los Insumos Adicionales")
    insumos_requeridos = [ins for ins in BOM.get(diseno_sel, []) if ins in CATALOGO_INSUMOS]
    if not insumos_requeridos:
        st.info("Este diseño no requiere insumos adicionales seleccionables.")
    if 'insumos_seleccion' not in st.session_state:
        st.session_state.insumos_seleccion = {}
    for insumo in insumos_requeridos:
        with st.container(border=True):
            st.markdown(f"**Insumo: {insumo}**")
            catalogo = CATALOGO_INSUMOS[insumo]
            refs = sorted(list(set(opt['ref'] for opt in catalogo['opciones'])))
            ref_sel = st.selectbox(f"Referencia {insumo}", options=refs, key=f"ref_{insumo}")
            colores_insumo = sorted(list(set(opt['color'] for opt in catalogo['opciones'] if opt['ref'] == ref_sel)))
            color_sel = st.selectbox(f"Color {insumo}", options=colores_insumo, key=f"color_{insumo}")
            insumo_info = next(opt for opt in catalogo['opciones'] if opt['ref'] == ref_sel and opt['color'] == color_sel)
            st.number_input(f"Precio por {catalogo['unidad']} ($)", value=insumo_info['pvp'], disabled=True, key=f"pvp_{insumo}")
            st.session_state.insumos_seleccion[insumo] = {'ref': ref_sel, 'color': color_sel, 'pvp': insumo_info['pvp'], 'unidad': catalogo['unidad']}
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
        action_button_label = "Guardar Cambios" if st.session_state.editando_index is not None else "Añadir al Resumen"
        if st.button(action_button_label, type="primary", use_container_width=True):
            guardar_cortina()

# --- FUNCIONES DE LÓGICA DE NEGOCIO Y PDF ---
def generar_pdf(datos_cotizacion, cortinas_resumen):
    pdf = PDF('P', 'mm', 'Letter')
    pdf.add_page()
    
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(95, 7, 'Cliente', 0, 0, 'L')
    pdf.cell(95, 7, 'Vendedor', 0, 1, 'L')
    pdf.set_font('Arial', '', 10)
    
    cliente = datos_cotizacion['cliente']
    vendedor = datos_cotizacion['vendedor']
    
    pdf.cell(95, 5, f"Nombre: {cliente.get('nombre', '')}", 0, 0, 'L')
    pdf.cell(95, 5, f"Nombre: {vendedor.get('nombre', '')}", 0, 1, 'L')
    pdf.cell(95, 5, f"Cedula/NIT: {cliente.get('cedula', '')}", 0, 0, 'L')
    pdf.cell(95, 5, f"Telefono: {vendedor.get('telefono', '')}", 0, 1, 'L')
    pdf.cell(95, 5, f"Telefono: {cliente.get('telefono', '')}", 0, 1, 'L')
    pdf.cell(95, 5, f"Direccion: {cliente.get('direccion', '')}", 0, 1, 'L')
    pdf.cell(95, 5, f"Correo: {cliente.get('correo', '')}", 0, 1, 'L')
    pdf.ln(10)

    pdf.set_font('Arial', 'B', 10)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(15, 7, 'Linea', 1, 0, 'C', 1)
    pdf.cell(60, 7, 'Nombre', 1, 0, 'C', 1)
    pdf.cell(85, 7, 'Caracteristicas', 1, 0, 'C', 1)
    pdf.cell(30, 7, 'Precio', 1, 1, 'C', 1)

    pdf.set_font('Arial', '', 9)
    for i, cortina in enumerate(cortinas_resumen):
        line_height = 5
        y_before = pdf.get_y()
        
        pdf.set_xy(25, y_before)
        partida_texto = "Sí" if cortina['partida'] == "SI" else "No"
        nombre_texto = f"{cortina['diseno']}\nDimensiones: {cortina['ancho']:.2f} mts x {cortina['alto']:.2f} mts\nCantidad: 1 und\nPartida: {partida_texto}"
        pdf.multi_cell(60, line_height, nombre_texto, 0, 'L')
        y_after_nombre = pdf.get_y()

        pdf.set_xy(85, y_before)
        caracteristicas_texto = f"- Tela: {cortina['tela']['referencia']} {cortina['tela']['color']}\n"
        for nombre, sel in cortina.get('insumos_seleccion', {}).items():
            caracteristicas_texto += f"- {nombre}: {sel['ref']} {sel['color']}\n"
        pdf.multi_cell(85, line_height, caracteristicas_texto, 0, 'L')
        y_after_caracteristicas = pdf.get_y()

        max_y = max(y_after_nombre, y_after_caracteristicas)
        row_height = max_y - y_before

        pdf.set_xy(10, y_before)
        pdf.cell(15, row_height, str(i + 1), 1, 0, 'C')
        pdf.set_xy(25, y_before)
        pdf.cell(60, row_height, '', 1, 0, 'L')
        pdf.set_xy(85, y_before)
        pdf.cell(85, row_height, '', 1, 0, 'L')
        pdf.set_xy(170, y_before)
        pdf.cell(30, row_height, f"${cortina['total']:,.2f}", 1, 1, 'R')

    total_final = sum(c['total'] for c in cortinas_resumen)
    iva = total_final * IVA_PERCENT
    subtotal = total_final - iva
    
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(160, 8, 'Subtotal:', 0, 0, 'R')
    pdf.cell(30, 8, f"${subtotal:,.2f}", 1, 1, 'R')
    pdf.cell(160, 8, f'IVA ({IVA_PERCENT:.0%}):', 0, 0, 'R')
    pdf.cell(30, 8, f"${iva:,.2f}", 1, 1, 'R')
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(160, 10, 'Total:', 0, 0, 'R')
    pdf.cell(30, 10, f"${total_final:,.2f}", 1, 1, 'R')

    return bytes(pdf.output())

def iniciar_edicion(index):
    st.session_state.editando_index = index
    cortina = st.session_state.cortinas_resumen[index]
    st.session_state.ancho = cortina['ancho']
    st.session_state.alto = cortina['alto']
    st.session_state.partida = cortina['partida']
    st.session_state.diseno_sel = cortina['diseno']
    st.session_state.multiplicador = cortina['multiplicador']
    st.session_state.tipo_tela_sel = cortina['tela']['tipo']
    st.session_state.ref_tela_sel = cortina['tela']['referencia']
    st.session_state.color_tela_sel = cortina['tela']['color']
    for nombre, seleccion in cortina.get('insumos_seleccion', {}).items():
        st.session_state[f"ref_{nombre}"] = seleccion['ref']
        st.session_state[f"color_{nombre}"] = seleccion['color']
    st.session_state.pagina_actual = 'cotizador'
    st.rerun()

def guardar_cortina():
    if st.session_state.editando_index is not None:
        st.session_state.cortinas_resumen[st.session_state.editando_index] = st.session_state.cortina_calculada
        st.success("Cortina actualizada en el resumen.")
        st.session_state.editando_index = None
    else:
        st.session_state.cortinas_resumen.append(st.session_state.cortina_calculada)
        st.success("Cortina añadida al resumen.")
    st.session_state.cortina_calculada = None
    st.session_state.pagina_actual = 'resumen'
    st.rerun()

def calcular_y_mostrar_cotizacion():
    diseno = st.session_state.diseno_sel
    ancho = st.session_state.ancho
    alto = st.session_state.alto
    multiplicador = st.session_state.multiplicador
    detalle_insumos = []
    subtotal = 0
    insumos_requeridos_diseno = BOM.get(diseno, [])
    insumos_requeridos_actuales = [ins for ins in insumos_requeridos_diseno if ins in CATALOGO_INSUMOS]
    insumos_seleccion_filtrados = {
        insumo: st.session_state.insumos_seleccion[insumo]
        for insumo in insumos_requeridos_actuales
        if insumo in st.session_state.insumos_seleccion
    }
    for nombre_insumo in insumos_requeridos_diseno:
        cantidad = 0; pvp = 0; unidad = ''; nombre_mostrado = nombre_insumo
        if nombre_insumo in ["RODACHINES REATA BROCHES", "RODACHINES REATA ITALIANA", "UÑETA REATA ITALIANA"]:
            cantidad = -(-ancho // PASO_RODACHIN)
        elif nombre_insumo in ["ARGOLLA PLASTICA", "ARGOLLA METALICA"]:
            cantidad = -(-(ancho * multiplicador) // DISTANCIA_OJALES)
        elif nombre_insumo == "BOTON":
            cantidad = -(-(ancho * multiplicador) // DISTANCIA_BOTON)
        else:
            cantidad = ancho * multiplicador
        if nombre_insumo == "TELA 1":
            pvp = st.session_state.pvp_tela
            unidad = "MT"
            nombre_mostrado = f"TELA: {st.session_state.ref_tela_sel} - {st.session_state.color_tela_sel}"
        elif nombre_insumo in CATALOGO_INSUMOS:
            seleccion = insumos_seleccion_filtrados[nombre_insumo]
            pvp = seleccion['pvp']
            unidad = seleccion['unidad']
            nombre_mostrado = f"{nombre_insumo} ({seleccion['ref']} - {seleccion['color']})"
        elif nombre_insumo in PRECIOS_MANO_DE_OBRA:
            info = PRECIOS_MANO_DE_OBRA[nombre_insumo]
            pvp = info['pvp']
            unidad = info['unidad']
        precio_total_insumo = cantidad * pvp
        subtotal += precio_total_insumo
        detalle_insumos.append({
            "Insumo": nombre_mostrado, "Cantidad": f"{cantidad:.2f}", "Unidad": unidad,
            "P.V.P/Unit ($)": f"${pvp:,.2f}", "Precio ($)": f"${precio_total_insumo:,.2f}"
        })
    total = subtotal
    iva = total * IVA_PERCENT
    subtotal = total - iva
    st.session_state.cortina_calculada = {
        "diseno": diseno, "multiplicador": multiplicador, "ancho": ancho, "alto": alto,
        "partida": st.session_state.partida,
        "tela": {"tipo": st.session_state.tipo_tela_sel, "referencia": st.session_state.ref_tela_sel, "color": st.session_state.color_tela_sel},
        "insumos_seleccion": insumos_seleccion_filtrados,
        "detalle_insumos": detalle_insumos, "subtotal": subtotal, "iva": iva, "total": total
    }

def generar_nombre_cortina(cortina):
    ancho_calc = cortina['ancho'] * cortina['multiplicador']
    partida_txt = "Partida" if cortina['partida'] == "SI" else "Entera"
    tela_txt = f"TELA: {cortina['tela']['tipo']} {cortina['tela']['referencia']} {cortina['tela']['color']}"
    insumos_txt_list = []
    for nombre, sel in cortina.get('insumos_seleccion', {}).items():
        insumos_txt_list.append(f"{nombre} {sel['ref']} {sel['color']}")
    insumos_txt = f"[{', '.join(insumos_txt_list)}]" if insumos_txt_list else ""
    return f"{cortina['diseno']}, {tela_txt}, {ancho_calc:.2f}x{cortina['alto']:.2f}m {partida_txt} {insumos_txt}"

# --- PUNTO DE ENTRADA PRINCIPAL DE LA APLICACIÓN ---
def main():
    inicializar_estado()
    mostrar_sidebar()
    if st.session_state.pagina_actual == 'datos':
        mostrar_pantalla_datos()
    elif st.session_state.pagina_actual == 'resumen':
        mostrar_pantalla_resumen()
    elif st.session_state.pagina_actual == 'cotizador':
        mostrar_pantalla_cotizador()
    else:
        mostrar_pantalla_cotizador()

if __name__ == "__main__":
    main()
