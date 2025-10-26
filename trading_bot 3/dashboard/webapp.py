import json, time, requests, datetime
from flask import Flask, jsonify
import dash
from dash import html, dcc, dash_table
from dash.dependencies import Input, Output
import pandas as pd
import logging 

server = Flask(__name__)

# [FIX] Deaktiviere die Standard-Logs des Webservers (Werkzeug)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@server.route("/api/snapshot")
def api_snapshot():
    try:
        from core.shared_state import shared_state
        return jsonify(shared_state.snapshot())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

BG="#0e0f12";CARD="#16181d";BORD="#23252b";TXT="#e8eaf1";ACC="#05f0ff"
POS="#00e08a";NEG="#ff4d7d"
card={"backgroundColor":CARD,"border":f"1px solid {BORD}",
      "borderRadius":"10px","padding":"12px","margin":"8px"}

def kpi(title,id_):
    return html.Div([
        html.Div(title,style={"color":ACC,"fontSize":"12px"}),
        html.Div(id=id_,style={"color":TXT,"fontWeight":"800","fontSize":"20px"})
    ],style=card)

app = dash.Dash(__name__, server=server, title="CrazyBot Dashboard")

cols_open = ["market", "symbol", "leverage", "sl", "margin_used", "strategy"]
cols_closed = ["symbol", "market", "leverage", "margin_used", "pnl", "close_ts"] 

dt_style = {
    "style_table": {"overflowX":"auto"},
    "style_cell": {"backgroundColor":CARD,"color":TXT, "fontFamily":"Inter,system-ui", "fontSize":13, "padding": "8px"},
    "style_header": {"backgroundColor":"#1b1e24","color":ACC,"fontWeight":"700"}
}

app.layout = html.Div([
    html.Div("CrazyBot Dashboard",style={"color":ACC,"textAlign":"center","fontWeight":"900","fontSize":"26px","margin":"10px 0"}),
    html.Div(id="status",style={"color":TXT,"textAlign":"center","marginBottom":"8px","opacity":"0.9"}),

    html.Div([
        kpi("BTC/USDT","btc_box"),
        kpi("Daycap (used / total)","daycap_box"),
        kpi("Total PnL","pnl_box"),
        kpi("Nächster Scan (s)","scan_eta"),
        kpi("Top 3 Hot-Coins","hot3"),
        kpi("Kerzen Gebildet (5m)","candle_status"),
    ],style={"display":"grid","gridTemplateColumns":"repeat(6,1fr)","gap":"8px"}),

    html.Div([
        html.Div([
            html.Div("Trades (Open)",style={"color":ACC,"fontWeight":"800","marginBottom":"6px"}),
            dash_table.DataTable(id="tbl_open",page_size=5, columns=[{"name":i,"id":i} for i in cols_open], **dt_style)
        ],style=card),
        html.Div([
            html.Div("Closed",style={"color":ACC,"fontWeight":"800","marginBottom":"6px"}),
            dash_table.DataTable(id="tbl_closed",page_size=5, columns=[{"name":i,"id":i} for i in cols_closed], **dt_style)
        ],style=card),
    ],style={"display":"grid","gridTemplateColumns":"1fr 1fr","gap":"8px"}),

    html.Div([
        html.Div(id="perf",style=card),
        html.Div(id="learn",style=card),
    ],style={"display":"grid","gridTemplateColumns":"1fr 1fr","gap":"8px"}),

    dcc.Interval(id="tick",interval=1000,n_intervals=0) 
],style={"backgroundColor":BG,"minHeight":"100vh","padding":"12px","fontFamily":"Inter,system-ui"})

def get_snapshot():
    try:
        r=requests.get("http://127.0.0.1:8050/api/snapshot",timeout=1)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}

