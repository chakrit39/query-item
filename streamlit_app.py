import streamlit as st
from google.cloud import bigquery
import pandas as pd
from datetime import datetime
from google.oauth2 import service_account
import plotly.express as px
import pytz
import numpy as np
from googleapiclient.discovery import build
import datetime as datetime2
import plotly.graph_objects as go
# --- 1. ตั้งค่าการเชื่อมต่อและ Scopes ---
st.set_page_config(layout="wide", page_title="Performance Dashboard")

@st.cache_data(ttl=43200)
def get_tor_data():
    info = st.secrets["gcp_service_account"]
    credentials = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    service = build('sheets', 'v4', credentials=credentials)
    
    # *** เปลี่ยนเป็น ID ของ Google Sheets ของคุณ ***
    SPREADSHEET_ID = '1_dyXM2SAJLINLW-wCEGPypAnNFzujAuTgK-1tBiy5Kg' 
    RANGE_NAME = 'TOR_Targets!A:Z' # ดึงแบบเผื่อคอลัมน์ไปทางขวา
    
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
    values = result.get('values', [])
    
    if not values:
        return pd.DataFrame()
    
    df_tor = pd.DataFrame(values[1:], columns=values[0])
    return df_tor
    
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
    #, TIME_SUBMIT
    query = "SELECT NAME, QUA_PIC, SURV_DATA, SURV_TYP, BUILD_FROM, DATE_SUBMIT, sheet_name FROM `dol-workspace.Dashboard_Work69.v_master_report`"
    df = client.query(query).to_dataframe()
    df['NAME'] = df['NAME'].fillna("ไม่ระบุชื่อ").astype(str) # เติมชื่อแทนค่าว่าง
    df = df[df['NAME']!="ไม่ระบุชื่อ"]
    df['sheet_name'] = df['sheet_name'].fillna("ไม่ระบุชีต").astype(str)
    tz = pytz.timezone('Asia/Bangkok')
    now_bkk = datetime.now(tz)
    return df ,now_bkk.strftime("%d/%m/%Y %H:%M:%S")
    
@st.cache_data(ttl=900)
def get_full_data_time():
    # ดึงข้อมูลจาก Secrets (Streamlit Cloud)
    info = st.secrets["gcp_service_account"]
    SCOPES = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/bigquery",
        "https://www.googleapis.com/auth/cloud-platform"
    ]
    credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    client = bigquery.Client(credentials=credentials, project="dol-workspace")
    query = "SELECT NAME, TIME_SUBMIT  FROM `dol-workspace.Dashboard_Work69.v_master_timestamp_report`"
    df = client.query(query).to_dataframe()
    df['NAME'] = df['NAME'].fillna("ไม่ระบุชื่อ").astype(str) # เติมชื่อแทนค่าว่าง
    df = df[df['NAME']!="ไม่ระบุชื่อ"]
    return df
# โหลดข้อมูล
try:
    df,st.session_state['last_update'] = get_full_data()
    df['DATE_SUBMIT'] = pd.to_datetime(df['DATE_SUBMIT']).dt.date
    today = datetime.now().date()
    df_tor = get_tor_data()  
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
        summary['มอบหมาย'] = 250
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
        width='stretch',
        hide_index=True,
        height=dynamic_height #dynamic_height
    )
    
