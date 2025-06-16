# app.py
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import mysql.connector
import os
import base64
from io import BytesIO
import bcrypt
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# === KONFIGURASI DATABASE ===
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'skripsi'
}

# === FOLDER UPLOAD ===
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# === HELPER FUNCTIONS ===
def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None

def detect_mime_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext == '.pdf':
        return 'application/pdf'
    elif ext in ['.doc', '.docx']:
        return 'application/msword'
    return 'application/octet-stream'

@app.route('/')
def index():
    return "Aplikasi backend UKM FKDK berjalan!"

# === ENDPOINT AUTH ===
# Register
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    if not all([username, email, password]):
        return jsonify({"error": "Lengkapi semua kolom."}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
    if cursor.fetchone():
        return jsonify({"error": "Username sudah digunakan."}), 409
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    cursor.execute("INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
                   (username, email, hashed.decode()))
    conn.commit()
    cursor.close(); conn.close()
    return jsonify({"message": "Registrasi berhasil!"}), 201

# Login
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if username == "fkdk" and password == "janissary":
        return jsonify({"message": "Login admin berhasil", "role": "admin"}), 200
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT username, password_hash FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    cursor.close(); conn.close()
    if user and bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
        return jsonify({"message": "Login berhasil", "role": "user"}), 200
    return jsonify({"error": "Login gagal"}), 401
    
@app.route('/submit_proposal', methods=['POST'])
def submit_proposal():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        tanggal_masuk = data.get('tanggalMasuk')
        departemen = data.get('departemen')
        nama_proker = data.get('namaProker')
        sekretaris = data.get('sekretaris')
        dokumen_name = data.get('dokumenName')
        dokumen_base64 = data.get('dokumenBase64')

        # Validasi minimal
        if not all([tanggal_masuk, departemen, nama_proker, sekretaris, dokumen_name, dokumen_base64]):
            return jsonify({"error": "Data proposal tidak lengkap. Pastikan semua field terisi, termasuk dokumen."}), 400

        # Hapus "data:mimetype;base64," prefix jika ada
        if ',' in dokumen_base64:
            dokumen_base64 = dokumen_base64.split(',')[1]

        conn = get_db_connection()
        cursor = conn.cursor()

        insert_query = """
        INSERT INTO Proposal (tanggalMasuk, departemen, namaProker, sekretaris, dokumenName, dokumenBase64)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (tanggal_masuk, departemen, nama_proker, sekretaris, dokumen_name, dokumen_base64))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"message": "Proposal berhasil dikirim!"}), 200

    except mysql.connector.Error as err:
        print(f"MySQL Error: {err}")
        return jsonify({"error": f"Kesalahan database: {err}"}), 500
    except Exception as e:
        print(f"Error submitting proposal: {e}")
        return jsonify({"error": f"Terjadi kesalahan internal: {e}"}), 500

@app.route('/get_proposals', methods=['GET'])
def get_proposals():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True) # Mengembalikan hasil sebagai dictionary
        cursor.execute("SELECT id, tanggalMasuk, departemen, namaProker, sekretaris, dokumenName, tanggalDisetujui, dokumenBase64 FROM Proposal")
        proposals = cursor.fetchall()
        cursor.close()
        conn.close()

        # Format tanggal agar sesuai dengan yang diharapkan oleh frontend
        for proposal in proposals:
            if proposal['tanggalMasuk']:
                proposal['tanggalMasuk'] = proposal['tanggalMasuk'].strftime('%Y-%m-%d')
            if proposal['tanggalDisetujui']:
                proposal['tanggalDisetujui'] = proposal['tanggalDisetujui'].strftime('%Y-%m-%d')
            else:
                proposal['tanggalDisetujui'] = '-' # Jika null, tampilkan '-'

        return jsonify(proposals), 200
    except mysql.connector.Error as err:
        print(f"MySQL Error: {err}")
        return jsonify({"error": f"Kesalahan database: {err}"}), 500
    except Exception as e:
        print(f"Error fetching proposals: {e}")
        return jsonify({"error": f"Terjadi kesalahan internal: {e}"}), 500

@app.route('/download_proposal/<int:proposal_id>', methods=['GET'])
def download_proposal(proposal_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT dokumenName, dokumenBase64 FROM Proposal WHERE id = %s", (proposal_id,))
        proposal = cursor.fetchone()
        cursor.close()
        conn.close()

        if proposal and proposal['dokumenBase64']:
            dokumen_name = proposal['dokumenName']
            dokumen_base64 = proposal['dokumenBase64']

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
        print(f"Error downloading proposal: {e}")
        return jsonify({"error": f"Terjadi kesalahan internal: {e}"}), 500

@app.route('/update_proposal/<int:proposal_id>', methods=['PUT'])
def update_proposal(proposal_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        tanggal_masuk = data.get('tanggalMasuk')
        departemen = data.get('departemen')
        nama_proker = data.get('namaProker')
        sekretaris = data.get('sekretaris')
        dokumen_name = data.get('dokumenName')
        dokumen_base64 = data.get('dokumenBase64')
        tanggal_disetujui = data.get('tanggalDisetujui')

        conn = get_db_connection()
        cursor = conn.cursor()

        update_query = """
        UPDATE Proposal
        SET tanggalMasuk = %s, departemen = %s, namaProker = %s, sekretaris = %s,
            dokumenName = %s, dokumenBase64 = %s, tanggalDisetujui = %s
        WHERE id = %s
        """
        cursor.execute(update_query, (
            tanggal_masuk, departemen, nama_proker, sekretaris,
            dokumen_name, dokumen_base64, tanggal_disetujui, proposal_id
        ))
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"error": "Proposal tidak ditemukan."}), 404

        cursor.close()
        conn.close()

        return jsonify({"message": "Proposal berhasil diupdate!"}), 200

    except mysql.connector.Error as err:
        print(f"MySQL Error: {err}")
        return jsonify({"error": f"Kesalahan database: {err}"}), 500
    except Exception as e:
        print(f"Error updating proposal: {e}")
        return jsonify({"error": f"Terjadi kesalahan internal: {e}"}), 500

@app.route('/delete_proposal/<int:proposal_id>', methods=['DELETE'])
def delete_proposal(proposal_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Proposal WHERE id = %s", (proposal_id,))
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"error": "Proposal tidak ditemukan."}), 404

        cursor.close()
        conn.close()

        return jsonify({"message": "Proposal berhasil dihapus!"}), 200
    except mysql.connector.Error as err:
        print(f"MySQL Error: {err}")
        return jsonify({"error": f"Kesalahan database: {err}"}), 500
    except Exception as e:
        print(f"Error deleting proposal: {e}")
        return jsonify({"error": f"Terjadi kesalahan internal: {e}"}), 500

@app.route('/submit_lpj', methods=['POST'])
def submit_lpj():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        tanggal_masuk = data.get('tanggalMasuk')
        departemen = data.get('departemen')
        nama_proker = data.get('namaProker')
        sekretaris = data.get('sekretaris')
        dokumen_name = data.get('dokumenName')
        dokumen_base64 = data.get('dokumenBase64')

        # Validasi minimal
        if not all([tanggal_masuk, departemen, nama_proker, sekretaris, dokumen_name, dokumen_base64]):
            return jsonify({"error": "Data lpj tidak lengkap. Pastikan semua field terisi, termasuk dokumen."}), 400

        # Hapus "data:mimetype;base64," prefix jika ada
        if ',' in dokumen_base64:
            dokumen_base64 = dokumen_base64.split(',')[1]

        conn = get_db_connection()
        cursor = conn.cursor()

        insert_query = """
        INSERT INTO LPJ (tanggalMasuk, departemen, namaProker, sekretaris, dokumenName, dokumenBase64)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (tanggal_masuk, departemen, nama_proker, sekretaris, dokumen_name, dokumen_base64))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"message": "LPJ berhasil dikirim!"}), 200

    except mysql.connector.Error as err:
        print(f"MySQL Error: {err}")
        return jsonify({"error": f"Kesalahan database: {err}"}), 500
    except Exception as e:
        print(f"Error submitting lpj: {e}")
        return jsonify({"error": f"Terjadi kesalahan internal: {e}"}), 500

