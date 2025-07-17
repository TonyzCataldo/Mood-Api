from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from collections import Counter
from datetime import date, timedelta
import os
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv 

load_dotenv()

# 🔹 Inicializa app Flask
app = Flask(__name__)

# 🔐 Chave secreta do JWT (vem do ambiente)
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "default-key-para-dev")

# 🔹 Configura banco de dados SQLite
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///usuarios.db"

# 🔹 Configura pasta de upload
app.config["UPLOAD_FOLDER"] = "uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# 🌐 CORS configurado para ambiente correto
app.config["CORS_ORIGINS"] = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")
CORS(app, resources={
    r"/*": {
        "origins": app.config["CORS_ORIGINS"],
        "supports_credentials": True,
        "allow_headers": ["Content-Type", "Authorization"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    }
})

# ☁️ Cloudinary seguro
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET")
)

# 🔧 Inicializa extensões
db = SQLAlchemy(app)
jwt = JWTManager(app)

# Modelos
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(128), nullable=False)
    nome = db.Column(db.String(100), default="User")
    imagem_url = db.Column(db.String(300))
    imagem_public_id = db.Column(db.String(200))
    onboarding_required = db.Column(db.Boolean, default=True)

class Registro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    humor = db.Column(db.String(50), nullable=False)
    como_se_sentiu = db.Column(db.String(300), nullable=False)
    descricao = db.Column(db.String(500))
    horas_sono = db.Column(db.String(10), nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

# Cria tabelas no primeiro run
with app.app_context():
    db.create_all()

# Rota de registro
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    email = data.get("email")
    senha = data.get("senha")

    if Usuario.query.filter_by(email=email).first():
        return jsonify({"msg": "User already exists. Please try logging in instead."}), 400

    senha_hash = generate_password_hash(senha)
    novo_usuario = Usuario(email=email, senha_hash=senha_hash)
    db.session.add(novo_usuario)
    db.session.commit()

    return jsonify({"msg": "Usuário criado com sucesso"}), 201

# Rota de login
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    senha = data.get("senha")

    usuario = Usuario.query.filter_by(email=email).first()
    if not usuario or not check_password_hash(usuario.senha_hash, senha):
        return jsonify({"msg": "Incorrect username or password."}), 401

    token = create_access_token(identity=str(usuario.id), expires_delta=timedelta(days=1))
    return jsonify({
        "token": token,
        "usuario_id": usuario.id,
        "onboarding_required": usuario.onboarding_required
    }), 200

# Rota para salvar nome/imagem e finalizar onboarding
@app.route("/onboarding", methods=["POST"])
@jwt_required()
def onboarding():
    usuario_id = int(get_jwt_identity())
    usuario = Usuario.query.get(usuario_id)

    nome = request.json.get("nome")
    if nome:
        usuario.nome = nome

    usuario.onboarding_required = False
    db.session.commit()

    return jsonify({"msg": "Onboarding atualizado com sucesso"})

# Atualizar status do onboarding
@app.route("/update-onboarding", methods=["PUT"])
@jwt_required()
def update_onboarding():
    usuario_id = int(get_jwt_identity())
    usuario = Usuario.query.get(usuario_id)

    if not usuario:
        return jsonify({"msg": "Usuário não encontrado"}), 404

    usuario.onboarding_required = False
    db.session.commit()
    return jsonify({"msg": "Onboarding marcado como concluído."})

# Registrar dados de humor/sono
@app.route("/registro", methods=["POST"])
@jwt_required()
def registrar_dados():
    usuario_id = int(get_jwt_identity())
    usuario = Usuario.query.get(usuario_id)

    data_hoje = date.today()
    humor = request.json.get("humor")
    como_se_sentiu = request.json.get("como_se_sentiu")
    descricao = request.json.get("descricao")
    horas_sono = request.json.get("horas_sono")

    registro_existente = Registro.query.filter_by(id_usuario=usuario_id, data=data_hoje).first()
    if registro_existente:
        return jsonify({"msg": "Você já registrou hoje."}), 400

    novo_registro = Registro(
        data=data_hoje,
        humor=humor,
        como_se_sentiu=como_se_sentiu,
        descricao=descricao,
        horas_sono=horas_sono,
        id_usuario=usuario_id
    )

    db.session.add(novo_registro)
    db.session.commit()

    registros = Registro.query.filter_by(id_usuario=usuario_id).order_by(Registro.id.desc()).all()
    if len(registros) > 11:
        registros_a_deletar = registros[11:]
        for r in registros_a_deletar:
            db.session.delete(r)
        db.session.commit()

    return jsonify({"msg": "Registro salvo com sucesso."}), 201

# Obter registros
@app.route("/registros", methods=["GET"])
@jwt_required()
def obter_registros():
    usuario_id = int(get_jwt_identity())

    registros = Registro.query.filter_by(id_usuario=usuario_id).order_by(Registro.data.desc()).limit(11).all()
    resultado = [
        {
            "data": r.data.strftime("%Y-%m-%d"),
            "humor": r.humor,
            "como_se_sentiu": r.como_se_sentiu,
            "descricao": r.descricao,
            "horas_sono": r.horas_sono,
        }
        for r in registros
    ]
    resultado.reverse()
    return jsonify(resultado), 200

# Servir imagens locais
@app.route("/uploads/<nome_arquivo>")
def servir_arquivo(nome_arquivo):
    return send_from_directory(app.config["UPLOAD_FOLDER"], nome_arquivo)

# Verificar se precisa fazer onboarding
@app.route("/check-onboarding", methods=["GET"])
@jwt_required()
def check_onboarding():
    usuario_id = int(get_jwt_identity())
    usuario = Usuario.query.get(usuario_id)

    if not usuario:
        return jsonify({"msg": "Usuário não encontrado"}), 404

    return jsonify({"onboarding_required": usuario.onboarding_required}), 200

# Dados do usuário
@app.route("/me", methods=["GET"])
@jwt_required()
def get_usuario():
    usuario_id = int(get_jwt_identity())
    usuario = Usuario.query.get(usuario_id)

    if not usuario:
        return jsonify({"msg": "Usuário não encontrado"}), 404

    return jsonify({
        "nome": usuario.nome,
        "email": usuario.email,
        "imagem_url": usuario.imagem_url or "/avatar-placeholder.svg"
    }), 200

# Upload de imagem com Cloudinary
@app.route("/upload-image", methods=["POST"])
@jwt_required()
def upload_image():
    usuario_id = int(get_jwt_identity())
    usuario = Usuario.query.get(usuario_id)

    imagem = request.files.get("imagem")
    if not imagem:
        return jsonify({"msg": "Nenhum arquivo enviado"}), 400

    if usuario.imagem_public_id:
        try:
            cloudinary.uploader.destroy(usuario.imagem_public_id)
        except Exception as e:
            print("Erro ao deletar imagem anterior:", e)

    result = cloudinary.uploader.upload(
        imagem,
        folder="mood",
        use_filename=True,
        unique_filename=True,
        resource_type="image"
    )

    usuario.imagem_url = result["secure_url"]
    usuario.imagem_public_id = result["public_id"]
    db.session.commit()

    return jsonify({
        "imagem_url": usuario.imagem_url,
        "public_id": usuario.imagem_public_id
    }), 200

# Verifica se já registrou hoje
@app.route("/ja-registrou-hoje", methods=["GET"])
@jwt_required()
def ja_registrou_hoje():
    usuario_id = int(get_jwt_identity())
    hoje = date.today()

    registro = Registro.query.filter_by(id_usuario=usuario_id, data=hoje).first()
    return jsonify({"ja_registrou": bool(registro)})

# Executa app localmente
if __name__ == "__main__":
    app.run(debug=True)
