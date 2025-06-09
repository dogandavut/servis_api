from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import get_connection
from datetime import datetime

talep_bp = Blueprint("talep", __name__)

# ✅ Talep oluştur
@talep_bp.route("/", methods=["POST"])
@jwt_required()
def talep_ekle():
    try:
        data = request.get_json()
        if not data or "MusteriID" not in data or "Baslik" not in data:
            return jsonify({"hata": "MusteriID ve Baslik alanları zorunludur"}), 400

        musteri_id = data["MusteriID"]
        baslik = data["Baslik"]
        aciklama = data.get("Aciklama", "")

        # Veri türü doğrulaması
        if not isinstance(musteri_id, int):
            return jsonify({"hata": "MusteriID tam sayı olmalıdır"}), 400
        if not isinstance(baslik, str) or not isinstance(aciklama, str):
            return jsonify({"hata": "Baslik ve Aciklama metin olmalıdır"}), 400
        if not baslik.strip():
            return jsonify({"hata": "Baslik boş olamaz"}), 400

        # MusteriID'nin varlığını ve aktifliğini kontrol et
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM Musteriler WHERE MusteriID = ? AND Aktif = 1", (musteri_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({"hata": "Geçersiz veya aktif olmayan MusteriID"}), 400

        # Kullanıcı kimliğini al
        kullanici = get_jwt_identity()
        if isinstance(kullanici, dict) and "KullaniciID" in kullanici:
            kullanici_id = kullanici["KullaniciID"]
        elif isinstance(kullanici, str):
            # KullaniciAdi ile KullaniciID'yi bul
            cursor.execute("SELECT KullaniciID FROM Kullanicilar WHERE KullaniciAdi = ?", (kullanici,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return jsonify({"hata": f"Kullanıcı '{kullanici}' bulunamadı"}), 400
            kullanici_id = row.KullaniciID
        else:
            conn.close()
            return jsonify({"hata": "Geçersiz kullanıcı kimliği"}), 400

        # Talep ekle
        cursor.execute("""
            INSERT INTO Talepler (MusteriID, Baslik, Aciklama, OlusturanKullaniciID, Durum, TalepTarihi)
            VALUES (?, ?, ?, ?, 'Beklemede', ?)
        """, (
            musteri_id,
            baslik,
            aciklama,
            kullanici_id,
            datetime.now()
        ))
        conn.commit()
        conn.close()
        return jsonify({"durum": "Talep kaydedildi"}), 201
    except Exception as e:
        print(f"talep_ekle hatası: {str(e)}")  # Hata günlüğü
        return jsonify({"hata": str(e)}), 500

# ✅ Talep güncelle
@talep_bp.route("/guncelle/<int:talep_id>", methods=["PUT"])
@jwt_required()
def talep_guncelle(talep_id):
    try:
        data = request.get_json()
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE Talepler
            SET Baslik = ?, Aciklama = ?
            WHERE TalepID = ?
        """, (
            data.get("Baslik", ""),
            data.get("Aciklama", ""),
            talep_id
        ))
        if cursor.rowcount == 0:
            return jsonify({"hata": "Talep bulunamadı"}), 404

        conn.commit()
        conn.close()
        return jsonify({"mesaj": "Talep güncellendi"})
    except Exception as e:
        print(f"talep_guncelle hatası: {str(e)}")
        return jsonify({"hata": str(e)}), 500

# ✅ Talep sil
@talep_bp.route("/sil/<int:talep_id>", methods=["DELETE"])
@jwt_required()
def talep_sil(talep_id):

    claims = get_jwt()
    if claims.get("rol", "").lower() not in ["admin", "teknik"]:
        return jsonify({"hata": "Yetkisiz erişim"}), 403

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Talepler WHERE TalepID = ?", (talep_id,))
        if cursor.rowcount == 0:
            return jsonify({"hata": "Talep bulunamadı"}), 404

        conn.commit()
        conn.close()
        return jsonify({"mesaj": "Talep silindi"})
    except Exception as e:
        print(f"talep_sil hatası: {str(e)}")
        return jsonify({"hata": str(e)}), 500

# ✅ Talep durumunu değiştir
@talep_bp.route("/durum", methods=["POST"])
@jwt_required()
def talep_durum_degistir():
    try:
        data = request.get_json()
        talep_id = data["TalepID"]
        yeni_durum = data["Durum"]

        gecerli_durumlar = ["Beklemede", "Reddedildi", "Onaylandı", "Atandı", "Tamamlandı"]
        if yeni_durum not in gecerli_durumlar:
            return jsonify({"hata": "Geçersiz talep durumu"}), 400

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Talepler
            SET Durum = ?
            WHERE TalepID = ?
        """, (yeni_durum, talep_id))

        if cursor.rowcount == 0:
            return jsonify({"hata": "Talep bulunamadı"}), 404

        conn.commit()
        conn.close()
        return jsonify({"durum": f"Talep {talep_id} durumu '{yeni_durum}' olarak güncellendi"})
    except Exception as e:
        print(f"talep_durum_degistir hatası: {str(e)}")
        return jsonify({"hata": str(e)}), 500

# ✅ Talep detaylarını getir
@talep_bp.route("/detay/<int:talep_id>", methods=["GET"])
@jwt_required()
def talep_detay(talep_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT TalepID, MusteriID, Baslik, Aciklama, TalepTarihi, Durum, OlusturanKullaniciID
            FROM Talepler
            WHERE TalepID = ?
        """, (talep_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({"hata": "Talep bulunamadı"}), 404

        return jsonify({
            "TalepID": row.TalepID,
            "MusteriID": row.MusteriID,
            "Baslik": row.Baslik,
            "Aciklama": row.Aciklama,
            "TalepTarihi": row.TalepTarihi.strftime("%Y-%m-%d"),
            "Durum": row.Durum,
            "OlusturanKullaniciID": row.OlusturanKullaniciID
        })
    except Exception as e:
        print(f"talep_detay hatası: {str(e)}")
        return jsonify({"hata": str(e)}), 500

# ✅ Tüm talepleri listele
@talep_bp.route("/liste", methods=["GET"])
@jwt_required()
def talepleri_listele():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT TalepID, MusteriID, Baslik, Aciklama, TalepTarihi, Durum
            FROM Talepler
            ORDER BY TalepID DESC
        """)
        kolonlar = [col[0] for col in cursor.description]
        veriler = [dict(zip(kolonlar, row)) for row in cursor.fetchall()]
        conn.close()
        return jsonify(veriler)
    except Exception as e:
        print(f"talepleri_listele hatası: {str(e)}")
        return jsonify({"hata": str(e)}), 500

# ✅ Talep onayla
@talep_bp.route("/onayla/<int:talep_id>", methods=["PATCH"])
@jwt_required()
def talep_onayla(talep_id):

    claims = get_jwt()
    if claims.get("rol", "").lower() not in ["admin", "teknik"]:
        return jsonify({"hata": "Yetkisiz erişim"}), 403

    try:
        kullanici = get_jwt_identity()
        conn = get_connection()
        cursor = conn.cursor()

        if isinstance(kullanici, dict) and "KullaniciID" in kullanici:
            kullanici_id = kullanici["KullaniciID"]
        elif isinstance(kullanici, str):
            # KullaniciAdi ile KullaniciID'yi bul
            cursor.execute("SELECT KullaniciID FROM Kullanicilar WHERE KullaniciAdi = ?", (kullanici,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return jsonify({"hata": f"Kullanıcı '{kullanici}' bulunamadı"}), 400
            kullanici_id = row.KullaniciID
        else:
            conn.close()
            return jsonify({"hata": "Geçersiz kullanıcı kimliği"}), 400

        cursor.execute("""
            UPDATE Talepler
            SET Durum = 'Onaylandı',
                OnaylayanKullaniciID = ?, 
                OnayTarihi = ?
            WHERE TalepID = ?
        """, (kullanici_id, datetime.now(), talep_id))
        if cursor.rowcount == 0:
            return jsonify({"hata": "Talep bulunamadı"}), 404
        conn.commit()
        conn.close()
        return jsonify({"mesaj": f"Talep {talep_id} onaylandı"}), 200
    except Exception as e:
        print(f"talep_onayla hatası: {str(e)}")
        return jsonify({"hata": str(e)}), 500