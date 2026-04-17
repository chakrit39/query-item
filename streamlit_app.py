import streamlit as st
from google.cloud import bigquery
import pandas as pd
from datetime import datetime
from google.oauth2 import service_account

# ดึงข้อมูลจาก Secrets มาสร้าง Credentials


# --- การตั้งค่าเบื้องต้น ---
st.set_page_config(layout="wide")

@st.cache_data(ttl=600)  # Cache ข้อมูล 10 นาที
def get_full_data():
    SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/bigquery",
    "https://www.googleapis.com/auth/cloud-platform"
    ]
    info = st.secrets["gcp_service_account"]
    credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    client = bigquery.Client(credentials=credentials, project="dol-workspace")
    query = "SELECT * FROM `dol-workspace.Dashboard_Work69.v_master_report`"
    return client.query(query).to_dataframe()

df = get_full_data()

# เตรียมข้อมูลวันที่ (แปลงเป็น Date เพื่อเปรียบเทียบ)
df['DATE_SUBMIT'] = pd.to_datetime(df['DATE_SUBMIT']).dt.date
today = datetime.now().date()

# --- ส่วนของการคำนวณสรุปผล (Aggregation) ---
def summary_data(input_df, group_col):
    # 1. นับจำนวนชื่อทั้งหมด (มอบคุณ)
    total_assigned = input_df.groupby(group_col).size().reset_index(name='มอบหมาย')
    
    # 2. นับจำนวนที่มีวันที่ (ทำเสร็จแล้ว/ส่งแล้ว)
    # กรองเอาเฉพาะแถวที่ DATE_SUBMIT ไม่เป็นค่าว่าง
    finished_tasks = input_df[input_df['DATE_SUBMIT'].notnull()].groupby(group_col).size().reset_index(name='ดำเนินการแล้ว')
    
    # รวมตารางเข้าด้วยกัน
    summary = pd.merge(total_assigned, finished_tasks, on=group_col, how='left').fillna(0)
    summary['ดำเนินการแล้ว'] = summary['ดำเนินการแล้ว'].astype(int)
    return summary

# --- การวาง Layout หน้าจอ ---
st.title("🚀 ระบบติดตามสถานะงานรายบุคคลและแผ่นงาน")
st.divider()

left_col, right_col = st.columns([1, 1])

# --- [ฝั่งซ้าย: ข้อมูลทั้งหมด] ---
with left_col:
    st.header("📊 สรุปยอดงานทั้งหมด")
    
    # ตารางตามรายชื่อพนักงาน
    st.subheader("👨‍💼 แยกตามรายชื่อ (Name)")
    df_name_all = summary_data(df, 'NAME')
    st.dataframe(df_name_all, use_container_width=True, hide_index=True)
    
    # ตารางตามชื่อแผ่นงาน
    st.subheader("📂 แยกตามชื่อแผ่นงาน (Sheet Name)")
    df_sheet_all = summary_data(df, 'sheet_name')
    st.dataframe(df_sheet_all, use_container_width=True, hide_index=True)

# --- [ฝั่งขวา: เฉพาะวันนี้] ---
with right_col:
    st.header(f"📅 เฉพาะวันนี้ ({today})")
    
    # กรองข้อมูลเฉพาะวันนี้
    df_today = df[df['DATE_SUBMIT'] == today]
    
    if df_today.empty:
        st.info("ยังไม่มีข้อมูลที่มีการระบุวันที่ของวันนี้")
    else:
        # ตารางตามรายชื่อพนักงาน (วันนี้)
        st.subheader("👨‍💼 แยกตามรายชื่อ (Name)")
        df_name_today = summary_data(df_today, 'NAME')
        st.dataframe(df_name_today, use_container_width=True, hide_index=True)
        
        # ตารางตามชื่อแผ่นงาน (วันนี้)
        st.subheader("📂 แยกตามชื่อแผ่นงาน (Sheet Name)")
        df_sheet_today = summary_data(df_today, 'sheet_name')
        st.dataframe(df_sheet_today, use_container_width=True, hide_index=True)

# --- เพิ่มเติม: ปุ่มสำหรับ Refresh ข้อมูล ---
if st.sidebar.button("ล้าง Cache และอัปเดตข้อมูล"):
    st.cache_data.clear()
    st.rerun()
