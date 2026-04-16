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

# --- YENİ EKLENEN MATEMATİKSEL TOPLAMA FONKSİYONU (DENEME 2 - KİLİTLİ) ---
def hesapla_genel_bakiye(data):
    toplam_genel = 0.0
    for r in data.get('receteler', []):
        yans_str = str(r.get('yansiyan', '0,00'))
        try:
            val = float(yans_str.replace('.', '').replace(',', '.'))
            toplam_genel += val
        except:
            pass
            
    parts = f"{toplam_genel:.2f}".split('.')
    tam_kisim = parts[0]
    ondalik_kisim = parts[1]
    
    tam_kisim_fmt = ""
    for i, digit in enumerate(reversed(tam_kisim)):
        if i > 0 and i % 3 == 0 and tam_kisim[0] != '-':
            tam_kisim_fmt = '.' + tam_kisim_fmt
        tam_kisim_fmt = digit + tam_kisim_fmt
        
    data['genel_bakiye'] = f"{tam_kisim_fmt},{ondalik_kisim}"
    return data

# --- ÖZEL BOTANİK METİN PARÇALAYICI (KİLİTLİ SİSTEM - YAPAY ZEKASIZ, 0.01 SANİYE) ---
def parse_botanik_text(text):
    data = {"hasta_adi_genel": "", "receteler": [], "genel_bakiye": "0,00"}
    
    pattern = r'(?=\d{2}\.\d{2}\.\d{4}\s\d{2}:\d{2})'
    blocks = re.split(pattern, text.strip())
    blocks = [b.strip() for b in blocks if b.strip()]
    
    for block in blocks:
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if not lines: continue
        
        header = lines[0]
        recete = {
            "ilaclar": [], "katilim_payi": "0,00", "muayene_ucreti": "0,00", 
            "recete_payi": "0,00", "toplam_fark": "0,00", "yansiyan": "0,00"
        }
        
        tarih_match = re.search(r'\d{2}\.\d{2}\.\d{4}', header)
        recete['tarih'] = tarih_match.group(0) if tarih_match else ""
        
        isim_match = re.search(r'\d{2}:\d{2}\s+(.*?)\s+(Reçetesi|Perakendesi)', header)
        if isim_match:
            recete['hasta_adi_ozel'] = isim_match.group(1).strip()
            if not data["hasta_adi_genel"]:
                data["hasta_adi_genel"] = recete['hasta_adi_ozel']
                
        is_perakende = "Perakendesi" in header
        if is_perakende:
            recete['kod'] = "Perakende Satış"
        else:
            kod_match = re.search(r'\(\d+\)\s+([A-Z0-9]+)', header)
            recete['kod'] = kod_match.group(1) if kod_match else ""
            
        hesaplar_idx = -1
        for i, line in enumerate(lines):
            if line.startswith("HESAPLAR"):
                hesaplar_idx = i
                break
                
        if hesaplar_idx != -1:
            for i in range(2, hesaplar_idx):
                ilac_line = lines[i]
                if "İlaç Adı" in ilac_line or "Fiyat" in ilac_line: continue
                    
                ilac_nums = re.findall(r'\d+,\d{2}|\b\d+\b', ilac_line)
                try:
                    if is_perakende and len(ilac_nums) >= 3:
                        fiyat = ilac_nums[-3]
                        adet = ilac_nums[-2]
                        fark = "0,00"
                        isim = ilac_line[:ilac_line.rfind(fiyat)].strip()
                        recete['ilaclar'].append({"ad": isim, "adet": adet, "fiyat": fiyat, "fiyat_farki": fark})
                    elif not is_perakende and len(ilac_nums) >= 4:
                        fiyat = ilac_nums[-4]
                        adet = ilac_nums[-3]
                        fark = ilac_nums[-1]
                        isim = ilac_line[:ilac_line.rfind(fiyat)].strip()
                        recete['ilaclar'].append({"ad": isim, "adet": adet, "fiyat": fiyat, "fiyat_farki": fark})
                except: pass
            
            if hesaplar_idx + 1 < len(lines):
                hesap_satiri = lines[hesaplar_idx + 1]
                if is_perakende:
                    odeme_match = re.search(r'Ödeme Toplam\s*:\s*([\d,]+)', hesap_satiri)
                    if odeme_match: recete['yansiyan'] = odeme_match.group(1)
                else:
                    h_kat = re.search(r'Hasta Kat\.\s*:?\s*([\d,]+)', hesap_satiri)
                    r_kat = re.search(r'Reç Kat\.\s*:?\s*([\d,]+)', hesap_satiri)
                    muayene = re.search(r'Muayene\s*:?\s*([\d,]+)', hesap_satiri)
                    f_fark = re.search(r'Fiyat Farkı\s*:?\s*([\d,]+)', hesap_satiri)
                    
                    recete['katilim_payi'] = h_kat.group(1) if h_kat else "0,00"
                    recete['recete_payi'] = r_kat.group(1) if r_kat else "0,00"
                    recete['muayene_ucreti'] = muayene.group(1) if muayene else "0,00"
                    recete['toplam_fark'] = f_fark.group(1) if f_fark else "0,00"
                    
                    def parse_num(val): return float(val.replace('.', '').replace(',', '.'))
                    try:
                        yans = parse_num(recete['katilim_payi']) + parse_num(recete['muayene_ucreti']) + parse_num(recete['recete_payi']) + parse_num(recete['toplam_fark'])
                        yans_str = f"{yans:.2f}".replace('.', ',')
                        recete['yansiyan'] = yans_str
                    except: pass
                        
        data['receteler'].append(recete)
    return data

