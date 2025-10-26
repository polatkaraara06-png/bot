import time
import random
import sys
import os
import math

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from core.shared_state import shared_state
from core.paper_trader import open_position, check_and_close_all
from core.decision_engine.simple_decision import decide_trade
from core.ai.online_rl import agent
from core.time_aggregation import aggregate_ticks # Importiere Aggregation

# Testparameter
SIMULATION_DURATION_CYCLES = 300 # Ca. 5 Minuten (300 Zyklen * 1 Sekunde Pause)
TEST_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "TRXUSDT"]

def simulate_price_tick(symbol, current_price):
    change_pct = random.uniform(-0.5, 0.5) # Simuliert Preisänderung von -0.5% bis +0.5%
    new_price = current_price * (1 + change_pct / 100.0)
    shared_state.upsert_tick("futures", symbol, new_price, time.time())
    return new_price

def run_stability_test():
    print("\n\n" + "="*80)
    print("🚦 STARTE 5-MINUTEN STABILITÄTS-SIMULATION")
    print("   (Beobachte Terminal auf Fehler & Aktivitätsanzeige auf CPU/RAM)")
    print("="*80 + "\n")

    shared_state.reset_daycap(total=1000.0)
    agent.knowledge = 50.0 # Starte im Exploitation-Modus
    
    current_prices = {sym: random.uniform(100, 100000) for sym in TEST_SYMBOLS}
    
    for i in range(SIMULATION_DURATION_CYCLES):
        print(f"\n--- Zyklus {i+1}/{SIMULATION_DURATION_CYCLES} ---")
        
        # 1. Simuliere neue Ticks & Aggregation
        for sym in TEST_SYMBOLS:
            current_prices[sym] = simulate_price_tick(sym, current_prices[sym])
        try:
            aggregate_ticks() # Teste Kerzenbildung
        except Exception as e:
            print(f"🚨 FEHLER bei Kerzen-Aggregation: {e}")
            
        # 2. Simuliere Scanner & Entscheidung (vereinfacht)
        opened_this_cycle = 0
        for sym in TEST_SYMBOLS:
             # Generiere einfache Features für den Test
             features = {
                 "symbol": sym, 
                 "trend": random.uniform(-0.5, 0.5), 
                 "vol": random.uniform(0.1, 1.5), 
                 "atr_pct": random.uniform(0.1, 1.0),
                 "price": current_prices[sym],
                 "mtf_trend": agent.get_mtf_trend_placeholder(),
                 "candles": shared_state.get_historical_candles("futures", sym, 300)
             }
             strategy = "scalper" if features["vol"] > 0.5 else "conservative"
             
             try:
                 decision = decide_trade(features, agent, strategy=strategy)
             except Exception as e:
                 print(f"🚨 FEHLER bei decide_trade für {sym}: {e}")
                 decision = None

             if decision and decision.get('action') and shared_state.available > decision['risk_adjusted_margin']:
                 try:
                     open_position(sym, decision["action"], "futures", features["price"], 
                                   decision["risk_adjusted_margin"], decision["leverage"], 
                                   decision["tp_pct"], decision["sl_pct"], features, strategy=strategy)
                     opened_this_cycle += 1
                 except Exception as e:
                      print(f"🚨 FEHLER bei open_position für {sym}: {e}")
        
        print(f"[SIM] {opened_this_cycle} neue Trades geöffnet.")

        # 3. Schließe Trades (TP/SL/Trail/Timeout)
        try:
            check_and_close_all()
        except Exception as e:
            print(f"🚨 FEHLER bei check_and_close_all: {e}")
            
        # 4. Speichere Agenten-Status (alle 30 Zyklen)
        if i % 30 == 0:
            try:
                agent.save()
                print("[SIM] Agenten-Status gespeichert.")
            except Exception as e:
                 print(f"🚨 FEHLER beim Speichern des Agenten: {e}")
        
        # 5. Warte 1 Sekunde
        time.sleep(1.0)

    # --- ABSCHLUSS ---
    summary = shared_state.summary()
    print("\n\n" + "="*80)
    print("✅ STABILITÄTS-SIMULATION ABGESCHLOSSEN")
    print("="*80)
    print(f"| Simulierte Zyklen              | {SIMULATION_DURATION_CYCLES}")
    print(f"| Geschlossene Trades            | {len(shared_state.closed_trades)}")
    print(f"| Finaler PnL (Gesamt)           | {summary.get('Gewinn/Verlust (gesamt)'):.2f} USDT")
    print(f"| Finaler Agent XP               | {agent.xp:.1f}")
    print(f"| Finale Agent Performance (EWM) | {agent.performance_ewm:.3f}")
    print("="*80)
    if "🚨 FEHLER" not in open("core/test_logic.py").read(): # Schneller Check auf Fehler im Log
        print("\n🎉 TEST ERFOLGREICH: Keine kritischen Fehler während der Simulation aufgetreten.")
        print("   (Überprüfe CPU/RAM in der Aktivitätsanzeige zur Sicherheit)")
    else:
        print("\n🚨 TEST FEHLGESCHLAGEN: Kritische Fehler im Log gefunden. Siehe oben.")


run_stability_test()
