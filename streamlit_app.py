import datetime
import random
import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
@st.cache_data
def get_UN_data():
    df = pd.read_csv('./data.csv',header=0)
    return df.set_index("ลำดับ")
st.title('บัญชีการตรวจสอบครุภัณฑ์ ')
"""
###### งวดตั้งแต่วันที่  ๑  ตุลาคม  ๒๕๖๖  ถึงวันที่  ๓๐  กันยายน  ๒๕๖๗
###### ส่วนปรับปรุงระวางแผนที่   กองเทคโนโลยีทำแผนที่   กรมที่ดิน
----------------------------------------------------
"""

df = get_UN_data()
iCount = len(df)
col1, col2 = st.columns([0.45, 0.55])
with col1:
    Select_fil = st.selectbox('รายการสืบค้น',['รายการ', 'หมายเลขครุภัณฑ์', 'หมายเลขสินทรัพย์ตามระบบ GFMIS'])

with col2:
    fil = st.text_input('คำค้นหา', key='fil')
    
"""
----------------------------------------------------
ตัวกรอง
"""
col5, col6 = st.columns(2)
with col5:
    List_ = []
    for i in df.ประเภท.unique(): List_.append(i)
    List_.sort()
    List_type = ['ทั้งหมด']
    List_type.extend(List_)
    Select_type = st.selectbox("ประเภท", List_type  , key='List_type')
    
    List_ = []
    for i in df.สถานที่.unique(): List_.append(i)
    List_.sort()
    List_place = ['ทั้งหมด']
    List_place.extend(List_)
    Select_place = st.selectbox("สถานที่", List_place , key='List_place')
    
with col6:
    List_ = []
    for i in df.รายการ.unique(): List_.append(i)
    List_.sort()
    List_name = ['ทั้งหมด']
    List_name.extend(List_)
    Select_name = st.selectbox("รายการ", List_name , key='List_name')
    
    List_ = []
    for i in df.สภาพครุภัณฑ์.unique(): List_.append(i)
    List_.sort()    
    List_status = ['ทั้งหมด']
    List_status.extend(List_)
    Select_status = st.selectbox("สภาพครุภัณฑ์", List_status , key='List_status')
    
"""
----------------------------------------------------
""" 
col3, col4 = st.columns([0.75, 0.25])
def onclick():
    st.session_state.fil = ''
    st.session_state.List_type = 'ทั้งหมด'
    st.session_state.List_name = 'ทั้งหมด'
    st.session_state.List_status = 'ทั้งหมด'
    st.session_state.List_place = 'ทั้งหมด'
col4.button('Reset', type="primary", on_click=onclick)

if not Select_name and Select_status and fil and Select_type and Select_place:
    with col3:
        "#### บัญชีครุภัณฑ์        | "+str(iCount)+" รายการ"
    st.dataframe(data=df,use_container_width=True)
elif Select_name == 'ทั้งหมด' and Select_status == 'ทั้งหมด' and fil == '' and Select_type == 'ทั้งหมด' and Select_place == 'ทั้งหมด':
    with col3:
        "#### บัญชีครุภัณฑ์        | "+str(iCount)+" รายการ"
    st.dataframe(data=df,use_container_width=True)
else:
    data = df[df[Select_fil].str.contains(str(fil))]
    if Select_type != 'ทั้งหมด': data = data[data.ประเภท==Select_type]
    if Select_name != 'ทั้งหมด': data = data[data.รายการ==Select_name]
    if Select_status != 'ทั้งหมด': data = data[data.สภาพครุภัณฑ์==Select_status]
    if Select_place != 'ทั้งหมด': data = data[data.สถานที่==Select_place]  
    data = data.reset_index(drop=True)
    data.index = np.arange(1, len(data) + 1)
    data.index.name = 'ลำดับ'
    with col3:
        "#### บัญชีครุภัณฑ์        | " + str(len(data)) + " จาก " + str(iCount) + " รายการ"
    st.dataframe(data=data,use_container_width=True)
