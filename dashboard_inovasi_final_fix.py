import io
from io import BytesIO
from typing import Optional
import folium
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# python -m streamlit run dashboard_inovasi.py -- cd c:/MAGANG/

# ------------- Page config -------------
st.set_page_config(layout="wide", page_title="Dashboard Inovasi Daerah")

# ------------- Cached helpers -------------
@st.cache_data
def load_data(uploaded_file: Optional[io.BytesIO] = None) -> pd.DataFrame:
    default_path = "/mnt/data/data_inovasi.xlsx"
    try:
        if uploaded_file is None:
            xls = pd.ExcelFile(default_path)
            sheet_name = xls.sheet_names[0]
            df = pd.read_excel(xls, sheet_name=sheet_name)
        else:
            df = pd.read_excel(uploaded_file, sheet_name=0)
    except Exception as e:
        st.error(f"Gagal memuat file: {e}")
        return pd.DataFrame()

    if df is None or df.empty:
        st.warning("Data kosong atau tidak terbaca.")
        return pd.DataFrame()
    
    
    # Normalize column names
    df.columns = [str(c).strip() for c in df.columns]

    # 🔹 Hapus duplikat data
    before = len(df)
    df = df.drop_duplicates()
    after = len(df)
    if before != after:
        st.info(f"🧹 Hapus duplikat: {before - after} baris terhapus, tersisa {after} baris.")
    else:
        st.success("✅ Tidak ada data duplikat. Data sudah bersih.")

    # Coerce numeric columns
    if 'Kematangan' in df.columns:
        df['Kematangan'] = pd.to_numeric(df['Kematangan'], errors='coerce')

    # Parse date columns if present
    date_cols = ['Tanggal Input', 'Tanggal Penerapan', 'Tanggal Pengembangan']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)

    # Split coordinates into lat/lon (support "Koordinat" as "lat,lon" or columns 'lat','lon')
    if 'Koordinat' in df.columns:
        coords = df['Koordinat'].astype(str).str.split(',', n=1, expand=True)
        df['lat'] = pd.to_numeric(coords[0], errors='coerce')
        df['lon'] = pd.to_numeric(coords[1], errors='coerce')
    else:
        # if lat/lon already present, coerce to numeric
        if 'lat' in df.columns:
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        if 'lon' in df.columns:
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce')

    # Ensure certain columns are string type
    cat_cols = ['Jenis', 'Bentuk Inovasi', 'Admin OPD', 'Kategori Admin OPD', 'Urusan Utama', 'Asta Cipta', 'Daerah']
    for c in cat_cols:
        if c in df.columns:
            df[c] = df[c].astype(str).replace(['nan', 'NaN', 'None'], np.nan)

    # 🔹 Tambahkan pengelompokan Admin OPD
    if 'Admin OPD' in df.columns:
        def categorize_admin(admin):
            if pd.isna(admin):
                return "Lainnya"
            admin_lower = str(admin).lower()
            if any(x in admin_lower for x in ["sma", "smk", "slb"]):
                return "Dinas Pendidikan"
            elif "iga2025.provinsi.jawa.timur" in admin_lower:
                return "Admin IGA 2025"
            else:
                return str(admin).split(".")[0].strip().title()

        df['Admin OPD Grouped'] = df['Admin OPD'].apply(categorize_admin)

    st.success(f"Data berhasil dimuat: {df.shape[0]} baris, {df.shape[1]} kolom")
    return df

@st.cache_data(hash_funcs={BytesIO: id})
def generate_wordcloud(text_series: pd.Series, max_words: int = 100, colormap: str = "viridis") -> Optional[BytesIO]:
    text = ' '.join(text_series.dropna().astype(str).values)
    if not text.strip():
        return None

    wc = WordCloud(
        width=800, height=400,
        background_color='white',
        max_words=max_words,
        colormap=colormap
    )
    wc.generate(text)

    img = wc.to_image()
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

