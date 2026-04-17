import streamlit as st
from google.cloud import bigquery
import pandas as pd
from datetime import datetime
from google.oauth2 import service_account
import plotly.express as px
# --- 1. ตั้งค่าการเชื่อมต่อและ Scopes ---
st.set_page_config(layout="wide", page_title="Performance Dashboard")

@st.cache_data(ttl=900)
def get_full_data():
    # ดึงข้อมูลจาก Secrets (Streamlit Cloud)
    info = st.secrets["gcp_service_account"]
    SCOPES = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/bigquery",
        "https://www.googleapis.com/auth/cloud-platform"
    ]
    credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    client = bigquery.Client(credentials=credentials, project="dol-workspace")
    
    query = "SELECT * FROM `dol-workspace.Dashboard_Work69.v_master_report`"
    df = client.query(query).to_dataframe()
    df['NAME'] = df['NAME'].fillna("ไม่ระบุชื่อ").astype(str) # เติมชื่อแทนค่าว่าง
    df = df[df['NAME']!="ไม่ระบุชื่อ"]
    df['sheet_name'] = df['sheet_name'].fillna("ไม่ระบุชีต").astype(str)
    return df

# โหลดข้อมูล
try:
    df = get_full_data()
    df['DATE_SUBMIT'] = pd.to_datetime(df['DATE_SUBMIT']).dt.date
    today = datetime.now().date()
except Exception as e:
    st.error(f"เกิดข้อผิดพลาดในการดึงข้อมูล: {e}")
    st.stop()

# --- 2. ฟังก์ชันคำนวณสรุปผลพร้อม Progress Bar ---
def summary_with_metrics(input_df, group_col, show_total=True, daily=False):
    # นับจำนวนงาน
    total_assigned = input_df.groupby(group_col).size().reset_index(name='มอบหมาย')
    finished_tasks = input_df[input_df['DATE_SUBMIT'].notnull()].groupby(group_col).size().reset_index(name='ดำเนินการแล้ว')
    
    # รวมตาราง
    summary = pd.merge(total_assigned, finished_tasks, on=group_col, how='left').fillna(0)
    summary['ดำเนินการแล้ว'] = summary['ดำเนินการแล้ว'].astype(int)
    if daily: 
        summary['มอบหมาย'] = 130
    # คำนวณเปอร์เซ็นต์ (%)
    summary['ความคืบหน้า (%)'] = (summary['ดำเนินการแล้ว'] / summary['มอบหมาย']) * 100
    
    # --- เพิ่มการเรียงลำดับจากมากไปน้อยตามคอลัมน์ 'ดำเนินการแล้ว' ---
    summary = summary.sort_values(by='ดำเนินการแล้ว', ascending=False)
    
    # เงื่อนไขการเพิ่มแถวผลรวม (Total)
    if show_total:
        total_row = pd.DataFrame({
            group_col: ['--- รวมทั้งหมด ---'],
            'มอบหมาย': [summary['มอบหมาย'].sum()],
            'ดำเนินการแล้ว': [summary['ดำเนินการแล้ว'].sum()],
            'ความคืบหน้า (%)': [(summary['ดำเนินการแล้ว'].sum() / summary['มอบหมาย'].sum() * 100) if summary['มอบหมาย'].sum() > 0 else 0]
        })
        return pd.concat([summary, total_row], ignore_index=True)
    
    return summary
    
def display_styled_dataframe(df_display, title):
    st.subheader(title)
    
    # คำนวณความสูงให้พอดีกับจำนวนแถว
    dynamic_height = 35 * (len(df_display) + 1)
    # จำกัดความสูงไม่ให้เกิน 500px เพื่อความสวยงามถ้าข้อมูลเยอะ
    container_height = min(dynamic_height, 500) 
    
    st.dataframe(
        df_display,
        column_config={
            "ความคืบหน้า (%)": st.column_config.ProgressColumn(
                "ความคืบหน้า (%)",
                help="เปอร์เซ็นต์งานที่ดำเนินการแล้วเทียบกับงานที่ได้รับมอบหมาย",
                format="%.2f%%",
                min_value=0,
                max_value=100,
            ),
            # จัดรูปแบบตัวเลขคอลัมน์อื่นๆ ให้ดูง่าย
            "มอบหมาย": st.column_config.NumberColumn("มอบหมาย", format="%,d ", alignment="center"),
            "ดำเนินการแล้ว": st.column_config.NumberColumn("ดำเนินการแล้ว", format="%,d ", alignment="center"),
        },
        use_container_width=True,
        hide_index=True,
        height=dynamic_height #dynamic_height
    )
    
