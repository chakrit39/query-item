import streamlit as st
from google.cloud import bigquery
import pandas as pd
from datetime import datetime
from google.oauth2 import service_account

# --- 1. ตั้งค่าการเชื่อมต่อและ Scopes ---
st.set_page_config(layout="wide", page_title="Performance Dashboard")

@st.cache_data(ttl=600)
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
def summary_with_metrics(input_df, group_col):
    # นับจำนวนงาน
    total_assigned = input_df.groupby(group_col).size().reset_index(name='มอบหมาย')
    finished_tasks = input_df[input_df['DATE_SUBMIT'].notnull()].groupby(group_col).size().reset_index(name='ดำเนินการแล้ว')
    
    # รวมตาราง
    summary = pd.merge(total_assigned, finished_tasks, on=group_col, how='left').fillna(0)
    summary['ดำเนินการแล้ว'] = summary['ดำเนินการแล้ว'].astype(int)
    
    # คำนวณเปอร์เซ็นต์ (%)
    summary['ความคืบหน้า (%)'] = (summary['ดำเนินการแล้ว'] / summary['มอบหมาย']) * 100
    
    # เพิ่มแถวผลรวม (Total)
    total_row = pd.DataFrame({
        group_col: ['--- รวมทั้งหมด ---'],
        'มอบหมาย': [summary['มอบหมาย'].sum()],
        'ดำเนินการแล้ว': [summary['ดำเนินการแล้ว'].sum()],
        'ความคืบหน้า (%)': [(summary['ดำเนินการแล้ว'].sum() / summary['มอบหมาย'].sum() * 100) if summary['มอบหมาย'].sum() > 0 else 0]
    })
    
    return pd.concat([summary, total_row], ignore_index=True)

# --- 3. การวาง Layout ---
st.title("🚀 Dashboard ติดตามงาน พร้อมระบบกรองรายบุคคล")

# สร้าง Dropdown กรองชื่อคน (Global หรือแยกฝั่ง)
all_names = ["แสดงทุกคน"] + sorted(df['NAME'].dropna().astype(str).unique().tolist())

left_col, right_col = st.columns([1, 1])

# --- [ฝั่งซ้าย: ข้อมูลทั้งหมด] ---
with left_col:
    st.header("📊 ยอดงานสะสมทั้งหมด")
    selected_name_l = st.selectbox("🔍 ค้นหาชื่อคน (ฝั่งซ้าย):", all_names, key="left_search")
    
    display_df_l = df if selected_name_l == "แสดงทุกคน" else df[df['NAME'] == selected_name_l]
    
    # ตารางรายคน
    st.subheader("👨‍💼 สรุปรายบุคคล")
    res_name_l = summary_with_metrics(display_df_l, 'NAME')
    st.dataframe(res_name_l, use_container_width=True, hide_index=True)
    
    # Progress Bar ภาพรวมฝั่งซ้าย
    total_pct_l = res_name_l.iloc[-1]['ความคืบหน้า (%)']
    st.write(f"**ความคืบหน้าภาพรวมสะสม:** {total_pct_l:.2f}%")
    st.progress(total_pct_l / 100)

    # ตารางรายแผ่นงาน
    st.subheader("📂 สรุปตามแผ่นงาน")
    res_sheet_l = summary_with_metrics(display_df_l, 'sheet_name')
    st.dataframe(res_sheet_l, use_container_width=True, hide_index=True)

# --- [ฝั่งขวา: เฉพาะวันนี้] ---
with right_col:
    st.header(f"📅 ผลงานเฉพาะวันนี้ ({today})")
    selected_name_r = st.selectbox("🔍 ค้นหาชื่อคน (ฝั่งขวา):", all_names, key="right_search")
    
    df_today = df[df['DATE_SUBMIT'] == today]
    display_df_r = df_today if selected_name_r == "แสดงทุกคน" else df_today[df_today['NAME'] == selected_name_r]
    
    if display_df_r.empty:
        st.warning("⚠️ ไม่มีข้อมูลงานที่ดำเนินการในวันนี้")
    else:
        # ตารางรายคน (วันนี้)
        st.subheader("👨‍💼 สรุปรายบุคคล (วันนี้)")
        res_name_r = summary_with_metrics(display_df_r, 'NAME')
        st.dataframe(res_name_r, use_container_width=True, hide_index=True)
        
        # Progress Bar ภาพรวมฝั่งขวา
        total_pct_r = res_name_r.iloc[-1]['ความคืบหน้า (%)']
        st.write(f"**ความคืบหน้างานวันนี้:** {total_pct_r:.2f}%")
        st.progress(total_pct_r / 100)

        # ตารางรายแผ่นงาน (วันนี้)
        st.subheader("📂 สรุปตามแผ่นงาน (วันนี้)")
        res_sheet_r = summary_with_metrics(display_df_r, 'sheet_name')
        st.dataframe(res_sheet_r, use_container_width=True, hide_index=True)
