import yfinance as yf

symbols = ["AAPL", "MSFT", "AMZN"]  
for symbol in symbols:
    data = yf.download(symbol, period="1mo", interval="1d")
    data.to_csv(f"data_{symbol}.csv")
    print("Dataset saved: data_{}.csv".format(symbol))
