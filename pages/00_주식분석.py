"""
글로벌·한국 주식 데이터 분석 웹앱
- 데이터: yfinance
- 시각화: plotly (인터랙티브)
- 배포: Streamlit Community Cloud
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# =========================================================
# 기본 설정
# =========================================================
st.set_page_config(
    page_title="주식 데이터 분석 대시보드",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================================================
# 자주 찾는 종목 (티커 입력을 쉽게 하기 위한 예시 목록)
# 한국 주식은 '.KS'(코스피) 또는 '.KQ'(코스닥)을 붙여야 합니다.
# =========================================================
POPULAR_TICKERS = {
    "🇰🇷 한국": {
        "삼성전자": "005930.KS",
        "SK하이닉스": "000660.KS",
        "NAVER": "035420.KS",
        "카카오": "035720.KS",
        "현대차": "005380.KS",
        "LG에너지솔루션": "373220.KS",
        "셀트리온": "068270.KS",
        "카카오뱅크": "323410.KS",
        "에코프로": "086520.KQ",
        "포스코퓨처엠": "003670.KS",
    },
    "🇺🇸 미국": {
        "Apple": "AAPL",
        "Microsoft": "MSFT",
        "NVIDIA": "NVDA",
        "Amazon": "AMZN",
        "Alphabet(Google)": "GOOGL",
        "Tesla": "TSLA",
        "Meta": "META",
        "Berkshire Hathaway": "BRK-B",
        "S&P500 ETF": "SPY",
        "나스닥100 ETF": "QQQ",
    },
    "🌏 기타 글로벌": {
        "TSMC(대만)": "TSM",
        "Toyota(일본)": "7203.T",
        "Alibaba(중국)": "BABA",
        "ASML(네덜란드)": "ASML",
        "Samsung(ADR X, 참고용 SK하이닉스)": "000660.KS",
    },
}

# =========================================================
# 사이드바 - 사용자 입력
# =========================================================
st.sidebar.title("🔍 종목 검색")

market = st.sidebar.selectbox("시장 선택", list(POPULAR_TICKERS.keys()))
stock_name = st.sidebar.selectbox("인기 종목에서 선택", list(POPULAR_TICKERS[market].keys()))
default_ticker = POPULAR_TICKERS[market][stock_name]

st.sidebar.markdown("— 또는 —")
custom_ticker = st.sidebar.text_input(
    "티커 직접 입력 (선택사항)",
    value="",
    placeholder="예: AAPL, 005930.KS",
    help="한국 주식은 코스피 종목 끝에 '.KS', 코스닥 종목은 '.KQ'를 붙여야 합니다. (예: 삼성전자 → 005930.KS)",
)
ticker = custom_ticker.strip() if custom_ticker.strip() else default_ticker

st.sidebar.markdown("---")
st.sidebar.subheader("📅 기간 설정")

period_option = st.sidebar.selectbox(
    "조회 기간",
    ["1개월", "3개월", "6개월", "1년", "2년", "5년", "직접 설정"],
    index=3,
)

period_map = {
    "1개월": 30, "3개월": 90, "6개월": 180,
    "1년": 365, "2년": 365 * 2, "5년": 365 * 5,
}

if period_option == "직접 설정":
    col1, col2 = st.sidebar.columns(2)
    start_date = col1.date_input("시작일", datetime.now() - timedelta(days=365))
    end_date = col2.date_input("종료일", datetime.now())
else:
    end_date = datetime.now()
    start_date = end_date - timedelta(days=period_map[period_option])

st.sidebar.markdown("---")
st.sidebar.subheader("📊 보조지표")
show_ma = st.sidebar.checkbox("이동평균선 (MA)", value=True)
ma_periods = st.sidebar.multiselect(
    "이동평균 기간(일)", [5, 20, 60, 120, 200], default=[20, 60]
) if show_ma else []
show_bollinger = st.sidebar.checkbox("볼린저 밴드", value=False)
show_rsi = st.sidebar.checkbox("RSI (상대강도지수)", value=True)
show_macd = st.sidebar.checkbox("MACD", value=False)
show_volume = st.sidebar.checkbox("거래량", value=True)

st.sidebar.markdown("---")
st.sidebar.caption("데이터 출처: Yahoo Finance (yfinance)")

# =========================================================
# 데이터 로드 함수 (캐시 적용 → 반복 요청 시 속도 향상)
# =========================================================
@st.cache_data(ttl=3600, show_spinner=False)
def load_data(ticker_symbol, start, end):
    data = yf.download(ticker_symbol, start=start, end=end, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

@st.cache_data(ttl=3600, show_spinner=False)
def load_info(ticker_symbol):
    try:
        return yf.Ticker(ticker_symbol).info
    except Exception:
        return {}

# =========================================================
# 보조지표 계산 함수
# =========================================================
def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calc_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calc_bollinger(series, period=20, num_std=2):
    ma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = ma + num_std * std
    lower = ma - num_std * std
    return upper, ma, lower

# =========================================================
# 메인 화면
# =========================================================
st.title("📈 글로벌 · 한국 주식 데이터 분석 대시보드")
st.caption("yfinance로 데이터를 불러오고 plotly로 인터랙티브 차트를 그립니다. 차트는 마우스로 확대/축소/이동이 가능해요.")

with st.spinner(f"'{ticker}' 데이터를 불러오는 중입니다..."):
    df = load_data(ticker, start_date, end_date)
    info = load_info(ticker)

if df.empty:
    st.error(
        f"'{ticker}' 데이터를 찾을 수 없습니다. 티커를 다시 확인해주세요. "
        "(한국 종목은 숫자코드+.KS 또는 .KQ, 미국 종목은 알파벳 코드를 입력해야 합니다.)"
    )
    st.stop()

# ---------------------------------------------------------
# 상단 요약 정보 (현재가, 등락률 등)
# ---------------------------------------------------------
company_name = info.get("longName") or info.get("shortName") or ticker
currency = info.get("currency", "")

last_close = float(df["Close"].iloc[-1])
prev_close = float(df["Close"].iloc[-2]) if len(df) > 1 else last_close
change = last_close - prev_close
change_pct = (change / prev_close * 100) if prev_close != 0 else 0

st.subheader(f"{company_name} ({ticker})")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric(
    "현재가(최근 종가)",
    f"{last_close:,.2f} {currency}",
    f"{change:+,.2f} ({change_pct:+.2f}%)",
)
col2.metric("기간 내 최고가", f"{df['High'].max():,.2f}")
col3.metric("기간 내 최저가", f"{df['Low'].min():,.2f}")
col4.metric("평균 거래량", f"{df['Volume'].mean():,.0f}")
if info.get("marketCap"):
    col5.metric("시가총액", f"{info['marketCap']/1e8:,.0f}억")
else:
    col5.metric("시가총액", "정보 없음")

st.markdown("---")

# ---------------------------------------------------------
# 캔들스틱 차트 + 이동평균선 + 볼린저밴드 + 거래량
# ---------------------------------------------------------
rows = 1
row_heights = [0.6]
specs_titles = ["가격 (캔들스틱)"]

if show_volume:
    rows += 1
    row_heights.append(0.15)
    specs_titles.append("거래량")
if show_rsi:
    rows += 1
    row_heights.append(0.15)
    specs_titles.append("RSI")
if show_macd:
    rows += 1
    row_heights.append(0.15)
    specs_titles.append("MACD")

# 비율 정규화
row_heights = [h / sum(row_heights) for h in row_heights]

fig = make_subplots(
    rows=rows, cols=1, shared_xaxes=True,
    vertical_spacing=0.03, row_heights=row_heights,
    subplot_titles=specs_titles,
)

# 캔들스틱
fig.add_trace(
    go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        name="가격",
        increasing_line_color="#e74c3c",  # 한국식: 상승=빨강
        decreasing_line_color="#3498db",  # 하락=파랑
    ),
    row=1, col=1,
)

# 이동평균선
ma_colors = ["#f39c12", "#9b59b6", "#2ecc71", "#1abc9c", "#34495e"]
for i, p in enumerate(ma_periods):
    ma_series = df["Close"].rolling(window=p).mean()
    fig.add_trace(
        go.Scatter(x=df.index, y=ma_series, name=f"MA{p}",
                   line=dict(width=1.3, color=ma_colors[i % len(ma_colors)])),
        row=1, col=1,
    )

# 볼린저 밴드
if show_bollinger:
    upper, mid, lower = calc_bollinger(df["Close"])
    fig.add_trace(go.Scatter(x=df.index, y=upper, name="볼린저 상단",
                              line=dict(width=1, dash="dot", color="gray")), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=lower, name="볼린저 하단",
                              line=dict(width=1, dash="dot", color="gray"),
                              fill="tonexty", fillcolor="rgba(150,150,150,0.1)"), row=1, col=1)

current_row = 1

# 거래량
if show_volume:
    current_row += 1
    colors = ["#e74c3c" if c >= o else "#3498db" for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(
        go.Bar(x=df.index, y=df["Volume"], name="거래량", marker_color=colors),
        row=current_row, col=1,
    )

# RSI
if show_rsi:
    current_row += 1
    rsi = calc_rsi(df["Close"])
    fig.add_trace(go.Scatter(x=df.index, y=rsi, name="RSI(14)", line=dict(color="#8e44ad")),
                  row=current_row, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=current_row, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=current_row, col=1)

# MACD
if show_macd:
    current_row += 1
    macd_line, signal_line, hist = calc_macd(df["Close"])
    fig.add_trace(go.Scatter(x=df.index, y=macd_line, name="MACD", line=dict(color="#2980b9")),
                  row=current_row, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=signal_line, name="Signal", line=dict(color="#e67e22")),
                  row=current_row, col=1)
    hist_colors = ["#e74c3c" if v >= 0 else "#3498db" for v in hist]
    fig.add_trace(go.Bar(x=df.index, y=hist, name="MACD 히스토그램", marker_color=hist_colors),
                  row=current_row, col=1)

fig.update_layout(
    height=250 * rows + 200,
    xaxis_rangeslider_visible=False,
    hovermode="x unified",
    template="plotly_white",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=10, r=10, t=60, b=10),
)

st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------
# 원본 데이터 테이블 + 다운로드
# ---------------------------------------------------------
with st.expander("📋 원본 데이터 보기 / 다운로드"):
    st.dataframe(df.sort_index(ascending=False), use_container_width=True)
    csv = df.to_csv().encode("utf-8-sig")
    st.download_button("CSV 다운로드", csv, file_name=f"{ticker}_data.csv", mime="text/csv")

# =========================================================
# 주식 용어 설명 (초보자를 위한 친절한 가이드)
# =========================================================
st.markdown("---")
st.header("📚 주식 용어, 쉽게 알아보기")
st.caption("차트에 나오는 용어들이 낯설다면 아래 설명을 펼쳐서 읽어보세요!")

terms = {
    "🕯️ 캔들스틱(봉차트)이 뭔가요?": """
