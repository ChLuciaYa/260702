"""
글로벌 · 미국 ETF 주식 데이터 분석 웹앱
Streamlit Cloud 배포용
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# ────────────────────────────────────────────────────────────
# 기본 설정
# ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ETF 데이터 분석기",
    page_icon="📈",
    layout="wide",
)

# 자주 찾는 ETF 목록 (티커: 설명)
POPULAR_ETFS = {
    "SPY": "S&P 500 지수 추종 (미국 대형주 전체)",
    "QQQ": "나스닥 100 지수 추종 (미국 대형 기술주 중심)",
    "VOO": "S&P 500 지수 추종 (뱅가드, SPY보다 보수 저렴)",
    "VTI": "미국 전체 주식시장 추종",
    "DIA": "다우존스 30 산업평균지수 추종",
    "IWM": "러셀 2000 지수 추종 (미국 중소형주)",
    "VEA": "미국을 제외한 선진국 주식",
    "VWO": "신흥국(이머징마켓) 주식",
    "EFA": "선진국(유럽·호주·극동) 주식",
    "ACWI": "전 세계 선진국+신흥국 주식 전체",
    "VNQ": "미국 리츠(부동산) 지수",
    "GLD": "금(Gold) 현물 가격 추종",
    "TLT": "미국 장기 국채(20년 이상) 추종",
    "AGG": "미국 채권시장 전체 추종",
    "SCHD": "미국 고배당 성장주",
    "ARKK": "혁신 기술 성장주 (ARK 인베스트)",
    "XLK": "미국 기술 섹터",
    "XLF": "미국 금융 섹터",
    "XLE": "미국 에너지 섹터",
    "EWY": "한국 주식시장(MSCI Korea) 추종",
}

TERM_EXPLANATIONS = {
    "ETF": "**ETF(상장지수펀드)** 는 여러 종목을 한 바구니에 담아 주식처럼 거래소에서 사고팔 수 있게 만든 펀드예요. 예를 들어 SPY 하나만 사도 미국 대표 기업 500개에 나눠 투자하는 효과가 있어요.",
    "종가": "**종가(Close)** 는 하루 거래가 끝났을 때의 마지막 가격이에요. 보통 주가 분석에서 가장 기본이 되는 값이에요.",
    "수정종가": "**수정종가(Adjusted Close)** 는 배당금 지급이나 액면분할 같은 이벤트를 반영해서 보정한 가격이에요. 장기 수익률을 비교할 때는 이 값을 쓰는 게 더 정확해요.",
    "이동평균선": "**이동평균선(Moving Average, MA)** 은 최근 N일간의 가격을 평균낸 선이에요. 예를 들어 20일 이동평균선은 최근 20일 종가의 평균을 매일 다시 계산해서 이은 선으로, 가격의 큰 흐름(추세)을 부드럽게 보여줘요.",
    "골든크로스": "**골든크로스**는 단기 이동평균선이 장기 이동평균선을 아래에서 위로 뚫고 올라가는 현상이에요. 보통 상승 추세 전환의 신호로 해석돼요.",
    "데드크로스": "**데드크로스**는 골든크로스의 반대로, 단기 이동평균선이 장기 이동평균선을 위에서 아래로 뚫고 내려가는 현상이에요. 하락 추세 전환의 신호로 해석돼요.",
    "거래량": "**거래량(Volume)** 은 하루 동안 사고팔린 주식(또는 ETF)의 수량이에요. 거래량이 갑자기 늘어나면 그날 시장의 관심이 커졌다는 뜻으로 해석할 수 있어요.",
    "캔들차트": "**캔들차트(Candlestick Chart)** 는 하루의 시가(시작 가격)·고가(가장 높았던 가격)·저가(가장 낮았던 가격)·종가(마감 가격)를 하나의 막대(캔들)로 보여주는 차트예요. 빨간색(또는 초록색)은 상승, 반대색은 하락을 의미해요(색상 기준은 국가마다 달라요).",
    "일간수익률": "**일간수익률(Daily Return)** 은 전날 대비 오늘 가격이 몇 % 변했는지를 나타내요. (오늘 종가 - 어제 종가) ÷ 어제 종가 × 100 으로 계산해요.",
    "누적수익률": "**누적수익률(Cumulative Return)** 은 투자 시작일부터 지금까지 총 몇 % 수익이 났는지를 보여줘요. 여러 ETF의 장기 성과를 비교할 때 유용해요.",
    "변동성": "**변동성(Volatility)** 은 가격이 얼마나 크게 오르내리는지를 나타내는 지표예요. 보통 일간수익률의 표준편차로 계산하고, 값이 클수록 가격 변동이 심하다(위험이 크다)는 뜻이에요.",
    "샤프비율": "**샤프비율(Sharpe Ratio)** 은 위험(변동성) 대비 수익이 얼마나 좋았는지를 보여주는 지표예요. 값이 높을수록 '위험 대비 수익률'이 좋았다는 뜻이에요. 단순 계산이라 무위험수익률은 0%로 가정했어요.",
    "MDD": "**MDD(최대낙폭, Maximum Drawdown)** 는 특정 기간 중 고점에서 저점까지 최대로 얼마나 하락했는지를 %로 보여줘요. 이 값이 클수록 과거에 큰 손실 구간이 있었다는 뜻이라 심리적으로 견디기 힘들 수 있어요.",
    "배당수익률": "**배당수익률(Dividend Yield)** 은 현재 주가 대비 연간 배당금이 몇 %인지를 나타내요. 예를 들어 배당수익률이 3%면, 100만원 투자 시 연 3만원 정도의 배당을 받는다는 의미예요(세전 기준, 변동 가능).",
    "RSI": "**RSI(상대강도지수)** 는 최근 가격이 얼마나 많이 오르고 내렸는지를 0~100 사이 숫자로 나타내는 지표예요. 보통 70 이상이면 '과매수'(너무 많이 올랐다), 30 이하면 '과매도'(너무 많이 내렸다)로 해석해요.",
    "볼린저밴드": "**볼린저밴드**는 이동평균선을 중심으로 위아래에 변동성만큼 폭을 넓힌 밴드예요. 가격이 밴드 상단에 가까우면 '단기적으로 비싸다', 하단에 가까우면 '단기적으로 싸다'는 참고 신호로 쓰여요.",
}


@st.cache_data(ttl=3600, show_spinner=False)
def load_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    """yfinance로 OHLCV 데이터를 불러오고 캐시합니다."""
    df = yf.download(ticker, start=start, end=end, auto_adjust=False, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(how="all")
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def load_info(ticker: str) -> dict:
    """yfinance로 ETF/종목 기본 정보를 불러옵니다."""
    try:
        return yf.Ticker(ticker).info
    except Exception:
        return {}


def add_indicators(df: pd.DataFrame, ma_windows: list) -> pd.DataFrame:
    """이동평균선, 일간/누적 수익률, RSI, 볼린저밴드를 계산해 컬럼으로 추가합니다."""
    df = df.copy()
    for w in ma_windows:
        df[f"MA{w}"] = df["Close"].rolling(window=w).mean()

    df["Daily_Return"] = df["Close"].pct_change() * 100
    df["Cumulative_Return"] = (df["Close"] / df["Close"].iloc[0] - 1) * 100

    # RSI (14일)
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))

    # 볼린저 밴드 (20일, ±2 표준편차)
    df["BB_Mid"] = df["Close"].rolling(window=20).mean()
    std20 = df["Close"].rolling(window=20).std()
    df["BB_Upper"] = df["BB_Mid"] + 2 * std20
    df["BB_Lower"] = df["BB_Mid"] - 2 * std20

    return df


def compute_summary(df: pd.DataFrame) -> dict:
    """요약 통계(변동성, 샤프비율, MDD 등)를 계산합니다."""
    returns = df["Close"].pct_change().dropna()
    total_return = (df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100
    ann_volatility = returns.std() * np.sqrt(252) * 100
    ann_return = returns.mean() * 252 * 100
    sharpe = (ann_return / ann_volatility) if ann_volatility != 0 else np.nan

    cum = (1 + returns).cumprod()
    running_max = cum.cummax()
    drawdown = (cum - running_max) / running_max
    mdd = drawdown.min() * 100

    return {
        "총 수익률(%)": total_return,
        "연환산 변동성(%)": ann_volatility,
        "샤프비율": sharpe,
        "최대낙폭 MDD(%)": mdd,
        "최고가": df["High"].max(),
        "최저가": df["Low"].min(),
        "평균 거래량": df["Volume"].mean(),
    }


# ────────────────────────────────────────────────────────────
# 사이드바 UI
# ────────────────────────────────────────────────────────────
st.sidebar.title("📊 설정")

input_mode = st.sidebar.radio("티커 선택 방식", ["인기 ETF 목록", "직접 입력"])

if input_mode == "인기 ETF 목록":
    ticker = st.sidebar.selectbox(
        "ETF 선택",
        options=list(POPULAR_ETFS.keys()),
        format_func=lambda t: f"{t} — {POPULAR_ETFS[t]}",
    )
else:
    ticker = st.sidebar.text_input("티커 직접 입력 (예: SPY, 005930.KS)", value="SPY").strip().upper()

compare_tickers = st.sidebar.text_input(
    "비교할 ETF 추가 입력 (쉼표로 구분, 선택)", placeholder="예: QQQ, VOO"
)

today = datetime.today()
default_start = today - timedelta(days=365 * 3)

col1, col2 = st.sidebar.columns(2)
with col1:
    start_date = st.date_input("시작일", value=default_start)
with col2:
    end_date = st.date_input("종료일", value=today)

st.sidebar.markdown("---")
st.sidebar.subheader("차트 옵션")
ma_options = st.sidebar.multiselect(
    "이동평균선(일)", options=[5, 20, 60, 120, 200], default=[20, 60]
)
show_bollinger = st.sidebar.checkbox("볼린저밴드 표시", value=False)
show_rsi = st.sidebar.checkbox("RSI 표시", value=True)
chart_type = st.sidebar.radio("가격 차트 종류", ["캔들차트", "선 그래프"])

st.sidebar.markdown("---")
st.sidebar.caption("데이터 출처: Yahoo Finance (yfinance) · 실시간 시세와 다를 수 있으며 투자 참고용입니다.")

# ────────────────────────────────────────────────────────────
# 메인 화면
# ────────────────────────────────────────────────────────────
st.title("📈 글로벌·미국 ETF 데이터 분석기")
st.caption("yfinance로 데이터를 불러오고 Plotly로 인터랙티브하게 시각화합니다.")

if not ticker:
    st.warning("사이드바에서 티커를 입력하거나 선택해주세요.")
    st.stop()

with st.spinner(f"{ticker} 데이터를 불러오는 중..."):
    raw_df = load_data(ticker, str(start_date), str(end_date))
    info = load_info(ticker)

if raw_df.empty:
    st.error(f"'{ticker}' 데이터를 찾을 수 없습니다. 티커를 다시 확인해주세요.")
    st.stop()

df = add_indicators(raw_df, ma_options)

# ── 기본 정보 카드 ──────────────────────────────────────────
name = info.get("longName") or info.get("shortName") or ticker
st.subheader(f"{name} ({ticker})")

last_close = df["Close"].iloc[-1]
prev_close = df["Close"].iloc[-2] if len(df) > 1 else last_close
change = last_close - prev_close
change_pct = (change / prev_close * 100) if prev_close else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric("최근 종가", f"${last_close:,.2f}", f"{change:+.2f} ({change_pct:+.2f}%)")
summary = compute_summary(df)
m2.metric("총 수익률", f"{summary['총 수익률(%)']:.2f}%")
m3.metric("연환산 변동성", f"{summary['연환산 변동성(%)']:.2f}%")
m4.metric("최대낙폭(MDD)", f"{summary['최대낙폭 MDD(%)']:.2f}%")

dy = info.get("dividendYield")
er = info.get("expenseRatio") or info.get("annualReportExpenseRatio")
aum = info.get("totalAssets")

info_cols = st.columns(3)
info_cols[0].write(f"**배당수익률**: {f'{dy*100:.2f}%' if isinstance(dy, (int, float)) else '정보 없음'}")
info_cols[1].write(f"**운용보수(Expense Ratio)**: {f'{er*100:.2f}%' if isinstance(er, (int, float)) else '정보 없음'}")
info_cols[2].write(f"**순자산(AUM)**: {f'${aum:,.0f}' if isinstance(aum, (int, float)) else '정보 없음'}")

st.markdown("---")

# ── 가격 차트 ────────────────────────────────────────────────
st.subheader("가격 차트")

row_heights = [0.55, 0.2]
specs = [[{"secondary_y": False}], [{"secondary_y": False}]]
if show_rsi:
    row_heights.append(0.25)
    specs.append([{"secondary_y": False}])

fig = make_subplots(
    rows=len(row_heights), cols=1, shared_xaxes=True,
    vertical_spacing=0.04, row_heights=row_heights,
    specs=specs,
    subplot_titles=["가격"] + (["거래량"]) + (["RSI"] if show_rsi else []),
)

if chart_type == "캔들차트":
    fig.add_trace(
        go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name=ticker,
        ),
        row=1, col=1,
    )
else:
    fig.add_trace(
        go.Scatter(x=df.index, y=df["Close"], mode="lines", name=f"{ticker} 종가"),
        row=1, col=1,
    )

for w in ma_options:
    fig.add_trace(
        go.Scatter(x=df.index, y=df[f"MA{w}"], mode="lines", name=f"MA{w}", line=dict(width=1.3)),
        row=1, col=1,
    )

if show_bollinger:
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_Upper"], line=dict(width=1, dash="dot"), name="볼린저 상단"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_Lower"], line=dict(width=1, dash="dot"), name="볼린저 하단",
                              fill="tonexty", fillcolor="rgba(100,149,237,0.1)"), row=1, col=1)

fig.add_trace(
    go.Bar(x=df.index, y=df["Volume"], name="거래량", marker_color="rgba(120,120,220,0.5)"),
    row=2, col=1,
)

if show_rsi:
    fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], mode="lines", name="RSI", line=dict(color="orange")), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

fig.update_layout(
    height=750, hovermode="x unified",
    xaxis_rangeslider_visible=False,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=10, r=10, t=40, b=10),
)

st.plotly_chart(fig, use_container_width=True)

# ── 수익률 비교 차트 ─────────────────────────────────────────
st.subheader("누적수익률 비교")

compare_list = [t.strip().upper() for t in compare_tickers.split(",") if t.strip()]
all_tickers = [ticker] + [t for t in compare_list if t != ticker]

return_fig = go.Figure()
comparison_summary_rows = []

for t in all_tickers:
    try:
        d = load_data(t, str(start_date), str(end_date)) if t != ticker else raw_df
        if d.empty:
            st.warning(f"'{t}' 데이터를 찾을 수 없어 비교에서 제외했습니다.")
            continue
        cum_ret = (d["Close"] / d["Close"].iloc[0] - 1) * 100
        return_fig.add_trace(go.Scatter(x=d.index, y=cum_ret, mode="lines", name=t))
        s = compute_summary(d)
        comparison_summary_rows.append({"티커": t, **s})
    except Exception as e:
        st.warning(f"'{t}' 처리 중 오류: {e}")

return_fig.update_layout(
    height=420, hovermode="x unified",
    yaxis_title="누적수익률 (%)",
    margin=dict(l=10, r=10, t=30, b=10),
)
st.plotly_chart(return_fig, use_container_width=True)

if comparison_summary_rows:
    comp_df = pd.DataFrame(comparison_summary_rows).set_index("티커")
    st.dataframe(comp_df.style.format("{:.2f}"), use_container_width=True)

st.markdown("---")

# ── 데이터 테이블 & 복붙용 다운로드 ──────────────────────────
st.subheader("원본 데이터 (복사/다운로드 가능)")

show_n = st.slider("표시할 최근 데이터 개수", min_value=10, max_value=min(500, len(df)), value=min(60, len(df)))
display_df = df.tail(show_n).sort_index(ascending=False)
st.dataframe(display_df, use_container_width=True)

csv = df.to_csv().encode("utf-8-sig")
st.download_button(
    label="📥 전체 데이터 CSV로 다운로드",
    data=csv,
    file_name=f"{ticker}_data.csv",
    mime="text/csv",
)

st.markdown("---")

# ── 용어 설명 ────────────────────────────────────────────────
st.subheader("📚 주식/ETF 용어 쉽게 알아보기")
st.caption("차트나 표에 나온 용어가 헷갈린다면 아래에서 찾아보세요.")

term_cols = st.columns(2)
term_keys = list(TERM_EXPLANATIONS.keys())
half = len(term_keys) // 2 + len(term_keys) % 2

with term_cols[0]:
    for k in term_keys[:half]:
        with st.expander(k):
            st.write(TERM_EXPLANATIONS[k])

with term_cols[1]:
    for k in term_keys[half:]:
        with st.expander(k):
            st.write(TERM_EXPLANATIONS[k])

st.markdown("---")
st.caption(
    "⚠️ 본 웹앱은 정보 제공 및 학습 목적이며 투자 권유가 아닙니다. "
    "투자 결정은 본인의 판단과 책임 하에 이루어져야 합니다."
)
