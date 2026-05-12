from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


INDEX_TICKERS = {
    "나스닥": "^IXIC",
    "S&P 500": "^GSPC",
    "다우존스": "^DJI",
}

VIX_TICKER = "^VIX"

SECTOR_ETFS = {
    "커뮤니케이션 서비스": "XLC",
    "임의소비재": "XLY",
    "필수소비재": "XLP",
    "에너지": "XLE",
    "금융": "XLF",
    "헬스케어": "XLV",
    "산업재": "XLI",
    "소재": "XLB",
    "부동산": "XLRE",
    "기술": "XLK",
    "유틸리티": "XLU",
}

CNN_FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
TELEGRAM_SEND_MESSAGE_URL = "https://api.telegram.org/bot{token}/sendMessage"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}
CNN_HEADERS = {
    "Referer": "https://edition.cnn.com/markets/fear-and-greed",
    "Origin": "https://edition.cnn.com",
}


@dataclass(frozen=True)
class MarketQuote:
    name: str
    ticker: str
    price: float
    change: float
    change_percent: float


@dataclass(frozen=True)
class FearGreedIndex:
    value: float | None
    rating: str
    updated_at: str | None = None
    error_message: str | None = None


def load_dotenv_file(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def request_json(
    url: str,
    *,
    params: dict[str, str] | None = None,
    method: str = "GET",
    headers: dict[str, str] | None = None,
) -> dict:
    encoded_body = None
    request_url = url

    if method == "GET" and params:
        request_url = f"{url}?{urlencode(params)}"
    elif params:
        encoded_body = json.dumps(params).encode("utf-8")

    request_headers = DEFAULT_HEADERS | {"Content-Type": "application/json"}
    if headers:
        request_headers |= headers

    request = Request(
        request_url,
        data=encoded_body,
        method=method,
        headers=request_headers,
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def get_env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"환경 변수 {name} 값을 설정해 주세요.")
    return value


def format_signed(value: float, digits: int = 2) -> str:
    return f"{value:+,.{digits}f}"


def fetch_quote(name: str, ticker: str) -> MarketQuote:
    url = YAHOO_CHART_URL.format(ticker=quote(ticker, safe=""))
    data = request_json(url, params={"range": "5d", "interval": "1d"})

    results = data.get("chart", {}).get("result") or []
    if not results:
        raise RuntimeError(f"{name}({ticker})의 가격 데이터를 가져오지 못했습니다.")

    closes = results[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
    valid_closes = [float(close) for close in closes if close is not None]
    if len(valid_closes) < 2:
        raise RuntimeError(f"{name}({ticker})의 가격 데이터를 충분히 가져오지 못했습니다.")

    latest_close = valid_closes[-1]
    previous_close = valid_closes[-2]
    change = latest_close - previous_close
    change_percent = change / previous_close * 100

    return MarketQuote(
        name=name,
        ticker=ticker,
        price=latest_close,
        change=change,
        change_percent=change_percent,
    )


def fetch_quotes(tickers: dict[str, str]) -> list[MarketQuote]:
    return [fetch_quote(name, ticker) for name, ticker in tickers.items()]


def fetch_fear_greed_index() -> FearGreedIndex:
    try:
        data = request_json(CNN_FEAR_GREED_URL, headers=CNN_HEADERS)
        current = data.get("fear_and_greed", {})

        value = current.get("score")
        rating = current.get("rating")
        updated_at = current.get("timestamp")

        if value is None or rating is None:
            raise RuntimeError("Fear & Greed 지수 응답 형식을 해석하지 못했습니다.")

        return FearGreedIndex(value=float(value), rating=str(rating), updated_at=format_timestamp(updated_at))
    except HTTPError as error:
        return FearGreedIndex(
            value=None,
            rating="N/A",
            error_message=f"CNN 요청 실패: HTTP {error.code}",
        )
    except (URLError, TimeoutError, RuntimeError, ValueError) as error:
        return FearGreedIndex(
            value=None,
            rating="N/A",
            error_message=f"CNN 요청 실패: {error}",
        )


def format_timestamp(timestamp: object) -> str | None:
    if timestamp is None:
        return None

    numeric_timestamp = float(timestamp)
    if numeric_timestamp > 10_000_000_000:
        numeric_timestamp /= 1000

    updated = datetime.fromtimestamp(numeric_timestamp, tz=ZoneInfo("America/New_York"))
    return updated.strftime("%Y-%m-%d %H:%M %Z")


def build_quote_line(quote: MarketQuote) -> str:
    return (
        f"• {quote.name}: {quote.price:,.2f} "
        f"({format_signed(quote.change)}, {format_signed(quote.change_percent)}%)"
    )


def build_sector_lines(sectors: list[MarketQuote]) -> tuple[list[str], list[str]]:
    sorted_sectors = sorted(sectors, key=lambda quote: quote.change_percent, reverse=True)
    top_gainers = sorted_sectors[:5]
    top_losers = sorted_sectors[-5:]

    gain_lines = [build_quote_line(quote) for quote in top_gainers]
    loss_lines = [build_quote_line(quote) for quote in reversed(top_losers)]
    return gain_lines, loss_lines


def build_message(
    indices: list[MarketQuote],
    vix: MarketQuote,
    fear_greed: FearGreedIndex,
    sectors: list[MarketQuote],
    timezone_name: str,
) -> str:
    now = datetime.now(ZoneInfo(timezone_name))
    gain_lines, loss_lines = build_sector_lines(sectors)

    if fear_greed.value is None:
        fear_greed_line = f"• Fear & Greed: 조회 실패 ({fear_greed.error_message or '알 수 없는 오류'})"
    else:
        fear_greed_updated = ""
        if fear_greed.updated_at:
            fear_greed_updated = f"\n• 업데이트: {fear_greed.updated_at}"
        fear_greed_line = f"• Fear & Greed: {fear_greed.value:.0f} ({fear_greed.rating}){fear_greed_updated}"

    return "\n".join(
        [
            f"🇺🇸 미국 증시 상태 알림 ({now.strftime('%Y-%m-%d %H:%M %Z')})",
            "",
            "📌 주요 지수",
            *[build_quote_line(quote) for quote in indices],
            "",
            "🌡 변동성/심리",
            build_quote_line(vix),
            fear_greed_line,
            "",
            "📈 섹터 상승 Top 5",
            *gain_lines,
            "",
            "📉 섹터 하락 Top 5",
            *loss_lines,
            "",
            "※ 가격 데이터는 Yahoo Finance, Fear & Greed는 CNN 공개 엔드포인트 기준입니다.",
        ]
    )


def send_telegram_message(token: str, chat_id: str, message: str) -> None:
    request_json(
        TELEGRAM_SEND_MESSAGE_URL.format(token=token),
        params={"chat_id": chat_id, "text": message, "disable_web_page_preview": True},
        method="POST",
    )


def main() -> None:
    load_dotenv_file()

    timezone_name = os.getenv("MARKET_TIMEZONE", "America/New_York")
    dry_run = get_env_bool("DRY_RUN")

    indices = fetch_quotes(INDEX_TICKERS)
    vix = fetch_quote("VIX", VIX_TICKER)
    fear_greed = fetch_fear_greed_index()
    sectors = fetch_quotes(SECTOR_ETFS)

    message = build_message(indices, vix, fear_greed, sectors, timezone_name)

    if dry_run:
        print(message)
        return

    token = get_required_env("TELEGRAM_BOT_TOKEN")
    chat_id = get_required_env("TELEGRAM_CHAT_ID")
    send_telegram_message(token, chat_id, message)


if __name__ == "__main__":
    main()
