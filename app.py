import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from rfp_parser import parse_rfp_pdf
from company_parser import parse_all_fs_files

# ---------------------------------------------------------
# Page Configuration & Custom CSS
# ---------------------------------------------------------
st.set_page_config(
    page_title="EDCF 입찰 컨소시엄 재무자격 자동 평가 시스템",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
    }
    
    .main-title {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.2rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        color: #64748B;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    
    .kpi-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1.25rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        height: 100%;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08);
    }
    .kpi-label {
        font-size: 0.85rem;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .kpi-value {
        font-size: 1.55rem;
        font-weight: 800;
        color: #0F172A;
        margin-top: 0.4rem;
    }
    .kpi-sub {
        font-size: 0.825rem;
        color: #2563EB;
        font-weight: 600;
        margin-top: 0.3rem;
    }
    
    .info-card {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 0.9rem 1.1rem;
        margin-bottom: 0.75rem;
    }
    .info-card-label {
        font-size: 0.8rem;
        font-weight: 600;
        color: #64748B;
        margin-bottom: 0.2rem;
    }
    .info-card-value {
        font-size: 1.02rem;
        font-weight: 700;
        color: #1E293B;
    }
    
    .banner-pass {
        background: linear-gradient(135deg, #059669 0%, #10B981 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 14px;
        text-align: center;
        box-shadow: 0 10px 15px -3px rgba(16, 185, 129, 0.3);
        margin-bottom: 1.5rem;
    }
    .banner-fail {
        background: linear-gradient(135deg, #DC2626 0%, #EF4444 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 14px;
        text-align: center;
        box-shadow: 0 10px 15px -3px rgba(239, 68, 68, 0.3);
        margin-bottom: 1.5rem;
    }
    .banner-title {
        font-size: 1.5rem;
        font-weight: 800;
        margin-bottom: 0.4rem;
    }
    .banner-desc {
        font-size: 0.95rem;
        opacity: 0.95;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Default Blank Session State Definitions
# ---------------------------------------------------------
BLANK_RFP_INFO = {
    "project_name": "— (RFP 미등록)",
    "client": "—",
    "country": "—",
    "bid_usd": 0,
    "exchange_rate": 1350.0,
    "eval_period": "—",
    "min_turnover_usd": 0,
    "cashflow_usd": 0,
    "net_worth_req": "—",
    "credit_rating": "—",
    "min_curr_ratio": None,
    "max_debt_ratio": None,
    "consortium_rule": "—",
    "rfp_filename": "— (미업로드)",
    "is_custom_uploaded": False,
    "file_size_kb": 0,
    "is_parsed": False
}

if "rfp_info" not in st.session_state:
    st.session_state.rfp_info = BLANK_RFP_INFO.copy()

if "target_bid_usd" in st.session_state:
    st.session_state["sidebar_bid_usd"] = st.session_state.pop("target_bid_usd")
if "target_exchange_rate" in st.session_state:
    st.session_state["sidebar_exchange_rate"] = st.session_state.pop("target_exchange_rate")

if "sidebar_bid_usd" not in st.session_state:
    st.session_state["sidebar_bid_usd"] = int(st.session_state.rfp_info.get("bid_usd", 0))
if "sidebar_exchange_rate" not in st.session_state:
    st.session_state["sidebar_exchange_rate"] = float(st.session_state.rfp_info.get("exchange_rate", 1350.0))

COMPANY_COLUMNS = [
    "기업명", "역할", "지분율 (%)", 
    "2022 매출액(원)", "2023 매출액(원)", "2024 매출액(원)", 
    "유동자산(원)", "유동부채(원)", "자본총계(원)", "부채총계(원)"
]

if "company_data" not in st.session_state:
    st.session_state.company_data = pd.DataFrame(columns=COMPANY_COLUMNS)

# ---------------------------------------------------------
# Sidebar Configuration
# ---------------------------------------------------------
st.sidebar.markdown("## ⚙️ 프로젝트 기본 설정")
st.sidebar.markdown("EDCF 입찰 사업의 기본 예산 및 환율을 설정합니다. (RFP 업로드 시 자동 추출/연동)")

total_bid_usd = st.sidebar.number_input(
    "전체 입찰 금액 (USD)",
    min_value=0,
    step=1_000_000,
    format="%d",
    help="EDCF 입찰 공고에 명시된 총 사업 예산 (USD) — RFP 업로드 시 자동 반영",
    key="sidebar_bid_usd"
)

exchange_rate = st.sidebar.number_input(
    "환율 (USD/KRW)",
    min_value=1.0,
    step=10.0,
    format="%.1f",
    help="평가 기준 적용 환율",
    key="sidebar_exchange_rate"
)

st.session_state.rfp_info["bid_usd"] = total_bid_usd
st.session_state.rfp_info["exchange_rate"] = exchange_rate
total_bid_krw = total_bid_usd * exchange_rate

st.sidebar.markdown("---")
st.sidebar.markdown("### 📌 원화 환산 예산")
if total_bid_usd > 0:
    st.sidebar.metric(
        label="총 사업비 (KRW)",
        value=f"{total_bid_krw / 1e8:,.1f} 억원",
        delta=f"${total_bid_usd:,.0f} USD"
    )
else:
    st.sidebar.metric(
        label="총 사업비 (KRW)",
        value="0 원",
        delta="RFP 업로드 대기"
    )
st.sidebar.markdown("---")
st.sidebar.caption("💡 Tip: 탭 1에서 제안요청서(RFP) 및 재무제표를 업로드하면 프로젝트 정보와 참여기업이 자동 추출되며, 탭 2에서 [지분율 전체 자동 최적화]를 실행할 수 있습니다.")

# ---------------------------------------------------------
# App Header
# ---------------------------------------------------------
st.markdown('<div class="main-title">🏛️ EDCF 입찰 컨소시엄 재무자격 자동 평가 시스템</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">EDCF(대외경제협력기금) 입찰 가이드라인 기반 RFP 분석, 재무자격 심사 및 원버튼 지분율 최적화 플랫폼</div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# Tabs Setup
# ---------------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "📋 탭 1: RFP 업로드 & 기본 정보 분석",
    "🏢 탭 2: 업체 역할 지정 & 지분율 자동 최적화",
    "📊 탭 3: 자격 평가 결과 및 대시보드"
])

# =========================================================
# TAB 1: RFP 업로드 & 기본 정보 분석
# =========================================================
with tab1:
    st.markdown("### 📄 Step 1. 입찰 제안요청서(RFP) 업로드 및 프로젝트 기본 정보 자동 추출")
    st.markdown(
        "공고된 **EDCF 입찰 제안요청서(RFP)** PDF 문서를 업로드하면, 분석 엔진이 문서 본문을 정밀 분석하여 "
        "**프로젝트 기본 메타정보(사업명, 발주처, 대상국가, 입찰 예산 등)**와 **필수 재무 자격 요건(평가 대상 연도, 연평균 매출액, 유동성, 순자산 등)**을 자동으로 추출하고 사이드바 기본 설정에 즉시 연동합니다."
    )
    
    with st.container(border=True):
        col_up, col_actions = st.columns([3, 1])
        with col_up:
            uploaded_rfp = st.file_uploader(
                "📂 EDCF 입찰 제안요청서(RFP) 파일 업로드 (PDF)",
                type=["pdf"],
                help="신규 입찰 공고문 또는 제안요청서 PDF 파일을 업로드하세요.",
                key="rfp_uploader"
            )
        with col_actions:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            parse_rfp_btn = st.button("⚡ RFP 분석 실행", type="primary", width="stretch")
            reset_rfp_btn = st.button("🔄 기본 초기화 (공란)", width="stretch")

        if reset_rfp_btn:
            st.session_state.rfp_info = BLANK_RFP_INFO.copy()
            st.session_state["target_bid_usd"] = 0
            st.session_state["target_exchange_rate"] = 1350.0
            st.session_state["last_parsed_file_key"] = None
            st.toast("기본 정보 및 재무기준이 공란으로 초기화되었습니다.", icon="🔄")
            st.rerun()

        if uploaded_rfp is not None:
            current_file_key = f"{uploaded_rfp.name}_{uploaded_rfp.size}"
            if st.session_state.get("last_parsed_file_key") != current_file_key or parse_rfp_btn:
                with st.spinner("업로드된 RFP PDF 문서에서 기본 정보 및 재무 자격 요건을 추출 중입니다..."):
                    try:
                        parsed_res = parse_rfp_pdf(uploaded_rfp)
                        if parsed_res:
                            parsed_res["rfp_filename"] = uploaded_rfp.name
                            parsed_res["is_custom_uploaded"] = True
                            parsed_res["file_size_kb"] = round(uploaded_rfp.size / 1024, 1)
                            parsed_res["is_parsed"] = True
                            st.session_state.rfp_info.update(parsed_res)
                            
                            st.session_state["target_bid_usd"] = int(parsed_res.get("bid_usd", 0))
                            st.session_state["target_exchange_rate"] = float(parsed_res.get("exchange_rate", 1350.0))
                            st.session_state["last_parsed_file_key"] = current_file_key
                            st.toast(f"✅ '{uploaded_rfp.name}' 분석 완료! 금액(${parsed_res.get('bid_usd', 0):,})과 재무기준이 추출되었습니다.", icon="🎉")
                            st.rerun()
                    except Exception as e:
                        st.error(f"⚠️ PDF 문서 파싱 중 오류가 발생했습니다: {e}")
        elif parse_rfp_btn:
            st.warning("⚠️ 먼저 분석할 EDCF 제안요청서(RFP) PDF 파일을 업로드해 주세요.")

    rfp_meta = st.session_state.rfp_info
    if rfp_meta.get("is_parsed", False):
        st.success(
            f"✅ **제안요청서 파싱 성공**: '{rfp_meta['rfp_filename']}' ({rfp_meta.get('file_size_kb', 0)} KB) — "
            f"국가: **{rfp_meta['country']}** | 차관/입찰번호: **{rfp_meta.get('loan_no', '-')}** / **{rfp_meta.get('bid_no', '-')}** | 총 사업비: **${rfp_meta['bid_usd']:,} USD**"
        )
    else:
        st.info("ℹ️ 현재 분석된 RFP 문서가 없습니다. 상단에서 PDF 파일을 업로드하여 분석을 시작하세요. (공란 상태)")

    st.markdown("#### 📌 1. 추출된 입찰 프로젝트 기본 정보")
    
    is_parsed = st.session_state.rfp_info.get("is_parsed", False)
    meta = st.session_state.rfp_info
    
    info_col1, info_col2, info_col3 = st.columns(3)
    with info_col1:
        st.markdown(f"""
        <div class="info-card">
            <div class="info-card-label">사업명 (Project Title)</div>
            <div class="info-card-value">{meta['project_name'] if is_parsed else '—'}</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown(f"""
        <div class="info-card">
            <div class="info-card-label">발주기관 / 재원 (Client / Source)</div>
            <div class="info-card-value">{meta.get('client', '—') if is_parsed else '—'}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with info_col2:
        st.markdown(f"""
        <div class="info-card">
            <div class="info-card-label">대상 국가 (Beneficiary Country)</div>
            <div class="info-card-value">{('🌏 ' + meta['country']) if is_parsed else '—'}</div>
        </div>
        """, unsafe_allow_html=True)
        bid_display = f"💵 ${total_bid_usd:,.0f} USD ({total_bid_krw / 1e8:,.1f} 억원)" if is_parsed and total_bid_usd > 0 else "—"
        st.markdown(f"""
        <div class="info-card">
            <div class="info-card-label">총 입찰 예산 (Total Bid Amount)</div>
            <div class="info-card-value">{bid_display}</div>
        </div>
        """, unsafe_allow_html=True)

    with info_col3:
        st.markdown(f"""
        <div class="info-card">
            <div class="info-card-label">RFP 파일명</div>
            <div class="info-card-value">{meta.get('rfp_filename', '—') if is_parsed else '— (미업로드)'}</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown(f"""
        <div class="info-card">
            <div class="info-card-label">컨소시엄 구성 요건</div>
            <div class="info-card-value">{meta['consortium_rule'] if is_parsed else '—'}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # RFP Extraction Summary Dashboard Cards
    if is_parsed:
        st.markdown(f"### 📋 파싱된 RFP 자격요건 요약: `{meta.get('project_name', '프로젝트')}`")
    else:
        st.markdown("### 📋 파싱된 RFP 자격요건 요약 (미업로드 대기 중)")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        bid_str = f"${meta['bid_usd']:,.0f}" if is_parsed else "$0"
        rate_str = f"환율: {meta['exchange_rate']:,.1f} KRW/USD" if is_parsed else "환율 미적용"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">총 사업 예산 (USD)</div>
            <div class="kpi-value">{bid_str}</div>
            <div class="kpi-sub">{rate_str}</div>
        </div>
        """, unsafe_allow_html=True)

    with k2:
        turnover_str = f"${meta['min_turnover_usd']:,.0f}" if is_parsed else "$0"
        period_str = f"평가기간: {meta['eval_period']}" if is_parsed else "평가기간 미지정"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">최소 연평균 매출액 요구</div>
            <div class="kpi-value">{turnover_str}</div>
            <div class="kpi-sub">{period_str}</div>
        </div>
        """, unsafe_allow_html=True)

    with k3:
        cashflow_str = f"${meta['cashflow_usd']:,.0f}" if is_parsed else "$0"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">필요 가용 유동성 자원</div>
            <div class="kpi-value">{cashflow_str}</div>
            <div class="kpi-sub">유동비율 >= 100% 충족시 대체</div>
        </div>
        """, unsafe_allow_html=True)

    with k4:
        if is_parsed and meta.get('max_debt_ratio'):
            max_debt_str = f"<= {meta['max_debt_ratio']}%"
        elif is_parsed:
            max_debt_str = "기준 없음"
        else:
            max_debt_str = "—"
            
        net_worth_str = f"순자산: {meta['net_worth_req']}" if is_parsed else "순자산: —"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">최대 허용 부채비율</div>
            <div class="kpi-value">{max_debt_str}</div>
            <div class="kpi-sub">{net_worth_str}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Financial Statements Multi-upload Section
    st.markdown("### 📑 Step 2. 참여기업 재무제표(감사보고서) 다중 업로드")
    st.markdown("컨소시엄에 참여하는 **모든 기업의 재무제표(PDF/Excel)**를 한 번에 다중 선택하여 업로드하세요. AI/OCR 파서가 3개년 매출 및 주요 재무항목을 추출합니다.")
    
    fs_files = st.file_uploader(
        "참여기업 재무제표 업로드 (복수 파일 선택 가능)", 
        type=["pdf", "xlsx", "xls"], 
        accept_multiple_files=True,
        key="fs_multi_uploader"
    )

    if fs_files:
        current_fs_keys = "_".join([f"{f.name}_{f.size}" for f in fs_files])
        if st.session_state.get("last_fs_keys") != current_fs_keys:
            with st.spinner(f"총 {len(fs_files)}개 기업의 재무제표 데이터를 추출 및 구조화 중입니다..."):
                status_list, new_company_df = parse_all_fs_files(fs_files)
                st.session_state["extracted_fs_status"] = status_list
                st.session_state["extracted_companies_df"] = new_company_df
                st.session_state["last_fs_keys"] = current_fs_keys
                st.session_state["fs_loaded_to_tab2"] = False
                st.toast("기업 재무제표 추출이 완료되었습니다! 탭 2에서 확인하세요.", icon="🏢")

        if "extracted_fs_status" in st.session_state:
            st.markdown("#### 🔍 재무제표 파일 파싱 처리 현황")
            st.table(pd.DataFrame(st.session_state["extracted_fs_status"]))
            
            if "extracted_companies_df" in st.session_state:
                extracted_comp_names = st.session_state["extracted_companies_df"]["기업명"].tolist()
                st.success(f"✅ **추출 성공 기업 ({len(extracted_comp_names)}개사)**: {', '.join(extracted_comp_names)} → **[탭 2: 역할 지정 & 지분율 최적화]**로 이동하여 지분율을 자동 배분하세요.")

# =========================================================
# TAB 2: 업체 역할 지정 & 지분율 자동 최적화
# =========================================================
with tab2:
    st.markdown("### 🏢 컨소시엄 기업 재무 데이터 및 역할/지분율 설정")
    st.markdown("""
    - **자동 로딩 및 최적화**: 탭 1에서 재무제표를 업로드한 경우, **[⚡ 지분율 전체 자동 최적화]** 버튼을 누르면 추출된 기업 정보가 즉시 로딩되고 역할에 맞는 최적 지분율(100%, 60:40, 50:N)이 자동 배분됩니다.
    - **자유로운 수정 권한**: 사용자는 테이블 내 **'역할'**뿐만 아니라 **'지분율 (%)'**도 직접 더블클릭하여 자유롭게 수정할 수 있습니다.
    """)
    
    has_extracted = "extracted_companies_df" in st.session_state
    if has_extracted and not st.session_state.get("fs_loaded_to_tab2", False):
        comps = st.session_state["extracted_companies_df"]["기업명"].tolist()
        st.info(
            f"📥 **탭 1에서 추출된 신규 참여기업 대기 중**: {', '.join(comps)} (총 {len(comps)}개사)\n\n"
            "아래 **[⚡ 지분율 전체 자동 최적화]** 또는 **[📥 탭1 추출 기업 불러오기]** 버튼을 클릭하면 테이블에 반영됩니다."
        )

    col_btn_opt, col_btn_load = st.columns([2, 1])
    with col_btn_opt:
        optimize_btn = st.button("⚡ 지분율 전체 자동 최적화", type="primary", width="stretch")
    with col_btn_load:
        if has_extracted:
            load_extracted_btn = st.button("📥 탭1 추출 기업 불러오기", width="stretch")
        else:
            load_extracted_btn = False

    if load_extracted_btn and has_extracted:
        st.session_state.company_data = st.session_state["extracted_companies_df"].copy()
        st.session_state["fs_loaded_to_tab2"] = True
        st.toast("탭 1에서 추출된 참여기업 데이터가 성공적으로 로딩되었습니다.", icon="📥")
        st.rerun()

    if optimize_btn:
        if has_extracted and not st.session_state.get("fs_loaded_to_tab2", False):
            df_to_opt = st.session_state["extracted_companies_df"].copy()
            st.session_state["fs_loaded_to_tab2"] = True
        else:
            df_to_opt = st.session_state.company_data.copy()

        if len(df_to_opt) > 0:
            lead_mask = df_to_opt["역할"] == "주관사"
            num_leads = lead_mask.sum()
            num_total = len(df_to_opt)
            
            if num_leads == 0:
                df_to_opt.iloc[0, df_to_opt.columns.get_loc("역할")] = "주관사"
                lead_mask = df_to_opt["역할"] == "주관사"
                num_leads = 1
            elif num_leads > 1:
                st.error(f"⚠️ [오류] 주관사는 단 1개사만 지정해야 합니다. (현재 주관사 {num_leads}개 지정됨)")
                st.stop()
            
            if num_total == 1:
                df_to_opt.loc[lead_mask, "지분율 (%)"] = 100.0
            elif num_total == 2:
                df_to_opt.loc[lead_mask, "지분율 (%)"] = 60.0
                df_to_opt.loc[~lead_mask, "지분율 (%)"] = 40.0
            else:
                df_to_opt.loc[lead_mask, "지분율 (%)"] = 50.0
                member_count = num_total - 1
                member_share = round(50.0 / member_count, 1)
                df_to_opt.loc[~lead_mask, "지분율 (%)"] = member_share
                
                current_sum = df_to_opt["지분율 (%)"].sum()
                diff = round(100.0 - current_sum, 1)
                if abs(diff) > 0:
                    last_idx = df_to_opt.index[-1]
                    df_to_opt.loc[last_idx, "지분율 (%)"] += diff

            st.session_state.company_data = df_to_opt
            st.toast("🎉 지분율 자동 최적화 완료! (주관사/참여사 역할별 100.0% 자동 배분)", icon="⚡")
            st.rerun()

    column_config = {
        "기업명": st.column_config.TextColumn("기업명", disabled=False),
        "역할": st.column_config.SelectboxColumn(
            "역할 (수정가능)",
            options=["주관사", "참여사"],
            required=True,
            help="컨소시엄 내 업체의 역할 선택 (주관사는 단 1개사 필수)"
        ),
        "지분율 (%)": st.column_config.NumberColumn(
            "지분율 (%) (수정가능)",
            format="%.1f%%",
            min_value=0.0,
            max_value=100.0,
            step=0.5,
            disabled=False,
            help="사용자가 직접 지분율을 수정할 수 있습니다 (합계 100.0% 충족 필요)"
        ),
        "2022 매출액(원)": st.column_config.NumberColumn("2022 매출액(원)", format="%d"),
        "2023 매출액(원)": st.column_config.NumberColumn("2023 매출액(원)", format="%d"),
        "2024 매출액(원)": st.column_config.NumberColumn("2024 매출액(원)", format="%d"),
        "유동자산(원)": st.column_config.NumberColumn("유동자산(원)", format="%d"),
        "유동부채(원)": st.column_config.NumberColumn("유동부채(원)", format="%d"),
        "자본총계(원)": st.column_config.NumberColumn("자본총계(원)", format="%d"),
        "부채총계(원)": st.column_config.NumberColumn("부채총계(원)", format="%d"),
    }

    if st.session_state.company_data.empty:
        st.info("ℹ️ 현재 등록된 기업 재무자료가 없습니다. 탭 1에서 재무제표를 업로드하거나 아래 표에 직접 기업 데이터를 입력하세요.")

    edited_df = st.data_editor(
        st.session_state.company_data,
        column_config=column_config,
        width="stretch",
        hide_index=True,
        num_rows="dynamic",
        key="data_editor_table"
    )

    st.session_state.company_data = edited_df

    if not edited_df.empty and "지분율 (%)" in edited_df.columns:
        total_share = float(edited_df["지분율 (%)"].sum())
        if abs(total_share - 100.0) < 0.05:
            st.success(f"✅ **현재 컨소시엄 지분율 합계**: **{total_share:.1f}%** (지분 요건 100.0% 충족)")
        else:
            st.warning(f"⚠️ **현재 컨소시엄 지분율 합계**: **{total_share:.1f}%** (합계가 100.0%가 되어야 합니다. 차이: **{100.0 - total_share:+.1f}%**)")

# =========================================================
# TAB 3: 자격 평가 결과 및 대시보드
# =========================================================
with tab3:
    is_parsed = st.session_state.rfp_info.get("is_parsed", False)
    has_companies = not st.session_state.company_data.empty

    if not is_parsed or not has_companies or total_bid_usd == 0:
        st.warning("⚠️ RFP(제안요청서) 및 참여기업 재무제표가 등록되어야 자격 평가 결과를 확인하실 수 있습니다.")
        if not is_parsed:
            st.info("👉 **탭 1**에서 제안요청서(RFP) PDF 문서를 먼저 업로드하여 분석해 주세요.")
        if not has_companies:
            st.info("👉 **탭 1**에서 참여기업 재무제표를 업로드하거나 **탭 2**에서 기업 재무자료를 등록해 주세요.")
        st.stop()

    df_eval = st.session_state.company_data.copy()

    df_eval["3년 평균 매출액(원)"] = (
        df_eval["2022 매출액(원)"].fillna(0) + df_eval["2023 매출액(원)"].fillna(0) + df_eval["2024 매출액(원)"].fillna(0)
    ) / 3.0

    df_eval["담당 사업금액(USD)"] = total_bid_usd * (df_eval["지분율 (%)"].fillna(0) / 100.0)
    df_eval["담당 사업금액(KRW)"] = total_bid_krw * (df_eval["지분율 (%)"].fillna(0) / 100.0)

    consortium_avg_rev = df_eval["3년 평균 매출액(원)"].sum()
    consortium_curr_assets = df_eval["유동자산(원)"].fillna(0).sum()
    consortium_curr_liab = df_eval["유동부채(원)"].fillna(0).sum()
    consortium_total_equity = df_eval["자본총계(원)"].fillna(0).sum()
    consortium_total_liab = df_eval["부채총계(원)"].fillna(0).sum()

    consortium_curr_ratio = (consortium_curr_assets / consortium_curr_liab * 100.0) if consortium_curr_liab > 0 else 0
    consortium_debt_ratio = (consortium_total_liab / consortium_total_equity * 100.0) if consortium_total_equity > 0 else 0

    min_turnover_usd = st.session_state.rfp_info.get("min_turnover_usd", total_bid_usd)
    min_turnover_krw = min_turnover_usd * exchange_rate
    cashflow_usd = st.session_state.rfp_info.get("cashflow_usd", 12_000_000)
    cashflow_krw = cashflow_usd * exchange_rate

    req_rev_pass = consortium_avg_rev >= min_turnover_krw if min_turnover_krw > 0 else True
    req_net_worth_pass = (df_eval["자본총계(원)"].fillna(0) > 0).all() if len(df_eval) > 0 else False
    req_cashflow_pass = (consortium_curr_assets >= cashflow_krw) or (consortium_curr_ratio >= 100.0)
    req_debt_pass = consortium_debt_ratio <= st.session_state.rfp_info.get("max_debt_ratio", 150.0) if st.session_state.rfp_info.get("max_debt_ratio") else True

    overall_pass = req_rev_pass and req_net_worth_pass and req_cashflow_pass and req_debt_pass

    if overall_pass:
        st.markdown("""
        <div class="banner-pass">
            <div class="banner-title">🎉 [종합 적격 : PASS] EDCF 입찰 재무자격 충족</div>
            <div class="banner-desc">본 컨소시엄은 RFP 요구 기준(연평균 매출액, 순자산 건전성, 유동성, 부채비율)을 모두 만족하여 최종 입찰 자격을 획득하였습니다.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="banner-fail">
            <div class="banner-title">⚠️ [종합 부적격 : FAIL] EDCF 입찰 재무자격 미달</div>
            <div class="banner-desc">컨소시엄의 일부 재무 지표가 RFP 요구 기준에 미달합니다. (아래 1:1 비교표 항목 확인 및 지분율/구성원 조정 필요)</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("### 📋 1. RFP 요구 기준 vs 컨소시엄 실적 1:1 비교")

    year_str = st.session_state.rfp_info['eval_period'].split('(')[0].strip() if is_parsed else "최근 3개년"
    turnover_target_str = f">= {min_turnover_krw / 1e8:,.1f} 억원 (${min_turnover_usd:,.0f} USD)" if min_turnover_krw > 0 else "—"
    cashflow_target_str = f">= {cashflow_krw / 1e8:,.1f} 억원 (${cashflow_usd:,.0f} USD)" if cashflow_krw > 0 else "—"

    comp_table = [
        {
            "평가 항목": f"3년 평균 매출액 ({year_str})",
            "RFP 요구 기준": turnover_target_str,
            "컨소시엄 실제 합산치": f"{consortium_avg_rev / 1e8:,.1f} 억원",
            "판정 결과": "🟢 PASS" if req_rev_pass else "🔴 FAIL (미달)"
        },
        {
            "평가 항목": "순자산 건전성 (자본잠식 여부, 각사 기준)",
            "RFP 요구 기준": "3개년 평균 순자산 > 0 (양수 필수)",
            "컨소시엄 실제 합산치": f"합산 자본총계 {consortium_total_equity / 1e8:,.1f} 억원 (전원 양수: {'충족' if req_net_worth_pass else '미달'})",
            "판정 결과": "🟢 PASS" if req_net_worth_pass else "🔴 FAIL"
        },
        {
            "평가 항목": "가용 유동성 자원 / 유동비율",
            "RFP 요구 기준": cashflow_target_str,
            "컨소시엄 실제 합산치": f"유동자산 {consortium_curr_assets / 1e8:,.1f} 억원 (유동비율 {consortium_curr_ratio:,.1f}%)",
            "판정 결과": "🟢 PASS" if req_cashflow_pass else "🔴 FAIL"
        },
        {
            "평가 항목": "컨소시엄 부채비율 (부채총계/자본총계)",
            "RFP 요구 기준": "<= 150.0 %",
            "컨소시엄 실제 합산치": f"{consortium_debt_ratio:,.1f} %",
            "판정 결과": "🟢 PASS" if req_debt_pass else "🔴 FAIL"
        }
    ]

    st.table(pd.DataFrame(comp_table))
    st.markdown("---")

    st.markdown("### 📊 2. 지분율 및 기업별 담당 사업 금액 시각화")

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        fig_pie = px.pie(
            df_eval,
            values="지분율 (%)",
            names="기업명",
            title="<b>컨소시엄 지분율 배분 현황</b>",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        fig_pie.update_layout(margin=dict(t=40, b=20, l=20, r=20))
        st.plotly_chart(fig_pie, width="stretch")

    with col_chart2:
        fig_bar = px.bar(
            df_eval,
            x="기업명",
            y="담당 사업금액(KRW)",
            text_auto='.2s',
            title="<b>기업별 담당 사업 금액 (원화 기준)</b>",
            color="역할",
            color_discrete_map={"주관사": "#1E3A8A", "참여사": "#3B82F6"}
        )
        fig_bar.update_layout(
            yaxis_title="담당 금액 (원)",
            margin=dict(t=40, b=20, l=20, r=20)
        )
        st.plotly_chart(fig_bar, width="stretch")

    st.markdown("---")

    st.markdown("### 📑 3. 기업별 담당 사업 금액 및 재무 세부 내역")

    display_cols = [
        "기업명", "역할", "지분율 (%)", "담당 사업금액(USD)", "담당 사업금액(KRW)",
        "3년 평균 매출액(원)", "유동자산(원)", "유동부채(원)", "자본총계(원)", "부채총계(원)"
    ]

    df_display = df_eval[display_cols].copy()

    df_formatted = df_display.copy()
    df_formatted["지분율 (%)"] = df_formatted["지분율 (%)"].map(lambda x: f"{x:.1f}%" if pd.notnull(x) else "—")
    df_formatted["담당 사업금액(USD)"] = df_formatted["담당 사업금액(USD)"].map(lambda x: f"${x:,.0f}" if pd.notnull(x) else "—")
    df_formatted["담당 사업금액(KRW)"] = df_formatted["담당 사업금액(KRW)"].map(lambda x: f"{x/1e8:,.1f} 억원" if pd.notnull(x) else "—")
    df_formatted["3년 평균 매출액(원)"] = df_formatted["3년 평균 매출액(원)"].map(lambda x: f"{x/1e8:,.1f} 억원" if pd.notnull(x) else "—")
    df_formatted["유동자산(원)"] = df_formatted["유동자산(원)"].map(lambda x: f"{x/1e8:,.1f} 억원" if pd.notnull(x) else "—")
    df_formatted["유동부채(원)"] = df_formatted["유동부채(원)"].map(lambda x: f"{x/1e8:,.1f} 억원" if pd.notnull(x) else "—")
    df_formatted["자본총계(원)"] = df_formatted["자본총계(원)"].map(lambda x: f"{x/1e8:,.1f} 억원" if pd.notnull(x) else "—")
    df_formatted["부채총계(원)"] = df_formatted["부채총계(원)"].map(lambda x: f"{x/1e8:,.1f} 억원" if pd.notnull(x) else "—")

    st.dataframe(df_formatted, width="stretch", hide_index=True)