# --- 3. การวาง Layout ---
st.title("🚀 Dashboard ติดตามงานขึ้นรูปแปลง")

# สร้าง Dropdown กรองชื่อคน (Global หรือแยกฝั่ง)
all_names = ["แสดงทุกคน"] + sorted(df['NAME'].dropna().astype(str).unique().tolist())

# --- ส่วนคำนวณกราฟเส้น 30 วัน พร้อม Buffer ---
st.divider()
st.subheader("📈 แนวโน้มผลงานย้อนหลัง 30 วัน")
col1, col2 = st.columns([0.2, 0.8])
selected_name = col1.selectbox("🔍 ค้นหาชื่อคน:", all_names, key="trend_search")

# 1. เตรียมข้อมูล (30 วันล่าสุด)
last_30_days = [today - pd.Timedelta(days=i) for i in range(30)]

df_last_30 = df if selected_name == "แสดงทุกคน" else df[df['NAME'] == selected_name]
df_last_30 = df_last_30[df_last_30['DATE_SUBMIT'].isin(last_30_days)]
trend_data_30 = (
    df_last_30.groupby('DATE_SUBMIT')
    .size()
    .reindex(last_30_days, fill_value=0)
    .reset_index(name='ยอดงาน')
    .sort_values('DATE_SUBMIT')
)

# 2. คำนวณหาค่าสูงสุด และเพิ่ม Buffer 20%
max_val = trend_data_30['ยอดงาน'].max()
y_upper_limit = max_val * 1.30 if max_val > 0 else 1000 # ถ้าค่าสูงสุดเป็น 0 ให้กันไว้ที่ 10

# 3. สร้างกราฟ
fig = px.line(
    trend_data_30, 
    x='DATE_SUBMIT', 
    y='ยอดงาน',
    text='ยอดงาน',
    markers=True
)

# 4. ปรับแต่งการแสดงผล
fig.update_traces(
    textposition="top center", 
    line_color="#29b5e8",
    marker=dict(size=8, symbol="circle"),
    textfont=dict(size=10, color="white") # ปรับขนาด/สีตัวเลขบนกราฟ
)

fig.update_layout(
    xaxis=dict(
        title="วันที่",
        type='date',
        tickformat="%d %b", # แสดงเป็น "17 Apr"
        dtick=86400000.0,    # บังคับแสดงทุกวัน (1 วัน = 86,400,000 ms)
        tickangle=-90    # เอียงตัวอักษรเพื่อให้ไม่ซ้อนกัน
    ),
    yaxis=dict(
        title="ยอดงาน",
        range=[0, y_upper_limit] # ตั้งค่าขอบเขตแกน Y ให้สูงกว่าค่า max 20%
    ),
    hovermode="x unified",
    height=500,
    #margin=dict(l=20, r=20, t=40, b=20)
)

# 5. แสดงกราฟ
st.plotly_chart(fig, use_container_width=True)

st.caption(f"📊 รวมผลงาน 30 วันล่าสุด: **{trend_data_30['ยอดงาน'].sum():,}** รายการ")

st.divider()

left_col, right_col = st.columns([1, 1])

# --- [ฝั่งซ้าย: ข้อมูลทั้งหมด] ---
with left_col:
    st.header("📊 ยอดงานสะสมทั้งหมด")
    l1, l2 = st.columns([0.5, 0.5])
    selected_name_l = l1.selectbox("🔍 ค้นหาชื่อคน (ฝั่งซ้าย):", all_names, key="left_search")
    
    display_df_l = df if selected_name_l == "แสดงทุกคน" else df[df['NAME'] == selected_name_l]
    
    # เช็คว่าจะโชว์ผลรวมไหม (ถ้าเลือกชื่อคน จะไม่โชว์)
    show_total_l = True if selected_name_l == "แสดงทุกคน" else False
    
    # ตารางรายคน (ส่ง show_total เข้าไป)
    #st.subheader("👨‍💼 สรุปรายบุคคล")
    res_name_l = summary_with_metrics(display_df_l, 'NAME', show_total=show_total_l)
    display_styled_dataframe(res_name_l, "👨‍💼 สรุปรายบุคคล")
    
    # Progress Bar ภาพรวมฝั่งซ้าย
    total_pct_l = res_name_l.iloc[-1]['ความคืบหน้า (%)']
    st.write(f"**ความคืบหน้าภาพรวมสะสม:** {total_pct_l:.2f}%")
    if total_pct_l > 100:
        total_pct_l = 100
    st.progress(total_pct_l / 100)

    # ตารางรายแผ่นงาน
    #st.subheader("📂 สรุปตามแผ่นงาน")
    res_sheet_l = summary_with_metrics(display_df_l, 'sheet_name')
    display_styled_dataframe(res_sheet_l, "📂 สรุปตามแผ่นงาน")

