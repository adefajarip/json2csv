import streamlit as st
import pandas as pd
import json

# Mengonfigurasi tampilan halaman Streamlit
st.set_page_config(page_title="JSON Multi-Media Converter", page_icon="📊", layout="wide")

st.title("📊 Konverter & Klasifikasi Data Per Media (Versi Final Bersih)")
st.write("Aplikasi ini secara otomatis mengurai struktur JSON kotor, melakukan *flattening* pada objek bersarang (seperti statistik media sosial), dan memisahkan setiap media berdasarkan kolom uniknya menggunakan pembatas pipa (`|`).")

uploaded_file = st.file_uploader("Pilih file JSON hasil scraping", type=["json"])

if uploaded_file is not None:
    try:
        # 1. Membaca isi file secara mentah (bytes)
        bytes_data = uploaded_file.read()
        
        # 2. Decode ke string dengan mengabaikan error karakter tersembunyi
        content = bytes_data.decode("utf-8", errors="ignore")
        
        data = None
        
        # --- STRATEGI PARSING INTERNASIONAL UNTUK JSON KOTOR / SEMI-BROKEN ---
        # Metode 1: Standard load dengan melonggarkan aturan escape character
        try:
            data = json.loads(content, strict=False)
        except json.JSONDecodeError:
            pass
            
        # Metode 2: Pembersihan literal untuk backslash liar yang sering merusak JSON media sosial
        if data is None:
            try:
                # Mengubah backslash tunggal yang bukan escape sequence standar menjadi double backslash
                content_fixed = content.replace('\\•', '•').replace('\\…', '…').replace('\\', '\\\\')
                data = json.loads(content_fixed, strict=False)
            except json.JSONDecodeError:
                pass

        # Metode 3: Jika file berbentuk objek baris per baris (atau gabungan)
        if data is None:
            try:
                # Bersihkan pembungkus array jika ada, lalu pecah per baris objek
                raw_lines = content.strip().strip('[]').split('},\n')
                data_list = []
                for line in raw_lines:
                    line = line.strip()
                    if not line:
                        continue
                    if not line.endswith('}'):
                        line += '}'
                    if not line.startswith('{'):
                        line = '{' + line
                    try:
                        # Ganti backslash liar secara lokal per baris
                        line_fixed = line.replace('\\•', '•').replace('\\…', '…').replace('\\', '\\\\')
                        data_list.append(json.loads(line_fixed, strict=False))
                    except Exception:
                        continue
                if data_list:
                    data = data_list
            except Exception:
                pass

        # Metode 4: Fallback terakhir menggunakan AST literal eval
        if data is None:
            import ast
            try:
                data = ast.literal_eval(content)
            except Exception:
                pass

        # --- PROSES PEMBENTUKAN DATAFRAME DENGAN FULL NORMALIZATION ---
        if data is not None:
            # Menggunakan pd.json_normalize agar objek bersarang seperti 'statistics.playCount' otomatis terurai menjadi kolom tersendiri
            raw_df = pd.json_normalize(data)

            # Memastikan kolom 'media' berhasil terdeteksi
            if 'media' in raw_df.columns:
                st.success("Struktur JSON berhasil dibaca dan dinormalisasi sepenuhnya!")
                
                # Mendapatkan daftar media unik secara otomatis (twitter, tiktok, instagram, media_online, dll)
                media_list = sorted(raw_df['media'].dropna().unique().tolist())
                
                st.subheader("📁 Pilih Klasifikasi Media")
                selected_media = st.selectbox(
                    "Pilih jenis media untuk diekstrak (Setiap media akan menampilkan kolom spesifiknya secara rapi):", 
                    media_list
                )
                
                # Filter data berdasarkan media terpilih
                df_filtered = raw_df[raw_df['media'] == selected_media].copy()
                
                # PEMBERSIHAN 1: Hapus kolom sampah yang seluruh barisnya kosong (NaN) khusus untuk media ini
                df_clean = df_filtered.dropna(how='all', axis=1)
                
                # PEMBERSIHAN 2: Bersihkan string teks dari karakter Enter/Line Break (\n atau \r) 
                # Langkah ini wajib agar saat diekspor menggunakan '|', baris tabel tidak melompat ke bawah
                for col in df_clean.columns:
                    if df_clean[col].dtype == 'object':
                        df_clean[col] = (df_clean[col]
                                         .astype(str)
                                         .str.replace(r'[\r\n]+', ' ', regex=True)
                                         .str.replace(r'\s+', ' ', regex=True)
                                         .str.strip())
                
                # Tampilkan Preview Data Bersih
                st.subheader(f"📋 Pratinjau Tabel Data Bersih: {selected_media.upper()}")
                st.dataframe(df_clean.head(10))
                
                st.subheader("📊 Statistik Hasil Pemrosesan")
                st.write(f"Jumlah Baris Data: `{df_clean.shape[0]}` | Jumlah Kolom Karakteristik: `{df_clean.shape[1]}`")
                
                # Tampilkan informasi field/kolom apa saja yang berhasil diekstrak
                with st.expander("Lihat Daftar Kolom yang Tersedia untuk Media Ini"):
                    st.write(list(df_clean.columns))

                # --- CONFIG DOWNLOAD CSV DENGAN PEMBATAS PIPE '|' ---
                st.sidebar.subheader("Pengaturan Output")
                sep = st.sidebar.selectbox("Pemisah Kolom (Separator)", ["|", ",", ";", "\\t"])
                include_index = st.sidebar.checkbox("Sertakan Indeks Nomor", value=False)
                
                # Generate data CSV dengan standard encoding utf-8-sig agar aman dibuka di Excel
                csv_data = df_clean.to_csv(index=include_index, sep=sep, encoding="utf-8-sig")
                
                # Penamaan file output otomatis yang rapi
                file_base_name = uploaded_file.name.rsplit('.', 1)[0]
                output_filename = f"{file_base_name}_{selected_media}_clean.csv"
                
                st.markdown("---")
                st.download_button(
                    label=f"📥 Unduh CSV Bersih Khusus {selected_media.upper()}",
                    data=csv_data,
                    file_name=output_filename,
                    mime="text/csv"
                )
            else:
                st.error("Gagal klasifikasi: Kolom identitas 'media' tidak ditemukan di dalam file JSON Anda.")
        else:
            st.error("Aplikasi gagal mem-parsing struktur JSON. Struktur file terindikasi rusak di beberapa baris.")
            st.info("Solusi alternatif: Pastikan file JSON Anda diawali tanda `[` dan diakhiri tanda `]` serta memiliki format objek yang valid.")
            
    except Exception as e:
        st.error(f"Terjadi kesalahan fatal pada sistem: {str(e)}")