from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from db import get_connection

musteri_bp = Blueprint("musteri_bp", __name__)
from flask_jwt_extended import jwt_required, get_jwt_identity
from fpdf import FPDF
import pyodbc
from config import DB_CONFIG

servis_bp = Blueprint('servis_bp', __name__)

def get_db_connection():
    conn_str = (
        f"DRIVER={{{DB_CONFIG['driver']}}};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"UID={DB_CONFIG['username']};"
        f"PWD={DB_CONFIG['password']}"
    )
    return pyodbc.connect(conn_str)

def to_latin1_safe(text):
    if isinstance(text, str):
        text = text.replace("₺", "TL")
        return text.encode("latin-1", "replace").decode("latin-1")
    return str(text)

class PDFSafe(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, to_latin1_safe("Servis Raporu"), ln=True, align="C")

    def add_talep_info(self, talep):
        self.set_font("Arial", "", 10)
        self.ln(5)
        for key, value in talep.items():
            if key != "TalepID":
                self.cell(0, 6, to_latin1_safe(f"{key}: {value}"), ln=True)

    def add_servis_table(self, detaylar):
        self.ln(5)
        self.set_font("Arial", "B", 10)
        self.cell(80, 8, to_latin1_safe("Ürün/Hizmet"), border=1)
        self.cell(30, 8, "Miktar", border=1)
        self.cell(40, 8, "Birim Fiyat", border=1)
        self.cell(40, 8, "Tutar", border=1)
        self.ln()
        self.set_font("Arial", "", 10)
        toplam = 0
        for d in detaylar:
            tutar = d["Miktar"] * d["BirimFiyat"]
            toplam += tutar
            self.cell(80, 8, to_latin1_safe(d["UrunHizmetAdi"]), border=1)
            self.cell(30, 8, str(d["Miktar"]), border=1)
            self.cell(40, 8, f"{d['BirimFiyat']:.2f} TL", border=1)
            self.cell(40, 8, f"{tutar:.2f} TL", border=1)
            self.ln()
        self.cell(150, 8, "TOPLAM", border=1)
        self.cell(40, 8, f"{toplam:.2f} TL", border=1)

@servis_bp.route('/pdf/<int:talep_id>', methods=['GET'])
@jwt_required()
def pdf_olustur(talep_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT t.TalepID, t.Baslik, t.Aciklama, t.TalepTarihi,
                   m.Unvan AS MusteriUnvan
            FROM Talepler t
            JOIN Musteriler m ON t.MusteriID = m.MusteriID
            WHERE t.TalepID = ?
        """, talep_id)
        row = cursor.fetchone()
        if not row:
            return jsonify({"hata": "Talep bulunamadı"}), 404

        talep_bilgi = {
            "TalepID": row.TalepID,
            "MusteriUnvan": row.MusteriUnvan,
            "Baslik": row.Baslik,
            "Aciklama": row.Aciklama,
            "TalepTarihi": row.TalepTarihi.strftime("%Y-%m-%d %H:%M:%S")
        }

        cursor.execute("""
            SELECT UrunHizmetAdi, Miktar, BirimFiyat
            FROM ServisDetaylari
            WHERE TalepID = ?
        """, talep_id)
        servis_detaylari = [
            {"UrunHizmetAdi": r.UrunHizmetAdi, "Miktar": r.Miktar, "BirimFiyat": float(r.BirimFiyat)}
            for r in cursor.fetchall()
        ]

        pdf = PDFSafe()
        pdf.add_page()
        pdf.add_talep_info(talep_bilgi)
        pdf.add_servis_table(servis_detaylari)

        pdf_path = f"servis_raporu_Talep{talep_id}.pdf"
        full_path = f"./{pdf_path}"
        pdf.output(full_path)

        return send_file(full_path, as_attachment=True)

    except Exception as e:
        return jsonify({"hata": str(e)}), 500

@servis_bp.route("/tamamla", methods=["POST"])
@jwt_required()
def servis_tamamla():
    try:
        data = request.get_json()
        talep_id = data["TalepID"]
        kullanici_id = get_jwt_identity()["kullanici_id"]

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE Servisler
            SET Tamamlandi = 1,
                TamamlanmaTarihi = GETDATE(),
                TamamlayanKullaniciID = ?
            WHERE TalepID = ?
        """, (kullanici_id, talep_id))

        cursor.execute("""
            UPDATE Talepler
            SET Durum = 'Tamamlandı'
            WHERE TalepID = ?
        """, (talep_id,))

        conn.commit()
        conn.close()
        return jsonify({"mesaj": "Servis tamamlandı ve durum güncellendi"}), 200
    except Exception as e:
        return jsonify({"hata": str(e)}), 500

@servis_bp.route("/detay-ekle", methods=["POST"])
@jwt_required()
def servis_detay_ekle():
    try:
        data = request.get_json()
        talep_id = data["TalepID"]
        detaylar = data["Detaylar"]

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT MusteriID FROM Talepler WHERE TalepID = ?", (talep_id,))
        result = cursor.fetchone()
        if not result:
            return jsonify({"hata": "Talep bulunamadı"}), 404
        musteri_id = result.MusteriID

        for d in detaylar:
            cursor.execute("""
                INSERT INTO ServisDetaylari (TalepID, UrunHizmetAdi, Miktar, BirimFiyat)
                OUTPUT INSERTED.ID
                VALUES (?, ?, ?, ?)
            """, (
                talep_id,
                d["UrunHizmetAdi"],
                d["Miktar"],
                d["BirimFiyat"]
            ))

            servis_detay_id = cursor.fetchone()[0]

            cursor.execute("""
                UPDATE MusteriPaketleri
                SET KalanCagri = KalanCagri - 1
                WHERE MusteriID = ? AND KalanCagri > 0
            """, (musteri_id,))

            if cursor.rowcount > 0:
                cursor.execute("""
                    INSERT INTO PaketKullanimGecmisi (MusteriID, TalepID, ServisDetayID, Aciklama)
                    VALUES (?, ?, ?, ?)
                """, (
                    musteri_id,
                    talep_id,
                    servis_detay_id,
                    f"{d['UrunHizmetAdi']} hizmeti sırasında çağrı kullanıldı."
                ))

        conn.commit()
        conn.close()
        return jsonify({"mesaj": "Servis detayları eklendi"}), 201
    except Exception as e:
        return jsonify({"hata": str(e)}), 500