하루(혹은 정해진 기간) 동안의 주가 움직임을 막대 모양으로 표현한 차트예요.

- **몸통(굵은 부분)**: 시가(시작 가격)와 종가(마감 가격)의 차이를 보여줘요.
- **위/아래 꼬리(얇은 선)**: 그 기간 동안의 최고가와 최저가를 보여줘요.
- 이 앱에서는 한국 스타일로 **오를 땐 빨간색, 내릴 땐 파란색**으로 표시했어요.
  (미국에서는 반대로 초록/빨강을 쓰는 경우가 많으니 헷갈리지 마세요!)
""",
    "📏 이동평균선(MA)이 뭔가요?": """
최근 N일 동안의 종가를 평균 낸 값을 선으로 이어 그린 거예요. 주가의 '큰 흐름(추세)'을 부드럽게 보여줘요.

- **MA5, MA20**: 짧은 기간 평균 → 단기 흐름 (변동에 민감)
- **MA60, MA120, MA200**: 긴 기간 평균 → 장기 흐름 (변동에 둔감, 안정적)
- 흔히 **단기선이 장기선을 위로 뚫고 올라가면 '골든크로스'(상승 신호로 해석)**,
  **아래로 뚫고 내려가면 '데드크로스'(하락 신호로 해석)**라고 불러요.
  (단, 100% 맞는 신호는 아니고 참고 지표예요!)
