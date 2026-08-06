from flask import Flask, request, jsonify
import numpy as np
from collections import deque
from datetime import datetime

app = Flask(__name__)

# Store recent readings in memory (last 100)
history = deque(maxlen=100)


# ----- Endpoint 1: Analyse a single reading -----
@app.route("/analyse", methods=["POST"])
def analyse():
    """
    Receives sensor data from Node-RED, returns analysis.
    
    Node-RED sends: {"temperature_C": 23.5, "humidity_pct": 61.2, "light_lux": 350}
    Python returns:  {"status": "normal", "alerts": [], "stats": {...}}
    """
    data = request.get_json()
    
    # Store the reading
    data["timestamp"] = datetime.now().isoformat()
    history.append(data)
    
    # --- Analysis logic ---
    alerts = []
    
    # Temperature check
    temp = data.get("temperature_C", 0)
    if temp > 28:
        alerts.append(f"🔴 High temperature: {temp}°C")
    elif temp < 15:
        alerts.append(f"🔵 Low temperature: {temp}°C")
    
    # Humidity check
    hum = data.get("humidity_pct", 0)
    if hum > 80:
        alerts.append(f"💧 High humidity: {hum}%")
    
    # Compute statistics from recent history
    if len(history) >= 5:
        recent_temps = [r["temperature_C"] for r in history]
        stats = {
            "mean_temp": round(np.mean(recent_temps), 1),
            "std_temp": round(np.std(recent_temps), 2),
            "min_temp": round(min(recent_temps), 1),
            "max_temp": round(max(recent_temps), 1),
            "trend": "rising" if recent_temps[-1] > recent_temps[-5] else "falling",
            "readings_count": len(history)
        }
    else:
        stats = {"readings_count": len(history), "message": "Collecting data..."}
    
    return jsonify({
        "status": "alert" if alerts else "normal",
        "alerts": alerts,
        "stats": stats
    })


# ----- Endpoint 2: Get summary of all collected data -----
@app.route("/summary", methods=["GET"])
def summary():
    """Returns statistics of all collected readings."""
    if len(history) < 2:
        return jsonify({"message": "Not enough data yet", "count": len(history)})
    
    temps = [r["temperature_C"] for r in history]
    hums = [r["humidity_pct"] for r in history]
    
    return jsonify({
        "count": len(history),
        "temperature": {
            "mean": round(np.mean(temps), 1),
            "std": round(np.std(temps), 2),
            "min": round(min(temps), 1),
            "max": round(max(temps), 1)
        },
        "humidity": {
            "mean": round(np.mean(hums), 1),
            "std": round(np.std(hums), 2),
            "min": round(min(hums), 1),
            "max": round(max(hums), 1)
        }
    })


# ----- Endpoint 3: Anomaly detection -----
@app.route("/anomaly", methods=["POST"])
def anomaly_check():
    """
    Checks if the current reading is anomalous based on recent history.
    Uses the z-score method (same as in the Python workshop).
    """
    data = request.get_json()
    temp = data.get("temperature_C", 0)
    
    if len(history) < 10:
        return jsonify({"is_anomaly": False, "message": "Need more data (min 10 readings)"})
    
    recent_temps = [r["temperature_C"] for r in history]
    mean_t = np.mean(recent_temps)
    std_t = np.std(recent_temps)
    
    z_score = abs(temp - mean_t) / std_t if std_t > 0 else 0
    is_anomaly = z_score > 2
    
    return jsonify({
        "is_anomaly": is_anomaly,
        "z_score": round(z_score, 2),
        "threshold": 2.0,
        "current_temp": temp,
        "mean_temp": round(mean_t, 1)
    })


if __name__ == "__main__":
    print("=" * 50)
    print("  ML2303 Sensor Analytics API")
    print("  Endpoints:")
    print("    POST /analyse  — analyse a sensor reading")
    print("    GET  /summary  — get statistics summary")
    print("    POST /anomaly  — check for anomalies")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5050, debug=True)