def calculate_tor_target(name, date_to_check, df_tor):
    person_row = df_tor[df_tor['NAME'] == name]
    if person_row.empty: 
        return 0
    
    row = person_row.iloc[0]
    total_acc_target = 0
    
    # กำหนดวันที่ 1 ของเดือนที่เลือกดู
    first_day_of_selected_month = date_to_check.replace(day=1)
    
    tor_configs = [
        {
            'total': 'TOR1', 'start': 'STARTDATE_TOR1', 'end': 'ENDDATE_TOR1', 
            'd_rate': 'DAY_RATE_TOR1', 'm_rate': 'MONTH_RATE_TOR1'
        },
        {
            'total': 'TOR2', 'start': 'STARTDATE_TOR2', 'end': 'ENDDATE_TOR2', 
            'd_rate': 'DAY_RATE_TOR2', 'm_rate': 'MONTH_RATE_TOR2'
        }
    ]
    
    for tor in tor_configs:
        try:
            if pd.isna(row[tor['start']]) or str(row[tor['start']]).strip() == "":
                if str(row[tor['total']]).strip() != "":
                    total_acc_target += pd.to_numeric(str(row[tor['total']]).replace(',', ''))
                continue
                
            start_dt = pd.to_datetime(row[tor['start']]).date()
            end_dt = pd.to_datetime(row[tor['end']]).date()
            target_total = pd.to_numeric(str(row[tor['total']]).replace(',', ''))
            day_rate = pd.to_numeric(row[tor['d_rate']])
            month_rate = pd.to_numeric(row[tor['m_rate']])

            # --- กรณีที่ 1: สัญญาจบไปแล้วก่อนเดือนที่เลือกดู (เช่น ดูเดือนเมษา แต่ TOR1 จบมีนา) ---
            if end_dt < date_to_check:
                total_acc_target += target_total

            # --- กรณีที่ 2: สัญญาปัจจุบัน (เริ่มไปแล้วและยังไม่จบ หรือกำลังดำเนินการในเดือนที่เลือก) ---
            elif start_dt <= date_to_check :
                temp_tor_acc = 0
                
                # 2.1 คำนวณเดือนที่ผ่านมาแล้วใน TOR นี้ (Full Months)
                # เริ่มเช็คตั้งแต่เดือนที่เริ่มสัญญา จนถึงเดือนก่อนหน้าเดือนปัจจุบัน
                check_month = start_dt.replace(day=1)
                while check_month < first_day_of_selected_month:
                    # ถ้าเดือนแรกเริ่มไม่ใช่วันที่ 1 ให้คิดรายวันของเดือนแรก
                    if check_month == start_dt.replace(day=1) and start_dt.day > 1:
                        last_day_of_first_month = (pd.to_datetime(start_dt) + pd.offsets.MonthEnd(0)).date()
                        days_in_first_month = np.busday_count(start_dt, (last_day_of_first_month + pd.Timedelta(days=1)).date())
                        temp_tor_acc += (days_in_first_month * day_rate)
                    else:
                        # เดือนปกติที่ทำเต็มเดือน
                        temp_tor_acc += month_rate
                    
                    # ขยับไปเดือนถัดไป
                    check_month = (pd.to_datetime(check_month) + pd.offsets.MonthBegin(1)).date()

                # 2.2 คำนวณวันทำงานของ "เดือนปัจจุบัน" (Current Month)
                # เริ่มนับจากวันที่ 1 ของเดือน (หรือวันเริ่มสัญญาถ้าเริ่มเดือนนี้) จนถึงวันที่เลือกดู
                count_start = max(start_dt, first_day_of_selected_month)
                if count_start <= date_to_check:
                    # หากวันที่เลือกดูเลยวันจบสัญญา ให้หยุดนับที่วันจบ
                    count_end = min(date_to_check, end_dt)
                    days_this_month = np.busday_count(count_start, 
                                                        (pd.to_datetime(count_end) + pd.Timedelta(days=1)).date()
                                                    )
                    #days_this_month = np.busday_count(count_start, (count_end + pd.Timedelta(days=1)).date())
                    temp_tor_acc += (days_this_month * day_rate)
                
                # รวมยอด TOR นี้เข้ากับยอดสะสมทั้งหมด (แต่ไม่เกินยอดรวมของ TOR นั้น)
                total_acc_target += min(temp_tor_acc, target_total)
                
        except Exception as e:
            continue
            
    return int(total_acc_target)
    
def format_status(val):
    icon = "🟢" if val >= 0 else "🔴"
    #label = "(ตามเป้า)" if val >= 0 else "(ต่ำกว่าเป้า)"
    label = ""
    # ถ้าเป็นบวก ให้ใส่เครื่องหมาย + นำหน้า
    sign = "+" if val > 0 else "" 
    return f"{icon} {sign}{val:,.1f} {label}"   
    