@st.cache_data
def to_excel_bytes(df_in: pd.DataFrame, sheet_name: str = "Filtered") -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_in.to_excel(writer, index=False, sheet_name=sheet_name)
        workbook = writer.book
        worksheet = writer.sheets[sheet_name]
        for i, col in enumerate(df_in.columns):
            max_len = max(df_in[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.set_column(i, i, max_len)
    return output.getvalue()

# ------------- Sidebar: file upload & filters -------------
with st.sidebar:
    st.header("📂 Sumber Data & Filter")
    uploaded_file = st.file_uploader(
        "Unggah file Excel (.xlsx) atau biarkan kosong untuk default",
        type=['xlsx']
    )

    # load data
    df = load_data(uploaded_file if uploaded_file is not None else None)

    st.markdown("---")
    st.subheader("🔎 Filter umum")

    # Filter Kematangan minimal
    min_kematangan = st.number_input(
        "Kematangan minimal",
        min_value=0,
        value=0,
        step=1
    )
# ================== Filter Jenis ==================
if 'Jenis' in df.columns:
    jenis_options = sorted(df['Jenis'].dropna().unique().astype(str).tolist())
    jenis_selected = st.multiselect(
        "Pilih Jenis (Digital/Non Digital)",
        options=['All'] + jenis_options,
        default=['All']
    )
else:
    jenis_selected = ['All']

# ================== Filter Admin OPD ==================
if 'Admin OPD Grouped' in df.columns:
    opd_options = sorted(df['Admin OPD Grouped'].dropna().unique().tolist())
    opd_selected = st.multiselect(
        "Pilih OPD (Admin OPD)",
        options=['All'] + opd_options,
        default=['All']
    )
else:
    opd_selected = ['All']

# ================== Filter Tambahan ==================
with st.expander("⚙️ Filter tambahan"):
    if 'Kategori Admin OPD' in df.columns:
        kategori_options = sorted(df['Kategori Admin OPD'].dropna().unique().astype(str).tolist())
        kategori_selected = st.multiselect(
            "Kategori Admin OPD",
            options=['All'] + kategori_options,
            default=['All']
        )
    else:
        kategori_selected = ['All']

    if 'Urusan Utama' in df.columns:
        urusan_options = sorted(df['Urusan Utama'].dropna().unique().astype(str).tolist())
        urusan_selected = st.multiselect(
            "Urusan Utama",
            options=['All'] + urusan_options,
            default=['All']
        )
    else:
        urusan_selected = ['All']

st.markdown("---")
st.info("💡 Tips: Klik grafik untuk interaksi. Gunakan filter di atas untuk mengupdate semua tampilan.")

# ================== Cek Data Sebelum Filter ==================
if df.empty:
    st.warning("⚠️ Data belum tersedia atau gagal dimuat.")
    st.info("👉 Silakan upload file Excel melalui sidebar, atau pastikan file `data_inovasi.xlsx` ada di folder `/mnt/data/`.")
    st.stop()


# ================== Terapkan Filter ==================
def apply_filters(
    df: pd.DataFrame,
    min_kematangan: int,
    jenis_selected: list,
    opd_selected: list,
    kategori_selected: list = None,
    urusan_selected: list = None
) -> pd.DataFrame:
    """Menerapkan berbagai filter pada DataFrame inovasi berdasarkan input pengguna."""

    df_filtered = df.copy()

    # --- Filter: Tingkat Kematangan ---
    if 'Kematangan' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Kematangan'] >= min_kematangan]

    # --- Filter: Jenis Inovasi (Digital / Non-Digital) ---
    if 'Jenis' in df_filtered.columns and jenis_selected and 'All' not in jenis_selected:
        df_filtered = df_filtered[df_filtered['Jenis'].isin(jenis_selected)]

    # --- Filter: Admin OPD Grouped ---
    if 'Admin OPD Grouped' in df_filtered.columns and opd_selected and 'All' not in opd_selected:
        df_filtered = df_filtered[df_filtered['Admin OPD Grouped'].isin(opd_selected)]

    # --- Filter: Kategori Admin OPD ---
    if kategori_selected and 'All' not in kategori_selected and 'Kategori Admin OPD' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Kategori Admin OPD'].isin(kategori_selected)]

    # --- Filter: Urusan Utama ---
    if urusan_selected and 'All' not in urusan_selected and 'Urusan Utama' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Urusan Utama'].isin(urusan_selected)]

    # --- Filter: Pencarian Asta Cipta ---
    if 'search_astacipta' in globals() and search_astacipta:
        df_filtered = df_filtered[
            df_filtered['Asta Cipta'].astype(str).str.contains(search_astacipta, case=False, na=False)
        ]

    # --- Filter: Daerah (untuk peta) ---
    if 'daerah_col' in globals() and daerah_col and 'daerah_selected' in globals() and daerah_selected != 'All':
        df_filtered = df_filtered[df_filtered[daerah_col] == daerah_selected]

    return df_filtered


# ================== Terapkan Fungsi Filter ==================
df_filtered = apply_filters(
    df,
    min_kematangan=min_kematangan,
    jenis_selected=jenis_selected,
    opd_selected=opd_selected,
    kategori_selected=kategori_selected,
    urusan_selected=urusan_selected
)

# ================== Jika Data Kosong ==================
if df_filtered.empty:
    st.warning("⚠️ Tidak ada data yang sesuai filter. Silakan ubah filter di sidebar.")
    st.stop()

# ================== Layout Utama ==================
st.title("📊 Dashboard Inovasi Daerah — Interactive")
st.markdown("""
Dashboard ini menampilkan berbagai visualisasi interaktif untuk memantau inovasi daerah.  
Gunakan filter di sidebar untuk mempersempit data berdasarkan **Kematangan, OPD, Jenis, Bentuk, Urusan**, dan lainnya.
""")

# Ringkasan filter aktif
st.subheader("1) Filter Aktif")
filter_summary = [
    f"Kematangan ≥ {min_kematangan}",
    f"Jenis: {', '.join(jenis_selected) if 'All' not in jenis_selected else 'Semua'}",
    f"Admin OPD: {', '.join(opd_selected) if 'All' not in opd_selected else 'Semua'}"
]
if kategori_selected and 'All' not in kategori_selected:
    filter_summary.append(f"Kategori: {', '.join(kategori_selected)}")
if urusan_selected and 'All' not in urusan_selected:
    filter_summary.append(f"Urusan: {', '.join(urusan_selected)}")

st.info(" | ".join(filter_summary))
st.divider()

# Metric
total_inovasi = len(df)
jumlah_terpilih = len(df_filtered)
persentase = (jumlah_terpilih / total_inovasi * 100) if total_inovasi > 0 else 0

st.metric(
    label=f"Jumlah inovasi (sesuai filter)",
    value=jumlah_terpilih,
    delta=f"{persentase:.1f}% dari total {total_inovasi}"
)

# Tabel contoh: tampilkan top setelah filter
if not df_filtered.empty:
    cols_to_show = [c for c in ['Judul Inovasi', 'Admin OPD', 'Kematangan', 'Tahapan Inovasi'] if c in df_filtered.columns]
    df_tampil = df_filtered[cols_to_show].sort_values(by="Kematangan", ascending=False).reset_index(drop=True)
    df_tampil.index = df_tampil.index + 1
    df_tampil.index.name = "No"
    st.dataframe(df_tampil, use_container_width=True)
else:
    st.warning("⚠️ Tidak ada data dengan filter tersebut.")

st.divider()

# 2) Analisis Berdasarkan OPD
st.subheader("2) Analisis berdasarkan Kategori Admin OPD")

if 'Admin OPD' in df_filtered.columns:
    import re
    import plotly.express as px

    # --- Fungsi mapping kategori utama ---
    def kategori_mapping(x):
        x_str = str(x)
        if x_str.upper() in ['SMA', 'SMK', 'SLB']:
            return 'Dinas Pendidikan'
        elif x_str.lower() == 'admin.jawa.timur':
            return 'Admin IGA'
        else:
            return x_str.title()

    # --- Fungsi membuat nama pendek ---
    def nama_pendek(x):
        x_str = str(x)
        if '(Jatimprov.' in x_str:
            match = re.search(r'\(Jatimprov\.([^)]+)\)', x_str)
            if match:
                return match.group(1).replace('.', ' ').title()
        elif '(Iga2024.' in x_str:
            match = re.search(r'\(Iga2024\.([^)]+)\)', x_str)
            if match:
                return match.group(1).replace('.', ' ').title()
        if '(' in x_str:
            return x_str.split('(')[0].strip().title()
        return x_str.title()

    # Tambahkan kolom kategori dan nama pendek
    df_filtered = df_filtered.assign(
        **{
            "Kategori Admin OPD": df_filtered['Admin OPD'].apply(kategori_mapping),
            "Nama Pendek OPD": df_filtered['Admin OPD'].apply(nama_pendek)
        }
    )

    # Hitung jumlah per nama pendek
    opd_counts = df_filtered['Nama Pendek OPD'].value_counts().reset_index()
    opd_counts.columns = ['Nama Pendek OPD', 'Jumlah']
    opd_counts.index = opd_counts.index + 1
    opd_counts.index.name = "No"

    # Batasi hanya top 30 agar tidak terlalu padat
    opd_counts_top = opd_counts.head(30).sort_values(by='Jumlah', ascending=True)

    # --- Chart horizontal agar label terbaca rapi ---
    fig = px.bar(
        opd_counts_top,
        x='Jumlah',
        y='Nama Pendek OPD',
        orientation='h',
        text='Jumlah',
        title="🏢 Top 30 Kategori Admin OPD dengan Jumlah Inovasi Terbanyak",
        color='Jumlah',
        color_continuous_scale='Blues'
    )

    fig.update_traces(
        textposition="outside",
        textfont=dict(size=12)
    )

    fig.update_layout(
        xaxis_title="Jumlah Inovasi",
        yaxis_title="Kategori Admin OPD",
        height=900,
        title_font=dict(size=18),
        margin=dict(l=150, r=40, t=80, b=40),
        coloraxis_showscale=False,
    )

    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("Kolom 'Admin OPD' tidak ditemukan di data.")


# 3) Bentuk Inovasi
st.subheader("3) Bentuk Inovasi")

if 'Bentuk Inovasi' in df_filtered.columns:
    bentuk_counts = df_filtered['Bentuk Inovasi'].value_counts().reset_index()
    bentuk_counts.columns = ['Bentuk Inovasi', 'Jumlah']

    # --- Tambahkan nomor urut mulai dari 1 ---
    bentuk_counts.index = bentuk_counts.index + 1
    bentuk_counts.index.name = "No"

    # --- Debug (cek isi df) ---
    st.write("Cek bentuk_counts:", bentuk_counts.head())

    # --- Pie chart ---
    fig_pie = px.pie(
        bentuk_counts,
        names="Bentuk Inovasi",   # kategori
        values="Jumlah",          # jumlah data
        title="Distribusi Bentuk Inovasi",
        hole=0.3
    )
    fig_pie.update_traces(textinfo='percent+label')

    # --- Bar chart ---
    fig_bar = px.bar(
        bentuk_counts.sort_values("Jumlah", ascending=True),
        x='Jumlah',
        y='Bentuk Inovasi',
        orientation='h',
        text='Jumlah',
        title="Jumlah Inovasi per Bentuk"
    )
    fig_bar.update_traces(textposition='outside')

    # --- Tabs untuk pilih chart ---
    tab1, tab2 = st.tabs(["Pie Chart", "Bar Chart"])
    with tab1:
        st.plotly_chart(fig_pie, use_container_width=True)
    with tab2:
        st.plotly_chart(fig_bar, use_container_width=True)

    # --- Tabel data dengan nomor urut rapi ---
    st.dataframe(bentuk_counts, use_container_width=True)

else:
    st.warning("Kolom 'Bentuk Inovasi' tidak ditemukan di data.")


# 4) Jenis Inovasi (Digital vs Non Digital) + Timeline
st.subheader("4) Jenis Inovasi (Digital vs Non Digital)")

if 'Jenis' in df_filtered.columns:
    # Hitung jumlah per jenis
    jenis_counts = (
        df_filtered['Jenis']
        .value_counts()
        .reset_index()
    )
    jenis_counts.columns = ['Jenis', 'Jumlah']   # pastikan nama kolom benar

    # --- Tambahkan nomor urut mulai dari 1 ---
    jenis_counts.index = jenis_counts.index + 1
    jenis_counts.index.name = "No"

    # --- Pie Chart ---
    fig_pie = px.pie(
        jenis_counts,
        names='Jenis',
        values='Jumlah',
        title="Proporsi Digital vs Non Digital",
        hole=0.3
    )
    fig_pie.update_traces(textinfo='percent+label')

    # --- Bar Chart ---
    fig_bar = px.bar(
        jenis_counts.sort_values('Jumlah', ascending=True),
        x='Jumlah',
        y='Jenis',
        orientation='h',
        text='Jumlah',
        title='Jumlah per Jenis Inovasi'
    )
    fig_bar.update_traces(textposition='outside')

    # --- Tabs untuk chart ---
    tab1, tab2 = st.tabs(["Pie Chart", "Bar Chart"])
    with tab1:
        st.plotly_chart(fig_pie, use_container_width=True)
    with tab2:
        st.plotly_chart(fig_bar, use_container_width=True)

    # --- Tabel angka dengan nomor urut rapi ---
    st.dataframe(jenis_counts, use_container_width=True)

    # --- Timeline (jika ada kolom tanggal) ---
    if 'Tanggal Input' in df_filtered.columns:
        df_time = df_filtered.copy()
        df_time['month'] = (
            pd.to_datetime(df_time['Tanggal Input'], errors='coerce')
            .dt.to_period('M')
            .dt.to_timestamp()
        )
        time_counts = df_time.groupby(['month', 'Jenis']).size().reset_index(name='Count')

        if not time_counts.empty:
            fig2 = px.line(
                time_counts,
                x='month',
                y='Count',
                color='Jenis',
                markers=True,
                title='Tren Digital vs Non Digital per Bulan (Tanggal Input)'
            )
            fig2.update_layout(xaxis_title="Bulan", yaxis_title="Jumlah Inovasi")
            st.plotly_chart(fig2, use_container_width=True)

else:
    st.info('Kolom "Jenis" tidak ditemukan di data.')

st.markdown("---")


# 5) Urusan Pemerintahan Utama
st.subheader("5) Urusan Pemerintahan Utama")

if 'Urusan Utama' in df_filtered.columns:
    # Hitung jumlah per urusan
    urusan_counts = (
        df_filtered['Urusan Utama']
        .value_counts()
        .reset_index()
    )
    urusan_counts.columns = ['Urusan', 'Jumlah']  # fix nama kolom

    # --- Tambahkan nomor urut mulai dari 1 ---
    urusan_counts.index = urusan_counts.index + 1
    urusan_counts.index.name = "No"

    # --- Tabs untuk berbagai visualisasi ---
    tab1, tab2, tab3 = st.tabs(["Treemap", "Pie Chart", "Bar Chart"])

    with tab1:
        fig_tree = px.treemap(
            urusan_counts,
            path=['Urusan'],
            values='Jumlah',
            title='Treemap Urusan Pemerintahan Utama'
        )
        st.plotly_chart(fig_tree, use_container_width=True)

    with tab2:
        fig_pie = px.pie(
            urusan_counts,
            names='Urusan',
            values='Jumlah',
            title='Distribusi Urusan Pemerintahan Utama',
            hole=0.3
        )
        fig_pie.update_traces(textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)

    with tab3:
        fig_bar = px.bar(
            urusan_counts.sort_values('Jumlah', ascending=True),
            x='Jumlah',
            y='Urusan',
            orientation='h',
            text='Jumlah',
            title='Jumlah Inovasi per Urusan Pemerintahan Utama'
        )
        fig_bar.update_traces(textposition='outside')
        st.plotly_chart(fig_bar, use_container_width=True)

    # --- Tabel angka rapi dengan nomor urut ---
    st.write("📊 Data Ringkas Urusan")
    st.dataframe(urusan_counts, use_container_width=True, height=400)

else:
    st.info('Kolom "Urusan Utama" tidak ditemukan di data.')

st.markdown("---")
# ==========================================================
# 5.5) 🔍 Perbandingan Antar Wilayah Berdasarkan Lokasi Geografis
# ==========================================================
import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_folium import st_folium
import folium
from folium.plugins import Fullscreen, MiniMap
import streamlit.components.v1 as components

# ======================================================
# Inject library fullscreen agar JS-nya pasti termuat
# ======================================================
components.html("""
<link rel="stylesheet" href="https://unpkg.com/leaflet.fullscreen@1.6.0/Control.FullScreen.css" />
<script src="https://unpkg.com/leaflet.fullscreen@1.6.0/Control.FullScreen.js"></script>
""", height=0)

st.subheader("5.5) Perbandingan Antar Wilayah (berdasarkan lokasi geografis aktual)")

# ======================================================
# 1️⃣ LOAD DATA GEOLOKASI (map_jatim.csv)
# ======================================================
@st.cache_data
def load_map_data():
    df_map = pd.read_csv("map_jatim.csv")
    df_map.columns = df_map.columns.str.lower()
    return df_map

map_jatim = load_map_data()

# ======================================================
# 2️⃣ CEK KEBERADAAN KOLOM LATITUDE & LONGITUDE
# ======================================================
lat_col, lon_col = None, None
for c in df_filtered.columns:
    if 'lat' in c.lower():
        lat_col = c
    if 'lon' in c.lower() or 'lng' in c.lower():
        lon_col = c

if lat_col and lon_col:
    df_geo = df_filtered.dropna(subset=[lat_col, lon_col]).copy()

    # ======================================================
    # 3️⃣ PENCARIAN NAMA DAERAH DARI DATA LOKAL (tanpa API)
    # ======================================================
    st.info("🔍 Mengidentifikasi nama daerah berdasarkan koordinat (offline cache aktif)...")

    def get_nearest_area(lat, lon, df_ref, threshold=0.01):
        diff = abs(df_ref["lat"] - lat) + abs(df_ref["lon"] - lon)
        idx = diff.idxmin()
        if diff[idx] < threshold:
            return df_ref.loc[idx, "kabupaten"]
        else:
            return "Wilayah Jawa Timur (tidak teridentifikasi spesifik)"

    @st.cache_data(show_spinner=False)
    def map_coordinates_to_region(df, df_ref):
        df = df.copy()
        df["Daerah"] = df.apply(lambda x: get_nearest_area(x[lat_col], x[lon_col], df_ref), axis=1)
        return df

    df_geo = map_coordinates_to_region(df_geo, map_jatim)

    # ======================================================
    # 4️⃣ PILIHAN DAERAH
    # ======================================================
    daerah_tersedia = sorted(df_geo["Daerah"].dropna().unique())
    selected_daerah = st.selectbox("🏙️ Pilih daerah untuk melihat inovasi:", daerah_tersedia, index=0)

    df_selected = df_geo[df_geo["Daerah"] == selected_daerah]

    if df_selected.empty:
        st.warning(f"Tidak ada inovasi ditemukan di wilayah **{selected_daerah}**.")
        st.stop()

    # ======================================================
    # 5️⃣ VISUALISASI PETA INTERAKTIF (FOLIUM)
    # ======================================================
    st.write(f"🗺️ **Sebaran Inovasi di Wilayah: {selected_daerah}**")

    center_lat = df_selected[lat_col].mean()
    center_lon = df_selected[lon_col].mean()

    m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="cartodb positron")

    # ✅ Tambahkan tombol Fullscreen & MiniMap
    Fullscreen(
        position="topright",
        title="Layar Penuh",
        title_cancel="Keluar dari Layar Penuh",
        force_separate_button=True
    ).add_to(m)

    MiniMap(toggle_display=True, position="bottomright").add_to(m)

    daerah_col = "Daerah" if "Daerah" in df_selected.columns else None

    for _, row in df_selected.iterrows():
        popup_html = f"""
        <div style="font-size:14px">
            <b>{row.get('Judul Inovasi', 'Tanpa Judul')}</b><br>
            <i>OPD:</i> {row.get('OPD', row.get('Admin OPD', '-'))}<br>
            <i>Jenis:</i> {row.get('Jenis', '-')}<br>
            <i>Bentuk:</i> {row.get('Bentuk Inovasi', '-')}<br>
            <i>Kematangan:</i> {row.get('Kematangan', '-')}<br>
            <i>{daerah_col if daerah_col else 'Daerah'}:</i> {row.get(daerah_col, '-')}
        """

        if 'Urusan Utama' in row and pd.notna(row['Urusan Utama']):
            popup_html += f"<br><b>Urusan Utama:</b> {row['Urusan Utama']}"
        if 'Urusan lain yang beririsan' in row and pd.notna(row['Urusan lain yang beririsan']):
            popup_html += f"<br><b>Urusan lain:</b> {row['Urusan lain yang beririsan']}"
        if 'Link Video' in row and pd.notna(row['Link Video']):
            link_video = str(row['Link Video']).strip()
            if link_video.lower() not in ['-', 'nan', 'none', '']:
                popup_html += f"<br><a href='{link_video}' target='_blank'>🎥 Tonton Video</a>"
        popup_html += "</div>"

        tooltip_text = row.get("Nama Inovasi", "Inovasi")
        folium.Marker(
            [row[lat_col], row[lon_col]],
            tooltip=tooltip_text,
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(color="green", icon="info-sign")
        ).add_to(m)

    # ✅ Render map dengan container penuh agar plugin aktif
    st_folium(m, width=None, height=550, use_container_width=True)

    # ======================================================
    # 6️⃣ RANGKUMAN DAN DISTRIBUSI
    # ======================================================
    col1, col2 = st.columns(2)
    col1.metric("Jumlah Inovasi", len(df_selected))
    if "Kematangan" in df_selected.columns:
        rata_kematangan = df_selected["Kematangan"].mean()
        col2.metric("Rata-rata Kematangan", f"{rata_kematangan:.2f}")

    if "Jenis" in df_selected.columns and not df_selected["Jenis"].isna().all():
        st.write("💡 **Distribusi Jenis Inovasi di Daerah Ini**")
        jenis_counts = df_selected["Jenis"].value_counts().reset_index()
        jenis_counts.columns = ["Jenis", "Jumlah"]
        fig_jenis = px.pie(
            jenis_counts,
            names="Jenis",
            values="Jumlah",
            title=f"Proporsi Jenis Inovasi di {selected_daerah}",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig_jenis.update_traces(textinfo="percent+label", pull=[0.05]*len(jenis_counts))
        st.plotly_chart(fig_jenis, use_container_width=True)

    st.write("📋 **Detail Inovasi di Daerah Ini**")
    st.dataframe(df_selected.reset_index(drop=True), use_container_width=True, hide_index=True)

else:
    st.warning("Kolom latitude dan longitude tidak ditemukan di data.")


# ==========================================================
# 6) PETA LOKASI INOVASI (DENGAN SEARCH & FIT-TO-SCREEN)
# ==========================================================
st.subheader("6) Peta Lokasi Inovasi (dengan search & fit-to-screen)")

# --- Pastikan kolom daerah tersedia ---
daerah_col = None
for col_candidate in ['Daerah', 'Kabupaten/Kota', 'Provinsi', 'Nama Daerah']:
    if col_candidate in df_filtered.columns:
        daerah_col = col_candidate
        break

# --- Input pencarian teks (Judul / Urusan) ---
search_keyword = st.text_input(
    "🔍 Cari berdasarkan kata kunci di 'Judul Inovasi', 'Urusan Utama', atau 'Urusan lain yang beririsan':",
    ""
)

# --- Dropdown filter daerah (opsional) ---
daerah_selected = 'All'
if daerah_col:
    daerah_options = ['All'] + sorted(df_filtered[daerah_col].dropna().unique().tolist())
    daerah_selected = st.selectbox(f"Pilih {daerah_col} (untuk memusatkan peta):", daerah_options)

# --- Persiapkan data peta ---
if {'lat', 'lon'}.issubset(df_filtered.columns):
    map_df = df_filtered.dropna(subset=['lat', 'lon']).copy()
else:
    map_df = pd.DataFrame()

# --- Terapkan filter pencarian & daerah ---
if not map_df.empty:
    if search_keyword.strip():
        search_cols = [
            col for col in ['Judul Inovasi', 'Urusan Utama', 'Urusan lain yang beririsan']
            if col in map_df.columns
        ]
        if search_cols:
            mask = pd.Series(False, index=map_df.index)
            for col in search_cols:
                mask |= map_df[col].astype(str).str.contains(search_keyword, case=False, na=False)
            map_df = map_df[mask]

    if daerah_col and daerah_selected != 'All':
        map_df = map_df[map_df[daerah_col] == daerah_selected]

# --- Batasi maksimum inovasi agar peta tidak berat ---
map_df = map_df.head(600)

# --- Ringkasan jumlah data yang muncul ---
total_data = len(map_df)
st.success(f"✅ Menampilkan {total_data} inovasi pada peta interaktif berdasarkan filter pencarian & daerah.")

# --- Jika tidak ada data yang cocok ---
if map_df.empty:
    st.info("❗ Tidak ada data inovasi yang cocok dengan filter atau pencarian.")
else:
    from folium.plugins import MarkerCluster, Fullscreen, LocateControl, MiniMap

    # Tentukan pusat peta (fit to data)
    center_lat = map_df['lat'].mean()
    center_lon = map_df['lon'].mean()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=6, tiles="cartodb positron", control_scale=True)

    # Plugin interaktif tambahan (tambahkan setelah peta dibuat)
    LocateControl(auto_start=False).add_to(m)
    MiniMap(toggle_display=True, position='bottomright').add_to(m)

    # Cluster marker
    marker_cluster = MarkerCluster().add_to(m)

    # Warna marker berdasarkan jenis inovasi
    def marker_color(row):
        jenis = str(row.get('Jenis', '')).lower()
        if 'digital' in jenis:
            return 'green'
        elif 'non' in jenis:
            return 'orange'
        else:
            return 'gray'

    # Tambahkan marker ke peta
    for _, row in map_df.iterrows():
        if pd.notna(row['lat']) and pd.notna(row['lon']):
            popup_html = f"""
            <div style="font-size:14px">
                <b>{row.get('Judul Inovasi', 'Tanpa Judul')}</b><br>
                <i>OPD:</i> {row.get('Admin OPD', '-')}<br>
                <i>Jenis:</i> {row.get('Jenis', '-')}<br>
                <i>Bentuk:</i> {row.get('Bentuk Inovasi', '-')}<br>
                <i>Kematangan:</i> {row.get('Kematangan', '-')}<br>
                <i>{daerah_col if daerah_col else 'Daerah'}:</i> {row.get(daerah_col, '-')}
            """

            if 'Urusan Utama' in row:
                popup_html += f"<br><b>Urusan Utama:</b> {row['Urusan Utama']}"
            if 'Urusan lain yang beririsan' in row:
                popup_html += f"<br><b>Urusan lain:</b> {row['Urusan lain yang beririsan']}"

            if 'Link Video' in row and pd.notna(row['Link Video']):
                link_video = str(row['Link Video'])
                if link_video.strip() not in ['-', 'nan', 'None']:
                    popup_html += f"<br><a href='{link_video}' target='_blank'>🎥 Tonton Video</a>"

            popup_html += "</div>"

            folium.CircleMarker(
                location=[row['lat'], row['lon']],
                radius=7,
                color=marker_color(row),
                fill=True,
                fill_color=marker_color(row),
                fill_opacity=0.8,
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=row.get('Judul Inovasi', 'Inovasi')
            ).add_to(marker_cluster)

    # --- Fit-to-bounds agar otomatis menyesuaikan tampilan ---
    if not map_df[['lat', 'lon']].dropna().empty:
        bounds = [
            [map_df['lat'].min(), map_df['lon'].min()],
            [map_df['lat'].max(), map_df['lon'].max()]
        ]
        m.fit_bounds(bounds, padding=(30, 30))

    # 🔁 Tambahkan Fullscreen di akhir agar tombolnya tampil di atas semua layer
    Fullscreen(position='topleft', force_separate_button=True).add_to(m)

    # --- Daftar inovasi hanya muncul jika filter aktif ---
    if search_keyword.strip() or (daerah_col and daerah_selected != 'All'):
        st.markdown("### 📋 Daftar Inovasi yang Ditampilkan")
        for i, row in map_df.iterrows():
            st.markdown(f"**{i+1}. {row.get('Judul Inovasi', 'Tanpa Judul')}**")
        st.markdown("---")

    # --- Tampilkan peta ---
    st_folium(m, width=1200, height=600)


# ==========================================================
# 6.5) PERBANDINGAN INOVASI & SARAN KOLABORASI AI (CERDAS & KONTEKSTUAL)
# ==========================================================
import streamlit as st
import pandas as pd
from itertools import combinations
from google import genai

st.subheader("6.5) Perbandingan Inovasi & Saran Kolaborasi AI (Cerdas & Kontekstual)")

# ==========================================================
# Konfigurasi API Gemini
# ==========================================================
client = genai.Client(api_key="AIzaSyBlAfaa52yeJKYIMlkrtijBkNo3UZbNwPc")  # ganti dengan API key kamu


# ==========================================================
# Fungsi: Saran Kolaborasi dari Gemini
# ==========================================================
def saran_kolaborasi_gemini(pasangan_inovasi, konteks_df):
    """
    Memberikan rekomendasi kolaborasi untuk kombinasi inovasi (2–5)
    menggunakan model Gemini (gemini-2.5-flash).
    """
    # Ambil hanya data kontekstual dari inovasi yang dipilih → jauh lebih cepat
    subset_df = konteks_df[konteks_df['Judul Inovasi'].isin(pasangan_inovasi)] if not konteks_df.empty else pd.DataFrame()
    kolom_utama = [c for c in ['Judul Inovasi', 'Urusan Utama', 'Bentuk Inovasi', 'Deskripsi'] if c in subset_df.columns]
    data_ringkas = subset_df[kolom_utama].to_dict(orient='records') if not subset_df.empty else "Data inovasi tidak tersedia"

    prompt = f"""
Kamu adalah asisten AI yang membantu mengusulkan kolaborasi antar inovasi pemerintahan.
Berikut data inovasi yang relevan:
{data_ringkas}

Analisis kolaborasi potensial antara inovasi berikut:
{', '.join(pasangan_inovasi)}

Tolong berikan rekomendasi dengan format:
1️⃣ **Judul Kolaborasi (Singkat dan Menarik)**
2️⃣ **Jenis Kolaborasi**
3️⃣ **Manfaat Kolaborasi**
4️⃣ **Alasan Kesesuaian / Sinergi**
5️⃣ **Potensi Dampak**

Jawaban maksimal 5 paragraf, padat dan relevan.
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text if hasattr(response, "text") else str(response)


# ==========================================================
# Gunakan df_filtered sebagai sumber utama (fallback aman)
# ==========================================================
if 'df_filtered' in locals() and isinstance(df_filtered, pd.DataFrame) and not df_filtered.empty:
    df_compare = df_filtered.copy()
    st.info("💡 Menggunakan data dari df_filtered sebagai sumber analisis inovasi.")
else:
    st.warning("⚠️ Data df_filtered belum tersedia. Menggunakan contoh data dummy sementara.")
    df_compare = pd.DataFrame({
        'Judul Inovasi': ['Inovasi A', 'Inovasi B', 'Inovasi C'],
        'Urusan Utama': ['Kesehatan', 'Transportasi', 'Pendidikan'],
        'Bentuk Inovasi': ['Aplikasi', 'Sistem Informasi', 'Program Edukasi'],
        'Deskripsi': ['Inovasi contoh untuk testing', 'Data dummy agar tidak error', 'Hanya untuk simulasi']
    })


# ==========================================================
# Pastikan kolom penting tersedia
# ==========================================================
if 'Judul Inovasi' not in df_compare.columns:
    st.error("❌ Dataset tidak memiliki kolom 'Judul Inovasi'. Tidak dapat melanjutkan analisis.")
    st.stop()


# ==========================================================
# Pilihan Inovasi
# ==========================================================
selected_inovasi = st.multiselect(
    "Pilih beberapa inovasi yang ingin dikolaborasikan (minimal 2, maksimal 5):",
    options=sorted(df_compare['Judul Inovasi'].dropna().unique().tolist())
)

# ==========================================================
# Slider untuk membatasi jumlah kombinasi
# ==========================================================
max_comb = st.slider(
    "🔢 Batas jumlah kombinasi yang dianalisis oleh AI:",
    min_value=1, max_value=10, value=5,
    help="Gunakan slider ini untuk membatasi berapa banyak kombinasi inovasi yang akan dianalisis oleh AI (agar tidak terlalu lama)."
)

# ==========================================================
# Proses Analisis Kolaborasi
# ==========================================================
if selected_inovasi:
    if len(selected_inovasi) < 2:
        st.warning("⚠️ Pilih minimal 2 inovasi untuk mendapatkan saran kolaborasi.")
    elif len(selected_inovasi) > 5:
        st.warning("⚠️ Maksimal 5 inovasi saja agar analisis tetap fokus.")
    else:
        st.success(f"✅ AI akan menganalisis {len(selected_inovasi)} inovasi terpilih.")

        # Semua kombinasi dari 2 sampai jumlah terpilih
        all_combinations = []
        for r in range(2, len(selected_inovasi) + 1):
            all_combinations.extend(list(combinations(selected_inovasi, r)))

        # Batasi jumlah kombinasi sesuai slider
        all_combinations = all_combinations[:max_comb]

        # Tampilkan hasil tiap kombinasi
        for pasangan in all_combinations:
            with st.spinner(f"🤝 Menganalisis kolaborasi untuk: {', '.join(pasangan)}..."):
                rekomendasi = saran_kolaborasi_gemini(pasangan, df_compare)

            st.markdown(f"### 🔹 Kolaborasi: {' + '.join(pasangan)}")
            st.markdown(rekomendasi)
            st.markdown("---")

else:
    st.info("Pilih minimal 2 inovasi untuk memulai analisis kolaborasi AI.")


# 7) Timeline / Gantt
st.subheader("7) Timeline & Gantt")

# ---------- Perbaikan Gantt End logic ----------
if 'Tanggal Input' in df_filtered.columns:
    gantt_df = df_filtered.copy()
    
    # Pastikan kolom Kematangan numerik (hindari string "100" dianggap < 100)
    if 'Kematangan' in gantt_df.columns:
        gantt_df['Kematangan'] = pd.to_numeric(gantt_df['Kematangan'], errors='coerce')

    gantt_df['Start'] = pd.to_datetime(gantt_df['Tanggal Input'], errors='coerce')

    # Ambil Tanggal Penerapan jika ada, else Tanggal Pengembangan, else NaT
    gantt_df['End'] = pd.NaT
    if 'Tanggal Penerapan' in gantt_df.columns:
        gantt_df['End'] = pd.to_datetime(gantt_df['Tanggal Penerapan'], errors='coerce')
    if 'Tanggal Pengembangan' in gantt_df.columns:
        gantt_df['End'] = gantt_df['End'].fillna(pd.to_datetime(gantt_df['Tanggal Pengembangan'], errors='coerce'))

    # Jika End masih NaT dan Start ada -> tambah 30 hari
    mask_need_end = gantt_df['Start'].notna() & gantt_df['End'].isna()
    gantt_df.loc[mask_need_end, 'End'] = gantt_df.loc[mask_need_end, 'Start'] + pd.Timedelta(days=30)

    # Hapus baris tanpa tanggal valid
    gantt_plot_df = gantt_df.dropna(subset=['Start', 'End']).copy()

    if not gantt_plot_df.empty:
        gantt_plot_df['Task'] = gantt_plot_df['Judul Inovasi'].astype(str)

        # Dropdown untuk pewarnaan
        color_options = []
        for c in ['Kategori Admin OPD', 'Admin OPD', 'Jenis', 'Kematangan']:
            if c in gantt_plot_df.columns:
                color_options.append(c)

        color_choice = st.selectbox(
            "Warna berdasarkan:", options=color_options, index=0 if color_options else None
        ) if color_options else None

        # Urutkan berdasarkan tanggal mulai
        gantt_plot_df = gantt_plot_df.sort_values("Start")

        # Plot timeline
        fig = px.timeline(
            gantt_plot_df,
            x_start='Start',
            x_end='End',
            y='Task',
            color=color_choice,
            title='Gantt: Perjalanan Inovasi',
            hover_data=['Admin OPD', 'Jenis', 'Kematangan'] 
            if set(['Admin OPD', 'Jenis', 'Kematangan']).issubset(gantt_plot_df.columns) else None
        )

        fig.update_yaxes(visible=False, showticklabels=False)
        if color_choice:
            fig.update_layout(legend_title=color_choice)

        fig.update_layout(height=700, xaxis_title="Tanggal")

        # Tambahkan indikator debug untuk memastikan filter bekerja
        st.caption(f"📊 Jumlah data Gantt setelah filter: {len(gantt_plot_df)} | "
                   f"Nilai kematangan terendah: {gantt_plot_df['Kematangan'].min()}")
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info('Tidak ada baris dengan Start dan End yang valid untuk membuat Gantt.')
else:
    st.info('Kolom tanggal (Tanggal Input) tidak ditemukan.')

st.markdown("---")

# --- TABEL INTERAKTIF & DOWNLOAD ---
st.subheader('Tabel Interaktif & Unduh')
st.write('Tabel sesuai filter saat ini:')
if not df_filtered.empty:
    # Hapus kolom 'No' duplikat dan buat ulang nomor mulai dari 1
    df_display = df_filtered.copy().reset_index(drop=True)
    if 'No' in df_display.columns:
        df_display = df_display.drop(columns=['No'])
    df_display.insert(0, 'No', range(1, len(df_display) + 1))

    # Tampilkan tabel interaktif
    st.dataframe(df_display.head(500), use_container_width=True, hide_index=True)

    # Tombol unduh Excel
    excel_bytes = to_excel_bytes(df_display)
    st.download_button(
        label='💾 Unduh data terfilter sebagai Excel',
        data=excel_bytes,
        file_name='data_inovasi_filtered.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
else:
    st.info("Tidak ada data sesuai filter.")

st.markdown("---")
st.caption('Aplikasi ini dibuat oleh TIM MAGANG MANDIRI UNESA — versi revisi: peta search & zoom ditambahkan')



