from flask import Flask, render_template, request, jsonify
import psycopg2
import os
import datetime

app = Flask(__name__)

# 🔐 Connect to PostgreSQL (Neon) via environment variable
conn = psycopg2.connect(os.environ["PG_CONN_STRING"], sslmode='require')
cursor = conn.cursor()

# ✅ Opprett bookings-tabell hvis den ikke finnes
cursor.execute('''
CREATE TABLE IF NOT EXISTS bookings (
    id SERIAL PRIMARY KEY,
    week_iso TEXT NOT NULL,
    weekday TEXT NOT NULL,
    time TEXT NOT NULL,
    name TEXT NOT NULL,
    repeat BOOLEAN DEFAULT FALSE,
    pin TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
''')
conn.commit()

# 📅 Ukedager og tidspunkter
DAYS = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
    "Sunday"
]
TIMES = [f"{h:02d}:{m:02d}" for h in range(7, 19)
         for m in (0, 30)]  # 07:00–19:00


# 🏠 Hovedvisning
@app.route("/")
def index():
    today = datetime.date.today()
    week = request.args.get(
        "week") or f"{today.isocalendar()[0]}-W{today.isocalendar()[1]:02d}"

    cursor.execute(
        """
        SELECT id, weekday, time, name FROM bookings
        WHERE week_iso = %s OR repeat = true
    """, (week, ))
    rows = cursor.fetchall()

    bookings = {(d, t): {"id": i, "name": n} for i, d, t, n in rows}
    return render_template("index.html",
                           week=week,
                           days=DAYS,
                           times=TIMES,
                           bookings=bookings)


# 📥 Lag booking
@app.route("/book", methods=["POST"])
def book():
    data = request.get_json()
    print("📥 Booking payload received:", data)

    if not data:
        print("❌ No data in request")
        return jsonify({"status": "error", "message": "No JSON data"}), 400

    week = data["week"]
    name = data["name"]
    slots = data["slots"]  # list of {"day": "Monday", "time": "07:00"}
    repeat = str(data.get("repeat", "false")).lower() == "true"
    pin = data.get("pin", "")

    print(f"🔁 repeat={repeat} name={name} week={week} slots={slots}")

    for slot in slots:
        print("→ Inserting slot:", slot)
        cursor.execute(
            """
            INSERT INTO bookings (week_iso, weekday, time, name, repeat, pin)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (week, slot["day"], slot["time"], name, repeat, pin))

    conn.commit()
    print("✅ Booking committed to DB")
    return jsonify({"status": "ok"})


# 🗑 Slett booking (med PIN)
@app.route("/delete", methods=["POST"])
def delete():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "No JSON data"}), 400

    booking_id = data["id"]
    pin = data.get("pin", "")

    cursor.execute("SELECT pin FROM bookings WHERE id = %s", (booking_id, ))
    row = cursor.fetchone()

    if not row or row[0] != pin:
        return jsonify({"status": "error", "message": "Feil PIN"}), 403

    cursor.execute("DELETE FROM bookings WHERE id = %s", (booking_id, ))
    conn.commit()
    return jsonify({"status": "deleted"})


# ▶️ Start Flask-app i Render (riktig port)
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print("✅ Connected to:", os.environ.get("PG_CONN_STRING", "NO DB FOUND"))
    app.run(host="0.0.0.0", port=port)