def summary_with_metrics_v2(input_df, group_col, df_tor, target_date, show_total=True, daily=False):
    # 1. นับจำนวนงานพื้นฐาน
    total_assigned = input_df.groupby(group_col).size().reset_index(name='มอบหมาย')
    finished_tasks = input_df[input_df['DATE_SUBMIT'].notnull()].groupby(group_col).size().reset_index(name='ดำเนินการแล้ว')
    summary = pd.merge(total_assigned, finished_tasks, on=group_col, how='left').fillna(0)
    summary['ดำเนินการแล้ว'] = summary['ดำเนินการแล้ว'].astype(int)
    
    
    # 3. คำนวณเป้าสะสม และ ความคืบหน้า
    if group_col == 'NAME':
        summary['ผลงาน (TOR)'] = summary['ดำเนินการแล้ว'] * 0.5
        if daily:
            def get_daily_rate(name):
                p_row = df_tor[df_tor['NAME'] == name]
                if p_row.empty: return 0
                row = p_row.iloc[0]
                
                for i in ['1', '2']:
                    # แก้ไข: ตรวจสอบว่าเป็น NaT หรือค่าว่างก่อนเปรียบเทียบ
                    raw_start = row.get(f'STARTDATE_TOR{i}')
                    raw_end = row.get(f'ENDDATE_TOR{i}')
                    
                    if pd.notna(raw_start) and pd.notna(raw_end) and str(raw_start).strip() != "" and str(raw_end).strip() != "":
                        try:
                            start = pd.to_datetime(raw_start).date()
                            end = pd.to_datetime(raw_end).date()
                            # ตรวจสอบช่วงวันที่
                            if start <= target_date <= end:
                                return pd.to_numeric(str(row[f'DAY_RATE_TOR{i}']).replace(',', ''))
                        except:
                            continue
                return 0
                
            # --- [โหมดรายวัน] เป้าสะสม = Day Rate ของ TOR ที่ Active ในวันนั้น ---
            summary['เป้าสะสม (TOR)'] = summary['NAME'].apply(get_daily_rate)
            # ถ้าไม่มี Day Rate (คนนอกเป้า) ให้ใช้ 0 หรือค่าที่ต้องการ (เช่น ค่าเฉลี่ยกลาง)
            summary['เป้าสะสม (TOR)'] = summary['เป้าสะสม (TOR)'].fillna(0)
            
            # จัดการคอลัมน์สำหรับรายวัน (เอา 'มอบหมาย' ออก)
            cols = [group_col, 'ดำเนินการแล้ว', 'เป้าสะสม (TOR)', 'ผลงาน (TOR)', '+/- เป้าหมาย', 'ความคืบหน้า (%)']
        else:
            # --- [โหมดสะสมปกติ] ---
            summary['เป้าสะสม (TOR)'] = summary['NAME'].apply(lambda x: calculate_tor_target(x, target_date, df_tor))
            cols = [group_col, 'มอบหมาย', 'ดำเนินการแล้ว', 'เป้าสะสม (TOR)', 'ผลงาน (TOR)', '+/- เป้าหมาย', 'ความคืบหน้า (%)']
        diff_val = summary['ผลงาน (TOR)'] - summary['เป้าสะสม (TOR)']
        summary['+/- เป้าหมาย'] = diff_val.apply(format_status)
        #summary['+/- เป้าหมาย'] = summary['ผลงาน (TOR)'] - summary['เป้าสะสม (TOR)']
        summary['ความคืบหน้า (%)'] = (summary['ผลงาน (TOR)'] / summary['เป้าสะสม (TOR)']) * 100
        summary = summary[cols]
    else:
        summary['ความคืบหน้า (%)'] = (summary['ดำเนินการแล้ว'] / summary['มอบหมาย']) * 100

    summary['ความคืบหน้า (%)'] = summary['ความคืบหน้า (%)'].replace([np.inf, -np.inf], 0).fillna(0)
    
    # เรียงลำดับตามความขยัน (ดำเนินการแล้ว) จากมากไปน้อย
    if group_col == 'NAME':
        summary = summary.sort_values(by='ดำเนินการแล้ว', ascending=False)
    elif group_col == 'sheet_name':
        summary = summary.sort_values(by='sheet_name', ascending=True)
    
    # 4. เพิ่มแถวผลรวม (Total)
    if show_total:
        total_row = {group_col: '--- รวมทั้งหมด ---', 'ดำเนินการแล้ว': summary['ดำเนินการแล้ว'].sum()}
        
        if not (group_col == 'NAME' and daily):
            total_row['มอบหมาย'] = summary['มอบหมาย'].sum()
        
        if group_col == 'NAME':
            t_target = summary['เป้าสะสม (TOR)'].sum()
            t_perf = summary['ผลงาน (TOR)'].sum()
            total_row['เป้าสะสม (TOR)'] = t_target
            total_row['ผลงาน (TOR)'] = t_perf
            total_row['+/- เป้าหมาย'] = format_status(t_perf - t_target)
            #total_row['+/- เป้าหมาย'] = t_perf - t_target
            total_row['ความคืบหน้า (%)'] = (t_perf / t_target * 100) if t_target > 0 else 0
        else:
            total_row['ความคืบหน้า (%)'] = (summary['ดำเนินการแล้ว'].sum() / summary['มอบหมาย'].sum() * 100) if summary['มอบหมาย'].sum() > 0 else 0
        
        summary = pd.concat([summary, pd.DataFrame([total_row])], ignore_index=True)
        summary.index = summary.index + 1
    return summary

def display_styled_dataframe_v2(df_display, title):
    st.subheader(title)
    dynamic_height = 35 * (len(df_display) + 1)
    
    st.dataframe(
        df_display,
        column_config={
            "ความคืบหน้า (%)": st.column_config.ProgressColumn("ความคืบหน้า (%)", format="%.2f%%", min_value=0, max_value=100),
            "ผลงาน (TOR)": st.column_config.NumberColumn("ผลงาน (TOR)", format="%,.1f", alignment="center"),
            "เป้าสะสม (TOR)": st.column_config.NumberColumn("เป้าหมาย (TOR)", format="%,d", alignment="center"),
            "+/- เป้าหมาย": st.column_config.TextColumn("สถานะ/ส่วนต่าง", alignment="center"),
            #"+/- เป้าหมาย": st.column_config.NumberColumn("+/- เป้าหมาย", format="%,.1f", alignment="center"),
            "มอบหมาย": st.column_config.NumberColumn("มอบหมาย", format="%,d", alignment="center"),
            "ดำเนินการแล้ว": st.column_config.NumberColumn("ดำเนินการแล้ว", format="%,d", alignment="center"),
        },
        width='stretch',
        #hide_index=True,
        height=dynamic_height
    )
    
