import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
import json
from PIL import Image

# 1. TARAYICI SEKMESİ (TİTLE) DÜZELTİLDİ
st.set_page_config(page_title="Eczane Cari Kart Dökümü", page_icon="💊", layout="wide")

# 2. ANA BAŞLIK DÜZELTİLDİ
st.title("💊 Eczane Cari Kart Dökümü")

try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
except:
    st.error("⚠️ Sistem Hatası: Lütfen Streamlit 'Secrets' bölümüne API anahtarınızı ekleyin.")
    st.stop()

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
        raw_text = st.text_area("Botanik Verisini Buraya Yapıştırın:", height=250)

    with tab2:
        st.info("💡 **İpucu:** Sayfa üzerindeyken **CTRL+V** yaparak görseli direkt yapıştırabilirsiniz!")
        uploaded_file = st.file_uploader("Görsel veya PDF yükleyin", type=["jpg", "jpeg", "png", "pdf"])
        if uploaded_file:
            if "pdf" in uploaded_file.type:
                st.info(f"📄 PDF hazır: {uploaded_file.name}")
            else:
                st.image(uploaded_file, caption="Sisteme Eklenen Görsel", use_column_width=True)

    # 3. BUTON İSMİ DÜZELTİLDİ
    submit_button = st.button("✨ Cari Kart Oluştur", type="primary", use_container_width=True)

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
            prompt_intro = "Aşağıdaki Botanik eczane otomasyonu metnini incele."
        else:
            st.warning("Lütfen işlem yapmadan önce sol taraftan bir metin girin veya dosya yükleyin.")
            st.stop()

        with st.spinner("🚀 Veriler Botanik şablonuna göre işleniyor..."):
            try:
                generation_config = {
                    "temperature": 0.0,
                    "response_mime_type": "application/json"
                }
                model = genai.GenerativeModel('gemini-2.5-flash', generation_config=generation_config)
                
                full_prompt = f"""
                {prompt_intro}
                
                HİÇBİR AÇIKLAMA YAZMA. Sadece JSON formatında çıktı ver.
                
                BOTANİK PROGRAMI KURALLARI:
                1. Veride hem "Reçetesi" hem de "Perakendesi" (elden satış) geçebilir. İkisini de "receteler" listesine blok olarak ekle.
                2. Perakende işlemlerde kod kısmına "Perakende Satış" yaz. Muayene, reçete ve katılım payları 0.00'dır. Yalnızca hastanın ödediği net "Ödeme Toplam" kısmını 'yansiyan' değerine yaz.
                3. Reçeteler için HESAPLAR satırındaki Hasta Katılım, Reçete Katılım, Muayene ve Fiyat Farkı toplamlarını alıp 'yansiyan' kısmına hastanın ödeyeceği tutarı yaz.
                4. "genel_bakiye" en sağ sütunda artarak giden (kümülatif) rakamın EN SONUNCUSUDUR.
                
                JSON ŞEMASI:
                {{
                  "hasta_adi": "Hasta Adı Soyadı",
                  "receteler": [
                    {{
                      "tarih": "GG.AA.YYYY",
                      "kod": "Reçete Kodu veya Perakende",
                      "ilaclar": [
                        {{"ad": "İlaç Adı", "fiyat_farki": "0.00"}}
                      ],
                      "katilim_payi": "0.00",
                      "muayene_ucreti": "0.00",
                      "recete_payi": "0.00",
                      "yansiyan": "0.00"
                    }}
                  ],
                  "genel_bakiye": "0.00"
                }}
                """
                
                response = model.generate_content([full_prompt] + content_to_send)
                data = json.loads(response.text)
                
                # Fiş içi HTML Başlığı da düzeltildi
                inner_html = f"""
                <div class="header">
                    <h1>Eczane Cari Kart Dökümü</h1>
                    <div class="patient-name">{data.get('hasta_adi', 'Hasta Bilgisi Alınamadı')}</div>
                </div>
                """
                
                for r in data.get('receteler', []):
                    inner_html += f"""
                    <div class="recete-block">
                        <div class="recete-header">
                            <span class="date-tag">{r.get('tarih', '')}</span>
                            <span class="kod-tag">{r.get('kod', '')}</span>
                        </div>
                    """
                    for ilac in r.get('ilaclar', []):
                        fark = str(ilac.get('fiyat_farki', '0.00'))
                        fark_str = f"<span class='fark-info'>Fiyat Farkı: {fark} TL</span>" if fark not in ["0.00", "0,00", "0", "0.0", "", None] else ""
                        inner_html += f"<div class='ilac-row'><span>{ilac.get('ad', '')}</span>{fark_str}</div>"
                    
                    if "Perakende" in r.get('kod', ''):
                        inner_html += f"""
                        <div class="details-box">
                            <div class="yansiyan-row"><span>Perakende / Nakit Tutar</span><span>{r.get('yansiyan', '0.00')} TL</span></div>
                        </div>
                        </div>
                        """
                    else:
                        inner_html += f"""
                        <div class="details-box">
                            <div class="detail-line"><span>Hasta Katılım Payı</span><span>{r.get('katilim_payi', '0.00')} TL</span></div>
                            <div class="detail-line"><span>Muayene Ücreti</span><span>{r.get('muayene_ucreti', '0.00')} TL</span></div>
                            <div class="detail-line"><span>Reçete Payı</span><span>{r.get('recete_payi', '0.00')} TL</span></div>
                            <div class="yansiyan-row"><span>Hastaya Yansıyan</span><span>{r.get('yansiyan', '0.00')} TL</span></div>
                        </div>
                        </div>
                        """
                    
                inner_html += f"""
                <div class="grand-footer">
                    <span>Genel Bakiye</span><span class="price">{data.get('genel_bakiye', '0.00')} TL</span>
                </div>
                """
                
                final_html = TEMPLATE_TOP + inner_html + TEMPLATE_BOTTOM
                
                st.success("⚡ Cari Kart Hazır!")
                components.html(final_html, height=900, scrolling=True)
                
            except json.JSONDecodeError:
                st.error("⚠️ Veri işlenirken bir hata oluştu. Lütfen tekrar deneyin.")
            except Exception as e:
                st.error(f"Beklenmeyen bir hata oluştu: {str(e)}")
    else:
        st.info("👈 Lütfen sol taraftan veriyi girip oluştur butonuna basın.")
