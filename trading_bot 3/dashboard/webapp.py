import json, time, requests
from flask import Flask, jsonify
import dash
from dash import html, dcc, dash_table
from dash.dependencies import Input, Output
import pandas as pd

# === Backend-Bridge ===
server = Flask(__name__)

@server.route("/api/snapshot")
def api_snapshot():
    try:
        from core.shared_state import shared_state
        return jsonify(shared_state.snapshot())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === Farben & Stil ===
BG="#0e0f12";CARD="#16181d";BORD="#23252b";TXT="#e8eaf1";ACC="#05f0ff"
POS="#00e08a";NEG="#ff4d7d"
card={"backgroundColor":CARD,"border":f"1px solid {BORD}",
      "borderRadius":"10px","padding":"12px","margin":"8px"}

def kpi(title,id_):
    return html.Div([
        html.Div(title,style={"color":ACC,"fontSize":"12px"}),
        html.Div(id=id_,style={"color":TXT,"fontWeight":"800","fontSize":"20px"})
    ],style=card)

# === Dashboard Layout ===
app = dash.Dash(__name__, server=server, title="CrazyBot Dashboard")
app.layout = html.Div([
    html.Div("CrazyBot Dashboard",style={"color":ACC,"textAlign":"center","fontWeight":"900","fontSize":"26px","margin":"10px 0"}),
    html.Div(id="status",style={"color":TXT,"textAlign":"center","marginBottom":"8px","opacity":"0.9"}),

    html.Div([
        kpi("BTC/USDT (Spot/Futures)","btc_box"),
        kpi("Daycap (used / total)","daycap_box"),
        kpi("Total PnL","pnl_box"),
        kpi("Nächster Scan (s)","scan_eta"),
        kpi("Top 3 Hot-Coins","hot3"),
    ],style={"display":"grid","gridTemplateColumns":"repeat(5,1fr)","gap":"8px"}),

    html.Div([
        html.Div([
            html.Div("Trades (Open)",style={"color":ACC,"fontWeight":"800","marginBottom":"6px"}),
            dash_table.DataTable(id="tbl_open",page_size=5,
                style_table={"overflowX":"auto"},
                style_cell={"backgroundColor":CARD,"color":TXT},
                style_header={"backgroundColor":"#1b1e24","color":ACC,"fontWeight":"700"})
        ],style=card),
        html.Div([
            html.Div("Closed",style={"color":ACC,"fontWeight":"800","marginBottom":"6px"}),
            dash_table.DataTable(id="tbl_closed",page_size=5,
                style_table={"overflowX":"auto"},
                style_cell={"backgroundColor":CARD,"color":TXT},
                style_header={"backgroundColor":"#1b1e24","color":ACC,"fontWeight":"700"})
        ],style=card),
    ],style={"display":"grid","gridTemplateColumns":"1fr 1fr","gap":"8px"}),

    html.Div([
        html.Div(id="perf",style=card),
        html.Div(id="learn",style=card),
    ],style={"display":"grid","gridTemplateColumns":"1fr 1fr","gap":"8px"}),

    dcc.Interval(id="tick",interval=2000,n_intervals=0)
],style={"backgroundColor":BG,"minHeight":"100vh","padding":"12px","fontFamily":"Inter,system-ui"})

# === Helper zum Abruf des Snapshots ===
def get_snapshot():
    try:
        r=requests.get("http://127.0.0.1:8050/api/snapshot",timeout=1)
        return r.json()
    except Exception:
        return {}

# === Callback (nach Layout!) ===
@app.callback(
    [Output("status","children"),
     Output("btc_box","children"),
     Output("daycap_box","children"),
     Output("pnl_box","children"),
     Output("scan_eta","children"),
     Output("hot3","children"),
     Output("tbl_open","data"), Output("tbl_open","columns"),
     Output("tbl_closed","data"), Output("tbl_closed","columns"),
     Output("perf","children"), Output("learn","children")],
    Input("tick","n_intervals")
)
def refresh(_):
    snap=get_snapshot()
    ws=snap.get("ws_status",{})
    if not isinstance(ws,dict):
        ws={"spot":str(ws),"futures":"?"}
    status=f"Spot: {ws.get('spot','?')} | Futures: {ws.get('futures','?')} | Latenz: {snap.get('latency_ms',0)} ms"

    ticks=snap.get("ticks",{})
    sp=ticks.get("spot:BTCUSDT",{}).get("price")
    fu=ticks.get("futures:BTCUSDT",{}).get("price")
    btc=f"S:{sp or '–'} | F:{fu or '–'}"

    dc=snap.get("accounts",{}).get("daycap",{"total":150,"used":0})
    daycap_text=f"{float(dc.get('used',0)):.2f} / {float(dc.get('total',150)):.2f} USDT"

    total_pnl=float(snap.get("accounts",{}).get("total_pnl",0))
    pnl_color=POS if total_pnl>=0 else NEG
    pnl=html.Span(f"{total_pnl:+.2f} USDT",style={"color":pnl_color,"fontWeight":"800"})

    eta=max(0,int(snap.get("next_scan_at",0)-time.time()))
    hot=", ".join(snap.get("hot_coins",[])[:3]) or "–"

    o=pd.DataFrame(snap.get("open_trades") or [])
    c=pd.DataFrame(snap.get("closed_trades") or [])
    if not o.empty: o=o.tail(5)
    if not c.empty: c=c.tail(5)
    def cols(df,fallback): return [{"name":i,"id":i} for i in (df.columns if not df.empty else fallback)]
    cols_o=cols(o,["id","market","symbol","side","entry_price","qty","leverage","tp","sl","timestamp","margin_used"])
    cols_c=cols(c,["id","market","symbol","side","entry_price","exit_price","qty","leverage","pnl","timestamp","margin_used"])

    perf=html.Div([
        html.Div(f"Closed Trades: {len(c) if not c.empty else 0}",style={"color":TXT}),
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

    return (status,btc,daycap_text,pnl,str(eta),hot,
            (o.to_dict("records") if not o.empty else []),cols_o,
            (c.to_dict("records") if not c.empty else []),cols_c,
            perf,learn)

# === Start ===
if __name__=="__main__":
    app.run(host="0.0.0.0",port=8050,debug=False)
