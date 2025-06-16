import os
from flask import Flask, request, jsonify, send_file
import mysql.connector
from flask_cors import CORS
from werkzeug.utils import secure_filename # Untuk mengamankan nama file

app = Flask(__name__)
CORS(app) # Mengaktifkan CORS untuk mengizinkan permintaan dari frontend Anda

# Konfigurasi Database MySQL
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root', # Ganti dengan username MySQL Anda
    'password': '', # Ganti dengan password MySQL Anda
    'database': 'skripsi'
}

# Direktori untuk menyimpan file yang diupload
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Fungsi untuk mendapatkan koneksi database
def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")
        return None

# --- Endpoints API untuk Persuratan ---

# 1. Menambahkan Data Persuratan Baru (POST)
@app.route('/persuratan', methods=['POST'])
def add_persuratan():
    data = request.json
    tanggal_masuk = data.get('tanggalMasuk')
    jenis_surat = data.get('jenisSurat')
    nama = data.get('nama')
    instansi = data.get('instansi')
    tanggal_approve = data.get('tanggalApprove') # Akan jadi '-' atau tanggal
    aktivitas = data.get('aktivitas') # Akan jadi '-'

    conn = get_db_connection()
    if conn is None:
        return jsonify({"message": "Database connection failed"}), 500
    cursor = conn.cursor()
    try:
        query = """
        INSERT INTO persuratan (tanggal_masuk, jenis_surat, nama, instansi, tanggal_approve, aktivitas)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        # Konversi '-' menjadi None untuk tanggal_approve jika itu adalah string '-'
        tanggal_approve_db = None if tanggal_approve == '-' else tanggal_approve
        aktivitas_db = None if aktivitas == '-' else aktivitas

        cursor.execute(query, (tanggal_masuk, jenis_surat, nama, instansi, tanggal_approve_db, aktivitas_db))
        conn.commit()
        return jsonify({"message": "Data persuratan berhasil disimpan!"}), 201
    except mysql.connector.Error as err:
        print(f"Error saving data: {err}")
        return jsonify({"message": f"Error saving data: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# 2. Mendapatkan Semua Data Persuratan (GET)
@app.route('/persuratan', methods=['GET'])
def get_persuratan():
    conn = get_db_connection()
    if conn is None:
        return jsonify({"message": "Database connection failed"}), 500
    cursor = conn.cursor(dictionary=True) # Mengambil hasil sebagai dictionary
    try:
        cursor.execute("SELECT id, tanggal_masuk, jenis_surat, nama, instansi, tanggal_approve, aktivitas FROM persuratan ORDER BY tanggal_masuk DESC")
        data = cursor.fetchall()
        
        # Format tanggal agar konsisten jika diperlukan, meskipun MySQL DATE sudah YYYY-MM-DD
        for row in data:
            if row['tanggal_masuk']:
                row['tanggal_masuk'] = row['tanggal_masuk'].strftime('%Y-%m-%d')
            if row['tanggal_approve']:
                row['tanggal_approve'] = row['tanggal_approve'].strftime('%Y-%m-%d')
            else:
                row['tanggal_approve'] = '-' # Jika None di DB, tampilkan '-'
            if not row['aktivitas']:
                row['aktivitas'] = '-' # Jika None di DB, tampilkan '-'

        return jsonify(data), 200
    except mysql.connector.Error as err:
        print(f"Error fetching data: {err}")
        return jsonify({"message": f"Error fetching data: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# 3. Memperbarui Data Persuratan (PUT)
@app.route('/persuratan/<int:persuratan_id>', methods=['PUT'])
def update_persuratan(persuratan_id):
    # Menggunakan request.form karena ada file upload
    tanggal_masuk = request.form.get('tanggalMasuk')
    jenis_surat = request.form.get('jenisSurat')
    nama = request.form.get('nama')
    instansi = request.form.get('instansi')
    tanggal_approve_str = request.form.get('tanggalApprove')
    aktivitas_filename_from_form = request.form.get('aktivitasFilename') # Nama file dari form (bisa yg lama atau baru)
    remove_existing_file_flag = request.form.get('removeExistingFile') == 'true'
    
    # Konversi '-' menjadi None untuk tanggal_approve
    tanggal_approve_db = None if tanggal_approve_str == '-' else tanggal_approve_str

    conn = get_db_connection()
    if conn is None:
        return jsonify({"message": "Database connection failed"}), 500
    cursor = conn.cursor()

    old_aktivitas_filename = None
    try:
        # Dapatkan nama file aktivitas yang lama (jika ada) untuk dihapus
        cursor.execute("SELECT aktivitas FROM persuratan WHERE id = %s", (persuratan_id,))
        result = cursor.fetchone()
        if result:
            old_aktivitas_filename = result[0]

        aktivitas_db = None

        if remove_existing_file_flag:
            # Jika user memilih '-', set aktivitas ke None dan hapus file fisik
            aktivitas_db = None
            if old_aktivitas_filename and old_aktivitas_filename != '-':
                file_path_to_delete = os.path.join(app.config['UPLOAD_FOLDER'], old_aktivitas_filename)
                if os.path.exists(file_path_to_delete):
                    os.remove(file_path_to_delete)
                    print(f"Deleted old file: {file_path_to_delete}")
                else:
                    print(f"Old file not found for deletion: {file_path_to_delete}")
        elif 'aktivitasFile' in request.files:
            # Jika ada file baru diupload
            file = request.files['aktivitasFile']
            if file.filename != '':
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                aktivitas_db = filename # Simpan nama file baru di DB

                # Hapus file lama jika ada dan berbeda dengan yang baru
                if old_aktivitas_filename and old_aktivitas_filename != '-' and old_aktivitas_filename != filename:
                    file_path_to_delete = os.path.join(app.config['UPLOAD_FOLDER'], old_aktivitas_filename)
                    if os.path.exists(file_path_to_delete):
                        os.remove(file_path_to_delete)
                        print(f"Deleted old file: {file_path_to_delete}")
                    else:
                        print(f"Old file not found for deletion: {file_path_to_delete}")
            else:
                # Jika input file kosong, gunakan nama file aktivitas yang ada sebelumnya (jika ada)
                aktivitas_db = old_aktivitas_filename if old_aktivitas_filename and old_aktivitas_filename != '-' else None
        else:
            # Jika tidak ada file baru diupload dan tidak ada instruksi untuk menghapus,
            # gunakan nama file aktivitas yang ada sebelumnya dari database
            aktivitas_db = old_aktivitas_filename if old_aktivitas_filename and old_aktivitas_filename != '-' else None


        query = """
        UPDATE persuratan
        SET tanggal_masuk = %s, jenis_surat = %s, nama = %s, instansi = %s, tanggal_approve = %s, aktivitas = %s
        WHERE id = %s
        """
        cursor.execute(query, (tanggal_masuk, jenis_surat, nama, instansi, tanggal_approve_db, aktivitas_db, persuratan_id))
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "Data not found or no changes made"}), 404
        return jsonify({"message": "Data persuratan berhasil diperbarui!"}), 200
    except mysql.connector.Error as err:
        print(f"Error updating data: {err}")
        return jsonify({"message": f"Error updating data: {err}"}), 500
    except Exception as e:
        print(f"Unexpected error during update: {e}")
        return jsonify({"message": f"Unexpected error: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

# 4. Menghapus Data Persuratan (DELETE)
@app.route('/persuratan/<int:persuratan_id>', methods=['DELETE'])
def delete_persuratan(persuratan_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({"message": "Database connection failed"}), 500
    cursor = conn.cursor()

    try:
        # Dapatkan nama file aktivitas yang terkait sebelum dihapus
        cursor.execute("SELECT aktivitas FROM persuratan WHERE id = %s", (persuratan_id,))
        result = cursor.fetchone()
        file_to_delete = None
        if result and result[0]:
            file_to_delete = result[0]

        query = "DELETE FROM persuratan WHERE id = %s"
        cursor.execute(query, (persuratan_id,))
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "Data not found"}), 404
        
        # Hapus file fisik jika ada
        if file_to_delete:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_to_delete)
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Deleted associated file: {file_path}")
            else:
                print(f"Associated file not found: {file_path}")

        return jsonify({"message": "Data persuratan berhasil dihapus!"}), 200
    except mysql.connector.Error as err:
        print(f"Error deleting data: {err}")
        return jsonify({"message": f"Error deleting data: {err}"}), 500
    except Exception as e:
        print(f"Unexpected error during deletion: {e}")
        return jsonify({"message": f"Unexpected error: {e}"}), 500
    finally:
        cursor.close()
        conn.close()

# 5. Mengunduh File Aktivitas (GET)
@app.route('/download_file/<int:persuratan_id>', methods=['GET'])
def download_file(persuratan_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({"message": "Database connection failed"}), 500
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT aktivitas FROM persuratan WHERE id = %s", (persuratan_id,))
        result = cursor.fetchone()
        
        if result and result[0]:
            filename = result[0]
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            if os.path.exists(file_path):
                return send_file(file_path, as_attachment=True, download_name=filename)
            else:
                return jsonify({"message": "File not found on server."}), 404
        else:
            return jsonify({"message": "No file associated with this record."}), 404
    except Exception as e:
        print(f"Error during file download: {e}")
        return jsonify({"message": f"Error downloading file: {e}"}), 500
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    # Untuk menjalankan Flask pada port 5000 dan dapat diakses dari luar localhost (debug=True hanya untuk pengembangan!)
    app.run(debug=True, host='127.0.0.1', port=5000)