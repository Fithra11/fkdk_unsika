# Auth.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import os
import bcrypt # Untuk hashing password

app = Flask(__name__)
CORS(app) # Sangat penting untuk mengatasi masalah CORS dari frontend

# Konfigurasi Database (Ganti dengan kredensial MySQL Anda)
MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '') # Ganti dengan password MySQL Anda
MYSQL_DB = os.getenv('MYSQL_DB', 'skripsi') # Anda bisa gunakan database yang sama, atau buat yang baru

def get_db_connection():
    conn = mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB
    )
    return conn

@app.route('/')
def home():
    return "Backend autentikasi berjalan!"

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        if not all([username, email, password]):
            return jsonify({"error": "Username, email, dan password harus diisi."}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Cek apakah username sudah ada
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "Username sudah digunakan, coba username lain!"}), 409 # Conflict

        # Hash password sebelum disimpan
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        insert_query = "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)"
        cursor.execute(insert_query, (username, email, hashed_password.decode('utf-8')))
        conn.commit()

        cursor.close()
        conn.close()
        return jsonify({"message": "Registrasi berhasil!"}), 201 # Created

    except mysql.connector.Error as err:
        print(f"MySQL Error: {err}")
        return jsonify({"error": f"Kesalahan database: {err}"}), 500
    except Exception as e:
        print(f"Error registering user: {e}")
        return jsonify({"error": f"Terjadi kesalahan internal: {e}"}), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        if not all([username, password]):
            return jsonify({"error": "Username dan password harus diisi."}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True) # Mengembalikan hasil sebagai dictionary

        # Cek untuk user 'fkdk' (admin hardcoded)
        if username == "fkdk" and password == "janissary":
            cursor.close()
            conn.close()
            return jsonify({"message": "Login berhasil!", "role": "admin", "username": username}), 200

        # Cek di database
        cursor.execute("SELECT username, password_hash FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            return jsonify({"message": "Login berhasil!", "role": "user", "username": username}), 200
        else:
            return jsonify({"error": "Username atau password salah!"}), 401 # Unauthorized

    except mysql.connector.Error as err:
        print(f"MySQL Error: {err}")
        return jsonify({"error": f"Kesalahan database: {err}"}), 500
    except Exception as e:
        print(f"Error logging in: {e}")
        return jsonify({"error": f"Terjadi kesalahan internal: {e}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001) # Gunakan port berbeda dari aplikasi RAB jika berjalan bersamaan