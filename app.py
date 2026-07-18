import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
import json
import re

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

# --- MATEMATİKSEL TOPLAMA FONKSİYONU (GÜNCELLENDİ: NOKTA/VİRGÜL HATASI ÇÖZÜLDÜ) ---
def hesapla_genel_bakiye(data):
    toplam_borc = 0.0
    toplam_odeme = 0.0
    
    # Akıllı Float Çevirici
    def cevir_float(val_str):
        val_str = str(val_str).strip()
        # Eğer virgül varsa Türkçe formattır (Örn: 9.197,63 veya 9197,63)
        if ',' in val_str:
            val_str = val_str.replace('.', '').replace(',', '.')
        # Virgül yoksa zaten yapay zekanın 9197.63 formatıdır, float() bunu doğrudan anlar
        try:
            return float(val_str)
        except:
            return 0.0

    # Reçetelerden gelen borçları topla
    for r in data.get('receteler', []):
        toplam_borc += cevir_float(r.get('yansiyan', '0,00'))
            
    # Tahsilatları (ödemeleri) topla
    for t in data.get('tahsilatlar', []):
        toplam_odeme += cevir_float(t.get('tutar', '0,00'))

    # Net bakiyeyi hesapla (Borç - Ödenen)
    net_bakiye = toplam_borc - toplam_odeme
    
    parts = f"{net_bakiye:.2f}".split('.')
    tam_kisim = parts[0]
    ondalik_kisim = parts[1] if len(parts) > 1 else "00"
    
    tam_kisim_fmt = ""
    is_negative = tam_kisim.startswith('-')
    if is_negative: tam_kisim = tam_kisim[1:]
        
    for i, digit in enumerate(reversed(tam_kisim)):
        if i > 0 and i % 3 == 0:
            tam_kisim_fmt = '.' + tam_kisim_fmt
        tam_kisim_fmt = digit + tam_kisim_fmt
        
    if is_negative: tam_kisim_fmt = '-' + tam_kisim_fmt
        
    data['genel_bakiye'] = f"{tam_kisim_fmt},{ondalik_kisim}"
    return data

