
from flask import Blueprint, request, jsonify, send_file
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
    from flask_jwt_extended import get_jwt
    claims = get_jwt()
    if claims.get("rol", "").lower() not in ["admin", "teknik"]:
        return jsonify({"hata": "Yetkisiz erişim"}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM Talepler WHERE TalepID = ?", (talep_id,))
        talep = cursor.fetchone()
        if not talep:
            return jsonify({"hata": "Talep bulunamadı"}), 404

        talep_dict = {column[0]: getattr(talep, column[0]) for column in cursor.description}

        cursor.execute("""
            SELECT UrunHizmetAdi, Miktar, BirimFiyat
            FROM ServisDetaylari
            WHERE TalepID = ?
        """, (talep_id,))
        detaylar = [
            {
                "UrunHizmetAdi": row.UrunHizmetAdi,
                "Miktar": row.Miktar,
                "BirimFiyat": row.BirimFiyat
            }
            for row in cursor.fetchall()
        ]

        conn.close()

        pdf = PDFSafe()
        pdf.add_page()
        pdf.add_talep_info(talep_dict)
        pdf.add_servis_table(detaylar)

        pdf_path = f"servis_raporu_Talep{talep_id}.pdf"
        pdf.output(pdf_path)

        return send_file(pdf_path, as_attachment=True)

    except Exception as e:
        return jsonify({"hata": str(e)}), 500