# --- HTML OLUŞTURUCU FONKSİYON (Tasarım İstekleri Buraya Uygulandı) ---
def generate_html(data):
    hasta_adi_dosya = data.get('hasta_adi_genel', 'Eczane_Cari').replace(" ", "_")
    
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
            fark = str(ilac.get('fiyat_farki', '0,00'))
            # İlaç içi turuncu fark rengi kilitli, aynen kaldı.
            fark_html = f"<span class='fark-info'>+ {fark} TL Fark</span>" if fark not in ["0.00", "0,00", "0", ""] else ""
            inner_html += f"""
            <div class="ilac-row">
                <div class="ilac-main">
                    <span>{ilac.get('ad', '')}</span>
                    <span>{ilac.get('fiyat', '0,00')} TL</span>
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
                <div class="yansiyan-row"><span>Perakende Tutar</span><span>{r.get('yansiyan', '0,00')} TL</span></div>
            </div></div>
            """
        else:
            inner_html += f"""
            <div class="details-box">
                <div class="detail-line"><span>Hasta Katılım Payı</span><span>{r.get('katilim_payi', '0,00')} TL</span></div>
                <div class="detail-line"><span>Muayene Ücreti</span><span>{r.get('muayene_ucreti', '0,00')} TL</span></div>
                <div class="detail-line"><span>Reçete Payı</span><span>{r.get('recete_payi', '0,00')} TL</span></div>
                <div class="detail-fark"><span>Fiyat Farkı</span><span>{r.get('toplam_fark', '0,00')} TL</span></div>
                <div class="yansiyan-row"><span>Hastaya Yansıyan</span><span>{r.get('yansiyan', '0,00')} TL</span></div>
            </div></div>
            """
    inner_html += f"""
    <div class="grand-footer">
        <span>Hastaya Yansıyan</span><span class="price">{data.get('genel_bakiye', '0,00')} TL</span>
    </div>
    """

    FULL_HTML = f"""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
        <style>
            :root {{ --primary: #00695c; --fark: #e67e22; --bg: #f4f7f6; --text: #333; }}
            body {{ font-family: 'Segoe UI', sans-serif; background: transparent; display: flex; flex-direction: column; align-items: center; padding: 0; color: var(--text); margin: 0; }}
            
            .sticky-bar {{ 
                position: sticky; top: 0; z-index: 1000; background-color: #fff9c4; border: 1px solid #f2d06b; border-radius: 12px; width: 100%; max-width: 500px; display: flex; justify-content: space-between; align-items: center; padding: 12px 18px; margin-bottom: 20px; box-sizing: border-box; box-shadow: 0 4px 10px rgba(0,0,0,0.05);
            }}
            .sticky-bar h2 {{ margin: 0; font-size: 16px; color: #5c4d0c; display: flex; align-items: center; gap: 8px; font-weight: 600; }}
            .action-buttons {{ display: flex; gap: 10px; margin: 0; }}
            
            .btn {{ border: none; padding: 10px 15px; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 13px; color: white; display: flex; align-items: center; gap: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); transition: 0.2s; }}
            .btn-print {{ background-color: #2980b9; }}
            .btn-print:hover {{ background-color: #1c5982; }}
            .btn-copy {{ background-color: #8e44ad; }}
            .btn-copy:hover {{ background-color: #732d91; }}
            .btn-jpg {{ background-color: #27ae60; }}
            .btn-jpg:hover {{ background-color: #1e8449; }}

            /* 3. İSTEK: Resim arkasına beyaz fon ve paylar (Padding) */
            .capture-wrapper {{ 
                background-color: #ffffff; /* Saf beyaz fon */
                padding: 25px; /* Dört bir yandan 25px pay */
                border-radius: 20px; /* Dış beyaz fonun köşelerini de oval yapalım şık dursun */
                max-width: 550px; /* 500px kart + 50px padding */
                margin-bottom: 30px;
                display: flex;
                justify-content: center;
                align-items: center;
            }}

            .container {{ width: 100%; max-width: 500px; background: white; border-radius: 20px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border: 1px solid #ddd; outline: none; margin: 0; /* Wrapper içinde margin olmamalı */ }}
            [contenteditable="true"] {{ cursor: text; }}
            [contenteditable="true"]:focus {{ outline: none; }}

            .header {{ background: var(--primary); color: white; padding: 25px; text-align: left; }}
            .header h1 {{ margin: 0; font-size: 18px; opacity: 0.9; font-weight: 400; }}
            .patient-name {{ font-size: 22px; font-weight: bold; margin-top: 5px; }}
            .recete-block {{ padding: 20px; border-bottom: 8px solid var(--bg); }}
            .recete-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid #eee; }}
            .recete-patient {{ font-size: 13px; font-weight: bold; color: #555; margin-bottom: 10px; display: block; }}
            .date-tag {{ font-weight: bold; color: var(--primary); font-size: 14px; }}
            .kod-tag {{ font-size: 11px; color: #999; border: 1px solid #eee; padding: 2px 6px; border-radius: 4px; }}
            .ilac-row {{ padding: 10px 0; border-bottom: 1px dashed #f0f0f0; }}
            .ilac-main {{ display: flex; justify-content: space-between; font-size: 13px; font-weight: 500; }}
            .ilac-sub {{ display: flex; justify-content: space-between; font-size: 11px; color: #777; margin-top: 2px; }}
            .fark-info {{ color: var(--fark); font-weight: bold; }}
            .details-box {{ background: #f9fdfc; padding: 12px; margin-top: 10px; border-radius: 10px; border: 1px solid #edf5f4; }}
            .detail-line {{ display: flex; justify-content: space-between; font-size: 11.5px; color: #666; margin-bottom: 4px; }}
            
            /* 1. İSTEK CSS: Koyu Gri, Kalın, Fiyat Farkı */
            .detail-fark {{ display: flex; justify-content: space-between; font-size: 12px; color: #444; /* Koyu Gri */ font-weight: bold; /* Kalın */ margin-bottom: 4px; padding-top: 4px; border-top: 1px dashed #eee; }}
            
            /* 2. İSTEK CSS: Kalın Hastaya Yansıyan Satırı */
            .yansiyan-row {{ display: flex; justify-content: space-between; font-size: 15px; font-weight: bold; /* Kalın */ color: #27ae60; margin-top: 8px; padding-top: 8px; border-top: 1px solid #d1e8e5; }}
            
            .grand-footer {{ background: var(--primary); color: white; padding: 25px; display: flex; justify-content: space-between; align-items: center; font-weight: bold; /* 2. İsteğe destek */ }}
            .grand-footer .price {{ font-size: 28px; font-weight: bold; }}
            @media print {{
                .sticky-bar {{ display: none !important; }}
                body {{ padding: 0; background: white; margin: 0; }}
                /* Yazdırırken beyaz fon ve payları kaldıralım kağıt zaten beyaz */
                .capture-wrapper {{ background: none; padding: 0; max-width: 100%; border-radius: 0; }}
                .container {{ box-shadow: none; border: none; border-radius: 0; margin-top: 0; max-width: 100%; }}
            }}
        </style>
    </head>
    <body>
        
        <div class="sticky-bar no-print">
            <h2>🧾 Hastaya Verilecek Döküm</h2>
            <div class="action-buttons">
                <button class="btn btn-print" onclick="window.print()">🖨️ Yazdır</button>
                <button class="btn btn-copy" onclick="copyImage()">📋 Kopyala</button>
                <button class="btn btn-jpg" onclick="downloadJPG()">📸 İndir</button>
            </div>
        </div>

        <div class="capture-wrapper" id="capture-area">
            <div class="container" contenteditable="true" spellcheck="false">
                {inner_html}
            </div>
        </div>

        <script>
            function getFileName() {{
                let d = new Date();
                let dateStr = d.toLocaleDateString('tr-TR').replace(/\./g, '-');
                return "{hasta_adi_dosya}_" + dateStr + ".jpg";
            }}

            function downloadJPG() {{
                // Kilitli kural: html2canvas wrapper'ın fotoğrafını çekiyor
                html2canvas(document.getElementById('capture-area'), {{ scale: 2, backgroundColor: "#ffffff" }}).then(canvas => {{
                    let link = document.createElement('a');
                    link.download = getFileName();
                    link.href = canvas.toDataURL('image/jpeg', 0.9);
                    link.click();
                }});
            }}

            function copyImage() {{
                let btn = document.querySelector('.btn-copy');
                let originalText = btn.innerHTML;
                btn.innerHTML = '⏳ Kopyalanıyor...';
                
                html2canvas(document.getElementById('capture-area'), {{ scale: 2, backgroundColor: "#ffffff" }}).then(canvas => {{
                    canvas.toBlob(blob => {{
                        try {{
                            const item = new ClipboardItem({{ 'image/png': blob }});
                            navigator.clipboard.write([item]).then(() => {{
                                btn.innerHTML = '✅ Kopyalandı!';
                                setTimeout(() => btn.innerHTML = originalText, 2500);
                            }}).catch(err => {{
                                alert('Kopyalama engellendi. Lütfen İndir butonunu kullanın.');
                                btn.innerHTML = originalText;
                            }});
                        }} catch(e) {{
                            alert('Tarayıcınız panoya direkt görsel kopyalamayı desteklemiyor. Lütfen İndir butonunu kullanın.');
                            btn.innerHTML = originalText;
                        }}
                    }}, 'image/png');
                }});
            }}
        </script>
    </body>
    </html>
    """
    return FULL_HTML

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
            st.image(uploaded_file, caption="Sisteme Eklenen Görsel", use_column_width=True)

    submit_button = st.button("✨ Cari Kart Oluştur", type="primary", use_container_width=True)