def display_hourly_trend_chart(df_input, selected_date, selected_name):
    
    # 1. จัดการเรื่อง Timezone +7
    tz_thai = datetime2.timezone(datetime2.timedelta(hours=7))
    now_thai = datetime2.datetime.now(tz_thai)
    current_date = now_thai.date()
    current_hour = now_thai.hour
    
    # 2. สร้างโครงเวลามาตรฐาน 07:00 - 20:00
    full_hours = [f"{h:02d}:00" for h in range(7, 21)]
    hourly_slots = pd.DataFrame({'HOUR': full_hours})
    
    # 3. เตรียมข้อมูล
    trend_df = df_input[df_input['TIME_SUBMIT'].notnull()].copy()
    trend_df['TIME_DT'] = pd.to_datetime(trend_df['TIME_SUBMIT'])
    
    mask = (trend_df['TIME_DT'].dt.date == selected_date)
    if selected_name != "แสดงทุกคน":
        mask = mask & (trend_df['NAME'] == selected_name)
    
    day_data = trend_df[mask].copy()
    
    # 4. คำนวณยอดสะสมรายชั่วโมง
    if not day_data.empty:
        day_data['HOUR'] = (day_data['TIME_DT']+pd.Timedelta(hours=1)).dt.strftime('%H:00')
        hourly_counts = day_data.groupby('HOUR').size().reset_index(name='hourly_done')
        merged_df = pd.merge(hourly_slots, hourly_counts, on='HOUR', how='left').fillna(0)
        merged_df['cumulative_perf'] = merged_df['hourly_done'].cumsum()
    else:
        merged_df = hourly_slots.copy()
        merged_df['hourly_done'] = 0.0
        merged_df['cumulative_perf'] = 0.0

    # 5. [Logic ใหม่] คำนวณชั่วโมงที่ทำงานจริง (Active Hours)
    if selected_date == current_date:
        plot_df = merged_df[merged_df['HOUR'].apply(lambda x: int(x.split(":")[0])) <= current_hour].copy()
    else:
        plot_df = merged_df.copy()
    # นับชั่วโมงที่ "มียอดงานเพิ่มขึ้น" (hourly_done > 0)
    # เราใช้ merged_df มาเช็คชั่วโมงที่เกิดงานจริงในช่วงเวลาที่ plot
    active_hours_df = plot_df[plot_df['hourly_done'] > 0]
    active_hours_count = len(active_hours_df)
    
    total_now = plot_df['cumulative_perf'].iloc[-1] if not plot_df.empty else 0
    
    # คำนวณค่าเฉลี่ย (ถ้าไม่มีชั่วโมงที่ทำงานเลยให้เป็น 0 เพื่อกัน Error)
    avg_per_hour = total_now / active_hours_count if active_hours_count > 0 else 0

    # 6. สร้างกราฟ
    st.subheader(f"📈 กราฟแนวโน้มรายชั่วโมง: {selected_name}")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=plot_df['HOUR'], y=plot_df['cumulative_perf'],
        mode='lines+markers+text',
        text=plot_df['cumulative_perf'].apply(lambda x: f"{x:,.1f}" if x > 0 else ""),
        textposition="top center",
        line=dict(color='#0068C9', width=4, shape='linear'),
        fill='tozeroy', fillcolor='rgba(0, 104, 201, 0.1)',
        hovertemplate='เวลา %{x}<br>สะสม: %{y:,.1f}<extra></extra>'
    ))

    fig.update_layout(
        xaxis=dict(type='category', categoryarray=full_hours),
        yaxis=dict(tickformat=",d"),
        hovermode="x unified",
        height=400,
        margin=dict(l=0, r=20, t=20, b=0),
    )
    st.plotly_chart(fig, width='stretch')
        # --- แสดงผล Metric ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("✨ ดำเนินการแล้ว", f"{total_now:,.1f}")
    with col2:
        st.metric("⏱️ เฉลี่ย/ชม. (ที่ทำจริง)", f"{avg_per_hour:,.2f}", 
                  help="หารเฉพาะชั่วโมงที่มียอดงานเพิ่มขึ้นเท่านั้น")
    with col3:
        st.metric("📅 เวลาที่ใช้จริง", f"{active_hours_count} ชม.", 
                  help="นับเฉพาะชั่วโมงที่มีการส่งงาน")

