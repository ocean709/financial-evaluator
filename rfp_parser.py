import re
import io
from pypdf import PdfReader

# Country dictionary for EDCF partner countries
COUNTRY_MAP = {
    "tanzania": ("탄자니아", "The United Republic of Tanzania"),
    "philippines": ("필리핀", "Republic of the Philippines"),
    "vietnam": ("베트남", "Socialist Republic of Vietnam"),
    "bangladesh": ("방글라데시", "People's Republic of Bangladesh"),
    "indonesia": ("인도네시아", "Republic of Indonesia"),
    "uzbekistan": ("우즈베키스탄", "Republic of Uzbekistan"),
    "cambodia": ("캄보디아", "Kingdom of Cambodia"),
    "laos": ("라오스", "Lao PDR"),
    "ghana": ("가나", "Republic of Ghana"),
    "uganda": ("우간다", "Republic of Uganda"),
    "sri lanka": ("스리랑카", "Democratic Socialist Republic of Sri Lanka"),
    "mongolia": ("몽골", "Mongolia")
}

def parse_rfp_pdf(file_source):
    """
    Parses an EDCF RFP PDF document from file path or bytes/BytesIO buffer.
    Returns structured dictionary with extracted project metadata and financial qualification requirements.
    """
    if isinstance(file_source, (str, bytes)):
        if isinstance(file_source, bytes):
            reader = PdfReader(io.BytesIO(file_source))
        else:
            reader = PdfReader(file_source)
    else:
        # Streamlit UploadedFile or BytesIO
        file_bytes = file_source.read()
        if hasattr(file_source, "seek"):
            file_source.seek(0)
        reader = PdfReader(io.BytesIO(file_bytes))

    num_pages = len(reader.pages)
    
    # Extract text from key sections:
    # 1. Front matter & IFB (pages 1-25)
    header_text = ""
    for i in range(min(25, num_pages)):
        header_text += (reader.pages[i].extract_text() or "") + "\n"

    # 2. Section II-A / Step 2 Qualification (usually pages 65-90)
    qual_text = ""
    for i in range(min(num_pages, 65), min(num_pages, 95)):
        qual_text += (reader.pages[i].extract_text() or "") + "\n"

    all_scanned_text = header_text + "\n" + qual_text

    # Default fallback info
    result = {
        "project_name": "EDCF 해외 인프라 구축 사업",
        "client": "한국수출입은행 EDCF / 현지 주무관청",
        "country": "기타 (EDCF 협력국)",
        "loan_no": "EDCF Loan Agreement",
        "bid_no": "-",
        "bid_usd": 20_000_000,
        "exchange_rate": 1350.0,
        "duration": "36개월",
        "eval_period": "2022 ~ 2024년 (최근 3개년)",
        "min_turnover_usd": 20_000_000,
        "min_turnover_desc": "최소 연평균 매출액",
        "cashflow_usd": 5_000_000,
        "net_worth_req": "양수 (> 0, 자본잠식 배제)",
        "credit_rating": "회사채 BBB- 이상 또는 기업어음 A3- 이상",
        "min_curr_ratio": 100.0,
        "max_debt_ratio": 150.0,
        "consortium_rule": "주관사 지분 40~50% 이상, 참여사 최소 10~20% 이상",
        "parsed_success": True
    }

    # -------------------------------------------------------------
    # 1. Detect Country
    # -------------------------------------------------------------
    text_lower = all_scanned_text.lower()
    for key, (kor_name, eng_name) in COUNTRY_MAP.items():
        if key in text_lower:
            result["country"] = f"{kor_name} ({eng_name})"
            break

    # -------------------------------------------------------------
    # 2. Detect Project Title
    # -------------------------------------------------------------
    proj_match = re.search(r"Project\s*:\s*([^\n\r]+)", header_text, re.IGNORECASE)
    if not proj_match:
        proj_match = re.search(r"For the\s+Procurement of\s+([^\n\r]+(?:\n[^\n\r]+)?)", header_text, re.IGNORECASE)
    if not proj_match:
        proj_match = re.search(r"procurement of\s+([^\n\r\.\,]+(?:Project|Works|System)[^\n\r\.\,]*)", header_text, re.IGNORECASE)

    if proj_match:
        raw_proj = proj_match.group(1).replace("\n", " ").strip()
        raw_proj = re.sub(r"\s+", " ", raw_proj)
        # Korean mapping for Tanzania National ID
        if "National ID System Expansion Project" in raw_proj and "Tanzania" in raw_proj:
            result["project_name"] = "National ID System Expansion Project (Phase II) in Tanzania (탄자니아 국가 주민등록 시스템 확장사업 2차)"
        else:
            result["project_name"] = raw_proj

    # -------------------------------------------------------------
    # 3. Detect Loan No & Bid No
    # -------------------------------------------------------------
    loan_match = re.search(r"(?:Loan Agreement No|EDCF Loan Agreement No|Loan No)[\s:]*([A-Z0-9\-_]+)", header_text, re.IGNORECASE)
    if loan_match:
        result["loan_no"] = loan_match.group(1).strip()

    bid_match = re.search(r"Bid Number\s*:\s*([A-Z0-9\/\-_]+)", header_text, re.IGNORECASE)
    if bid_match:
        result["bid_no"] = bid_match.group(1).strip()

    # -------------------------------------------------------------
    # 4. Detect Executing Agency (Client)
    # -------------------------------------------------------------
    if "national identification authority" in text_lower or "nida" in text_lower:
        result["client"] = f"탄자니아 국가신분증청 (NIDA) / 한국수출입은행 EDCF (차관: {result['loan_no']})"
    elif "department of public works and highways" in text_lower or "dpwh" in text_lower:
        result["client"] = f"필리핀 공공사업도로부 (DPWH) / 한국수출입은행 EDCF (차관: {result['loan_no']})"
    else:
        # Generic agency search
        agency_match = re.search(r"(?:Executing Agency|Purchaser|Employer)[\s:]*([^\n\r]+)", header_text, re.IGNORECASE)
        if agency_match:
            result["client"] = f"{agency_match.group(1).strip()} / 한국수출입은행 EDCF"

    # -------------------------------------------------------------
    # 5. Detect Total Bid Budget / Loan Amount (USD)
    # -------------------------------------------------------------
    # Look for "amount of Seventy million US dollars (USD 70,000,000)" or similar
    amount_match = re.search(r"(?:amount of|loan of|sum of|cost of)\s+([^\(\n\r]+)\s*\(\s*(?:USD|US\$)\s*([0-9,]+)\s*\)", header_text, re.IGNORECASE)
    if amount_match:
        clean_num = int(amount_match.group(2).replace(",", ""))
        result["bid_usd"] = clean_num
    else:
        # Search for first large USD amount in IFB
        usd_matches = re.findall(r"(?:USD|US\$)\s*([0-9]{1,3}(?:,[0-9]{3}){2,})", header_text)
        if usd_matches:
            # take largest or first major amount
            amounts = [int(m.replace(",", "")) for m in usd_matches if int(m.replace(",", "")) >= 1_000_000]
            if amounts:
                result["bid_usd"] = amounts[0]

    # -------------------------------------------------------------
    # 6. Detect Evaluation Period (Years)
    # -------------------------------------------------------------
    years_match = re.search(r"(?:past|within the past|last)\s*(?:three|3)\s*\(3\)\s*years\s*\(([0-9,\s\-and]+)\)", all_scanned_text, re.IGNORECASE)
    if not years_match:
        years_match = re.search(r"3\s*[-–]\s*Year\s*\(([0-9]{4}\s*[-–]\s*[0-9]{4})\)", all_scanned_text, re.IGNORECASE)
    if not years_match:
        years_match = re.search(r"(20[2-3][0-9]\s*[-~,]\s*20[2-3][0-9])", all_scanned_text)

    if years_match:
        raw_years = years_match.group(1).strip()
        raw_years = raw_years.replace("and", ",").replace("  ", " ")
        if "2022" in raw_years and "2024" in raw_years:
            result["eval_period"] = "2022 ~ 2024년 (최근 3개년 결산)"
        else:
            result["eval_period"] = f"{raw_years} (최근 3개년 결산)"

    # -------------------------------------------------------------
    # 7. Detect Financial Criteria: Annual Turnover
    # -------------------------------------------------------------
    turnover_match = re.search(
        r"Minimum average annual turnover\s+shall not be less\s+(?:than\s+)?([^\(\n\r]+)\s*\(\s*([0-9,]+)\s*\)\s*million US Dollars",
        all_scanned_text,
        re.IGNORECASE
    )
    if turnover_match:
        t_mil = int(turnover_match.group(2).replace(",", ""))
        result["min_turnover_usd"] = t_mil * 1_000_000
        result["min_turnover_desc"] = f"최소 연평균 {t_mil}백만 달러 (USD {result['min_turnover_usd']:,}) 이상"
    else:
        # Fallback to total bid amount if turnover equals budget
        result["min_turnover_usd"] = result["bid_usd"]
        result["min_turnover_desc"] = f"입찰 예산의 100% (USD {result['bid_usd']:,}) 이상"

    # -------------------------------------------------------------
    # 8. Detect Cash Flow / Liquid Resources
    # -------------------------------------------------------------
    cashflow_match = re.search(
        r"cash\s*[-–]\s*flow requirement of\s+([^\(\n\r]+)\s*\(\s*([0-9,]+)\s*\)\s*(?:million\s+)?US\s*Dollars",
        all_scanned_text,
        re.IGNORECASE
    )
    if cashflow_match:
        c_num = int(cashflow_match.group(2).replace(",", ""))
        # Check if million is mentioned
        if c_num < 1000:
            result["cashflow_usd"] = c_num * 1_000_000
        else:
            result["cashflow_usd"] = c_num

    # -------------------------------------------------------------
    # 9. Detect Net Worth & Credit Rating
    # -------------------------------------------------------------
    if "average net worth" in text_lower and "positive" in text_lower:
        result["net_worth_req"] = "양수 (> 0, 자본잠식 배제)"
    
    if "credit rating" in text_lower and "bbb-" in text_lower:
        result["credit_rating"] = "회사채 BBB- 이상 / 기업어음 A3- 이상 (각 파트너 필수)"

    # Consortium rules for JVA
    if "all partners combined" in text_lower:
        result["consortium_rule"] = "JVA 전 파트너 합산 100%, 1개사 40% 이상, 각 참여사 최소 20% 충족"

    return result