with col2:
    st.subheader(" ") 
    
    if submit_button:
        if raw_text.strip() != "":
            with st.spinner("🚀 Saf Yazılım Gücüyle Veriler Çekiliyor (Işık Hızı)..."):
                try:
                    data = parse_botanik_text(raw_text)
                    data = hesapla_genel_bakiye(data) # KİLİTLİ MATEMATİK MOTORU
                    final_html = generate_html(data)
                    st.success("⚡ Şimşek Hızında Cari Kart Hazır! 💡 İPUCU: Kartın üzerindeki yazılara tıklayarak anında düzenleyebilirsiniz.")
                    components.html(final_html, height=1000, scrolling=True) # Yükseklik padding nedeniyle biraz artırıldı
                except Exception as e:
                    st.error(f"⚠️ Metin işlenirken hata oluştu: {str(e)}")
                    
        elif uploaded_file:
            with st.spinner("🤖 Görsel Yapay Zeka Tarafından Okunuyor (3-5 Sn Sürebilir)..."):
                try:
                    img = Image.open(uploaded_file)
                    generation_config = {"temperature": 0.0}
                    model = genai.GenerativeModel('gemini-2.5-flash', generation_config=generation_config)
                    
                    full_prompt = """
                    Bu görseldeki Botanik eczane cari dökümünü incele ve sadece JSON formatında yanıt ver. 
                    ÖNEMLİ KURALLAR:
                    1. Her reçetenin başında yazan HASTA ADINI ('... Reçetesi' veya '... Perakendesi' yazan yerdeki isim) mutlaka her blok için ayrı yakala.
                    2. Her ilaç için ADET (Miktar) ve FİYAT (Birim fiyat veya Toplam fiyat) bilgilerini mutlaka çek.
                    3. "Fiyat Farkı" kısmını her ilaç için kontrol et, varsa çek.
                    4. Reçeteler için HESAPLAR satırındaki tutarları (Katılım Payları, Muayene, Reçete Payı VE Fiyat Farkı Toplamı) eksiksiz ayıkla.
                    5. En alttaki genel bakiyeyi SEN HESAPLAMA, sadece boş "0.00" ver, sistem kendi hesaplayacak.
                    
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
                          "katilim_payi": "0.00", 
                          "muayene_ucreti": "0.00", 
                          "recete_payi": "0.00", 
                          "toplam_fark": "0.00", 
                          "yansiyan": "0.00"
                        }
                      ],
                      "genel_bakiye": "0.00"
                    }
                    """
                    
                    response = model.generate_content([full_prompt, img])
                    raw_response = response.text.replace("```json", "").replace("```", "").strip()
                    json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
                    data = json.loads(json_match.group(0) if json_match else raw_response)
                    
                    data = hesapla_genel_bakiye(data) # KİLİTLİ MATEMATİK MOTORU
                    final_html = generate_html(data)
                    st.success("🤖 Yapay Zeka Okumayı Tamamladı! 💡 İPUCU: Kartın üzerindeki yazılara tıklayarak anında düzenleyebilirsiniz.")
                    components.html(final_html, height=1000, scrolling=True)
                except Exception as e:
                    st.error(f"⚠️ Görsel okunurken hata oluştu: {str(e)}")
        else:
            st.warning("Lütfen işlem yapmadan önce sol taraftan bir metin girin veya dosya yükleyin.")
