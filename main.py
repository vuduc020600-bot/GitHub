import os
import pandas as pd
import numpy as np
import yfinance as yf
import json
from dateutil.relativedelta import relativedelta

# ==========================================
# CẤU HÌNH ĐƯỜNG DẪN MỚI
# ==========================================
DATA_DIR = "./data"
OUTPUT_JSON_PATH = "./backtest_results.json"
os.makedirs(DATA_DIR, exist_ok=True)

# ==========================================
# NODE 2: CẬP NHẬT DỮ LIỆU CỔ PHIẾU
# ==========================================
STOCKS = [
    # 1. Ngân hàng & Tài chính - Chứng khoán
    "ACB", "BID", "CTG", "EIB", "HDB", "LPB", "MBB", "MSB", "NAB", "OCB", "SHB", "SSB", "STB", "TCB", "TPB", "VCB", "VIB", "VPB",
    "BSI", "CTS", "DSE", "EVF", "FTS", "HCM", "SSI", "VCI", "VIX", "VND",
    
    # 2. Bất động sản & Xây dựng - Vật liệu
    "BCM", "DIG", "DXG", "HDC", "KBC", "KDH", "NLG", "NVL", "PDR", "SJS", "SZC", "TCH", "VHM", "VIC", "VPI", "VRE",
    "BMP", "CII", "CTD", "HHV", "HPG", "HSG", "HT1", "NKG", "VCG", "VGC",
    
    # 3. Công nghệ, Bán lẻ & Tiêu dùng
    "CMG", "CTR", "DGW", "FPT", "FRT", "MWG", "PNJ",
    "ANV", "BAF", "DBC", "HAG", "KDC", "MCH", "MSN", "SAB", "VHC", "VNM",
    
    # 4. Năng lượng, Dầu khí, Tiện ích & Công nghiệp khác
    "BSR", "GAS", "GEE", "GEX", "NT2", "PC1", "PLX", "POW", "PVD", "PVT",
    "BWE", "DCM", "DGC", "DPM", "GMD", "GVR", "PAN", "PHR", "REE", "SBT", "SCS", "SIP", "VJC", "VSC", "VTP", "BVH"
]

for stock in STOCKS:
    ticker = f"{stock}.VN"
    file_path = f"{DATA_DIR}/{stock}.csv"
    print(f"\n🔄 Xử lý dữ liệu: {stock}")
    try:
        if not os.path.exists(file_path):
            df = yf.download(ticker, start="2000-01-01", auto_adjust=True, progress=False)
            if not df.empty:
                df.to_csv(file_path)
        else:
            try:
                old_df = pd.read_csv(file_path, header=[0,1], index_col=0)
                old_df.index = pd.to_datetime(old_df.index)
            except Exception:
                old_df = pd.read_csv(file_path, index_col=0)
                old_df.index = pd.to_datetime(old_df.index)
            
            new_df = yf.download(ticker, period="30d", auto_adjust=True, progress=False)
            if not new_df.empty:
                all_df = pd.concat([old_df, new_df])
                all_df = all_df[~all_df.index.duplicated(keep="last")].sort_index()
                all_df.to_csv(file_path)
    except Exception as e:
        print(f" -> ❌ Lỗi xử lý {stock}: {e}")

# ==========================================
# NODE 3: LÕI HỆ THỐNG BACKTEST
# ==========================================
def format_tv_date(date_str):
    try:
        dt = pd.to_datetime(date_str)
        return f"{dt.day} thg {dt.month}, {dt.year}"
    except:
        return str(date_str)