@app.callback(
    [Output("status","children"),
     Output("btc_box","children"),
     Output("daycap_box","children"),
     Output("pnl_box","children"),
     Output("scan_eta","children"),
     Output("hot3","children"),
     Output("candle_status","children"),
     Output("tbl_open","data"),
     Output("tbl_closed","data"),
     Output("perf","children"), Output("learn","children")],
    Input("tick","n_intervals")
)
def refresh(_):
    snap=get_snapshot()
    ws=snap.get("ws_status",{})
    if not isinstance(ws,dict):
        ws={"spot":str(ws),"futures":"?"}
    
    spot_status = ws.get('spot','?')
    futures_status = ws.get('futures','?')
    latency = snap.get('latency_ms', 0)
    latency_str = f"{latency} ms" if latency > 0 else "..."
    status=f"Spot: {spot_status} | Futures: {futures_status} | Latenz: {latency_str}"

    ticks=snap.get("ticks",{})
    sp=ticks.get("spot:BTCUSDT",{}).get("price")
    fu=ticks.get("futures:BTCUSDT",{}).get("price")
    
    btc_price = fu or sp
    btc = f"{btc_price:.1f}" if btc_price else "–"

    dc=snap.get("accounts",{}).get("daycap",{"total":150,"used":0})
    daycap_text=f"{float(dc.get('used',0)):.2f} / {float(dc.get('total',150)):.2f} USDT"

    total_pnl=float(snap.get("accounts",{}).get("total_pnl",0))
    pnl_color=POS if total_pnl>=0 else NEG
    pnl=html.Span(f"{total_pnl:+.2f} USDT",style={"color":pnl_color,"fontWeight":"800"})

    eta=max(0,int(snap.get("next_scan_at",0)-time.time()))
    hot=", ".join(snap.get("hot_coins",[])[:3]) or "–"
    
    candle_count = snap.get("candle_count", 0)
    candle_status = f"{candle_count} / 200"

    open_trades = snap.get("open_trades", [])
    closed_trades = snap.get("closed_trades", [])

    def format_trades(trades, cols):
        formatted = []
        for t in trades:
            row = {}
            for col in cols:
                val = t.get(col)
                if isinstance(val, float):
                    if col in ['pnl']: row[col] = f"{val:+.2f}"
                    elif col in ['sl', 'tp']: row[col] = f"{val:.1f}%" if val else "-"
                    elif col in ['margin_used']: row[col] = f"{val:.2f}"
                    else: row[col] = round(val, 4)
                elif col == 'timestamp' and val: row[col] = datetime.datetime.fromtimestamp(val).strftime('%H:%M:%S')
                elif col == 'close_ts' and val: row[col] = datetime.datetime.fromtimestamp(val).strftime('%H:%M:%S')
                else: row[col] = val if val is not None else "-"
            formatted.append(row)
        return formatted

    open_data = format_trades(open_trades, cols_open)
    closed_data = format_trades(closed_trades, cols_closed)

    perf=html.Div([
        html.Div(f"Closed Trades: {len(closed_trades)}",style={"color":TXT}),
        html.Div(f"Gesamt PnL: {total_pnl:+.2f} USDT",style={"color":pnl_color,"fontWeight":"700"})
    ])

    learn="Keine Daten"
    try:
        with open("data/curriculum_state.json","r") as f: st=json.load(f)
        lvl=int(st.get("level",0)); xp=float(st.get("xp",0)); nxt=float(st.get("xp_to_next",100))
        bar=int((xp/max(1,nxt))*100)
        learn=html.Div([
            html.Div(f"Level {lvl} | XP {xp:.0f}/{nxt:.0f} ({bar}%)",style={"color":ACC,"fontWeight":"800"}),
            html.Div(f"Knowledge: {st.get('knowledge',0):.2f} | Perf(EWM): {st.get('performance_ewm',0):+.3f}",style={"color":TXT})
        ])
    except Exception: pass

    return (status,btc,daycap_text,pnl,str(eta),hot,candle_status, 
            open_data,
            closed_data,
            perf,learn)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=8050,debug=False)