""",
    "🎈 볼린저 밴드가 뭔가요?": """
이동평균선을 중심으로 위아래에 '표준편차'만큼 띠(밴드)를 그린 거예요.

- 주가가 **밴드 상단에 가까울수록** 통계적으로 '많이 올랐다(과열 가능성)'고 해석하고,
- **밴드 하단에 가까울수록** '많이 내렸다(저평가 가능성)'고 해석해요.
- 밴드의 폭이 좁아지면 변동성이 작다는 뜻이고, 넓어지면 변동성이 크다는 뜻이에요.
""",
    "💪 RSI(상대강도지수)가 뭔가요?": """
최근 상승폭과 하락폭을 비교해서 **'매수세 vs 매도세'가 얼마나 강한지**를 0~100 사이 숫자로 나타낸 지표예요.

- **70 이상**: 너무 많이 올랐다 → '과매수' 구간 (조정 가능성 참고)
- **30 이하**: 너무 많이 내렸다 → '과매도' 구간 (반등 가능성 참고)
- 그 사이(30~70)는 특별한 신호 없이 중립 구간으로 봐요.
""",
    "📉 MACD가 뭔가요?": """
서로 다른 두 이동평균선(단기 12일, 장기 26일)의 차이를 이용한 추세 지표예요.

- **MACD선**: 단기평균 - 장기평균
- **시그널선**: MACD선을 다시 9일 평균 낸 값
- **MACD선이 시그널선을 위로 돌파**하면 상승 추세 시작으로,
  **아래로 돌파**하면 하락 추세 시작으로 해석하는 경우가 많아요.
