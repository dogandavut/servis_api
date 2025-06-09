from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from db import get_connection
from datetime import datetime, timedelta
import openpyxl
import io

urun_bp = Blueprint("urun", __name__)

# 🎯 Tek tek ürün ekle
@urun_bp.route("/", methods=["POST"])
@jwt_required()
def urun_ekle():
    claims = get_jwt()
    if claims.get("rol", "").lower() != "admin":
        return jsonify({"hata": "Yetkisiz erişim"}), 403

    try:
        data = request.get_json()
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO UrunHizmetler (
                MusteriID, UrunAdi, Aciklama, SatinAlmaTarihi,
                BitisTarihi, AlisFiyati, SatisFiyati
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            data["MusteriID"],
            data["UrunAdi"],
            data.get("Aciklama", ""),
            data["SatinAlmaTarihi"],
            data["BitisTarihi"],
            data["AlisFiyati"],
            data["SatisFiyati"]
        ))

        conn.commit()
        conn.close()
        return jsonify({"mesaj": "Ürün/Hizmet başarıyla kaydedildi"}), 201
    except Exception as e:
        return jsonify({"hata": str(e)}), 500

# 🎯 Müşteri bazlı ürün listesi
@urun_bp.route("/<int:musteri_id>", methods=["GET"])
@jwt_required()
def urunleri_getir(musteri_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                UrunID AS ID,
                UrunAdi, Aciklama, SatinAlmaTarihi, BitisTarihi,
                AlisFiyati, SatisFiyati,
                (SatisFiyati - AlisFiyati) AS Kar
            FROM UrunHizmetler
            WHERE MusteriID = ?
        """, (musteri_id,))

        kolonlar = [column[0] for column in cursor.description]
        sonuc = [dict(zip(kolonlar, row)) for row in cursor.fetchall()]
        conn.close()
        return jsonify(sonuc)
    except Exception as e:
        return jsonify({"hata": str(e)}), 500

# 🎯 Vadesi yaklaşan ürünleri getir (30 gün içinde bitenler)
@urun_bp.route("/yaklasan/<int:musteri_id>", methods=["GET"])
@jwt_required()
def yaklasan_urunleri_getir(musteri_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        today = datetime.today().date()
        end_date = today + timedelta(days=30)

        cursor.execute("""
            SELECT 
                UrunID AS ID,
                UrunAdi, Aciklama, SatinAlmaTarihi, BitisTarihi,
                AlisFiyati, SatisFiyati,
                (SatisFiyati - AlisFiyati) AS Kar
            FROM UrunHizmetler
            WHERE MusteriID = ?
              AND BitisTarihi BETWEEN ? AND ?
        """, (musteri_id, today, end_date))

        kolonlar = [col[0] for col in cursor.description]
        sonuc = [dict(zip(kolonlar, row)) for row in cursor.fetchall()]
        conn.close()
        return jsonify(sonuc)
    except Exception as e:
        return jsonify({"hata": str(e)}), 500

# 🎯 Excel'den toplu ürün yükle
@urun_bp.route("/excel-yukle", methods=["POST"])
@jwt_required()
def urunleri_excelden_yukle():
    claims = get_jwt()
    if claims.get("rol", "").lower() != "admin":
        return jsonify({"hata": "Yetkisiz erişim"}), 403

    try:
        if "excel" not in request.files:
            return jsonify({"hata": "Excel dosyası yüklenmedi"}), 400

        file = request.files["excel"]
        wb = openpyxl.load_workbook(filename=io.BytesIO(file.read()))
        sheet = wb.active

        conn = get_connection()
        cursor = conn.cursor()

        for row in sheet.iter_rows(min_row=2, values_only=True):
            if not row or row[0] is None:
                continue  # boş satır atla

            cursor.execute("""
                INSERT INTO UrunHizmetler (
                    MusteriID, UrunAdi, Aciklama, SatinAlmaTarihi,
                    BitisTarihi, AlisFiyati, SatisFiyati
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, row)

        conn.commit()
        conn.close()

        return jsonify({"mesaj": "Excel'den ürünler başarıyla yüklendi"}), 201
    except Exception as e:
        return jsonify({"hata": str(e)}), 500

# 🎯 Bildirim kontrolü
@urun_bp.route("/bildirim-kontrol", methods=["POST"])
@jwt_required()
def bildirim_kontrolu_yap():
    claims = get_jwt()
    if claims.get("rol", "").lower() != "admin":
        return jsonify({"hata": "Yetkisiz erişim"}), 403

    try:
        conn = get_connection()
        cursor = conn.cursor()

        today = datetime.today().date()
        end_date = today + timedelta(days=15)

        cursor.execute("""
            SELECT UrunID, MusteriID, UrunAdi, BitisTarihi
            FROM UrunHizmetler
            WHERE BildirimGonderildi = 0 AND BitisTarihi BETWEEN ? AND ?
        """, (today, end_date))

        urunler = cursor.fetchall()
        bildirilen_idler = []

        for urun in urunler:
            urun_id = urun.UrunID
            urun_adi = urun.UrunAdi
            musteri_id = urun.MusteriID
            bitis = urun.BitisTarihi.strftime("%Y-%m-%d")

            # 📣 Buraya mail/sms/log kodu entegre edilebilir
            print(f"🔔 Bildirim: Müşteri {musteri_id} - Ürün: {urun_adi} ({bitis})")
            bildirilen_idler.append(urun_id)

        if bildirilen_idler:
            cursor.executemany("""
                UPDATE UrunHizmetler
                SET BildirimGonderildi = 1
                WHERE UrunID = ?
            """, [(id,) for id in bildirilen_idler])
            conn.commit()

        conn.close()

        return jsonify({
            "bildirimSayisi": len(bildirilen_idler),
            "bildirilenIDler": bildirilen_idler
        })

    except Exception as e:
        return jsonify({"hata": str(e)}), 500