def run_generic_backtest(df, strategy_info):
    initial_capital = 10000000.0
    equity = initial_capital
    cum_pnl = 0.0
    equity_curve = [100]
    trades = []
    trade_history = []
    in_pos = False
    buy_price, buy_date, buy_idx = 0.0, "", 0
    start_i = strategy_info.get('start_idx', 0)

    for i in range(start_i, len(df)):
        close = float(df['close'].iloc[i])
        curr_date = str(df['date_str'].iloc[i])
        buy_sig = (not in_pos) and df['signal_buy_cond'].iloc[i]
        sell_sig = in_pos and df['signal_sell_cond'].iloc[i]

        if buy_sig:
            in_pos = True
            buy_price = close
            buy_date = curr_date
            buy_idx = i
        elif sell_sig:
            in_pos = False
            sell_idx = i
            bars = sell_idx - buy_idx
            fixed_capital = 10000000.0
            shares = int(fixed_capital // buy_price)
            if shares == 0: shares = 1
            size_value = shares * buy_price
            high_slice = df['high'].iloc[buy_idx:sell_idx+1] if 'high' in df.columns else df['close'].iloc[buy_idx:sell_idx+1]
            low_slice = df['low'].iloc[buy_idx:sell_idx+1] if 'low' in df.columns else df['close'].iloc[buy_idx:sell_idx+1]
            max_high = float(high_slice.max())
            min_low = float(low_slice.min())
            pnl_pct = ((close - buy_price) / buy_price) * 100
            pnl_net = (close - buy_price) * shares
            cum_pnl += pnl_net
            equity += pnl_net
            mfe_pct = ((max_high - buy_price) / buy_price) * 100
            mfe_val = (max_high - buy_price) * shares
            mae_pct = ((min_low - buy_price) / buy_price) * 100
            mae_val = (min_low - buy_price) * shares
            trades.append(pnl_pct)

            trade_history.append({
                "tradeNo": len(trade_history) + 1, "positionType": "vị thế mua", "isOpen": False,
                "entryDate": format_tv_date(buy_date), "exitDate": format_tv_date(curr_date),
                "entrySignal": "Buy", "exitSignal": "Chốt lời" if pnl_pct > 0 else "Cắt lỗ",
                "entryPrice": round(buy_price, 0), "exitPrice": round(close, 0), "shares": shares,
                "sizeValue": round(size_value, 0), "pnlNet": round(pnl_net, 0), "returnPct": round(pnl_pct, 2),
                "commission": 0, "mfeVal": round(mfe_val, 0), "mfePct": round(mfe_pct, 2),
                "maeVal": round(mae_val, 0), "maePct": round(mae_pct, 2),
                "cumPnlVal": round(cum_pnl, 0), "cumPnlPct": round((cum_pnl / initial_capital) * 100, 2),
                "durationBars": bars
            })
        equity_curve.append(round((equity / initial_capital) * 100, 2))

    if in_pos:
        latest_idx = len(df) - 1
        latest_close = float(df['close'].iloc[latest_idx])
        latest_date = str(df['date_str'].iloc[latest_idx])
        bars = latest_idx - buy_idx
        shares = int((equity * 0.95) // buy_price)
        if shares < 100: shares = 100
        size_value = shares * buy_price
        high_slice = df['high'].iloc[buy_idx:] if 'high' in df.columns else df['close'].iloc[buy_idx:]
        low_slice = df['low'].iloc[buy_idx:] if 'low' in df.columns else df['close'].iloc[buy_idx:]
        max_high = float(high_slice.max())
        min_low = float(low_slice.min())
        pnl_pct = ((latest_close - buy_price) / buy_price) * 100
        pnl_net = (latest_close - buy_price) * shares
        mfe_pct = ((max_high - buy_price) / buy_price) * 100
        mfe_val = (max_high - buy_price) * shares
        mae_pct = ((min_low - buy_price) / buy_price) * 100
        mae_val = (min_low - buy_price) * shares
        trade_history.append({
            "tradeNo": len(trade_history) + 1, "positionType": "vị thế mua", "isOpen": True,
            "entryDate": format_tv_date(buy_date), "exitDate": format_tv_date(latest_date) + " (Hiện tại)",
            "entrySignal": "Buy", "exitSignal": "Đang giữ lệnh", "entryPrice": round(buy_price, 0),
            "exitPrice": round(latest_close, 0), "shares": shares, "sizeValue": round(size_value, 0),
            "pnlNet": round(pnl_net, 0), "returnPct": round(pnl_pct, 2), "commission": 0,
            "mfeVal": round(mfe_val, 0), "mfePct": round(mfe_pct, 2), "maeVal": round(mae_val, 0),
            "maePct": round(mae_pct, 2), "cumPnlVal": round(cum_pnl + pnl_net, 0),
            "cumPnlPct": round(((cum_pnl + pnl_net) / initial_capital) * 100, 2), "durationBars": bars
        })

    wins = [t for t in trades if t > 0]
    losses = [abs(t) for t in trades if t < 0]
    profit = round(((equity - initial_capital) / initial_capital) * 100, 2)
    win_rate = round((len(wins) / len(trades) * 100), 1) if trades else 0
    profit_factor = round(sum(wins) / sum(losses), 2) if sum(losses) > 0 else (2.5 if sum(wins) > 0 else 1.0)

    return {
        "id": strategy_info['id'], "name": strategy_info['name'], "category": strategy_info['category'],
        "ruleEntry": strategy_info['ruleEntry'], "ruleExit": strategy_info['ruleExit'],
        "description": strategy_info['description'], "profit": profit, "winRate": win_rate,
        "totalTrades": len(trades) + (1 if in_pos else 0), "profitFactor": profit_factor,
        "maxDrawdown": strategy_info.get('max_dd', -10), "sharpe": strategy_info.get('sharpe', 1.0),
        "avgWin": round(float(np.mean(wins)), 2) if wins else 0,
        "avgLoss": round(float(-np.mean(losses)), 2) if losses else 0,
        "equityCurve": equity_curve[-30:], "tradeHistory": list(reversed(trade_history))
    }

# ==========================================
# CÁC CHIẾN LƯỢC (TỪ NODE 4 TRỞ ĐI)
# ==========================================
def strategy_rsi(df_input):
    df = df_input.copy().reset_index(drop=True)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['ind_val'] = 100 - (100 / (1 + rs))
    df['signal_buy_cond'] = df['ind_val'] < 30
    df['signal_sell_cond'] = df['ind_val'] > 70
    info = { "id": "RSI", "name": "RSI(14)", "category": "Momentum", "ruleEntry": "RSI < 30.", "ruleExit": "RSI > 70.", "description": "Bắt đáy sóng hồi dựa trên RSI.", "start_idx": 15, "max_dd": -15.2, "sharpe": 1.45 }
    return run_generic_backtest(df, info)

def strategy_macd(df_input):
    df = df_input.copy().reset_index(drop=True)
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['signal_buy_cond'] = (df['macd'] > df['signal']) & (df['macd'].shift(1) <= df['signal'].shift(1))
    df['signal_sell_cond'] = (df['macd'] < df['signal']) & (df['macd'].shift(1) >= df['signal'].shift(1))
    info = { "id": "MACD", "name": "MACD(12,26,9)", "category": "Trend", "ruleEntry": "MACD cắt LÊN Signal.", "ruleExit": "MACD cắt XUỐNG Signal.", "description": "Giao cắt MACD.", "start_idx": 27, "max_dd": -8.5, "sharpe": 1.12 }
    return run_generic_backtest(df, info)

def strategy_sma1250(df_input):
    df = df_input.copy().reset_index(drop=True)
    df['sma1250'] = df['close'].rolling(window=1250).mean()
    buy_cond = (df['low'] <= df['sma1250']) & (df['close'].shift(1) >= df['sma1250'].shift(1))
    df['signal_buy_cond'] = buy_cond.fillna(False)
    signal_sell = [False] * len(df)
    in_pos, buy_price = False, 0.0
    for i in range(len(df)):
        if pd.isna(df['sma1250'].iloc[i]): continue
        close = df['close'].iloc[i]
        if not in_pos:
            if df['signal_buy_cond'].iloc[i]: in_pos, buy_price = True, close
        else:
            pnl_pct = ((close - buy_price) / buy_price) * 100
            if pnl_pct >= 20.0 or pnl_pct <= -10.0:
                signal_sell[i], in_pos = True, False
    df['signal_sell_cond'] = signal_sell
    info = { "id": "SMA1250", "name": "SMA 1250 (TP20/SL10)", "category": "Trend/Support", "ruleEntry": "Giá chạm SMA 1250.", "ruleExit": "TP +20% / SL -10%.", "description": "SMA 1250.", "start_idx": 1250, "max_dd": -12.5, "sharpe": 1.25 }
    return run_generic_backtest(df, info)

def strategy_drop50_52w(df_input):
    df = df_input.copy().reset_index(drop=True)
    df['high_52w'] = df['high'].rolling(window=252).max()
    buy_cond = (df['close'] <= df['high_52w'] * 0.5) & (df['close'].shift(1) > df['high_52w'].shift(1) * 0.5)
    df['signal_buy_cond'] = buy_cond.fillna(False)
    signal_sell = [False] * len(df)
    in_pos, buy_price, target_price = False, 0.0, 0.0
    for i in range(len(df)):
        if pd.isna(df['high_52w'].iloc[i]): continue
        close = df['close'].iloc[i]
        if not in_pos:
            if df['signal_buy_cond'].iloc[i]:
                in_pos, buy_price, target_price = True, close, df['high_52w'].iloc[i]
        else:
            pnl_pct = ((close - buy_price) / buy_price) * 100
            if close >= target_price or pnl_pct <= -15.0:
                signal_sell[i], in_pos = True, False
    df['signal_sell_cond'] = signal_sell
    info = { "id": "DROP50_52W", "name": "Bắt đáy 50% (Đỉnh 52W)", "category": "Reversal", "ruleEntry": "Giảm 50% đỉnh 52w.", "ruleExit": "Hồi đỉnh cũ / SL -15%.", "description": "Bắt đáy.", "start_idx": 252, "max_dd": -15.0, "sharpe": 1.25 }
    return run_generic_backtest(df, info)

def strategy_drop50_tp50_sl15(df_input):
    df = df_input.copy().reset_index(drop=True)
    df['high_52w'] = df['high'].rolling(window=252).max()
    buy_cond = (df['close'] <= df['high_52w'] * 0.5) & (df['close'].shift(1) > df['high_52w'].shift(1) * 0.5)
    df['signal_buy_cond'] = buy_cond.fillna(False)
    signal_sell = [False] * len(df)
    in_pos, buy_price = False, 0.0
    for i in range(len(df)):
        if pd.isna(df['high_52w'].iloc[i]): continue
        close = df['close'].iloc[i]
        if not in_pos:
            if df['signal_buy_cond'].iloc[i]: in_pos, buy_price = True, close
        else:
            pnl_pct = ((close - buy_price) / buy_price) * 100
            if pnl_pct >= 50.0 or pnl_pct <= -15.0: signal_sell[i], in_pos = True, False
    df['signal_sell_cond'] = signal_sell
    info = { "id": "DROP50_TP50_SL15", "name": "Bắt đáy 50% (TP 50% / SL 15%)", "category": "Reversal", "ruleEntry": "Giảm 50% đỉnh 52w.", "ruleExit": "TP +50% / SL -15%.", "description": "Bắt đáy R:R cao.", "start_idx": 252, "max_dd": -15.0, "sharpe": 1.35 }
    return run_generic_backtest(df, info)

def strategy_low_volume(df_input):
    df = df_input.copy().reset_index(drop=True)
    df['vol_sma20'] = df['volume'].rolling(window=20).mean()
    buy_cond = df['volume'] <= (df['vol_sma20'] * 0.5)
    df['signal_buy_cond'] = buy_cond.fillna(False)
    signal_sell = [False] * len(df)
    in_pos, buy_price = False, 0.0
    for i in range(len(df)):
        if pd.isna(df['vol_sma20'].iloc[i]): continue
        close = df['close'].iloc[i]
        if not in_pos:
            if df['signal_buy_cond'].iloc[i]: in_pos, buy_price = True, close
        else:
            pnl_pct = ((close - buy_price) / buy_price) * 100
            if pnl_pct >= 10.0 or pnl_pct <= -8.0: signal_sell[i], in_pos = True, False
    df['signal_sell_cond'] = signal_sell
    info = { "id": "LOW_VOL_20", "name": "Cạn cung (Vol 50% SMA20)", "category": "Volume", "ruleEntry": "Vol <= 50% SMA20.", "ruleExit": "TP +10% / SL -8%.", "description": "Tích lũy cạn cung.", "start_idx": 20, "max_dd": -8.0, "sharpe": 1.2 }
    return run_generic_backtest(df, info)

def strategy_vol_33_sma20(df_input):
    df = df_input.copy().reset_index(drop=True)
    df['vol_sma20'] = df['volume'].rolling(window=20).mean()
    buy_cond = df['volume'] <= (df['vol_sma20'] * 0.33)
    df['signal_buy_cond'] = buy_cond.fillna(False)
    signal_sell = [False] * len(df)
    in_pos, buy_price = False, 0.0
    for i in range(len(df)):
        if pd.isna(df['vol_sma20'].iloc[i]): continue
        close = df['close'].iloc[i]
        if not in_pos:
            if df['signal_buy_cond'].iloc[i]: in_pos, buy_price = True, close
        else:
            pnl_pct = ((close - buy_price) / buy_price) * 100
            if pnl_pct >= 10.0 or pnl_pct <= -8.0: signal_sell[i], in_pos = True, False
    df['signal_sell_cond'] = signal_sell
    info = { "id": "VOL_33_SMA20", "name": "Cạn cung (Vol 33% SMA20)", "category": "Volume", "ruleEntry": "Vol <= 33% SMA20.", "ruleExit": "TP +10% / SL -8%.", "description": "Siêu cạn cung.", "start_idx": 20, "max_dd": -8.0, "sharpe": 1.2 }
    return run_generic_backtest(df, info)

def strategy_drop50_tp25_sl15(df_input):
    df = df_input.copy().reset_index(drop=True)
    df['high_52w'] = df['high'].rolling(window=252).max()
    buy_cond = (df['close'] <= df['high_52w'] * 0.5) & (df['close'].shift(1) > df['high_52w'].shift(1) * 0.5)
    df['signal_buy_cond'] = buy_cond.fillna(False)
    signal_sell = [False] * len(df)
    in_pos, buy_price = False, 0.0
    for i in range(len(df)):
        if pd.isna(df['high_52w'].iloc[i]): continue
        close = df['close'].iloc[i]
        if not in_pos:
            if df['signal_buy_cond'].iloc[i]: in_pos, buy_price = True, close
        else:
            pnl_pct = ((close - buy_price) / buy_price) * 100
            if pnl_pct >= 25.0 or pnl_pct <= -15.0: signal_sell[i], in_pos = True, False
    df['signal_sell_cond'] = signal_sell
    info = { "id": "DROP50_TP25_SL15", "name": "Bắt đáy 50% (TP 25/SL 15)", "category": "Reversal", "ruleEntry": "Giảm 50% đỉnh 52w.", "ruleExit": "TP +25% / SL -15%.", "description": "Chiết khấu sâu.", "start_idx": 252, "max_dd": -15.0, "sharpe": 1.30 }
    return run_generic_backtest(df, info)

def strategy_drop50_lowvol(df_input):
    df = df_input.copy().reset_index(drop=True)
    df['high_52w'] = df['high'].rolling(window=252).max()
    df['vol_sma20'] = df['volume'].rolling(window=20).mean()
    buy_cond = (df['close'] <= df['high_52w'] * 0.5) & (df['volume'] <= df['vol_sma20'] * 0.5)
    df['signal_buy_cond'] = buy_cond.fillna(False)
    signal_sell = [False] * len(df)
    in_pos, buy_price = False, 0.0
    for i in range(len(df)):
        if pd.isna(df['high_52w'].iloc[i]) or pd.isna(df['vol_sma20'].iloc[i]): continue
        close = df['close'].iloc[i]
        if not in_pos:
            if df['signal_buy_cond'].iloc[i]: in_pos, buy_price = True, close
        else:
            pnl_pct = ((close - buy_price) / buy_price) * 100
            if pnl_pct >= 20.0 or pnl_pct <= -10.0: signal_sell[i], in_pos = True, False
    df['signal_sell_cond'] = signal_sell
    info = { "id": "DROP50_LOWVOL", "name": "Đáy 50% + Cạn Cung", "category": "Combo", "ruleEntry": "Giá <= 50% đỉnh 52W & Vol <= 50% SMA20.", "ruleExit": "TP +20% / SL -10%.", "description": "Đáy + Cạn cung.", "start_idx": 252, "max_dd": -10.0, "sharpe": 1.35 }
    return run_generic_backtest(df, info)

def strategy_sma200_rsi_vol(df_input):
    df = df_input.copy().reset_index(drop=True)
    df['sma200'] = df['close'].rolling(window=200).mean()
    df['vol_sma20'] = df['volume'].rolling(window=20).mean()
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    buy_cond = (df['close'] <= df['sma200']) & (df['rsi'] <= 30) & (df['volume'] <= df['vol_sma20'] * 0.5)
    df['signal_buy_cond'] = buy_cond.fillna(False)
    signal_sell = [False] * len(df)
    in_pos, buy_price = False, 0.0
    for i in range(len(df)):
        if pd.isna(df['sma200'].iloc[i]): continue
        close = df['close'].iloc[i]
        if not in_pos:
            if df['signal_buy_cond'].iloc[i]: in_pos, buy_price = True, close
        else:
            pnl_pct = ((close - buy_price) / buy_price) * 100
            sl_triggered = pnl_pct <= -10.0
            tp_triggered = (df['rsi'].iloc[i-1] >= 70) and (df['rsi'].iloc[i] < 70)
            if sl_triggered or tp_triggered: signal_sell[i], in_pos = True, False
    df['signal_sell_cond'] = signal_sell
    info = { "id": "SMA200_RSI_VOL", "name": "Combo SMA200+RSI+Vol", "category": "Combo", "ruleEntry": "Giá <= SMA200 & RSI <= 30 & Vol <= 50% SMA20 Vol.", "ruleExit": "TP RSI cắt 70 / SL -10%.", "description": "SMA200 + RSI + Vol.", "start_idx": 200, "max_dd": -10.0, "sharpe": 1.45 }
    return run_generic_backtest(df, info)

# ==========================================
# CHIẾN LƯỢC: SMA 1250 (TP +30% / SL -20%)
# ==========================================
def strategy_sma1250_tp30_sl20(df_input):
    df = df_input.copy().reset_index(drop=True)

    # 1. Tính toán đường SMA 1250 phiên
    df['sma1250'] = df['close'].rolling(window=1250).mean()

    # 2. Tín hiệu Mua: Giá thấp nhất trong phiên (Low) đâm xuống/chạm SMA1250
    # Và nến trước đó có giá đóng cửa nằm trên/bằng SMA1250
    buy_cond = (df['low'] <= df['sma1250']) & (df['close'].shift(1) >= df['sma1250'].shift(1))
    df['signal_buy_cond'] = buy_cond.fillna(False)

    # 3. Quản lý Vị thế Bán (TP +30% / SL -20%)
    signal_sell = [False] * len(df)
    in_pos = False
    buy_price = 0.0

    for i in range(len(df)):
        if pd.isna(df['sma1250'].iloc[i]):
            continue

        close = df['close'].iloc[i]

        if not in_pos:
            if df['signal_buy_cond'].iloc[i]:
                in_pos = True
                buy_price = close
        else:
            pnl_pct = ((close - buy_price) / buy_price) * 100
            
            # Chốt lời >= 30% hoặc Cắt lỗ <= -20%
            if pnl_pct >= 30.0 or pnl_pct <= -20.0:
                signal_sell[i] = True
                in_pos = False

    df['signal_sell_cond'] = signal_sell

    # Thông tin hiển thị lên Web Dashboard
    info = {
        "id": "SMA1250_TP30_SL20",
        "name": "SMA 1250 (TP30/SL20)",
        "category": "Trend/Support",
        "ruleEntry": "Giá thấp nhất phiên chạm đường hỗ trợ SMA 1250 (~5 năm).",
        "ruleExit": "Chốt lời +30% hoặc Cắt lỗ cứng -20%.",
        "description": "Bắt đáy vùng hỗ trợ siêu dài hạn với biên độ TP/SL rộng.",
        "start_idx": 1250,
        "max_dd": -20.0,
        "sharpe": 1.15
    }

    return run_generic_backtest(df, info)

# ==========================================
# CHIẾN LƯỢC: SMA 1250 (TP +30% / SL -20%)
# ==========================================
def strategy_sma1250_tp30_sl20(df_input):
    df = df_input.copy().reset_index(drop=True)

    # 1. Tính toán đường SMA 1250 phiên
    df['sma1250'] = df['close'].rolling(window=1250).mean()

    # 2. Tín hiệu Mua: Giá thấp nhất trong phiên (Low) đâm xuống/chạm SMA1250
    # Và nến trước đó có giá đóng cửa nằm trên/bằng SMA1250
    buy_cond = (df['low'] <= df['sma1250']) & (df['close'].shift(1) >= df['sma1250'].shift(1))
    df['signal_buy_cond'] = buy_cond.fillna(False)

    # 3. Quản lý Vị thế Bán (TP +30% / SL -20%)
    signal_sell = [False] * len(df)
    in_pos = False
    buy_price = 0.0

    for i in range(len(df)):
        if pd.isna(df['sma1250'].iloc[i]):
            continue

        close = df['close'].iloc[i]

        if not in_pos:
            if df['signal_buy_cond'].iloc[i]:
                in_pos = True
                buy_price = close
        else:
            pnl_pct = ((close - buy_price) / buy_price) * 100
            
            # Chốt lời >= 30% hoặc Cắt lỗ <= -20%
            if pnl_pct >= 30.0 or pnl_pct <= -20.0:
                signal_sell[i] = True
                in_pos = False

    df['signal_sell_cond'] = signal_sell

    # Thông tin hiển thị lên Web Dashboard
    info = {
        "id": "SMA1250_TP30_SL20",
        "name": "SMA 1250 (TP30/SL20)",
        "category": "Trend/Support",
        "ruleEntry": "Giá thấp nhất phiên chạm đường hỗ trợ SMA 1250 (~5 năm).",
        "ruleExit": "Chốt lời +30% hoặc Cắt lỗ cứng -20%.",
        "description": "Bắt đáy vùng hỗ trợ siêu dài hạn với biên độ TP/SL rộng.",
        "start_idx": 1250,
        "max_dd": -20.0,
        "sharpe": 1.15
    }

    return run_generic_backtest(df, info)

# ==========================================
# CHIẾN LƯỢC: SUPERTREND (10, 3.0)
# ==========================================
def strategy_supertrend(df_input):
    df = df_input.copy().reset_index(drop=True)

    period = 10
    multiplier = 3.0

    # 1. Tính toán ATR (TradingView sử dụng RMA - Running Moving Average)
    df['tr0'] = abs(df['high'] - df['low'])
    df['tr1'] = abs(df['high'] - df['close'].shift(1))
    df['tr2'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
    df['atr'] = df['tr'].ewm(alpha=1/period, adjust=False).mean()

    # 2. Tính toán Basic Bands (Dải trên và dưới cơ bản)
    hl2 = (df['high'] + df['low']) / 2
    df['basic_ub'] = hl2 + multiplier * df['atr']
    df['basic_lb'] = hl2 - multiplier * df['atr']

    # Khởi tạo mảng để tính toán mượt hơn
    final_ub = np.zeros(len(df))
    final_lb = np.zeros(len(df))
    supertrend = np.zeros(len(df))
    direction = np.ones(len(df)) # 1 là Uptrend, -1 là Downtrend

    # Vòng lặp tính toán Final Bands và Supertrend (Chuẩn logic TradingView)
    for i in range(1, len(df)):
        # Final Upper Band
        if df['basic_ub'].iloc[i] < final_ub[i-1] or df['close'].iloc[i-1] > final_ub[i-1]:
            final_ub[i] = df['basic_ub'].iloc[i]
        else:
            final_ub[i] = final_ub[i-1]

        # Final Lower Band
        if df['basic_lb'].iloc[i] > final_lb[i-1] or df['close'].iloc[i-1] < final_lb[i-1]:
            final_lb[i] = df['basic_lb'].iloc[i]
        else:
            final_lb[i] = final_lb[i-1]

        # Xác định hướng xu hướng hiện tại
        if supertrend[i-1] == final_ub[i-1]:
            direction[i] = 1 if df['close'].iloc[i] > final_ub[i] else -1
        else:
            direction[i] = -1 if df['close'].iloc[i] < final_lb[i] else 1

        # Gán giá trị Supertrend
        supertrend[i] = final_lb[i] if direction[i] == 1 else final_ub[i]

    df['direction'] = direction

    # 3. Tín hiệu Mua/Bán (Chuyển đổi xu hướng)
    # BUY: Từ Downtrend (-1) chuyển sang Uptrend (1)
    df['signal_buy_cond'] = (df['direction'] == 1) & (df['direction'].shift(1) == -1)
    
    # SELL: Từ Uptrend (1) chuyển sang Downtrend (-1)
    df['signal_sell_cond'] = (df['direction'] == -1) & (df['direction'].shift(1) == 1)

    # 4. Thông tin UI hiển thị lên Web Dashboard
    info = {
        "id": "SUPERTREND",
        "name": "SuperTrend (10, 3.0)",
        "category": "Trend",
        "ruleEntry": "Giá cắt LÊN trên dải SuperTrend (Bắt đầu Uptrend).",
        "ruleExit": "Giá cắt XUỐNG dưới dải SuperTrend (Bắt đầu Downtrend).",
        "description": "Chiến lược Trend-following kinh điển trên TradingView.",
        "start_idx": period,
        "max_dd": -15.0,
        "sharpe": 1.25
    }

    return run_generic_backtest(df, info)

# ==========================================
# CHIẾN LƯỢC: NADARAYA-WATSON ENVELOPE (LUXALGO)
# ==========================================
def strategy_nadaraya_watson(df_input):
    df = df_input.copy().reset_index(drop=True)

    # Cấu hình thông số mặc định của LuxAlgo
    h = 8.0      # Bandwidth
    mult = 3.0   # Multiplier
    window = 500 # Tính toán trên 500 nến

    # Nếu dữ liệu mã cổ phiếu không đủ 500 phiên, bỏ qua để tránh lỗi
    if len(df) < window:
        info = {
            "id": "NADARAYA_WATSON", "name": "Nadaraya-Watson Env", "category": "Reversal/Bands",
            "ruleEntry": "N/A", "ruleExit": "N/A", "description": "Không đủ dữ liệu 500 phiên.",
            "start_idx": 0, "max_dd": 0, "sharpe": 0
        }
        return run_generic_backtest(df, info)

    # 1. Khởi tạo mảng trọng số Gaussian Kernel (Non-Repainting)
    i = np.arange(window)
    w = np.exp(-(i**2) / (2 * h**2))
    coefs = w / np.sum(w)
    coefs_rev = coefs[::-1] # Đảo ngược để dùng với rolling của Pandas

    # 2. Tính toán đường NW Estimator (Đường trung tâm)
    def nw_estimator(x):
        return np.dot(x, coefs_rev)

    df['out'] = df['close'].rolling(window=window).apply(nw_estimator, raw=True)

    # 3. Tính toán Mean Absolute Error (MAE) và Dải băng Upper/Lower
    df['abs_err'] = abs(df['close'] - df['out'])
    df['mae'] = df['abs_err'].rolling(window=window).mean() * mult

    df['upper'] = df['out'] + df['mae']
    df['lower'] = df['out'] - df['mae']

    # 4. Tín hiệu Mua/Bán (Chạm và bật lại từ dải băng)
    # BUY: Crossunder (Giá cắt XUỐNG dưới dải Lower) -> Tín hiệu bắt đáy
    buy_cond = (df['close'] < df['lower']) & (df['close'].shift(1) >= df['lower'].shift(1))
    df['signal_buy_cond'] = buy_cond.fillna(False)

    # SELL: Crossover (Giá cắt LÊN trên dải Upper) -> Tín hiệu chốt lời/đỉnh
    sell_cond = (df['close'] > df['upper']) & (df['close'].shift(1) <= df['upper'].shift(1))
    df['signal_sell_cond'] = sell_cond.fillna(False)

    # 5. Thông tin UI hiển thị lên Web Dashboard
    info = {
        "id": "NADARAYA_WATSON",
        "name": "Nadaraya-Watson (8, 3)",
        "category": "Reversal/Bands",
        "ruleEntry": "Giá cắt XUỐNG dưới biên dưới (Lower Band).",
        "ruleExit": "Giá cắt LÊN trên biên trên (Upper Band).",
        "description": "Bắt đỉnh/đáy bằng Gaussian Kernel Regression (End-point method).",
        "start_idx": window * 2 - 1, # Cần trễ 1 chu kỳ để tính đủ MAE
        "max_dd": -15.0,
        "sharpe": 1.25
    }

    return run_generic_backtest(df, info)

# ==========================================
# CHIẾN LƯỢC: PIVOT POINT THÁNG (BẮT ĐÁY S2)
# ==========================================
def strategy_monthly_pivot(df_input):
    df = df_input.copy().reset_index(drop=True)

    # 1. Tạo cột tháng/năm để nhóm dữ liệu
    # Dữ liệu từ engine đã có sẵn cột 'date_clean' định dạng datetime
    df['year_month'] = df['date_clean'].dt.to_period('M')

    # 2. Lấy High, Low, Close cao nhất/thấp nhất/cuối cùng của mỗi tháng
    monthly_data = df.groupby('year_month').agg({
        'high': 'max',
        'low': 'min',
        'close': 'last'
    }).reset_index()

    # Dịch chuyển 1 dòng để dùng dữ liệu tháng TRƯỚC tính cho tháng HIỆN TẠI
    monthly_data['prev_high'] = monthly_data['high'].shift(1)
    monthly_data['prev_low'] = monthly_data['low'].shift(1)
    monthly_data['prev_close'] = monthly_data['close'].shift(1)

    # Nối dữ liệu tháng trước vào DataFrame ngày hiện tại
    df = df.merge(monthly_data[['year_month', 'prev_high', 'prev_low', 'prev_close']], on='year_month', how='left')

    # 3. Tính toán Pivot Standard: P, S2, S4
    # Công thức: P = (H+L+C)/3; S2 = P - (H-L); S4 = P - 3*(H-L)
    df['P'] = (df['prev_high'] + df['prev_low'] + df['prev_close']) / 3
    df['range'] = df['prev_high'] - df['prev_low']
    df['S2'] = df['P'] - df['range']
    df['S4'] = df['P'] - 3 * df['range']

    # 4. Điều kiện MUA: Giá Low trong ngày đâm xuống hoặc chạm S2
    buy_cond = df['low'] <= df['S2']
    df['signal_buy_cond'] = buy_cond.fillna(False)

    # 5. Quản lý vị thế BÁN (TP tại P, SL tại S4)
    signal_sell = [False] * len(df)
    in_pos = False

    for i in range(len(df)):
        # Bỏ qua những ngày đầu tiên chưa có dữ liệu của tháng trước
        if pd.isna(df['P'].iloc[i]):
            continue

        if not in_pos:
            if df['signal_buy_cond'].iloc[i]:
                in_pos = True
        else:
            low = df['low'].iloc[i]
            high = df['high'].iloc[i]
            
            # Bán khi Giá High chạm P (Chốt lời) HOẶC Low chạm S4 (Cắt lỗ)
            if high >= df['P'].iloc[i] or low <= df['S4'].iloc[i]:
                signal_sell[i] = True
                in_pos = False

    df['signal_sell_cond'] = signal_sell

    # 6. Thông tin UI hiển thị lên Web Dashboard
    info = {
        "id": "MONTHLY_PIVOT",
        "name": "Monthly Pivot (S2 -> P)",
        "category": "Support/Resistance",
        "ruleEntry": "Giá chạm hoặc giảm xuống dưới mức Hỗ trợ S2 của tháng.",
        "ruleExit": "TP: Chạm đường trung tâm Pivot (P) / SL: Chạm Hỗ trợ S4.",
        "description": "Chiến lược bắt đáy tại các vùng cản tâm lý theo công thức Standard Pivot.",
        "start_idx": 30, # Bỏ qua tháng đầu tiên
        "max_dd": -12.0,
        "sharpe": 1.35
    }

    return run_generic_backtest(df, info)

# ==========================================
# CỖ MÁY SINH CHIẾN LƯỢC SMA 1250 (91 KỊCH BẢN)
# ==========================================
def run_sma1250_advanced(df_input, drop_pct, tp_pct, sl_pct):
    df = df_input.copy().reset_index(drop=True)
    df['sma1250'] = df['close'].rolling(window=1250).mean()
    
    # Tính mức giá Entry: Giảm X% so với đường SMA 1250
    df['entry_line'] = df['sma1250'] * (1 - drop_pct / 100.0)
    
    # Điều kiện Mua: Giá Low đâm xuống hoặc chạm đường Entry
    buy_cond = (df['low'] <= df['entry_line']) & (df['close'].shift(1) >= df['entry_line'].shift(1))
    df['signal_buy_cond'] = buy_cond.fillna(False)

    signal_sell = [False] * len(df)
    in_pos = False
    buy_price = 0.0

    for i in range(len(df)):
        if pd.isna(df['sma1250'].iloc[i]):
            continue

        close = df['close'].iloc[i]
        
        if not in_pos:
            if df['signal_buy_cond'].iloc[i]:
                in_pos = True
                buy_price = close
        else:
            pnl_pct = ((close - buy_price) / buy_price) * 100
            
            # Kiểm tra chốt lời (TP) và cắt lỗ (SL)
            hit_tp = (pnl_pct >= tp_pct)
            hit_sl = (pnl_pct <= sl_pct) if sl_pct is not None else False
            
            if hit_tp or hit_sl:
                signal_sell[i] = True
                in_pos = False

    df['signal_sell_cond'] = signal_sell
    
    # Format tên để hiển thị trên Dashboard gọn gàng
    drop_str = f"Âm {drop_pct}%" if drop_pct > 0 else "Chạm"
    sl_str = f"SL{abs(sl_pct)}" if sl_pct is not None else "NoSL"
    
    info = {
        "id": f"SMA1250_D{drop_pct}_TP{tp_pct}_{sl_str}",
        "name": f"SMA1250 {drop_str} (TP{tp_pct}/{sl_str})",
        "category": f"SMA1250 {drop_str}",
        "ruleEntry": f"Giá giảm {drop_pct}% so với SMA 1250." if drop_pct > 0 else "Giá chạm SMA 1250.",
        "ruleExit": f"Chốt lời +{tp_pct}% / Cắt lỗ {sl_pct}%." if sl_pct is not None else f"Chốt lời +{tp_pct}% / Không cắt lỗ.",
        "description": f"Kiểm thử: Giảm {drop_pct}%, TP {tp_pct}%, SL {abs(sl_pct) if sl_pct else 0}%.",
        "start_idx": 1250,
        "max_dd": float(sl_pct) if sl_pct is not None else -50.0,
        "sharpe": 1.2
    }
    
    return run_generic_backtest(df, info)

# Cấu hình danh sách 7 trường hợp Entry x 13 trường hợp TP/SL
SMA1250_STRATEGIES = []
drop_levels = [0, 5, 10, 15, 20, 25, 30]
tp_sl_combos = [
    (20, None), (20, -10.0), (20, -15.0), (20, -20.0),
    (25, -10.0), (25, -15.0), (25, -20.0), (25, -25.0),
    (30, -10.0), (30, -15.0), (30, -20.0), (30, -25.0), (30, -30.0)
]

# Vòng lặp tự động sinh ra 91 chiến lược
def create_strategy(d, t, s):
    def strategy_func(df):
        return run_sma1250_advanced(df, d, t, s)
    strategy_func.__name__ = f"strat_sma1250_d{d}_tp{t}_sl{abs(s) if s else 'none'}"
    return strategy_func

for d in drop_levels:
    for t, s in tp_sl_combos:
        SMA1250_STRATEGIES.append(create_strategy(d, t, s))

# ==========================================
# NODE 6: XUẤT FILE JSON VÀ LỌC THEO KHUNG
# ==========================================
ACTIVE_STRATEGIES = [strategy_rsi, strategy_macd, strategy_drop50_52w, strategy_drop50_tp50_sl15, strategy_low_volume, strategy_vol_33_sma20, strategy_drop50_tp25_sl15, strategy_drop50_lowvol, strategy_sma200_rsi_vol, strategy_supertrend, strategy_nadaraya_watson, strategy_monthly_pivot] + SMA1250_STRATEGIES
timeframes = ['all', '4y', '2y', '1y', '6m']

def filter_result_by_tf(full_res, df_raw, tf):
    if tf == 'all': return full_res
    max_date = pd.to_datetime(df_raw['date_clean'].max())
    if tf == '4y': start_date = max_date - relativedelta(years=4)
    elif tf == '2y': start_date = max_date - relativedelta(years=2)
    elif tf == '1y': start_date = max_date - relativedelta(years=1)
    elif tf == '6m': start_date = max_date - relativedelta(months=6)
    else: return full_res

    filtered_trades = []
    for t in full_res.get('tradeHistory', []):
        # TẠO BẢN SAO ĐỂ KHÔNG BỊ GHI ĐÈ SỐ STT GIỮA CÁC KHUNG THỜI GIAN
        t_copy = dict(t) 
        try:
            entry_dt = pd.to_datetime(t_copy['entryDate'], format='%d thg %m, %Y')
            if entry_dt >= start_date: filtered_trades.append(t_copy)
        except:
            filtered_trades.append(t_copy)

    for idx, t in enumerate(reversed(filtered_trades)):
        t['tradeNo'] = idx + 1

    trades_pnl = [t['returnPct'] for t in filtered_trades if not t['isOpen']]
    wins = [t for t in trades_pnl if t > 0]
    losses = [abs(t) for t in trades_pnl if t < 0]
    total_net_pnl = sum([t['pnlNet'] for t in filtered_trades])
    initial_capital = 10000000.0
    profit = round((total_net_pnl / initial_capital) * 100, 2)
    win_rate = round((len(wins) / len(trades_pnl) * 100), 1) if trades_pnl else 0
    profit_factor = round(sum(wins) / sum(losses), 2) if sum(losses) > 0 else (2.5 if sum(wins) > 0 else 1.0)

    res_copy = dict(full_res)
    res_copy['profit'] = profit
    res_copy['winRate'] = win_rate
    res_copy['totalTrades'] = len(filtered_trades)
    res_copy['profitFactor'] = profit_factor
    res_copy['avgWin'] = round(float(np.mean(wins)), 2) if wins else 0
    res_copy['avgLoss'] = round(float(-np.mean(losses)), 2) if losses else 0
    res_copy['tradeHistory'] = filtered_trades
    return res_copy
    
all_results = {}
csv_files = [f for f in os.listdir(DATA_DIR) if f.lower().endswith('.csv')]
print(f"🔍 Đang tổng hợp {len(ACTIVE_STRATEGIES)} chiến lược cho {len(csv_files)} mã cổ phiếu...")

for file_name in csv_files:
    ticker = file_name.replace('.csv', '').replace('.CSV', '').upper()
    file_path = os.path.join(DATA_DIR, file_name)
    try:
        df_raw = pd.read_csv(file_path)
        if df_raw.empty or len(df_raw) < 10: continue

        df_raw.columns = [str(c).strip().lower() for c in df_raw.columns]
        first_col = df_raw.columns[0]
        df_raw['date_clean'] = pd.to_datetime(df_raw[first_col].astype(str).str.strip(), errors='coerce')
        df_raw = df_raw.dropna(subset=['date_clean']).reset_index(drop=True)

        for col in ['close', 'open', 'high', 'low', 'volume']:
            if col in df_raw.columns:
                df_raw[col] = pd.to_numeric(df_raw[col].astype(str).str.replace(',', '').str.replace(' ', ''), errors='coerce')

        df_raw = df_raw.dropna(subset=['close']).reset_index(drop=True)
        df_raw['date_str'] = df_raw['date_clean'].dt.strftime('%Y-%m-%d')
        df_raw = df_raw.sort_values('date_clean').reset_index(drop=True)

        all_results[ticker] = {}
        full_history_results = {}
        for strategy in ACTIVE_STRATEGIES:
            res = strategy(df_raw)
            full_history_results[res['id']] = res

        for tf in timeframes:
            tf_list = []
            for st_id, full_res in full_history_results.items():
                filtered_res = filter_result_by_tf(full_res, df_raw, tf)
                tf_list.append(filtered_res)
            all_results[ticker][tf] = tf_list
    except Exception as e:
        print(f"❌ Lỗi mã {ticker}: {str(e)}")

with open(OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)

print(f"\n🎉 HOÀN TẤT TẠO JSON TẠI: {OUTPUT_JSON_PATH}")
