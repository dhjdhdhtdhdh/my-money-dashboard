import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# ==========================================
# 1. 페이지 설정 및 초기화
# ==========================================
st.set_page_config(page_title="인터랙티브 가계부 대시보드", layout="wide", initial_sidebar_state="expanded")
st.title("💸 스마트 가계부 대시보드 (데이터 수정 가능)")
st.markdown("가비지 데이터를 표에서 직접 **수정/추가/삭제**하세요. 변경 사항이 즉시 차트에 반영됩니다.")

# ==========================================
# 2. 사이드바 - 파일 업로드 및 필터
# ==========================================
with st.sidebar:
    st.header("📂 데이터 설정")
    uploaded_file = st.file_uploader("뱅크샐러드 엑셀/CSV 업로드", type=['xlsx', 'csv'])
    
    st.markdown("---")
    st.header("🎯 목표 예산 설정")
    target_budget = st.number_input("이번 달 목표 지출액 (원)", min_value=0, value=1500000, step=100000)
    
    st.markdown("---")
    st.header("🔤 키워드 사전 설정 (선택)")
    keyword_file = st.file_uploader("자동 분류 키워드 파일 업로드", type=['xlsx', 'csv'])
    st.caption("💡 엑셀 1행에 '키워드', '대분류', '소분류' 컬럼이 있어야 합니다.")
    
    st.markdown("---")
    st.markdown("💡 **이용 팁**\n"
                "1. 표 안의 셀을 더블클릭하여 수정하세요.\n"
                "2. 행을 선택하고 `Delete` 키를 누르면 삭제됩니다.\n"
                "3. 맨 아래 빈 행에 새 데이터를 추가할 수 있습니다.")

# ==========================================
# 2-5. 키워드 사전 파싱 함수
# ==========================================
@st.cache_data(show_spinner=False)
def parse_keywords(file):
    if file is None:
        return {}
    try:
        if file.name.endswith('.csv'):
            k_df = pd.read_csv(file)
        else:
            k_df = pd.read_excel(file)
            
        if not all(col in k_df.columns for col in ['키워드', '대분류', '소분류']):
            st.sidebar.error("⚠️ 키워드 파일에 '키워드', '대분류', '소분류' 컬럼이 필요합니다.")
            return {}
            
        k_df = k_df.dropna(subset=['키워드', '대분류'])
        rules = {}
        for _, row in k_df.iterrows():
            rules[str(row['키워드']).strip()] = (
                str(row['대분류']).strip(), 
                str(row['소분류']).strip() if pd.notna(row['소분류']) else ""
            )
        return rules
    except Exception as e:
        st.sidebar.error(f"키워드 파일 로드 오류: {e}")
        return {}

# ==========================================
# 3. 데이터 로드 및 전처리 (캐싱)
# ==========================================
@st.cache_data(show_spinner=False)
def load_data(file, keyword_rules):
    if file.name.endswith('.csv'):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file, sheet_name='가계부 내역')
        
    # 필수 컬럼 전처리
    if '날짜' in df.columns:
        df['날짜'] = pd.to_datetime(df['날짜']).dt.date
    if '금액' in df.columns:
        df['금액'] = pd.to_numeric(df['금액'], errors='coerce').fillna(0)
    
    # === [변경됨] 외부 키워드 기반 자동 분류 규칙 적용 ===
    if '내용' in df.columns and '대분류' in df.columns and keyword_rules:
        # 사용자가 업로드한 키워드 딕셔너리를 순회하며 일괄 업데이트
        for keyword, (main_cat, sub_cat) in keyword_rules.items():
            mask = df['내용'].astype(str).str.contains(keyword, na=False, case=False)
            df.loc[mask, '대분류'] = main_cat
            if '소분류' in df.columns and sub_cat:
                df.loc[mask, '소분류'] = sub_cat

    # 필요한 컬럼만 추출 (존재하는 경우만)
    cols_to_keep = ['날짜', '시간', '타입', '대분류', '소분류', '내용', '금액', '결제수단']
    available_cols = [c for c in cols_to_keep if c in df.columns]
    
    return df[available_cols].copy()