@app.route('/get_lpjs', methods=['GET'])
def get_lpjs():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True) # Mengembalikan hasil sebagai dictionary
        cursor.execute("SELECT id, tanggalMasuk, departemen, namaProker, sekretaris, dokumenName, tanggalDisetujui, dokumenBase64 FROM LPJ")
        lpjs = cursor.fetchall()
        cursor.close()
        conn.close()

        # Format tanggal agar sesuai dengan yang diharapkan oleh frontend
        for lpj in lpjs:
            if lpj['tanggalMasuk']:
                lpj['tanggalMasuk'] = lpj['tanggalMasuk'].strftime('%Y-%m-%d')
            if lpj['tanggalDisetujui']:
                lpj['tanggalDisetujui'] = lpj['tanggalDisetujui'].strftime('%Y-%m-%d')
            else:
                lpj['tanggalDisetujui'] = '-' # Jika null, tampilkan '-'

        return jsonify(lpjs), 200
    except mysql.connector.Error as err:
        print(f"MySQL Error: {err}")
        return jsonify({"error": f"Kesalahan database: {err}"}), 500
    except Exception as e:
        print(f"Error fetching lpjs: {e}")
        return jsonify({"error": f"Terjadi kesalahan internal: {e}"}), 500

@app.route('/download_lpj/<int:lpj_id>', methods=['GET'])
def download_lpj(lpj_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT dokumenName, dokumenBase64 FROM LPJ WHERE id = %s", (lpj_id,))
        lpj = cursor.fetchone()
        cursor.close()
        conn.close()

        if lpj and lpj['dokumenBase64']:
            dokumen_name = lpj['dokumenName']
            dokumen_base64 = lpj['dokumenBase64']

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
        print(f"Error downloading lpj: {e}")
        return jsonify({"error": f"Terjadi kesalahan internal: {e}"}), 500

@app.route('/update_lpj/<int:lpj_id>', methods=['PUT'])
def update_lpj(lpj_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        tanggal_masuk = data.get('tanggalMasuk')
        departemen = data.get('departemen')
        nama_proker = data.get('namaProker')
        sekretaris = data.get('sekretaris')
        dokumen_name = data.get('dokumenName')
        dokumen_base64 = data.get('dokumenBase64')
        tanggal_disetujui = data.get('tanggalDisetujui')

        conn = get_db_connection()
        cursor = conn.cursor()

        update_query = """
        UPDATE LPJ
        SET tanggalMasuk = %s, departemen = %s, namaProker = %s, sekretaris = %s,
            dokumenName = %s, dokumenBase64 = %s, tanggalDisetujui = %s
        WHERE id = %s
        """
        cursor.execute(update_query, (
            tanggal_masuk, departemen, nama_proker, sekretaris,
            dokumen_name, dokumen_base64, tanggal_disetujui, lpj_id
        ))
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"error": "LPJ tidak ditemukan."}), 404

        cursor.close()
        conn.close()

        return jsonify({"message": "LPJ berhasil diupdate!"}), 200

    except mysql.connector.Error as err:
        print(f"MySQL Error: {err}")
        return jsonify({"error": f"Kesalahan database: {err}"}), 500
    except Exception as e:
        print(f"Error updating lpj: {e}")
        return jsonify({"error": f"Terjadi kesalahan internal: {e}"}), 500

