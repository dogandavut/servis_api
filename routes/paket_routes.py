from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
import pyodbc
from config import DB_CONFIG

paket_bp = Blueprint("paket_bp", __name__)

def get_db_connection():
    conn_str = (
        f"DRIVER={{{DB_CONFIG['driver']}}};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"UID={DB_CONFIG['username']};"
        f"PWD={DB_CONFIG['password']}"
    )
    return pyodbc.connect(conn_str)

# 🎯 Paket Güncelle
@paket_bp.route("/guncelle/<int:paket_id>", methods=["PUT"])
@jwt_required()
def paket_guncelle(paket_id):
    from flask_jwt_extended import get_jwt
    claims = get_jwt()
    if claims.get("rol", "").lower() != "admin":
        return jsonify({"hata": "Yetkisiz erişim"}), 403

    try:
        data = request.get_json()
        conn = get_db_connection()
        cursor = conn.cursor()

        set_clause = []
        values = []

        for key in ["PaketAdi", "CagriSayisi", "Fiyat", "SureAy", "Aciklama", "Aktif"]:
            if key in data:
                set_clause.append(f"{key} = ?")
                values.append(data[key])

        if not set_clause:
            return jsonify({"hata": "Güncellenecek alan belirtilmedi"}), 400

        values.append(paket_id)
        query = f"UPDATE Paketler SET {', '.join(set_clause)} WHERE PaketID = ?"
        cursor.execute(query, values)
        conn.commit()
        conn.close()

        return jsonify({"mesaj": "Paket güncellendi"})
    except Exception as e:
        return jsonify({"hata": str(e)}), 500