# --- HİBRİT BOTANİK METİN PARÇALAYICI (AYNI KALDI) ---
def parse_botanik_text(text):
    data = {"hasta_adi_genel": "", "receteler": [], "tahsilatlar": [], "genel_bakiye": "0,00"}
    
    # FORMAT C (YENİ HASTA BİLGİLENDİRME FİŞİ)
    if "Sayın :" in text and "Tc Kimlik No:" in text:
        blocks = re.split(r'(?=Sayın\s*:)', text.strip())
        blocks = [b.strip() for b in blocks if b.strip()]
        
        for block in blocks:
            recete = {
                "ilaclar": [], "katilim_payi": "0,00", "muayene_ucreti": "0,00", 
                "recete_payi": "0,00", "toplam_fark": "0,00", "yansiyan": "0,00", "kod": "Reçete Bilgisi"
            }
            
            isim_m = re.search(r'Sayın\s*:\s*(.*?)(?=Tc Kimlik)', block)
            if isim_m:
                recete['hasta_adi_ozel'] = isim_m.group(1).strip()
                if not data["hasta_adi_genel"]: data["hasta_adi_genel"] = recete['hasta_adi_ozel']
            
            tarih_m = re.search(r'İşlem Tarihi:.*?\s+(\d{2}-\d{2}-\d{4})', block)
            recete['tarih'] = tarih_m.group(1).replace('-', '.') if tarih_m else ""
            
            fark_m = re.search(r'Fiyat Farkı\s+([\d,.]+)', block)
            mua_m = re.search(r'Muayene Katkı Payı\s+([\d,.]+)', block)
            tahsilat_m = re.search(r'Ödenecek Toplam\s+([\d,.]+)', block)
            
            if fark_m: recete['toplam_fark'] = fark_m.group(1)
            if mua_m: recete['muayene_ucreti'] = mua_m.group(1)
            if tahsilat_m: recete['yansiyan'] = tahsilat_m.group(1)

            drug_section = re.search(r'Doktor\s*:.*?\n(.*?)(?=Rx Kat\.Pay)', block, re.DOTALL)
            if drug_section:
                drug_text = drug_section.group(1)
                drug_matches = re.finditer(r'(.*?)\s+Doz.*?\n.*?\)\s+(\d+)\s+([\d,.]+)', drug_text)
                for m in drug_matches:
                    recete['ilaclar'].append({
                        "ad": m.group(1).strip(),
                        "adet": m.group(2).strip(),
                        "fiyat": "0,00", 
                        "fiyat_farki": m.group(3).strip()
                    })
            
            data['receteler'].append(recete)
        return data

    # FORMAT A ve B (DETAYLI BOTANİK ve ÖZET)
    pattern = r'(?=\d{2}\.\d{2}\.\d{4}\s\d{2}:\d{2})'
    blocks = re.split(pattern, text.strip())
    blocks = [b.strip() for b in blocks if b.strip()]
    
    for block in blocks:
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if not lines: continue
        header = lines[0]
        recete = {"ilaclar": [], "katilim_payi": "0,00", "muayene_ucreti": "0,00", "recete_payi": "0,00", "toplam_fark": "0,00", "yansiyan": "0,00"}
        
        tarih_match = re.search(r'\d{2}\.\d{2}\.\d{4}', header)
        recete['tarih'] = tarih_match.group(0) if tarih_match else ""
        
        isim_match = re.search(r'\d{2}:\d{2}\s+(.*?)\s+(Reçetesi|Perakendesi)', header)
        if isim_match:
            recete['hasta_adi_ozel'] = isim_match.group(1).strip()
            if not data["hasta_adi_genel"]: data["hasta_adi_genel"] = recete['hasta_adi_ozel']
        
        is_perakende = "Perakendesi" in header
        recete['kod'] = "Perakende Satış" if is_perakende else (re.search(r'\(\d+\)\s+([A-Z0-9]+)', header).group(1) if re.search(r'\(\d+\)\s+([A-Z0-9]+)', header) else "")
        
        hesaplar_idx = next((i for i, line in enumerate(lines) if line.startswith("HESAPLAR")), -1)
        if hesaplar_idx != -1:
            for i in range(2, hesaplar_idx):
                ilac_line = lines[i]
                if "İlaç Adı" in ilac_line or "Fiyat" in ilac_line: continue
                ilac_nums = re.findall(r'\d+,\d{2}|\b\d+\b', ilac_line)
                try:
                    if is_perakende and len(ilac_nums) >= 3:
                        fiyat = ilac_nums[-3]
                        adet = ilac_nums[-2]
                        toplam = ilac_nums[-1]
                        
                        pattern_str = r'(.*?)\s+' + re.escape(fiyat) + r'\s+' + re.escape(adet) + r'\s+' + re.escape(toplam) + r'\s*$'
                        match = re.search(pattern_str, ilac_line)
                        isim = match.group(1).strip() if match else ilac_line.rsplit(fiyat, 1)[0].strip()
                        
                        recete['ilaclar'].append({"ad": isim, "adet": adet, "fiyat": fiyat, "fiyat_farki": "0,00"})
                    elif not is_perakende and len(ilac_nums) >= 4:
                        fiyat = ilac_nums[-4]
                        adet = ilac_nums[-3]
                        toplam = ilac_nums[-2]
                        fark = ilac_nums[-1]
                        
                        pattern_str = r'(.*?)\s+' + re.escape(fiyat) + r'\s+' + re.escape(adet) + r'.*?' + re.escape(fark) + r'\s*$'
                        match = re.search(pattern_str, ilac_line)
                        isim = match.group(1).strip() if match else ilac_line.rsplit(fiyat, 1)[0].strip()
                            
                        recete['ilaclar'].append({"ad": isim, "adet": adet, "fiyat": fiyat, "fiyat_farki": fark})
                except: pass
            
            if hesaplar_idx + 1 < len(lines):
                hesap_satiri = lines[hesaplar_idx + 1]
                if is_perakende:
                    odeme_m = re.search(r'Ödeme Toplam\s*:\s*([\d,]+)', hesap_satiri)
                    if odeme_m: recete['yansiyan'] = odeme_m.group(1)
                else:
                    recete['katilim_payi'] = re.search(r'Hasta Kat\.\s*:?\s*([\d,]+)', hesap_satiri).group(1) if re.search(r'Hasta Kat\.\s*:?\s*([\d,]+)', hesap_satiri) else "0,00"
                    recete['recete_payi'] = re.search(r'Reç Kat\.\s*:?\s*([\d,]+)', hesap_satiri).group(1) if re.search(r'Reç Kat\.\s*:?\s*([\d,]+)', hesap_satiri) else "0,00"
                    recete['muayene_ucreti'] = re.search(r'Muayene\s*:?\s*([\d,]+)', hesap_satiri).group(1) if re.search(r'Muayene\s*:?\s*([\d,]+)', hesap_satiri) else "0,00"
                    recete['toplam_fark'] = re.search(r'Fiyat Farkı\s*:?\s*([\d,]+)', hesap_satiri).group(1) if re.search(r'Fiyat Farkı\s*:?\s*([\d,]+)', hesap_satiri) else "0,00"
                    def parse_num(val): return float(val.replace('.', '').replace(',', '.'))
                    try:
                        yans = parse_num(recete['katilim_payi']) + parse_num(recete['muayene_ucreti']) + parse_num(recete['recete_payi']) + parse_num(recete['toplam_fark'])
                        recete['yansiyan'] = f"{yans:.2f}".replace('.', ',')
                    except: pass
        data['receteler'].append(recete)
    return data