def display_trend_chart_fixed(df_input):
    st.subheader("📈 แนวโน้มผลงานสะสม (1 ต.ค. 68 - 30 ก.ย. 69)")
    
    # 1. กำหนดช่วงเวลาที่ต้องการ (ปีงบประมาณ 2569)
    start_period = pd.to_datetime('2025-10-01').date()
    end_period = pd.to_datetime('2026-09-30').date()
    
    # สร้างโครงวันที่ทั้งหมดในช่วงนี้
    all_dates = pd.date_range(start=start_period, end=end_period).date
    base_df = pd.DataFrame({'DATE_SUBMIT': all_dates})
    
    # 2. เตรียมข้อมูลจริง
    trend_df = df_input[df_input['DATE_SUBMIT'].notnull()].copy()
    trend_df['DATE_SUBMIT'] = pd.to_datetime(trend_df['DATE_SUBMIT']).dt.date
    
    # นับจำนวนงานต่อวัน
    daily_count = trend_df.groupby('DATE_SUBMIT').size().reset_index(name='daily_done')
    
    # 3. Merge ข้อมูลจริงเข้ากับโครงวันที่ (เพื่อให้กราฟแสดงครบทุกวัน)
    merged_df = pd.merge(base_df, daily_count, on='DATE_SUBMIT', how='left').fillna(0)
    merged_df = merged_df.sort_values('DATE_SUBMIT')
    
    # คำนวณสะสม (งานที่ทำเสร็จ * 0.5)
    merged_df['cumulative_perf'] = (merged_df['daily_done'] * 0.5).cumsum()
    
    # กรองเฉพาะถึง "วันปัจจุบัน" เพื่อไม่ให้เส้นจริงลากเป็นเส้นตรงไปในอนาคต
    today = pd.Timestamp.now().date()
    plot_df = merged_df[merged_df['DATE_SUBMIT'] <= today].copy()

    # 4. สร้างกราฟ
    fig = go.Figure()

    # เส้นเป้าหมาย 1,000,000 (ลากยาวตั้งแต่วันแรกถึงวันสุดท้าย)
    target_value = 1000000
    fig.add_trace(go.Scatter(
        x=[start_period, end_period],
        y=[target_value, target_value],
        mode='lines',
        name='เป้าหมาย (1M)',
        line=dict(color='rgba(255, 0, 0, 0.5)', width=2, dash='dash'),
        hovertemplate='เป้าหมาย: 1,000,000<extra></extra>'
    ))

    # เส้นผลงานสะสมจริง
    fig.add_trace(go.Scatter(
        x=plot_df['DATE_SUBMIT'], 
        y=plot_df['cumulative_perf'],
        mode='lines',
        name='ผลงานสะสมจริง',
        line=dict(color='#00CC96', width=3),
        fill='tozeroy', # ระบายสีใต้กราฟให้ดูสวยงาม
        fillcolor='rgba(0, 204, 150, 0.1)',
        hovertemplate='วันที่: %{x}<br>สะสม: %{y:,.1f}<extra></extra>'
    ))

    # ปรับแต่ง Layout
    fig.update_layout(
        xaxis=dict(
            range=[start_period, end_period], # บังคับแกน X เริ่ม-จบ ตามที่กำหนด
            type='date'
        ),
        yaxis=dict(
            range=[0, 1100000], # ปรับช่วงแกน Y ให้เห็นเส้น 1M ชัดเจน
            tickformat=",d"
        ),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=0, r=0, t=30, b=0),
        height=450
    )

    st.plotly_chart(fig, width='stretch')
# --- 3. การวาง Layout ---
st.title("🚀 Dashboard ติดตามผลงานขึ้นรูปแปลง")

if 'last_update' in st.session_state:
    st.caption(f"🕒 อัปเดตข้อมูลล่าสุดเมื่อ: {st.session_state['last_update']}")
# สร้าง Dropdown กรองชื่อคน (Global หรือแยกฝั่ง)
all_names = ["แสดงทุกคน"] + sorted(df['NAME'].dropna().astype(str).unique().tolist())

# --- ส่วนคำนวณกราฟเส้น 30 วัน พร้อม Buffer ---
st.divider()
col1, col2 = st.columns([0.2, 0.8])
selected_name = col1.selectbox("🔍 ค้นหาชื่อคน:", all_names, key="trend_search")
st.subheader("📈 แนวโน้มผลงานย้อนหลัง 30 วัน")

# --- ส่วนของการเลือกช่วงเวลา ---
time_option = st.selectbox("เลือกช่วงเวลาการแสดงผล", ["30 วันล่าสุด", "ทั้งหมด"])

# 1. เตรียมข้อมูล
df_trend = df.copy()
if selected_name != "แสดงทุกคน":
    df_trend = df_trend[df_trend['NAME'] == selected_name]

# แปลงเป็น datetime และดึงเฉพาะวันที่ (date)
df_trend['DATE_DT'] = pd.to_datetime(df_trend['DATE_SUBMIT'])
df_trend['DATE_ONLY'] = df_trend['DATE_DT'].dt.date # สร้างคอลัมน์ DATE_ONLY ให้ตรงกับที่เรียกใช้

# หาช่วงวันที่
today = pd.Timestamp.now().date()
if time_option == "30 วันล่าสุด":
    date_range = pd.date_range(end=today, periods=30).date
else:
    # แก้ไขตรงนี้: ใช้คอลัมน์ที่สร้างขึ้นใหม่ หรือใช้ DATE_DT.min().date()
    if not df_trend.empty:
        start_date = df_trend['DATE_ONLY'].min()
    else:
        start_date = today
    date_range = pd.date_range(start=start_date, end=today).date

