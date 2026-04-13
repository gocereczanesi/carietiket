Haklısın, Botanik dökümünde o bilgiler çok net görünüyor ve hastanın neye ne kadar ödediğini anlaması için adet ve fiyat bilgisi şart. Ayrıca her reçetenin başında isim yazdığı için, sistemin bu isimleri de doğru yakalayıp her bloğun içine işlemesi daha güvenli olur.

İstediğin güncellemeleri yaptım:
1.  **Adet ve Fiyat Eklendi:** Her ilacın yanında kaç adet olduğu ve birim fiyatı artık görünüyor.
2.  **Kişiye Özel Reçete Takibi:** Her reçete bloğunun içine "Hasta:" alanı eklendi. Böylece dökümde farklı isimler varsa karıştırılmayacak.
3.  **Hız ve Kilitlenme Koruması:** Mevcut yüksek hız ve kilitlenme koruması yapısı korundu.

Lütfen `app.py` dosyanın içini tamamen silip bu en gelişmiş versiyonu yapıştır:

```python
import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
import json
import re
from PIL import Image

# Sayfa Ayarları
st.set_page_config(page_title="Eczane Cari Kart Dökümü", page_icon="💊", layout="wide")

st.title("💊 Eczane Cari Kart Dökümü")

# Metin kutusunu temizleme fonksiyonu
if "raw_text_input" not in st.session_state:
    st.session_state["raw_text_input"] = ""

def clear_text():
    st.session_state["raw_text_input"] = ""

try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
except:
    st.error("⚠️ Sistem Hatası: Lütfen Streamlit 'Secrets' bölümüne API anahtarınızı ekleyin.")
    st.stop()

# --- HTML ŞABLONLARI ---
TEMPLATE_TOP = """
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
        .recete-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid #eee; }
        .recete-patient { font-size: 13px; font-weight: bold; color: #555; margin-bottom: 10px; display: block; }
        .date-tag { font-weight: bold; color: var(--primary); font-size: 14px; }
        .kod-tag { font-size: 11px; color: #999; border: 1px solid #eee; padding: 2px 6px; border-radius: 4px; }
        
        .ilac-row { padding: 10px 0; border-bottom: 1px dashed #f0f0f0; }
        .ilac-main { display: flex; justify-content: space-between; font-size: 13px; font-weight: 500; }
        .ilac-sub { display: flex; justify-content: space-between; font-size: 11px; color: #777; margin-top: 2px; }
        
        .fark-info { color: var(--fark); font-weight: bold; }
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
"""

TEMPLATE_BOTTOM = """
    </div>
    <script>
        function downloadJPG() {
            html2canvas(document.getElementById('capture-area'), { scale: 2, backgroundColor: "#ffffff" }).then(canvas => {
                let link = document.createElement('a');
                link.download = 'Eczane_Cari_Kart_Dokumu.jpg';
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
    
    tab1, tab2 = st.tabs(["📄 Metin Yapıştır", "📸 Görsel Yükle"])

    with tab1:
        header_col, btn_col = st.columns([3, 1])
        with header_col:
            st.markdown("<p style='margin-top: 10px; margin-bottom: 0px; font-weight: bold;'>Botanik Verisini Yapıştırın:</p>", unsafe_allow_html=True)
        with btn_col:
            st.button("🗑️ Temizle", on_click=clear_text, use_container_width=True)
            
        raw_text = st.text_area("Gizli Label", key="raw_text_input", label_visibility="collapsed", height=250)

    with tab2:
        st.info("💡 **İpucu:** Sayfa üzerindeyken **CTRL+V** yaparak görseli direkt yapıştırabilirsiniz!")
        uploaded_file = st.file_uploader("Görsel veya PDF yükleyin", type=["jpg", "jpeg", "png", "pdf"])
        if uploaded_file:
            if "pdf" in uploaded_file.type:
                st.info(f"📄 PDF hazır: {uploaded_file.name}")
            else:
                st.image(uploaded_file, caption="Sisteme Eklenen Görsel", use_column_width=True)

    submit_button = st.button("✨ Cari Kart Oluştur", type="primary", use_container_width=True)

with col2:
    st.subheader("🧾 2. Hastaya Verilecek Döküm")
    
    if submit_button:
        content_to_send = []
        
        if uploaded_file:
            if "pdf" in uploaded_file.type:
                content_to_send.append({"mime_type": "application/pdf", "data": uploaded_file.getvalue()})
            else:
                img = Image.open(uploaded_file)
                content_to_send.append(img)
        elif raw_text.strip() != "":
            content_to_send.append(raw_text)
        else:
            st.warning("Lütfen işlem yapmadan önce sol taraftan bir metin girin veya dosya yükleyin.")
            st.stop()

        with st.spinner("🚀 Veriler işleniyor..."):
            try:
                generation_config = {"temperature": 0.0}
                model = genai.GenerativeModel('gemini-2.5-flash', generation_config=generation_config)
                
                full_prompt = """
                Aşağıdaki Botanik eczane cari metnini/görselini incele ve sadece JSON formatında yanıt ver. 
                
                ÖNEMLİ KURALLAR:
                1. Her reçetenin başında yazan HASTA ADINI ('... Reçetesi' veya '... Perakendesi' yazan yerdeki isim) mutlaka her blok için ayrı yakala.
                2. Her ilaç için ADET (Miktar) ve FİYAT (Birim fiyat veya Toplam fiyat) bilgilerini mutlaka çek.
                3. "Fiyat Farkı" kısmını her ilaç için kontrol et, varsa çek.
                4. Reçeteler için HESAPLAR satırındaki tutarları (Katılım Payları, Muayene, Reçete Payı) ayıkla.
                5. "genel_bakiye" en sağ sütundaki son kümülatif rakamdır.
                
                JSON ŞEMASI:
                {
                  "hasta_adi_genel": "Ana Hasta Adı",
                  "receteler": [
                    {
                      "tarih": "GG.AA.YYYY",
                      "hasta_adi_ozel": "Bu Reçetedeki İsim",
                      "kod": "Reçete Kodu",
                      "ilaclar": [
                        {"ad": "İlaç Adı", "adet": "1", "fiyat": "0.00", "fiyat_farki": "0.00"}
                      ],
                      "katilim_payi": "0.00", "muayene_ucreti": "0.00", "recete_payi": "0.00", "yansiyan": "0.00"
                    }
                  ],
                  "genel_bakiye": "0.00"
                }
                """
                
                response = model.generate_content([full_prompt] + content_to_send)
                raw_response = response.text.replace("```json", "").replace("```", "").strip()
                json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
                data = json.loads(json_match.group(0) if json_match else raw_response)
                
                inner_html = f"""
                <div class="header">
                    <h1>Eczane Cari Kart Dökümü</h1>
                    <div class="patient-name">{data.get('hasta_adi_genel', 'Hasta Bilgisi')}</div>
                </div>
                """
                
                for r in data.get('receteler', []):
                    inner_html += f"""
                    <div class="recete-block">
                        <div class="recete-patient">Hasta: {r.get('hasta_adi_ozel', '')}</div>
                        <div class="recete-header">
                            <span class="date-tag">{r.get('tarih', '')}</span>
                            <span class="kod-tag">{r.get('kod', '')}</span>
                        </div>
                    """
                    for ilac in r.get('ilaclar', []):
                        fark = str(ilac.get('fiyat_farki', '0.00'))
                        fark_html = f"<span class='fark-info'>+ {fark} TL Fark</span>" if fark not in ["0.00", "0,00", "0", ""] else ""
                        
                        inner_html += f"""
                        <div class="ilac-row">
                            <div class="ilac-main">
                                <span>{ilac.get('ad', '')}</span>
                                <span>{ilac.get('fiyat', '0.00')} TL</span>
                            </div>
                            <div class="ilac-sub">
                                <span>Adet: {ilac.get('adet', '1')}</span>
                                {fark_html}
                            </div>
                        </div>
                        """
                    
                    if "Perakende" in r.get('kod', ''):
                        inner_html += f"""
                        <div class="details-box">
                            <div class="yansiyan-row"><span>Perakende Tutar</span><span>{r.get('yansiyan', '0.00')} TL</span></div>
                        </div></div>
                        """
                    else:
                        inner_html += f"""
                        <div class="details-box">
                            <div class="detail-line"><span>Hasta Katılım Payı</span><span>{r.get('katilim_payi', '0.00')} TL</span></div>
                            <div class="detail-line"><span>Muayene Ücreti</span><span>{r.get('muayene_ucreti', '0.00')} TL</span></div>
                            <div class="detail-line"><span>Reçete Payı</span><span>{r.get('recete_payi', '0.00')} TL</span></div>
                            <div class="yansiyan-row"><span>Hastaya Yansıyan</span><span>{r.get('yansiyan', '0.00')} TL</span></div>
                        </div></div>
                        """
                    
                inner_html += f"""
                <div class="grand-footer">
                    <span>Genel Bakiye</span><span class="price">{data.get('genel_bakiye', '0.00')} TL</span>
                </div>
                """
                
                st.success("⚡ Cari Kart Hazır!")
                components.html(TEMPLATE_TOP + inner_html + TEMPLATE_BOTTOM, height=900, scrolling=True)
                
            except Exception as e:
                st.error(f"⚠️ Hata: {str(e)}")
else:
    st.info("👈 Lütfen sol taraftan veriyi girip oluştur butonuna basın.")
```