# ==========================================
# 4. 메인 화면 - 데이터 편집기 및 시각화
# ==========================================
if uploaded_file is not None:
    # 키워드 규칙 파싱 및 최초 로드
    dynamic_rules = parse_keywords(keyword_file)
    raw_df = load_data(uploaded_file, dynamic_rules)
    
    # 월 필터링 추출
    raw_df['연월'] = pd.to_datetime(raw_df['날짜']).dt.strftime('%Y-%m')
    month_list = sorted(raw_df['연월'].dropna().unique(), reverse=True)
    
    selected_month = st.sidebar.selectbox("📅 조회할 월 선택", ["전체 기간"] + list(month_list))
    
    if selected_month != "전체 기간":
        filtered_df = raw_df[raw_df['연월'] == selected_month].drop(columns=['연월'])
    else:
        filtered_df = raw_df.drop(columns=['연월'])

    st.subheader(f"🛠️ 데이터 수정/삭제 ({selected_month})")
    
    # 대분류/타입 드롭다운 목록 구성
    type_options = ["지출", "수입", "이체"]
    cat_options = list(raw_df['대분류'].dropna().unique()) if '대분류' in raw_df.columns else []

    # st.data_editor를 통한 인터랙티브 표 제공 (CRUD 기능 핵심)
    edited_df = st.data_editor(
        filtered_df,
        num_rows="dynamic", # 행 추가/삭제 허용
        column_config={
            "타입": st.column_config.SelectboxColumn("타입", options=type_options, required=True),
            "대분류": st.column_config.SelectboxColumn("대분류", options=cat_options),
            "금액": st.column_config.NumberColumn("금액(원)", format="%d"),
            "날짜": st.column_config.DateColumn("날짜")
        },
        use_container_width=True,
        height=350,
        key="data_editor"
    )

    # 수정된 데이터를 바탕으로 분석 수행
    # '지출' 내역만 필터링하고 금액을 양수로 변환
    expenses = edited_df[edited_df['타입'] == '지출'].copy()
    expenses['지출금액'] = expenses['금액'].abs()
    
    incomes = edited_df[edited_df['타입'] == '수입'].copy()
    
    # ==========================================
    # 5. 핵심 지표 (KPI)
    # ==========================================
    total_expense = expenses['지출금액'].sum()
    total_income = incomes['금액'].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("📉 총 지출 (수정 반영)", f"{total_expense:,.0f} 원")
    col2.metric("📈 총 수입 (수정 반영)", f"{total_income:,.0f} 원")
    col3.metric("💳 총 거래 건수", f"{len(edited_df)} 건")
    
    # === [추가됨] 예산 소진율 프로그레스 바 ===
    st.markdown("### 📊 예산 소진율")
    budget_ratio = total_expense / target_budget if target_budget > 0 else 0
    budget_ratio_clamped = min(budget_ratio, 1.0)
    
    if budget_ratio > 1.0:
        st.error(f"⚠️ 목표 예산을 **{total_expense - target_budget:,.0f}원** 초과했습니다! (소진율: {budget_ratio*100:.1f}%)")
        st.progress(1.0)
    else:
        st.success(f"✅ 예산 내에서 순항 중입니다. (남은 예산: **{target_budget - total_expense:,.0f}원** / 소진율: {budget_ratio*100:.1f}%)")
        st.progress(budget_ratio_clamped)
        
    st.markdown("---")

    # ==========================================
    # 6. 동적 차트 시각화
    # ==========================================
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        st.subheader("🍩 카테고리별 지출 비중")
        if not expenses.empty:
            cat_summary = expenses.groupby('대분류')['지출금액'].sum().reset_index()
            cat_summary = cat_summary[cat_summary['지출금액'] > 0]
            
            fig_pie = px.pie(cat_summary, values='지출금액', names='대분류', hole=0.4,
                             color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_pie.update_traces(textinfo='percent+label', hovertemplate='%{label}: %{value:,.0f}원')
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("지출 데이터가 없습니다.")
            
    with chart_col2:
        st.subheader("📊 일자별 지출 흐름")
        if not expenses.empty:
            daily_expense = expenses.groupby('날짜')['지출금액'].sum().reset_index()
            fig_bar = px.bar(daily_expense, x='날짜', y='지출금액', 
                             color_discrete_sequence=['#FF9F9F'])
            fig_bar.update_traces(hovertemplate='날짜: %{x}<br>지출: %{y:,.0f}원')
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("지출 데이터가 없습니다.")

    # ==========================================
    # 7. 수정된 데이터 다운로드
    # ==========================================
    st.markdown("---")
    st.subheader("💾 정리된 데이터 저장")
    @st.cache_data
    def convert_df(df):
        return df.to_csv(index=False).encode('utf-8-sig')

    csv = convert_df(edited_df)
    st.download_button(
        label="수정된 가계부 데이터 다운로드 (CSV)",
        data=csv,
        file_name='cleaned_ledger.csv',
        mime='text/csv',
    )
    
else:
    st.info("👈 왼쪽 사이드바에서 뱅크샐러드 엑셀/CSV 파일을 업로드해주세요.")