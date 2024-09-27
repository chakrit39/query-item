import datetime
import random

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
@st.cache_data
def get_UN_data():
    df = pd.read_csv('./Data.csv',header=0)
    return df.set_index("ลำดับ")
st.title('บัญชีการตรวจสอบครุภัณฑ์ ')
"""
###### งวดตั้งแต่วันที่  ๑  ตุลาคม  ๒๕๖๖  ถึงวันที่  ๑๙  กันยายน  ๒๕๖๗
###### ส่วนปรับปรุงระวางแผนที่   กองเทคโนโลยีทำแผนที่
----------------------------------------------------
"""


df = get_UN_data()
iCount = len(df)
col1, col2 = st.columns(2)
with col1:
    Select_fil = st.selectbox('รายการสืบค้น',['รายการ', 'หมายเลขครุภัณฑ์', 'หมายเลขสินทรัพย์ตามระบบ GFMIS'])

with col2:
    fil = st.text_input('คำค้นหา', key='fil')

"""
----------------------------------------------------
ตัวกรอง
"""
List_type = ['ทั้งหมด']
for i in df.ประเภท.unique(): List_type.append(i)
Select_type = st.selectbox("ประเภท", List_type, key='List_type')

List_name = ['ทั้งหมด']
for i in df.รายการ.unique(): List_name.append(i)
Select_name = st.selectbox("รายการ", List_name, key='List_name')

List_status = ['ทั้งหมด']
for i in df.สภาพครุภัณฑ์.unique(): List_status.append(i)
Select_status = st.selectbox("สภาพครุภัณฑ์", List_status, key='List_status')
"""
----------------------------------------------------
""" 
col3, col4 ,col5 = st.columns(3)
def onclick():
    st.session_state.fil = ''
    st.session_state.List_type = 'ทั้งหมด'
    st.session_state.List_name = 'ทั้งหมด'
    st.session_state.List_status = 'ทั้งหมด'
col5.button('Reset', type="primary", on_click=onclick)

if not Select_name and Select_status and fil and Select_type:
    with col3:
        "#### บัญชีครุภัณฑ์        | "+str(iCount)+" รายการ"
    st.dataframe(data=df,use_container_width=True)
elif Select_name == 'ทั้งหมด' and Select_status == 'ทั้งหมด' and fil == '' and Select_type == 'ทั้งหมด':
    with col3:
        "#### บัญชีครุภัณฑ์        | "+str(iCount)+" รายการ"
    st.dataframe(data=df,use_container_width=True)
else:
    data = df[df[Select_fil].str.contains(str(fil))]
    if Select_type != 'ทั้งหมด': data = data[data.ประเภท==Select_type]
    if Select_name != 'ทั้งหมด': data = data[data.รายการ==Select_name]
    if Select_status != 'ทั้งหมด': data = data[data.สภาพครุภัณฑ์==Select_status]
    data = data.reset_index(drop=True)
    data.index = np.arange(1, len(data) + 1)
    data.index.name = 'ลำดับ'
    with col3:
        "#### บัญชีครุภัณฑ์        | " + str(len(data)) + " จาก " + str(iCount) + " รายการ"
    st.dataframe(data=data,use_container_width=True)
