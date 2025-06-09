from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from functools import wraps
from db import get_connection
import logging

# Blueprint tanımı
paket_admin_bp = Blueprint("paket_admin", __name__)

# Özel decorator for admin yetkisi kontrolü
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        claims = get_jwt()
        if claims.get("rol", "").lower() != "admin":
            logging.warning(f"Yetkisiz erişim denemesi: {get_jwt_identity()}")
            return jsonify({"hata": "Yetkisiz erişim"}), 403
        return f(*args, **kwargs)
    return decorated_function

# Yardımcı fonksiyon: Admin kontrolü
def is_admin(kullanici):
    if isinstance(kullanici, dict) and kullanici.get("rol") == "admin":
        return True
    elif isinstance(kullanici, str):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT Rol FROM Kullanicilar WHERE KullaniciAdi = ?", (kullanici,))
            row = cursor.fetchone()
            return row and row.Rol.lower() == "admin"
    return False

# ✅ Yeni paket ekleme
@paket_admin_bp.route("/ekle", methods=["POST"])
@jwt_required()
@admin_required
def paket_ekle():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"hata": "Geçersiz veri"}), 400

        # Zorunlu alan kontrolü
        required_fields = ["PaketAdi", "CagriSayisi", "Fiyat", "SureAy"]
        if any(field not in data for field in required_fields):
            return jsonify({"hata": "Tüm zorunlu alanları doldurun"}), 400

        # Veri tipi kontrolleri
        validations = [
            ("PaketAdi", str, lambda x: x.strip()),
            ("CagriSayisi", int, lambda x: x > 0),
            ("Fiyat", (int, float), lambda x: x > 0),
            ("SureAy", int, lambda x: x > 0)
        ]

        for field, types, validator in validations:
            if not isinstance(data[field], types) or not validator(data[field]):
                return jsonify({"hata": f"Geçersiz {field} değeri"}), 400

        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Paket adı benzersiz mi kontrolü
            cursor.execute("SELECT 1 FROM Paketler WHERE PaketAdi = ?", (data["PaketAdi"],))
            if cursor.fetchone():
                return jsonify({"hata": "Bu paket adı zaten kullanılıyor"}), 400

            # Yeni paket ekleme
            cursor.execute("""
                INSERT INTO Paketler (PaketAdi, CagriSayisi, Fiyat, SureAy, Aciklama, Aktif)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (
                data["PaketAdi"],
                data["CagriSayisi"],
                data["Fiyat"],
                data["SureAy"],
                data.get("Aciklama", "")
            ))
            conn.commit()

        return jsonify({"mesaj": "Paket başarıyla eklendi", "paket_id": cursor.lastrowid}), 201

    except Exception as e:
        logging.error(f"Paket ekleme hatası: {str(e)}", exc_info=True)
        return jsonify({"hata": "Sunucu hatası"}), 500

# ✅ Paket güncelleme
@paket_admin_bp.route("/guncelle/<int:paket_id>", methods=["PUT"])
@jwt_required()
@admin_required
def paket_guncelle(paket_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"hata": "Geçersiz veri"}), 400

        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Paket varlık kontrolü
            cursor.execute("SELECT 1 FROM Paketler WHERE PaketID = ?", (paket_id,))
            if not cursor.fetchone():
                return jsonify({"hata": "Paket bulunamadı"}), 404

            # Güncelleme işlemi
            cursor.execute("""
                UPDATE Paketler SET
                    PaketAdi = ?,
                    CagriSayisi = ?,
                    Fiyat = ?,
                    SureAy = ?,
                    Aciklama = ?
                WHERE PaketID = ?
            """, (
                data.get("PaketAdi"),
                data.get("CagriSayisi"),
                data.get("Fiyat"),
                data.get("SureAy"),
                data.get("Aciklama", ""),
                paket_id
            ))
            conn.commit()

        return jsonify({"mesaj": "Paket başarıyla güncellendi"}), 200

    except Exception as e:
        logging.error(f"Paket güncelleme hatası: {str(e)}", exc_info=True)
        return jsonify({"hata": "Sunucu hatası"}), 500

# ✅ Paket pasifleştirme
@paket_admin_bp.route("/pasif-yap/<int:paket_id>", methods=["PATCH"])
@jwt_required()
@admin_required
def paket_pasif_yap(paket_id):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE Paketler SET Aktif = 0 WHERE PaketID = ?", (paket_id,))
            
            if cursor.rowcount == 0:
                return jsonify({"hata": "Paket bulunamadı"}), 404
                
            conn.commit()
        return jsonify({"mesaj": "Paket pasif hale getirildi"}), 200

    except Exception as e:
        logging.error(f"Paket pasifleştirme hatası: {str(e)}", exc_info=True)
        return jsonify({"hata": "Sunucu hatası"}), 500

# ✅ Aktif paket listesi
@paket_admin_bp.route("/liste", methods=["GET"])
@jwt_required()
@admin_required
def paket_listele():
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT PaketID, PaketAdi, CagriSayisi, Fiyat, SureAy, Aciklama
                FROM Paketler
                WHERE Aktif = 1
                ORDER BY PaketAdi
            """)
            
            kolonlar = [column[0] for column in cursor.description]
            paketler = [dict(zip(kolonlar, row)) for row in cursor.fetchall()]

        return jsonify(paketler), 200

    except Exception as e:
        logging.error(f"Paket listeleme hatası: {str(e)}", exc_info=True)
        return jsonify({"hata": "Sunucu hatası"}), 500