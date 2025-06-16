# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
from datetime import datetime
import base64

app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',  # Ganti dengan username MySQL Anda
    'password': '',  # Ganti dengan password MySQL Anda
    'database': 'skripsi'
}

def get_db_connection():
    """Establishes a database connection."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")
        return None

@app.route('/inventaris', methods=['POST'])
def add_inventaris():
    """Adds a new inventaris entry to the database."""
    data = request.json
    nama = data.get('nama')
    instansi = data.get('instansi')
    tanggal_masuk = datetime.strptime(data.get('suratMasuk'), '%Y-%m-%d').date() if data.get('suratMasuk') else None
    tanggal_ambil = datetime.strptime(data.get('pengambilan'), '%Y-%m-%d').date() if data.get('pengambilan') else None
    tanggal_kembali = datetime.strptime(data.get('pengembalian'), '%Y-%m-%d').date() if data.get('pengembalian') else None
    
    # --- Pastikan pengambilan nilai 'masa' dan 'status' dari JSON request ---
    masa_sewa = data.get('masa')
    keterangan_dp_lunas = data.get('status')
    # --- End penambahan ---

    bukti_base64 = data.get('bukti', {}).get('base64')
    bukti_name = data.get('bukti', {}).get('name')

    conn = get_db_connection()
    if conn is None:
        return jsonify({"message": "Database connection failed"}), 500

    cursor = conn.cursor()
    try:
        query = """
        INSERT INTO inventaris (nama, instansi, tanggal_surat_masuk, tanggal_pengambilan, tanggal_pengembalian, masa_sewa, keterangan_dp_lunas, bukti_pembayaran_base64, bukti_pembayaran_name)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (nama, instansi, tanggal_masuk, tanggal_ambil, tanggal_kembali, masa_sewa, keterangan_dp_lunas, bukti_base64, bukti_name))
        conn.commit()
        return jsonify({"message": "Inventaris data added successfully!"}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"message": f"Error: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/inventaris', methods=['GET'])
def get_inventaris():
    """Retrieves all inventaris entries from the database."""
    conn = get_db_connection()
    if conn is None:
        return jsonify({"message": "Database connection failed"}), 500

    cursor = conn.cursor(dictionary=True) # Return results as dictionaries
    try:
        query = "SELECT id, nama, instansi, tanggal_surat_masuk, tanggal_pengambilan, tanggal_pengembalian, masa_sewa, keterangan_dp_lunas, bukti_pembayaran_base64, bukti_pembayaran_name FROM inventaris"
        cursor.execute(query)
        inventaris_list = []
        for row in cursor.fetchall():
            # Format tanggal menjadi string YYYY-MM-DD
            row['tanggal_surat_masuk'] = row['tanggal_surat_masuk'].strftime('%Y-%m-%d') if row['tanggal_surat_masuk'] else None
            row['tanggal_pengambilan'] = row['tanggal_pengambilan'].strftime('%Y-%m-%d') if row['tanggal_pengambilan'] else None
            row['tanggal_pengembalian'] = row['tanggal_pengembalian'].strftime('%Y-%m-%d') if row['tanggal_pengembalian'] else None
            
            # --- Perubahan utama: Petakan nama kolom database ke nama properti yang diharapkan frontend ---
            row['masa'] = row['masa_sewa']
            row['status'] = row['keterangan_dp_lunas']
            # --- End perubahan ---

            # Reconstruct bukti object for frontend
            bukti = None
            if row['bukti_pembayaran_base64'] and row['bukti_pembayaran_name']:
                bukti = {
                    'base64': row['bukti_pembayaran_base64'],
                    'name': row['bukti_pembayaran_name']
                }
            row['bukti'] = bukti
            
            # Hapus kolom asli dari objek yang dikembalikan ke frontend
            del row['masa_sewa']
            del row['keterangan_dp_lunas']
            del row['bukti_pembayaran_base64']
            del row['bukti_pembayaran_name']
            
            inventaris_list.append(row)
        return jsonify(inventaris_list), 200
    except mysql.connector.Error as err:
        return jsonify({"message": f"Error: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/inventaris/<int:inventaris_id>', methods=['PUT'])
def update_inventaris(inventaris_id):
    """Updates an existing inventaris entry in the database."""
    data = request.json
    nama = data.get('nama')
    instansi = data.get('instansi')
    tanggal_masuk = datetime.strptime(data.get('suratMasuk'), '%Y-%m-%d').date() if data.get('suratMasuk') else None
    tanggal_ambil = datetime.strptime(data.get('pengambilan'), '%Y-%m-%d').date() if data.get('pengambilan') else None
    tanggal_kembali = datetime.strptime(data.get('pengembalian'), '%Y-%m-%d').date() if data.get('pengembalian') else None
    
    # --- Pastikan pengambilan nilai 'masa' dan 'status' dari JSON request ---
    masa_sewa = data.get('masa')
    keterangan_dp_lunas = data.get('status')
    # --- End penambahan ---

    bukti_base64 = data.get('bukti', {}).get('base64') if data.get('bukti') else None
    bukti_name = data.get('bukti', {}).get('name') if data.get('bukti') else None

    conn = get_db_connection()
    if conn is None:
        return jsonify({"message": "Database connection failed"}), 500

    cursor = conn.cursor()
    try:
        query = """
        UPDATE inventaris
        SET nama = %s, instansi = %s, tanggal_surat_masuk = %s, tanggal_pengambilan = %s, tanggal_pengembalian = %s, masa_sewa = %s, keterangan_dp_lunas = %s, bukti_pembayaran_base64 = %s, bukti_pembayaran_name = %s
        WHERE id = %s
        """
        cursor.execute(query, (nama, instansi, tanggal_masuk, tanggal_ambil, tanggal_kembali, masa_sewa, keterangan_dp_lunas, bukti_base64, bukti_name, inventaris_id))
        conn.commit()
        if cursor.rowcount > 0:
            return jsonify({"message": "Inventaris data updated successfully!"}), 200
        else:
            return jsonify({"message": "Inventaris data not found."}), 404
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"message": f"Error: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/inventaris/<int:inventaris_id>', methods=['DELETE'])
def delete_inventaris(inventaris_id):
    """Deletes an inventaris entry from the database."""
    conn = get_db_connection()
    if conn is None:
        return jsonify({"message": "Database connection failed"}), 500

    cursor = conn.cursor()
    try:
        query = "DELETE FROM inventaris WHERE id = %s"
        cursor.execute(query, (inventaris_id,))
        conn.commit()
        if cursor.rowcount > 0:
            return jsonify({"message": "Inventaris data deleted successfully!"}), 200
        else:
            return jsonify({"message": "Inventaris data not found."}), 404
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"message": f"Error: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    app.run(debug=True, port=5000)