"""
pip install streamlit reportlab streamlit-pdf-viewer
"""

import streamlit as st
import base64
from io import BytesIO
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from streamlit_pdf_viewer import pdf_viewer

st.set_page_config(page_title="Gerador de Etiquetas Pimaco A4248", layout="wide")
st.title("Gerador de Etiquetas Pimaco A4248")

def gerar_pdf(rotulos):
    page_width, page_height = A4

    cols = 6
    rows = 16
    label_width = 31 * mm
    label_height = 17 * mm
    qr_size = 13 * mm

    gap_col = 2 * mm
    gap_row = 0 * mm

    total_width = cols * label_width + (cols - 1) * gap_col
    total_height = rows * label_height + (rows - 1) * gap_row
    margin_left = (page_width - total_width) / 2
    margin_top = (page_height - total_height) / 2

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    data_atual = datetime.now().strftime("%d/%m/%Y")
    hora_atual = datetime.now().strftime("%H:%M:%S")

    total_labels = len(rotulos)
    labels_per_page = cols * rows

    for page_start in range(0, total_labels, labels_per_page):
        page_labels = rotulos[page_start:page_start + labels_per_page]

        for idx, label_text in enumerate(page_labels):
            row = idx // cols
            col = idx % cols

            x = margin_left + col * (label_width + gap_col)
            y = page_height - margin_top - (row + 1) * label_height - row * gap_row

            # QR Code
            qr_margin = 1 * mm
            qr_x = x + qr_margin
            qr_y = y + (qr_size / 2) - 5

            qr_widget = qr.QrCodeWidget(label_text)
            bounds = qr_widget.getBounds()
            qr_width = bounds[2] - bounds[0]
            qr_height = bounds[3] - bounds[1]

            drawing = Drawing(qr_size, qr_size)
            scale = min(qr_size / qr_width, qr_size / qr_height)
            drawing.add(qr_widget)
            drawing.scale(scale, scale)
            drawing.drawOn(c, qr_x, qr_y)

            # Área de texto
            text_x_start = qr_x + qr_size + 1 * mm
            text_width = label_width - (text_x_start - x) - 1 * mm
            text_area_x = text_x_start
            text_area_width = text_width

            c.setFillColorRGB(0, 0, 0)
            c.setFont("Helvetica-Bold", 8)
            label_y = y + label_height - 3 * mm
            c.drawCentredString(text_area_x + text_area_width / 2, label_y, label_text)

            c.setFont("Helvetica", 7)
            data_y = label_y - 3.5 * mm
            c.drawCentredString(text_area_x + text_area_width / 2, data_y, data_atual)

            hora_y = data_y - 3.5 * mm
            c.drawCentredString(text_area_x + text_area_width / 2, hora_y, hora_atual)

        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer.getvalue()

# Sidebar
st.sidebar.header("Configurações")
with st.sidebar.form("config_form"):
    inicial = st.number_input("Número inicial", value=1, step=1, min_value=1)
    final = st.number_input("Número final", value=50, step=1, min_value=1)
    prefixo = st.text_input("Prefixo", value="L-01.05.")
    digitos = st.number_input("Quantidade de dígitos", value=3, step=1, min_value=1)
    gerar = st.form_submit_button("Gerar")

if gerar:
    if inicial > final:
        st.error("O número inicial deve ser menor ou igual ao final.")
    else:
        rotulos = [f"{prefixo}{str(num).zfill(digitos)}" for num in range(inicial, final + 1)]
        st.success(f"Gerando {len(rotulos)} etiquetas de {rotulos[0]} a {rotulos[-1]}")

        pdf_bytes = gerar_pdf(rotulos)

        # --- Visualização inline com streamlit-pdf-viewer ---
        st.markdown("### 📄 Visualização do PDF")
        try:
            pdf_viewer(pdf_bytes, width=1000, height=800)
        except Exception as e:
            st.error(f"Erro ao exibir o PDF: {e}")
            st.info("Use os botões abaixo para salvar ou imprimir.")

        # --- Botões Salvar e Imprimir lado a lado ---
        col1, col2 = st.columns(2)

        # Codifica o PDF em base64 para uso nos botões
        base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
        pdf_data_uri = f"data:application/pdf;base64,{base64_pdf}"

        with col1:
            # Botão de download (Salvar)
            st.download_button(
                label="💾 Salvar PDF",
                data=pdf_bytes,
                file_name="etiquetas_pimaco_a4248.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        with col2:
            # Botão de impressão – abre o PDF em nova aba e chama print()
            print_html = f"""
            <button onclick="
                var win = window.open('{pdf_data_uri}', '_blank');
                win.onload = function() {{
                    win.print();
                }};
            " style="
                background-color: #2196F3;
                color: white;
                padding: 0.5rem 1rem;
                border: none;
                border-radius: 0.5rem;
                font-weight: bold;
                font-size: 1rem;
                cursor: pointer;
                width: 100%;
            ">
                🖨️ Imprimir PDF
            </button>
            """
            st.markdown(print_html, unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.info(
    """
    **Instruções**
    1. Preencha os dados no painel lateral.
    2. Clique em **Gerar**.
    3. O PDF será exibido na área principal.
    4. Use **Salvar PDF** para baixar o arquivo.
    5. Use **Imprimir PDF** para abrir e imprimir diretamente.
    """
)