# Groupby และ Reindex
trend_data = (
    df_trend.groupby('DATE_ONLY')
    .size()
    .reindex(date_range, fill_value=0)
    .reset_index()
)
trend_data.columns = ['DATE_SUBMIT', 'ยอดงาน']

# 2. คำนวณขอบเขตแกน Y
max_val = trend_data['ยอดงาน'].max()
y_upper_limit = max_val * 1.30 if max_val > 0 else 10

# 3. สร้างกราฟ
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=trend_data['DATE_SUBMIT'],
    y=trend_data['ยอดงาน'],
    mode='lines+markers+text',
    text=trend_data['ยอดงาน'].apply(lambda x: int(x) if x > 0 else ""),
    textposition="top center",
    line=dict(color="#29b5e8", width=3, shape='linear'),
    marker=dict(size=8),
    fill='tozeroy',
    fillcolor='rgba(41, 181, 232, 0.1)',
    name='ยอดงาน'
))

# 4. ปรับแต่ง Layout (ล็อกแกน และทำ Pan/Scroll)
fig.update_layout(
    xaxis=dict(
        title="วันที่ (เลื่อนแถบด้านล่างเพื่อดูวันอื่น)",
        type='date',
        tickformat="%d %b",
        # กำหนดให้เริ่มต้นแสดงแค่ 7 วันล่าสุด (เพื่อให้ช่องกว้างเท่ากัน)
        range=[date_range[-30], date_range[-1]] if len(date_range) > 30 else None,
        rangeslider=dict(visible=True, thickness=0.05), # แถบเลื่อนด้านล่าง
        fixedrange=False, # ยอมให้เลื่อน (Pan) ได้
        dtick="D1",
        tickangle=-45
    ),
    yaxis=dict(
        title="จำนวนงาน",
        range=[0, y_upper_limit],
        fixedrange=True # ล็อกแกน Y ไม่ให้ขยับ/ซูม
    ),
    hovermode="x unified",
    height=550,
    dragmode=False # ปิดฟังก์ชันการลากเมาส์เพื่อซูม (Box Zoom)
)

# 5. แสดงกราฟ และปิดปุ่มเครื่องมือ (Modebar)
st.plotly_chart(fig, width='stretch', config={
    'displayModeBar': False, # ปิดแถบเครื่องมือทั้งหมดเหนือชื่อกราฟ
    'scrollZoom': False      # ปิดการใช้ลูกกลิ้งเมาส์ซูม
})
# --- ส่วนคำนวณ Metric (ต่อจากขั้นตอนเตรียม trend_data) ---

# ตรวจสอบให้แน่ใจว่าเป็น datetime เพื่อใช้ฟังก์ชัน .dt
trend_data['DATE_DT'] = pd.to_datetime(trend_data['DATE_SUBMIT'])

# 1. สร้างคอลัมน์ระบุวันในสัปดาห์ (0=จันทร์, 5=เสาร์, 6=อาทิตย์)
trend_data['day_of_week'] = trend_data['DATE_DT'].dt.dayofweek

# 2. กรองข้อมูลสำหรับหาค่าเฉลี่ย:
# เงื่อนไข: จันทร์-ศุกร์ (day_of_week < 5) และต้องมียอดงานมากกว่า 0
filtered_for_avg = trend_data[
    (trend_data['day_of_week'] < 5) & 
    (trend_data['ยอดงาน'] > 0)
]

# 3. คำนวณค่าทางสถิติ
if not filtered_for_avg.empty:
    avg_performance = filtered_for_avg['ยอดงาน'].mean()
    working_days_count = len(filtered_for_avg)
    max_day_record = filtered_for_avg['ยอดงาน'].max()
else:
    avg_performance = 0
    working_days_count = 0
    max_day_record = 0

# 4. แสดงผล Metric
# ใช้คำอธิบายตามตัวเลือก Dropdown (time_option คือตัวแปรจากข้อที่แล้ว)
label_suffix = f"({time_option})"

c1, c2, c3, c4 = st.columns(4)

with c1:
    total_sum = trend_data['ยอดงาน'].sum()
    st.metric(f"📊 ผลงานรวม", f"{total_sum:,.0f}", help=f"รวมยอดงานทั้งหมดในช่วง {label_suffix}")

with c2:
    st.metric(f"🎯 เฉลี่ย/วันทำการ", f"{avg_performance:,.2f}", 
              help="คำนวณเฉพาะวันจันทร์-ศุกร์ที่มีการส่งงานจริง (ไม่นับวันที่ยอดเป็น 0)")

with c3:
    st.metric(f"📅 วันที่ทำงานจริง", f"{working_days_count} วัน", 
              help="นับเฉพาะวันธรรมดาที่มีการส่งงาน")

with c4:
    # เพิ่ม Metric พิเศษ: วันที่ทำได้สูงสุด
    st.metric(f"🏆 High Score", f"{max_day_record:,.0f}", 
              help="ยอดงานที่ทำได้สูงสุดต่อวัน (เฉพาะวันธรรมดา)")


