from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager

app = Flask(__name__)
CORS(app)

app.config['JWT_SECRET_KEY'] = '11223344'
jwt = JWTManager(app)

from routes.kullanici_routes import kullanici_bp
from routes.musteri_routes import musteri_bp
from routes.talep_routes import talep_bp
from routes.servis_routes import servis_bp
from routes.paket_routes import paket_bp
from routes.urun_routes import urun_bp
from routes.paket_admin_routes import paket_admin_bp

app.register_blueprint(kullanici_bp, url_prefix="/api/kullanicilar")
app.register_blueprint(musteri_bp, url_prefix="/api/musteriler")
app.register_blueprint(talep_bp, url_prefix="/api/talepler")
app.register_blueprint(servis_bp, url_prefix="/api/servis")
app.register_blueprint(paket_bp, url_prefix="/api/paket")
app.register_blueprint(urun_bp, url_prefix="/api/urunler")
app.register_blueprint(paket_admin_bp, url_prefix="/api/admin/paketler")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)