# --- [ฝั่งขวา: เฉพาะวันนี้] ---
with right_col:
    
    st.header(f"📅 ผลงานตามวันที่")
    
    r1, r2 = st.columns([0.5, 0.5])
    selected_name_r = r1.selectbox("🔍 ค้นหาชื่อคน (ฝั่งขวา):", all_names, key="right_search")
    selected_date = r2.date_input( "📆 เลือกวันที่ต้องการดู:",today, key="date_selector")
    
    df_today = df[df['DATE_SUBMIT'] == selected_date]
    display_df_r = df_today if selected_name_r == "แสดงทุกคน" else df_today[df_today['NAME'] == selected_name_r]
    
    if display_df_r.empty:
        st.warning("⚠️ ไม่มีข้อมูลงานที่ดำเนินการในวันนี้")
    else:
        # เช็คว่าจะโชว์ผลรวมไหม (ถ้าเลือกชื่อคน จะไม่โชว์)
        show_total_r = True if selected_name_r == "แสดงทุกคน" else False
        
        # ตารางรายคน (วันนี้)
        #st.subheader("👨‍💼 สรุปรายบุคคล (วันนี้)")
        res_name_r = summary_with_metrics(display_df_r, 'NAME', show_total=show_total_r, daily=True)
        display_styled_dataframe(res_name_r, f"👨‍💼 สรุปรายบุคคลวันที่ {selected_date}")
        
        # Progress Bar ภาพรวมฝั่งขวา
        total_pct_r = res_name_r.iloc[-1]['ความคืบหน้า (%)']
        st.write(f"**ความคืบหน้างานวันนี้:** {total_pct_r:.2f}%")
        if total_pct_r > 100:
            total_pct_r = 100
        st.progress(total_pct_r / 100)

        # ตารางรายแผ่นงาน (วันนี้)
        #st.subheader("📂 สรุปตามแผ่นงาน (วันนี้)")
        res_sheet_r = summary_with_metrics(display_df_r, 'sheet_name')
        display_styled_dataframe(res_sheet_r, f"📂 สรุปตามแผ่นงานวันที่ {selected_date}")
        
st.divider()
left_col_, right_col_ = st.columns([1, 1])
    #total_assigned = input_df.groupby(group_col).size().reset_index(name='มอบหมาย')
    #finished_tasks = input_df[input_df['DATE_SUBMIT'].notnull()].groupby(group_col).size().reset_index(name='ดำเนินการแล้ว')
df_TYP = df.groupby('SURV_TYP').size().reset_index(name='จำนวน')
df_TYP = df_TYP.sort_values(by='จำนวน', ascending=False)
df_TYP = df_TYP[df_TYP['SURV_TYP']!="                                                                                                                                                                                                      "]
dynamic_height = 35 * (len(df_TYP) + 1)
left_col_.dataframe(df_TYP, use_container_width=True, hide_index=True,
                    column_config={
                                    "จำนวน": st.column_config.NumberColumn("มอบหมาย", format="%,d ", alignment="center"),
                                    },
                    height=dynamic_height
                   )

df_BUILD = df.groupby('BUILD_FROM').size().reset_index(name='จำนวน')
df_BUILD = df_BUILD.sort_values(by='จำนวน', ascending=False)
df_BUILD = df_BUILD[df_BUILD['BUILD_FROM']!="                                                                                                                                                                                                      "]
dynamic_height = 35 * (len(df_TYP) + 1)
right_col_.dataframe(df_BUILD, use_container_width=True, hide_index=True,
                     column_config={
                                    "จำนวน": st.column_config.NumberColumn("มอบหมาย", format="%,d ", alignment="center"),
                                    },
                     height=dynamic_height
                   )