st.caption(f"💡 *หมายเหตุ: ค่าเฉลี่ยคำนวณจากยอดงานรวมหารด้วยจำนวนวันที่ส่งงานจริง (ไม่นับรวมวันเสาร์-อาทิตย์ และวันที่ไม่มีงาน)*")
st.divider()

st.caption(f"📊 ยอดงานสะสมทั้งหมด [เป้าหมาย (TOR)] นับจากวันที่เริ่มสัญญาจนถึงวันนี้ | 📅 ผลงานตามวันที่ [เป้าหมาย (TOR)] คือยอดรายวันในสัญญาของวันที่เลือก | [ผลงาน (TOR)] คิดจากยอด 0.5(ตามค่า weight จากการขึ้นรูปแปลงไม่รวมการต่อรูปแปลง) ต่อแปลงจากที่ดำเนินการแล้ว")
left_col, right_col = st.columns([1, 1])

# --- [ฝั่งซ้าย: ข้อมูลทั้งหมด] ---
with left_col:
    st.header("📊 ยอดงานสะสมทั้งหมด")
    #l1, l2 = st.columns([0.5, 0.5])
    selected_name_l = selected_name #l1.selectbox("🔍 ค้นหาชื่อคน (ฝั่งซ้าย):", all_names, key="left_search")
    
    display_df_l = df if selected_name_l == "แสดงทุกคน" else df[df['NAME'] == selected_name_l]
    
    # เช็คว่าจะโชว์ผลรวมไหม (ถ้าเลือกชื่อคน จะไม่โชว์)
    show_total_l = True if selected_name_l == "แสดงทุกคน" else False
    
    # ตารางรายคน (ส่ง show_total เข้าไป)
    #st.subheader("👨‍💼 สรุปรายบุคคล")
    #res_name_l = summary_with_metrics(display_df_l, 'NAME', show_total=show_total_l)
    #display_styled_dataframe(res_name_l, "👨‍💼 สรุปรายบุคคล")
    res_name_l = summary_with_metrics_v2(display_df_l, 'NAME', df_tor, today, show_total=show_total_l)
    display_styled_dataframe_v2(res_name_l, "👨‍💼 สรุปรายบุคคลด")
    # Progress Bar ภาพรวมฝั่งซ้าย
    total_pct_l = res_name_l.iloc[-1]['ความคืบหน้า (%)']
    st.write(f"**ความคืบหน้าภาพรวมสะสม:** {total_pct_l:.2f}%")
    if total_pct_l > 100:
        total_pct_l = 100
    st.progress(total_pct_l / 100)

    # ตารางรายแผ่นงาน
    #st.subheader("📂 สรุปตามแผ่นงาน")
    #res_sheet_l = summary_with_metrics(display_df_l, 'sheet_name')
    #display_styled_dataframe(res_sheet_l, "📂 สรุปตามแผ่นงาน")
    res_sheet_l = summary_with_metrics_v2(display_df_l, 'sheet_name', df_tor, today)
    display_styled_dataframe_v2(res_sheet_l, "📂 สรุปตามแผ่นงาน")
