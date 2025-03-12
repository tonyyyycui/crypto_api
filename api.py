import re  # Import regex module
from flask import Flask, jsonify
from selenium import webdriver 
from selenium.webdriver.chrome.service import Service 
from selenium.webdriver.chrome.options import Options 
from selenium.webdriver.common.by import By
import threading
import time
from webdriver_manager.chrome import ChromeDriverManager 

app = Flask(__name__)
BITCOIN_PRICE = {"price": None}
PRICE_HISTORY = []

def scrape_bitcoin_price():
    options = Options()
    options.add_argument("--headless")  
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-images")  
    options.add_argument("--disable-extensions")  
    options.add_argument("--disable-infobars")  
    options.add_argument("--log-level=3")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    url = "https://www.coindesk.com/price/bitcoin"
    driver.get(url)
    PRICE_HISTORY.append(-1)

    while True:
        try:
            raw_price = driver.execute_script("""
                return document.querySelector("div[class*='text-4xl']")?.innerText;
            """)

            if raw_price:
                # ✅ Extract only the numerical part using regex
                match = re.search(r"([\d,]+\.\d+)", raw_price)
                if match:
                    price = float(match.group(1).replace(",", ""))  # Convert to float
                    BITCOIN_PRICE["price"] = price
                    prev_price = PRICE_HISTORY[-1] if PRICE_HISTORY else None
                    
                    if prev_price and price != prev_price:
                        print("Bitcoin Price:", price)
                        print("Price Change:", price - prev_price)
                        # Maintain price history (store last 100 values)
                        PRICE_HISTORY.append(price)
                        if len(PRICE_HISTORY) > 100:
                            PRICE_HISTORY.pop(0)

                    print("Updated Bitcoin Price:", BITCOIN_PRICE["price"])

        except Exception as e:
            print("Error scraping Bitcoin price:", e)

        time.sleep(0.5)  # Update every second

# Run the scraper in a background thread
threading.Thread(target=scrape_bitcoin_price, daemon=True).start()

def calculate_ema(prices, period):
    """Calculate Exponential Moving Average (EMA)."""
    if len(prices) < period:
        return None

    ema = prices[0]
    multiplier = 2 / (period + 1)

    for price in prices[1:]:
        ema = (price - ema) * multiplier + ema

    return ema

def calculate_rsi(prices, period=14):
    """Calculate Relative Strength Index (RSI)."""
    if len(prices) < period:
        return None

    gains, losses = [], []
    for i in range(1, period + 1):
        diff = prices[-i] - prices[-i - 1]
        if diff > 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))

    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0

    if avg_loss == 0:
        return 100  # RSI = 100 when no losses

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi

@app.route("/bitcoin_price", methods=["GET"])
def get_bitcoin_price():
    return jsonify(BITCOIN_PRICE)

@app.route("/trade_signal", methods=["GET"])
def get_trade_signal():
    if len(PRICE_HISTORY) < 30 or -1 in PRICE_HISTORY:
        return jsonify({"signal": "WAIT", "reason": "Not enough data"})

    short_ema = calculate_ema(PRICE_HISTORY[-20:], 10)  # 10-period EMA
    long_ema = calculate_ema(PRICE_HISTORY[-40:], 30)   # 30-period EMA
    rsi = calculate_rsi(PRICE_HISTORY)

    if short_ema and long_ema and rsi is not None:
        if short_ema > long_ema and rsi < 30:
            signal = "BUY"
        elif short_ema < long_ema and rsi > 70:
            signal = "SELL"
        else:
            signal = "HOLD"
    else:
        signal = "WAIT"

    # Print signal to terminal
    print(f"Trade Signal: {signal}")
    print(f"Short EMA: {short_ema}, Long EMA: {long_ema}, RSI: {rsi}")
    
    return jsonify({
        "signal": signal,
        "short_ema": short_ema,
        "long_ema": long_ema,
        "rsi": rsi
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