- 막대(히스토그램)는 두 선의 차이를 보여줘서, 추세의 '힘'을 시각적으로 표현해요.
""",
    "📊 거래량은 왜 중요한가요?": """
그 기간 동안 실제로 사고 판 주식의 수량이에요.

- 주가가 오르는데 **거래량도 함께 늘면** → 많은 사람이 동의하는 '진짜' 상승일 가능성이 높아요.
- 주가는 오르는데 **거래량이 적으면** → 소수의 힘으로 오른 것이라 '가짜' 상승(속임수)일 수도 있어요.
- 즉, 거래량은 가격 움직임의 '신뢰도'를 판단하는 데 도움을 줘요.
""",
    "💰 시가총액이 뭔가요?": """
**주가 × 총 발행 주식 수**로 계산되는, '이 회사 전체의 시장 가치'예요.

- 시가총액이 클수록 (삼성전자, 애플처럼) '대형주'라고 부르고, 상대적으로 안정적인 경향이 있어요.
- 시가총액이 작으면 '소형주'라고 부르고, 성장 가능성도 크지만 변동성도 큰 편이에요.
""",
    "🇰🇷 코스피(KOSPI)와 코스닥(KOSDAQ)의 차이는?": """
- **코스피(KOSPI)**: 한국의 대표 증권시장. 삼성전자, SK하이닉스 같은 대기업 위주. 티커 뒤에 **'.KS'**를 붙여요.
- **코스닥(KOSDAQ)**: 중소·벤처기업, 기술주 위주의 시장 (미국의 나스닥과 비슷한 성격). 티커 뒤에 **'.KQ'**를 붙여요.
- 예: 삼성전자 → `005930.KS`,  에코프로 → `086520.KQ`
""",
}

for title, content in terms.items():
    with st.expander(title):
        st.markdown(content)

st.markdown("---")
st.caption(
    "⚠️ 본 앱은 정보 제공 및 학습 목적으로 제작되었으며, 투자 조언이 아닙니다. "
    "투자 판단과 책임은 본인에게 있습니다."
)
