import websocket
import json
# WebSocket URL
symbol = 'btcusdt'  # 你想要查询的标的，例如btcusdt
socket = f'wss://stream.binance.com:9443/ws/{symbol}@depth'
# 定义WebSocket回调函数
def on_message(ws, message):
    data = json.loads(message)
    print("买盘（Bids）：")
    for bid in data['bids'][:5]:  # 只显示前五档
        print(f"价格: {bid[0]}, 数量: {bid[1]}")
    print("\n卖盘（Asks）：")
    for ask in data['asks'][:5]:  # 只显示前五档
        print(f"价格: {ask[0]}, 数量: {ask[1]}")
    print("\n" + "=" * 30 + "\n")
def on_error(ws, error):
    print(f"Error: {error}")
def on_close(ws, close_status_code, close_msg):
    print("WebSocket closed")
def on_open(ws):
    print("WebSocket connected")
# 初始化WebSocket
ws = websocket.WebSocketApp(socket,
                            on_message=on_message,
                            on_error=on_error,
                            on_close=on_close)
ws.on_open = on_open
# 启动WebSocket
ws.run_forever()