# --- HTML OLUŞTURUCU FONKSİYON (GÜNCELLENDİ: TAHSİLATLAR EKLENDİ) ---
def generate_html(data):
    hasta_adi_dosya = data.get('hasta_adi_genel', 'Eczane_Cari').replace(" ", "_")
    
    # Üst Kısım ve İlaçlar
    inner_html = f"""
    <div class="content-area">
        <div class="header">
            <h1>Cari Kart Dökümü</h1>
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
            fark_html = f"<span class='fark-info'>+ {fark} TL Fark</span>" if fark not in ["0.00", "0,00", "0", ""] else ""
            inner_html += f"""
            <div class='ilac-row'>
                <div class='ilac-main'>
                    <span>{ilac.get('ad', '')}</span>
                    <span>{ilac.get('fiyat', '0,00')} TL</span>
                </div>
                <div class='ilac-sub'>
                    <span>Adet: {ilac.get('adet', '1')}</span>
                    {fark_html}
                </div>
            </div>
            """
        
        if "Perakende" in r.get('kod', ''):
            inner_html += f"""
            <div class='details-box'>
                <div class='yansiyan-row'><span>Perakende Tutar</span><span>{r.get('yansiyan', '0,00')} TL</span></div>
            </div></div>
            """
        else:
            inner_html += f"""
            <div class='details-box'>
                <div class='detail-line'><span>Hasta Katılım Payı</span><span>{r.get('katilim_payi', '0,00')} TL</span></div>
                <div class='detail-line'><span>Muayene Ücreti</span><span>{r.get('muayene_ucreti', '0,00')} TL</span></div>
                <div class='detail-line'><span>Reçete Payı</span><span>{r.get('recete_payi', '0,00')} TL</span></div>
                <div class='detail-fark'><span>Fiyat Farkı</span><span>{r.get('toplam_fark', '0,00')} TL</span></div>
                <div class='yansiyan-row'><span>Reçete Toplamı (Borç)</span><span>{r.get('yansiyan', '0,00')} TL</span></div>
            </div></div>
            """
            
    # Tahsilatlar (Ödemeler) Bloğu
    if data.get('tahsilatlar'):
        inner_html += "<div class='recete-block' style='border-top: 3px dashed #eee;'>"
        inner_html += "<div class='patient-name' style='font-size: 18px; color: #27ae60; margin-bottom: 15px;'>💳 Yapılan Ödemeler (Tahsilat)</div>"
        for t in data.get('tahsilatlar', []):
            inner_html += f"""
            <div class='ilac-row'>
                <div class='ilac-main' style='color: #27ae60;'>
                    <span>✔️ {t.get('tur', 'Tahsilat')} ({t.get('tarih', '')})</span>
                    <span>- {t.get('tutar', '0,00')} TL</span>
                </div>
            </div>
            """
        inner_html += "</div>"

    inner_html += "</div>" # content-area sonu

    # Alt Kısım (En alta sabitlenir)
    inner_html += f"""
    <div class='grand-footer'>
        <span style='line-height: 1.2;'>Kalan<br>Net Bakiye</span>
        <span class='price'>{data.get('genel_bakiye', '0,00')} TL</span>
    </div>
    """

    return f"""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
        <style>
            :root {{ --primary: #00695c; --fark: #e67e22; --bg: #f4f7f6; --text: #333; }}
            body {{ font-family: 'Segoe UI', sans-serif; background: transparent; display: flex; flex-direction: column; align-items: center; padding: 0; color: var(--text); margin: 0; }}
            
            /* --- SARI KONTROL PANELİ --- */
            .sticky-bar {{ 
                position: sticky; top: 0; z-index: 1000; background-color: #fff9c4; border: 1px solid #f2d06b; border-radius: 12px; 
                width: 100%; max-width: 600px; 
                display: flex; justify-content: space-between; align-items: center; padding: 12px 18px; margin-bottom: 20px; box-sizing: border-box; box-shadow: 0 4px 10px rgba(0,0,0,0.05);
            }}
            .sticky-bar h2 {{ margin: 0; font-size: 16px; color: #5c4d0c; display: flex; align-items: center; gap: 8px; font-weight: 600; }}
            .action-buttons {{ display: flex; gap: 10px; }}
            .btn {{ border: none; padding: 10px 15px; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 13px; color: white; display: flex; align-items: center; gap: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); transition: 0.2s; }}
            .btn-print {{ background-color: #2980b9; }} .btn-copy {{ background-color: #8e44ad; }} .btn-jpg {{ background-color: #27ae60; }}

            /* --- 1:0.75 BOY:EN ORANI --- */
            .capture-wrapper {{ 
                background-color: #ffffff; padding: 50px; border-radius: 20px; 
                max-width: 700px; 
                margin-bottom: 30px; display: flex; justify-content: center; align-items: center;
            }}
            .container {{ 
                width: 600px; 
                min-height: 800px; 
                background: white; border-radius: 20px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border: 1px solid #ddd; outline: none; 
                display: flex; flex-direction: column; 
            }}

            .content-area {{ flex-grow: 1; background-color: white; }}
            .header {{ background: var(--primary); color: white; padding: 25px 35px; text-align: left; }}
            .patient-name {{ font-size: 24px; font-weight: bold; margin-top: 8px; }}
            .recete-block {{ padding: 20px 35px; border-bottom: 8px solid var(--bg); }}
            .recete-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #eee; }}
            .date-tag {{ font-weight: bold; color: var(--primary); font-size: 15px; }}
            .kod-tag {{ font-size: 11px; color: #999; border: 1px solid #eee; padding: 3px 8px; border-radius: 4px; }}
            .ilac-row {{ padding: 12px 0; border-bottom: 1px dashed #f0f0f0; }}
            .ilac-main {{ display: flex; justify-content: space-between; font-size: 14px; font-weight: 500; }}
            .ilac-sub {{ display: flex; justify-content: space-between; font-size: 12px; color: #777; margin-top: 4px; }}
            .fark-info {{ color: var(--fark); font-weight: bold; }}
            .details-box {{ background: #f9fdfc; padding: 15px 25px; margin-top: 15px; border-radius: 12px; border: 1px solid #edf5f4; }}
            .detail-line {{ display: flex; justify-content: space-between; font-size: 13px; color: #666; margin-bottom: 6px; }}
            .detail-fark {{ display: flex; justify-content: space-between; font-size: 13px; color: #444; font-weight: bold; padding-top: 6px; border-top: 1px dashed #eee; }}
            .yansiyan-row {{ display: flex; justify-content: space-between; font-size: 16px; font-weight: bold; color: #c0392b; margin-top: 10px; padding-top: 10px; border-top: 1px solid #d1e8e5; }}
            
            .grand-footer {{ background: var(--primary); color: white; padding: 25px 35px; display: flex; justify-content: space-between; align-items: center; font-weight: bold; }}
            .grand-footer .price {{ font-size: 32px; font-weight: bold; }}
            
            [contenteditable="true"] {{ cursor: text; }}
            [contenteditable="true"]:focus {{ outline: none; }}
            @media print {{ .sticky-bar {{ display: none !important; }} .capture-wrapper {{ padding: 0; }} .container {{ box-shadow: none; border: none; }} }}
        </style>
    </head>
    <body>
        <div class="sticky-bar no-print">
            <h2>🧾 Hastaya Verilecek Döküm (1:0.75 Altın Oran)</h2>
            <div class="action-buttons">
                <button class="btn btn-print" onclick="window.print()">🖨️ Yazdır</button>
                <button class="btn btn-copy" onclick="copyImage()">📋 Kopyala</button>
                <button class="btn btn-jpg" onclick="downloadJPG()">📸 İndir</button>
            </div>
        </div>
        <div class="capture-wrapper" id="capture-area">
            <div class="container" contenteditable="true" spellcheck="false">{inner_html}</div>
        </div>
        <script>
            function getFileName() {{ let d = new Date(); return "{hasta_adi_dosya}_" + d.toLocaleDateString('tr-TR').replace(/\./g, '-') + ".jpg"; }}
            function downloadJPG() {{ 
                html2canvas(document.getElementById('capture-area'), {{ scale: 4, backgroundColor: "#ffffff", useCORS: true }}).then(canvas => {{ 
                    let link = document.createElement('a'); link.download = getFileName(); link.href = canvas.toDataURL('image/jpeg', 1.0); link.click(); 
                }}); 
            }}
            function copyImage() {{ 
                let btn = document.querySelector('.btn-copy'); let originalText = btn.innerHTML; btn.innerHTML = '⏳...'; 
                html2canvas(document.getElementById('capture-area'), {{ scale: 4, backgroundColor: "#ffffff", useCORS: true }}).then(canvas => {{ 
                    canvas.toBlob(blob => {{ try {{ const item = new ClipboardItem({{ 'image/png': blob }}); navigator.clipboard.write([item]).then(() => {{ btn.innerHTML = '✅!'; setTimeout(() => btn.innerHTML = originalText, 2500); }}); }} catch(e) {{ alert('Hata!'); btn.innerHTML = originalText; }} }}, 'image/png', 1.0); 
                }}); 
            }}
        </script>
    </body>
    </html>
    """

col1, col2 = st.columns([1, 2.5], gap="large")
with col1:
    st.subheader("📥 1. Veri Girişi")
    tab1, tab2 = st.tabs(["📄 Metin Yapıştır", "🌐 HTML Dosyası Yükle"])
    
    with tab1:
        header_col, btn_col = st.columns([3, 1])
        with header_col: st.markdown("<p style='font-weight: bold;'>Botanik Verisini Yapıştırın:</p>", unsafe_allow_html=True)
        with btn_col: st.button("🗑️", on_click=clear_text, use_container_width=True)
        raw_text = st.text_area("Gizli Label", key="raw_text_input", label_visibility="collapsed", height=250)
        
    with tab2:
        st.info("💡 **Sistemden aldığınız hasta ekstresi (.html)** dosyasını buraya yükleyebilirsiniz!")
        uploaded_file = st.file_uploader("HTML Dosyası Yükleyin", type=["html"])
        
    submit_button = st.button("✨ Cari Kart Oluştur", type="primary", use_container_width=True)

with col2:
    st.subheader(" ") 
    if submit_button:
        if raw_text.strip() != "":
            with st.spinner("🚀 Hız Motoru Çalışıyor..."):
                try:
                    data = parse_botanik_text(raw_text)
                    data = hesapla_genel_bakiye(data)
                    components.html(generate_html(data), height=1100, scrolling=True)
                except Exception as e: st.error(f"Hata: {str(e)}")
                
        elif uploaded_file:
            with st.spinner("🤖 Yapay Zeka HTML Dosyasını Okuyor..."):
                try:
                    # HTML dosyasını metin olarak oku
                    html_content = uploaded_file.getvalue().decode("utf-8")
                    
                    # Gemini modeli ayarları (Görsel okuma yerine artık doğrudan metin tabanlı çalışıyor)
                    model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"temperature": 0.0})
                    prompt = """
                    Ekteki HTML formatındaki eczane/hasta dökümünü detaylıca incele ve istenen JSON formatında veriyi döndür. 
                    ÖNEMLİ KURALLAR:
                    1. HTML içindeki ana hasta adını, reçete girişlerini, ilaç adlarını, fiyat ve adetlerini ayıkla.
                    2. İlaç "ad" alanına SADECE ilacın ismini yaz (fiyat ve adet rakamlarını KESİNLİKLE isme dahil etme).
                    3. Tabloda hastanın yaptığı "Nakit Tahsilat", "Kredi Kartı", "POS" gibi ÖDEMELER varsa bunları ayıklayıp "tahsilatlar" listesine ekle.
                    4. genel_bakiye'yi 0.00 bırak, sistem kendi matematik formülüyle hesaplayacak.
                    
                    JSON ŞEMASI:
                    {
                      "hasta_adi_genel": "Ana Hasta Adı",
                      "receteler": [
                        {
                          "tarih": "GG.AA.YYYY",
                          "hasta_adi_ozel": "Bu Reçetedeki İsim",
                          "kod": "İşlem Türü veya Reçete Kodu",
                          "ilaclar": [
                            {"ad": "SADECE İlaç Adı", "adet": "1", "fiyat": "0.00", "fiyat_farki": "0.00"}
                          ],
                          "katilim_payi": "0.00", 
                          "muayene_ucreti": "0.00", 
                          "recete_payi": "0.00", 
                          "toplam_fark": "0.00", 
                          "yansiyan": "0.00"
                        }
                      ],
                      "tahsilatlar": [
                        {
                          "tarih": "GG.AA.YYYY",
                          "tur": "Nakit Tahsilat vb.",
                          "tutar": "0.00"
                        }
                      ],
                      "genel_bakiye": "0.00"
                    }
                    """
                    response = model.generate_content([prompt, html_content])
                    
                    # JSON'u yanıttan ayıkla
                    json_str = re.search(r'\{.*\}', response.text, re.DOTALL).group(0)
                    data = json.loads(json_str)
                    
                    # Genel bakiyeyi hesapla ve ekrana bas
                    data = hesapla_genel_bakiye(data)
                    components.html(generate_html(data), height=1100, scrolling=True)
                except Exception as e: st.error(f"Yapay Zeka Okuma Hatası: {str(e)}")
