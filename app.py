import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
from PIL import Image

st.set_page_config(page_title="Eczane Şeffaf Hesap", page_icon="💊", layout="wide")

st.title("💊 Eczane Akıllı Hesap Dökümü")

try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
except:
    st.error("⚠️ Sistem Hatası: Lütfen Streamlit 'Secrets' bölümüne API anahtarınızı ekleyin.")
    st.stop()

# --- YAZDIR/İNDİR BUTONLU VE FİYAT FARKI DÜZENLEMELİ ŞABLON ---
TEMPLATE_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
    <style>
        :root { --primary: #00695c; --fark: #e67e22; --bg: #f4f7f6; --text: #333; }
        body { font-family: 'Segoe UI', sans-serif; background: transparent; display: flex; flex-direction: column; align-items: center; padding: 10px; color: var(--text); }
        
        .action-buttons { display: flex; gap: 15px; margin-bottom: 20px; width: 100%; max-width: 500px; justify-content: center; }
        .btn { border: none; padding: 12px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 14px; color: white; display: flex; align-items: center; gap: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); transition: 0.2s; }
        .btn-print { background-color: #2980b9; }
        .btn-print:hover { background-color: #1c5982; }
        .btn-jpg { background-color: #27ae60; }
        .btn-jpg:hover { background-color: #1e8449; }

        .container { width: 100%; max-width: 500px; background: white; border-radius: 20px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border: 1px solid #ddd; }
        .header { background: var(--primary); color: white; padding: 25px; text-align: left; }
        .header h1 { margin: 0; font-size: 18px; opacity: 0.9; font-weight: 400; }
        .patient-name { font-size: 22px; font-weight: bold; margin-top: 5px; }
        .recete-block { padding: 20px; border-bottom: 8px solid var(--bg); }
        .recete-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #eee; }
        .date-tag { font-weight: bold; color: var(--primary); font-size: 14px; }
        .kod-tag { font-size: 11px; color: #999; border: 1px solid #eee; padding: 2px 6px; border-radius: 4px; }
        .ilac-row { display: flex; justify-content: space-between; font-size: 12.5px; padding: 8px 0; border-bottom: 1px dashed #f0f0f0; }
        .fark-info { color: var(--fark); font-weight: bold; font-size: 11px; display: block; margin-top: 2px; }
        .details-box { background: #f9fdfc; padding: 12px; margin-top: 10px; border-radius: 10px; border: 1px solid #edf5f4; }
        .detail-line { display: flex; justify-content: space-between; font-size: 11.5px; color: #666; margin-bottom: 4px; }
        .yansiyan-row { display: flex; justify-content: space-between; font-size: 15px; font-weight: bold; color: #27ae60; margin-top: 8px; padding-top: 8px; border-top: 1px solid #d1e8e5; }
        .grand-footer { background: var(--primary); color: white; padding: 25px; display: flex; justify-content: space-between; align-items: center; }
        .grand-footer .price { font-size: 28px; font-weight: bold; }
        
        @media print {
            .action-buttons { display: none !important; }
            body { padding: 0; background: white; }
            .container { box-shadow: none; border: none; border-radius: 0; }
        }
    </style>
</head>
<body>

    <div class="action-buttons no-print">
        <button class="btn btn-print" onclick="window.print()">🖨️ Yazdır</button>
        <button class="btn btn-jpg" onclick="downloadJPG()">📸 JPG İndir (WhatsApp)</button>
    </div>

    <div class="container" id="capture-area">
        </div>

    <script>
        function downloadJPG() {
            html2canvas(document.getElementById('capture-area'), { scale: 2, backgroundColor: "#ffffff" }).then(canvas => {
                let link = document.createElement('a');
                link.download = 'Eczane_Hesap_Dokumu.jpg';
                link.href = canvas.toDataURL('image/jpeg', 0.9);
                link.click();
            });
        }
    </script>
</body>
</html>
"""

col1, col2 = st.columns([1, 2.5], gap="large")

with col1:
    st.subheader("📥 1. Veri Girişi")
    
    tab1, tab2 = st.tabs(["📄 Metin Yapıştır", "📸 Görsel Yükle/Yapıştır"])

    with tab1:
        raw_text = st.text_area("Cari Metnini Buraya Yapıştırın:", height=250)

    with tab2:
        # CTRL+V İpucunu buraya ekledik
        st.info("💡 **İpucu:** Ekran görüntüsü aldıktan sonra sayfa üzerindeyken **CTRL+V** yaparak görseli direkt yapıştırabilirsiniz!")
        uploaded_file = st.file_uploader("Görsel veya PDF yükleyin", type=["jpg", "jpeg", "png", "pdf"])
        if uploaded_file:
            if "pdf" in uploaded_file.type:
                st.info(f"📄 PDF hazır: {uploaded_file.name}")
            else:
                st.image(uploaded_file, caption="Sisteme Eklenen Görsel", use_column_width=True)

    submit_button = st.button("✨ Şeffaf Döküm Oluştur", type="primary", use_container_width=True)

with col2:
    st.subheader("🧾 2. Hastaya Verilecek Döküm")
    
    if submit_button:
        content_to_send = []
        
        if uploaded_file:
            if "pdf" in uploaded_file.type:
                content_to_send.append({"mime_type": "application/pdf", "data": uploaded_file.getvalue()})
                prompt_intro = "Bu PDF dosyasındaki eczane cari dökümünü incele."
            else:
                img = Image.open(uploaded_file)
                content_to_send.append(img)
                prompt_intro = "Bu görseldeki eczane cari dökümünü incele."
        elif raw_text.strip() != "":
            content_to_send.append(raw_text)
            prompt_intro = "Aşağıdaki eczane cari metnini incele."
        else:
            st.warning("Lütfen işlem yapmadan önce sol taraftan bir metin girin veya dosya yükleyin.")
            st.stop()

        with st.spinner("Yapay zeka verileri şablona diziyor..."):
            try:
                model = genai.GenerativeModel('gemini-2.5-flash')
                
                full_prompt = f"""
                {prompt_intro}
                
                Verdiğim HTML/CSS şablonunu KESİNLİKLE BOZMADAN kullanarak, metindeki/görseldeki BÜTÜN reçeteleri, ilaçları ve fiyatları HTML içine yerleştir.
                
                TALİMATLAR:
                1. Hiçbir ilacı atlama. Reçete tarihlerini ve kodlarını doğru oku.
                2. Her reçete için 'Hasta Katılım Payı', 'Muayene Ücreti', 'Reçete Payı' kalemlerini ayıkla.
                3. İlaçların altındaki fark kısmına KESİNLİKLE sadece "Fark" yerine "Fiyat Farkı" yaz. (Örn: Fiyat Farkı: 15.00 TL)
                4. 'Hastaya Yansıyan' kısmını her reçete için hesapla/bul.
                5. En altta Genel Bakiye'yi göster.
                6. SADECE HTML kodu üret.
                
                TASARIM ŞABLONU:
                {TEMPLATE_HTML}
                """
                
                response = model.generate_content([full_prompt] + content_to_send)
                final_html = response.text.replace("```html", "").replace("```", "").strip()
                
                st.success("Tasarım Başarıyla Oluşturuldu!")
                
                components.html(final_html, height=900, scrolling=True)
                
            except Exception as e:
                st.error(f"Beklenmeyen bir hata oluştu: {str(e)}")
    else:
        st.info("👈 Lütfen sol taraftan veriyi girip oluştur butonuna basın.")
