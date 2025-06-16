from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import mysql.connector
import os
import base64
from io import BytesIO

app = Flask(__name__)
CORS(app) # Ini sangat penting untuk mengatasi masalah CORS

# Konfigurasi Database (Ganti dengan kredensial MySQL Anda)
MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '') # Ganti dengan password MySQL Anda
MYSQL_DB = os.getenv('MYSQL_DB', 'skripsi')

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
    return "Backend untuk aplikasi RAB berjalan!"

@app.route('/submit_rab', methods=['POST'])
def submit_rab():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        tanggal_masuk = data.get('tanggalMasuk')
        departemen = data.get('departemen')
        nama_proker = data.get('namaProker')
        bendahara = data.get('bendahara')
        dokumen_name = data.get('dokumenName')
        dokumen_base64 = data.get('dokumenBase64')

        # Validasi minimal
        if not all([tanggal_masuk, departemen, nama_proker, bendahara, dokumen_name, dokumen_base64]):
            return jsonify({"error": "Data RAB tidak lengkap. Pastikan semua field terisi, termasuk dokumen."}), 400

        # Hapus "data:mimetype;base64," prefix jika ada
        if ',' in dokumen_base64:
            dokumen_base64 = dokumen_base64.split(',')[1]

        conn = get_db_connection()
        cursor = conn.cursor()

        insert_query = """
        INSERT INTO RAB (tanggalMasuk, departemen, namaProker, bendahara, dokumenName, dokumenBase64)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (tanggal_masuk, departemen, nama_proker, bendahara, dokumen_name, dokumen_base64))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"message": "RAB berhasil dikirim!"}), 200

    except mysql.connector.Error as err:
        print(f"MySQL Error: {err}")
        return jsonify({"error": f"Kesalahan database: {err}"}), 500
    except Exception as e:
        print(f"Error submitting RAB: {e}")
        return jsonify({"error": f"Terjadi kesalahan internal: {e}"}), 500

@app.route('/get_rabs', methods=['GET'])
def get_rabs():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True) # Mengembalikan hasil sebagai dictionary
        cursor.execute("SELECT id, tanggalMasuk, departemen, namaProker, bendahara, dokumenName, tanggalDisetujui, dokumenBase64 FROM RAB")
        rabs = cursor.fetchall()
        cursor.close()
        conn.close()

        # Format tanggal agar sesuai dengan yang diharapkan oleh frontend
        for rab in rabs:
            if rab['tanggalMasuk']:
                rab['tanggalMasuk'] = rab['tanggalMasuk'].strftime('%Y-%m-%d')
            if rab['tanggalDisetujui']:
                rab['tanggalDisetujui'] = rab['tanggalDisetujui'].strftime('%Y-%m-%d')
            else:
                rab['tanggalDisetujui'] = '-' # Jika null, tampilkan '-'

        return jsonify(rabs), 200
    except mysql.connector.Error as err:
        print(f"MySQL Error: {err}")
        return jsonify({"error": f"Kesalahan database: {err}"}), 500
    except Exception as e:
        print(f"Error fetching rabs: {e}")
        return jsonify({"error": f"Terjadi kesalahan internal: {e}"}), 500

@app.route('/download_rab/<int:rab_id>', methods=['GET'])
def download_rab(rab_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT dokumenName, dokumenBase64 FROM RAB WHERE id = %s", (rab_id,))
        rab = cursor.fetchone()
        cursor.close()
        conn.close()

        if rab and rab['dokumenBase64']:
            dokumen_name = rab['dokumenName']
            dokumen_base64 = rab['dokumenBase64']

            # Deteksi MIME type dari base64 string
            # Ambil bagian sebelum koma (data:mimetype)
            mime_type_part = dokumen_base64.split(';')[0]
            if ':' in mime_type_part:
                mime_type = mime_type_part.split(':')[1]
            else:
                # Fallback atau tebak dari ekstensi jika tidak ada mimetype di base64 string
                ext = os.path.splitext(dokumen_name)[1].lower()
                if ext == '.pdf':
                    mime_type = 'application/pdf'
                elif ext == '.doc' or ext == '.docx':
                    mime_type = 'application/msword' # atau application/vnd.openxmlformats-officedocument.wordprocessingml.document
                else:
                    mime_type = 'application/octet-stream' # Default jika tidak diketahui

            # Hapus header data URI jika ada (misalnya 'data:application/pdf;base64,')
            if ',' in dokumen_base64:
                base64_data = dokumen_base64.split(',')[1]
            else:
                base64_data = dokumen_base64

            file_bytes = base64.b64decode(base64_data)
            return send_file(BytesIO(file_bytes),
                             mimetype=mime_type,
                             as_attachment=True,
                             download_name=dokumen_name)
        else:
            return jsonify({"error": "Dokumen tidak ditemukan atau data kosong."}), 404
    except mysql.connector.Error as err:
        print(f"MySQL Error: {err}")
        return jsonify({"error": f"Kesalahan database: {err}"}), 500
    except Exception as e:
        print(f"Error downloading RAB: {e}")
        return jsonify({"error": f"Terjadi kesalahan internal: {e}"}), 500

@app.route('/update_rab/<int:rab_id>', methods=['PUT'])
def update_rab(rab_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        tanggal_masuk = data.get('tanggalMasuk')
        departemen = data.get('departemen')
        nama_proker = data.get('namaProker')
        bendahara = data.get('bendahara')
        dokumen_name = data.get('dokumenName')
        dokumen_base64 = data.get('dokumenBase64')
        tanggal_disetujui = data.get('tanggalDisetujui')

        conn = get_db_connection()
        cursor = conn.cursor()

        update_query = """
        UPDATE RAB
        SET tanggalMasuk = %s, departemen = %s, namaProker = %s, bendahara = %s,
            dokumenName = %s, dokumenBase64 = %s, tanggalDisetujui = %s
        WHERE id = %s
        """
        cursor.execute(update_query, (
            tanggal_masuk, departemen, nama_proker, bendahara,
            dokumen_name, dokumen_base64, tanggal_disetujui, rab_id
        ))
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"error": "RAB tidak ditemukan."}), 404

        cursor.close()
        conn.close()

        return jsonify({"message": "RAB berhasil diupdate!"}), 200

    except mysql.connector.Error as err:
        print(f"MySQL Error: {err}")
        return jsonify({"error": f"Kesalahan database: {err}"}), 500
    except Exception as e:
        print(f"Error updating RAB: {e}")
        return jsonify({"error": f"Terjadi kesalahan internal: {e}"}), 500

@app.route('/delete_rab/<int:rab_id>', methods=['DELETE'])
def delete_rab(rab_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM RAB WHERE id = %s", (rab_id,))
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"error": "RAB tidak ditemukan."}), 404

        cursor.close()
        conn.close()

        return jsonify({"message": "RAB berhasil dihapus!"}), 200
    except mysql.connector.Error as err:
        print(f"MySQL Error: {err}")
        return jsonify({"error": f"Kesalahan database: {err}"}), 500
    except Exception as e:
        print(f"Error deleting RAB: {e}")
        return jsonify({"error": f"Terjadi kesalahan internal: {e}"}), 500

if __name__ == '__main__':
    app.run(debug=True) # debug=True akan memberikan pesan error lebih detail di terminal