# --- [ฝั่งขวา: เฉพาะวันนี้] ---
with right_col:
    
    #r1, r2 = st.columns([0.5, 0.5])
    #r1.header(f"📅 ผลงานตามวันที่")
    # 1. สร้างคอลัมน์ โดยให้คอลัมน์ซ้ายกว้างกว่า (สำหรับ Header) และคอลัมน์ขวาพอดีกับวันที่
    col_title, col_date, col_date_ = st.columns([0.4, 0.2,0.4])
    
    with col_title:
        # ใช้ anchor=False เพื่อไม่ให้มีไอคอนลิงก์โผล่มาทับ
        st.header("📅 ผลงานตามวันที่", anchor=False)
    
    with col_date:
        st.markdown("""
                <style>
                /* เลือกช่อง Date Input เฉพาะในส่วนนี้ */
                div[data-testid="stDateInput"] {
                    margin-top: 1px; /* ปรับค่าตัวเลขนี้ (8-12px) จนกว่าจะตรงตามความพอใจ */
                }
                /* ปรับความกว้างของช่องให้กระชับขึ้นถ้าจำเป็น */
                div[data-testid="stDateInput"] > div {
                    width: 100%;
                }
                </style>
            """, unsafe_allow_html=True)
        selected_date = st.date_input(
            "เลือกวันที่ต้องการดู:", # ใส่ไว้เป็นความหมาย แต่จะถูกซ่อน
            value=today,
            label_visibility="collapsed",
            key="main_date_input"
        )
    
    selected_name_r = selected_name #r1.selectbox("🔍 ค้นหาชื่อคน (ฝั่งขวา):", all_names, key="right_search")
    #selected_date = r2.date_input( "📆 เลือกวันที่ต้องการดู:",today, key="date_selector",label_visibility="collapsed")
    
    df_today = df[df['DATE_SUBMIT'] == selected_date]
    display_df_r = df_today if selected_name_r == "แสดงทุกคน" else df_today[df_today['NAME'] == selected_name_r]
    
    if display_df_r.empty:
        st.warning("⚠️ ไม่มีข้อมูลงานที่ดำเนินการในวันนี้")
    else:
        # เช็คว่าจะโชว์ผลรวมไหม (ถ้าเลือกชื่อคน จะไม่โชว์)
        show_total_r = True if selected_name_r == "แสดงทุกคน" else False
        
        # ตารางรายคน (วันนี้)
        #st.subheader("👨‍💼 สรุปรายบุคคล (วันนี้)")
        #res_name_r = summary_with_metrics(display_df_r, 'NAME', show_total=show_total_r, daily=True)
        #display_styled_dataframe(res_name_r, f"👨‍💼 สรุปรายบุคคลวันที่ {selected_date}")
        res_name_r = summary_with_metrics_v2(display_df_r, 'NAME', df_tor, selected_date, show_total=show_total_r, daily=True)
        display_styled_dataframe_v2(res_name_r, f"👨‍💼 สรุปรายบุคคลวันที่ {selected_date}")
        
        # Progress Bar ภาพรวมฝั่งขวา
        total_pct_r = res_name_r.iloc[-1]['ความคืบหน้า (%)']
        st.write(f"**ความคืบหน้างานวันนี้:** {total_pct_r:.2f}%")
        if total_pct_r > 100:
            total_pct_r = 100
        st.progress(total_pct_r / 100)

        # ตารางรายแผ่นงาน (วันนี้)
        #st.subheader("📂 สรุปตามแผ่นงาน (วันนี้)")
        #res_sheet_r = summary_with_metrics(display_df_r, 'sheet_name')
        #display_styled_dataframe(res_sheet_r, f"📂 สรุปตามแผ่นงานวันที่ {selected_date}")
        res_sheet_r = summary_with_metrics_v2(display_df_r, 'sheet_name', df_tor, selected_date)
        display_styled_dataframe_v2(res_sheet_r, f"📂 สรุปตามแผ่นงานวันที่ {selected_date}")
        
st.divider()
if st.checkbox("แสดงข้อมูลประเภทงานที่ดำเนินการแล้ว"):
    df_ = df if selected_name == "แสดงทุกคน" else df[df['NAME'] == selected_name]
    left_col_, cen_col_, right_col_ = st.columns([1, 1, 1])
        #total_assigned = input_df.groupby(group_col).size().reset_index(name='มอบหมาย')
        #finished_tasks = input_df[input_df['DATE_SUBMIT'].notnull()].groupby(group_col).size().reset_index(name='ดำเนินการแล้ว')
    df_TYP = df_.groupby('SURV_TYP').size().reset_index(name='จำนวน')
    df_TYP = df_TYP.sort_values(by='จำนวน', ascending=False)
    df_TYP = df_TYP[df_TYP['SURV_TYP']!="                                                                                                                                                                                                      "]
    dynamic_height = 35 * (len(df_TYP) + 1)
    cen_col_ .dataframe(df_TYP, width='stretch', hide_index=True,
                        column_config={
                                        "จำนวน": st.column_config.NumberColumn("จำนวน", format="%,d ", alignment="center"),
                                        },
                        height=dynamic_height
                       )
    
    df_IMG = df_.groupby('QUA_PIC').size().reset_index(name='จำนวน')
    df_IMG = df_IMG.sort_values(by='จำนวน', ascending=False)
    df_IMG = df_IMG[df_IMG['QUA_PIC']!="                                                                                                                                                                                                      "]
    dynamic_height = 35 * (len(df_IMG) + 1)
    right_col_ .dataframe(df_IMG, width='stretch', hide_index=True,
                        column_config={
                                        "จำนวน": st.column_config.NumberColumn("จำนวน", format="%,d ", alignment="center"),
                                        },
                        height=dynamic_height
                       )
    
    df_BUILD = df_.groupby('BUILD_FROM').size().reset_index(name='จำนวน')
    df_BUILD = df_BUILD.sort_values(by='จำนวน', ascending=False)
    df_BUILD = df_BUILD[df_BUILD['BUILD_FROM']!="                                                                                                                                                                                                      "]
    dynamic_height = 35 * (len(df_BUILD) + 1)
    left_col_.dataframe(df_BUILD, width='stretch', hide_index=True,
                         column_config={
                                        "จำนวน": st.column_config.NumberColumn("จำนวน", format="%,d ", alignment="center"),
                                        },
                         height=dynamic_height
                       )
st.divider()   
if st.checkbox("แสดงข้อมูลราย ชม."):
    df_timestamp = get_full_data_time()
    display_hourly_trend_chart(df_timestamp, selected_date, selected_name)

st.divider() 
if st.checkbox("แสดงแนวโน้มผลงานสะสม"):
    display_trend_chart_fixed(df)