@app.route('/delete_lpj/<int:lpj_id>', methods=['DELETE'])
def delete_lpj(lpj_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM LPJ WHERE id = %s", (lpj_id,))
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"error": "LPJ tidak ditemukan."}), 404

        cursor.close()
        conn.close()

        return jsonify({"message": "LPJ berhasil dihapus!"}), 200
    except mysql.connector.Error as err:
        print(f"MySQL Error: {err}")
        return jsonify({"error": f"Kesalahan database: {err}"}), 500
    except Exception as e:
        print(f"Error deleting lpj: {e}")
        return jsonify({"error": f"Terjadi kesalahan internal: {e}"}), 500

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

@app.route('/submit_lra', methods=['POST'])
def submit_lra():
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
            return jsonify({"error": "Data LRA tidak lengkap. Pastikan semua field terisi, termasuk dokumen."}), 400

        # Hapus "data:mimetype;base64," prefix jika ada
        if ',' in dokumen_base64:
            dokumen_base64 = dokumen_base64.split(',')[1]

        conn = get_db_connection()
        cursor = conn.cursor()

        insert_query = """
        INSERT INTO LRA (tanggalMasuk, departemen, namaProker, bendahara, dokumenName, dokumenBase64)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (tanggal_masuk, departemen, nama_proker, bendahara, dokumen_name, dokumen_base64))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"message": "LRA berhasil dikirim!"}), 200

    except mysql.connector.Error as err:
        print(f"MySQL Error: {err}")
        return jsonify({"error": f"Kesalahan database: {err}"}), 500
    except Exception as e:
        print(f"Error submitting LRA: {e}")
        return jsonify({"error": f"Terjadi kesalahan internal: {e}"}), 500

@app.route('/get_lras', methods=['GET'])
def get_lras():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True) # Mengembalikan hasil sebagai dictionary
        cursor.execute("SELECT id, tanggalMasuk, departemen, namaProker, bendahara, dokumenName, tanggalDisetujui, dokumenBase64 FROM LRA")
        lras = cursor.fetchall()
        cursor.close()
        conn.close()

        # Format tanggal agar sesuai dengan yang diharapkan oleh frontend
        for lra in lras:
            if lra['tanggalMasuk']:
                lra['tanggalMasuk'] = lra['tanggalMasuk'].strftime('%Y-%m-%d')
            if lra['tanggalDisetujui']:
                lra['tanggalDisetujui'] = lra['tanggalDisetujui'].strftime('%Y-%m-%d')
            else:
                lra['tanggalDisetujui'] = '-' # Jika null, tampilkan '-'

        return jsonify(lras), 200
    except mysql.connector.Error as err:
        print(f"MySQL Error: {err}")
        return jsonify({"error": f"Kesalahan database: {err}"}), 500
    except Exception as e:
        print(f"Error fetching lras: {e}")
        return jsonify({"error": f"Terjadi kesalahan internal: {e}"}), 500

@app.route('/download_lra/<int:lra_id>', methods=['GET'])
def download_lra(lra_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT dokumenName, dokumenBase64 FROM LRA WHERE id = %s", (lra_id,))
        lra = cursor.fetchone()
        cursor.close()
        conn.close()

        if lra and lra['dokumenBase64']:
            dokumen_name = lra['dokumenName']
            dokumen_base64 = lra['dokumenBase64']

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
        print(f"Error downloading LRA: {e}")
        return jsonify({"error": f"Terjadi kesalahan internal: {e}"}), 500

@app.route('/update_lra/<int:lra_id>', methods=['PUT'])
def update_lra(lra_id):
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
        UPDATE LRA
        SET tanggalMasuk = %s, departemen = %s, namaProker = %s, bendahara = %s,
            dokumenName = %s, dokumenBase64 = %s, tanggalDisetujui = %s
        WHERE id = %s
        """
        cursor.execute(update_query, (
            tanggal_masuk, departemen, nama_proker, bendahara,
            dokumen_name, dokumen_base64, tanggal_disetujui, lra_id
        ))
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"error": "LRA tidak ditemukan."}), 404

        cursor.close()
        conn.close()

        return jsonify({"message": "LRA berhasil diupdate!"}), 200

    except mysql.connector.Error as err:
        print(f"MySQL Error: {err}")
        return jsonify({"error": f"Kesalahan database: {err}"}), 500
    except Exception as e:
        print(f"Error updating LRA: {e}")
        return jsonify({"error": f"Terjadi kesalahan internal: {e}"}), 500

@app.route('/delete_lra/<int:lra_id>', methods=['DELETE'])
def delete_lra(lra_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM LRA WHERE id = %s", (lra_id,))
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"error": "LRA tidak ditemukan."}), 404

        cursor.close()
        conn.close()

        return jsonify({"message": "LRA berhasil dihapus!"}), 200
    except mysql.connector.Error as err:
        print(f"MySQL Error: {err}")
        return jsonify({"error": f"Kesalahan database: {err}"}), 500
    except Exception as e:
        print(f"Error deleting LRA: {e}")
        return jsonify({"error": f"Terjadi kesalahan internal: {e}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)