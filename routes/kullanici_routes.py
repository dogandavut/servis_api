from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
import pyodbc
import hashlib
from config import DB_CONFIG

kullanici_bp = Blueprint("kullanici_bp", __name__)

def get_db_connection():
    conn_str = (
        f"DRIVER={{{DB_CONFIG['driver']}}};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"UID={DB_CONFIG['username']};"
        f"PWD={DB_CONFIG['password']}"
    )
    return pyodbc.connect(conn_str)

# 🔐 SHA256 ile şifreyi hashle
def hash_sifre(sifre):
    return hashlib.sha256(sifre.encode('utf-8')).hexdigest()

# ✅ Giriş (Login) endpoint
from flask_jwt_extended import create_access_token

@kullanici_bp.route("/giris", methods=["POST"])
def kullanici_giris():
    try:
        data = request.get_json()
        kullanici_adi = data.get("KullaniciAdi")
        sifre = data.get("Sifre")

        if not kullanici_adi or not sifre:
            return jsonify({"hata": "Kullanıcı adı ve şifre gerekli"}), 400

        sifre_hash = hash_sifre(sifre)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT KullaniciID, AdSoyad, Rol
            FROM Kullanicilar
            WHERE KullaniciAdi = ? AND SifreHash = ? AND Aktif = 1
        """, (kullanici_adi, sifre_hash))

        user = cursor.fetchone()
        conn.close()

        if user:
            access_token = create_access_token(identity=kullanici_adi, additional_claims={"rol": user.Rol})

            return jsonify({
                "basarili": True,
                "KullaniciID": user.KullaniciID,
                "AdSoyad": user.AdSoyad,
                "Rol": user.Rol,
                "token": access_token
            }), 200

        else:
            return jsonify({"basarili": False, "hata": "Geçersiz giriş"}), 401

    except Exception as e:
        return jsonify({"hata": str(e)}), 500

# ➕ Yeni kullanıcı ekleme (opsiyonel - sadece admin kullanır)
@kullanici_bp.route("/ekle", methods=["POST"])
def kullanici_ekle():
    try:
        data = request.get_json()
        kullanici_adi = data["KullaniciAdi"]
        sifre = data["Sifre"]
        adsoyad = data.get("AdSoyad", "")
        rol = data.get("Rol", "Teknik")

        sifre_hash = hash_sifre(sifre)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Kullanicilar (KullaniciAdi, SifreHash, AdSoyad, Rol, Aktif)
            VALUES (?, ?, ?, ?, 1)
        """, (kullanici_adi, sifre_hash, adsoyad, rol))
        conn.commit()
        conn.close()

        return jsonify({"mesaj": "Kullanıcı başarıyla eklendi"}), 201

    except Exception as e:
        return jsonify({"hata": str(e)}), 500
