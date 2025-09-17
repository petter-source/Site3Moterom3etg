from flask import Flask, render_template, request, jsonify
import psycopg2
import os
import datetime

app = Flask(__name__)

# 🔐 Connect to PostgreSQL
conn = psycopg2.connect(os.environ["PG_CONN_STRING"], sslmode='require')

# ✅ Opprett tabell om den ikke finnes
with conn.cursor() as cursor:
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

# 📅 Ukedager og tider
DAYS = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
    "Sunday"
]
TIMES = [f"{h:02d}:{m:02d}" for h in range(7, 19)
         for m in (0, 30)]  # 07:00–19:00


# 🌐 Forside
@app.route("/")
def index():
    today = datetime.date.today()
    week = request.args.get(
        "week") or f"{today.isocalendar()[0]}-W{today.isocalendar()[1]:02d}"

    with conn.cursor() as cursor:
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


# ➕ Lag booking
@app.route("/book", methods=["POST"])
def book():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "No JSON data"}), 400

    week = data["week"]
    name = data["name"]
    slots = data["slots"]
    repeat = str(data.get("repeat", "false")).lower() == "true"
    pin = data.get("pin", "")

    with conn.cursor() as cursor:
        for slot in slots:
            cursor.execute(
                """
                INSERT INTO bookings (week_iso, weekday, time, name, repeat, pin)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (week, slot["day"], slot["time"], name, repeat, pin))
        conn.commit()

    return jsonify({"status": "ok"})


# ❌ Slett booking med PIN
@app.route("/delete", methods=["POST"])
def delete():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "No JSON data"}), 400

    booking_id = data["id"]
    pin = data.get("pin", "")

    with conn.cursor() as cursor:
        cursor.execute("SELECT pin FROM bookings WHERE id = %s",
                       (booking_id, ))
        row = cursor.fetchone()

        if not row or row[0] != pin:
            return jsonify({"status": "error", "message": "Feil PIN"}), 403

        cursor.execute("DELETE FROM bookings WHERE id = %s", (booking_id, ))
        conn.commit()

    return jsonify({"status": "deleted"})


# 🤖 robots.txt
@app.route("/robots.txt")
def robots():
    return app.send_static_file("robots.txt")


# ▶️ Kjør server
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
