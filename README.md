# Stock Market Status

Python 기반 미국 증시 상태 텔레그램 알림 스크립트입니다. Windows 노트북의 **작업 스케줄러**에 등록해 하루에 한 번 실행하는 용도로 만들었습니다.

## 알림 내용

- 주요 지수: 나스닥, S&P 500, 다우존스
- VIX 지수
- CNN Fear & Greed 지수
- 미국 섹터 ETF 기준 상승 Top 5 / 하락 Top 5

섹터는 SPDR 섹터 ETF(`XLC`, `XLY`, `XLP`, `XLE`, `XLF`, `XLV`, `XLI`, `XLB`, `XLRE`, `XLK`, `XLU`)의 전일 종가 대비 등락률로 계산합니다.

## 설치

```powershell
cd C:\path\to\Stock_Market_Status
py -m venv .venv
.\.venv\Scripts\Activate.ps1
# 외부 패키지는 필요 없지만, 향후 의존성이 추가되어도 같은 절차를 유지할 수 있습니다.
pip install -r requirements.txt
copy .env.example .env
```

`.env` 파일을 열어 아래 값을 입력합니다.

```env
TELEGRAM_BOT_TOKEN=BotFather에서_받은_토큰
TELEGRAM_CHAT_ID=알림을_받을_채팅_ID
MARKET_TIMEZONE=America/New_York
DRY_RUN=false
```

## 텔레그램 설정

1. 텔레그램에서 `@BotFather`를 열고 `/newbot`으로 봇을 생성합니다.
2. 발급받은 토큰을 `.env`의 `TELEGRAM_BOT_TOKEN`에 넣습니다.
3. 봇에게 아무 메시지나 한 번 보냅니다.
4. `https://api.telegram.org/bot<토큰>/getUpdates`를 브라우저에서 열어 `chat.id` 값을 확인합니다.
5. 해당 값을 `.env`의 `TELEGRAM_CHAT_ID`에 넣습니다.

## 실행

텔레그램 전송 전 메시지만 확인하려면 `.env`에서 `DRY_RUN=true`로 바꾼 뒤 실행합니다.

```powershell
.\.venv\Scripts\python.exe stock_market_status.py
```

## Windows 작업 스케줄러 등록 예시

1. **작업 스케줄러** → **작업 만들기**를 엽니다.
2. **트리거** 탭에서 매일 원하는 시간을 지정합니다.
   - 미국 장 마감 이후 데이터를 받으려면 한국 시간 기준 다음 날 오전 시간대를 권장합니다.
3. **동작** 탭에서 아래처럼 입력합니다.
   - 프로그램/스크립트: `C:\path\to\Stock_Market_Status\.venv\Scripts\python.exe`
   - 인수 추가: `stock_market_status.py`
   - 시작 위치: `C:\path\to\Stock_Market_Status`
4. 저장 후 **실행**으로 테스트합니다.

## 데이터 출처

- 가격/등락률: Yahoo Finance Chart API
- Fear & Greed: CNN 공개 데이터 엔드포인트
- 텔레그램 전송: Telegram Bot API
