import os
from flask import Flask, request, jsonify, abort, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# Configura la conexión a PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres:root@localhost/vrObjects"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = True  # Para ver las consultas SQL

# Carpeta para subir imágenes
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)
ma = Marshmallow(app)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Modelo con nuevo campo image_path
class Model(db.Model):
    __tablename__ = 'objects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(255), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    image_path = db.Column(db.String(255), nullable=True)

class ModelSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Model
        load_instance = True

model_schema = ModelSchema()
models_schema = ModelSchema(many=True)

# Endpoint para listar modelos
@app.route('/models', methods=['GET'])
def get_models():
    all_models = Model.query.all()
    return models_schema.jsonify(all_models)

# Endpoint para crear un modelo
@app.route('/models', methods=['POST'])
def create_model():
    data = request.get_json()
    if not data or not data.get('name') or not data.get('url'):
        abort(400, "Faltan 'name' o 'url' en el cuerpo JSON")
    nuevo_modelo = Model(
        name=data['name'],
        url=data['url'],
        description=data.get('description')
    )
    try:
        db.session.add(nuevo_modelo)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        abort(500, f"Error al guardar en base de datos: {e}")
    return model_schema.jsonify(nuevo_modelo), 201

# Endpoint para subir imagen asociada a modelo
@app.route('/models/<int:model_id>/upload-image', methods=['POST'])
def upload_image(model_id):
    if 'image' not in request.files:
        abort(400, "No se encontró el archivo 'image' en la petición")

    file = request.files['image']

    if file.filename == '':
        abort(400, "No se seleccionó ningún archivo")

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filename = f"{model_id}_{filename}"  # Para evitar colisiones
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        modelo = Model.query.get(model_id)
        if not modelo:
            abort(404, "Modelo no encontrado")

        modelo.image_path = filename  # Guardamos solo el nombre para construir la URL después
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            abort(500, f"Error al guardar ruta de imagen en base de datos: {e}")

        return jsonify({
            "message": "Imagen subida correctamente",
            "image_url": f"/uploads/{filename}"
        })

    else:
        abort(400, "Archivo no permitido")

# Endpoint para servir imágenes
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Obtener un objeto por id
@app.route('/models/<int:model_id>', methods=['GET'])
def get_model(model_id):
    modelo = Model.query.get_or_404(model_id)
    return model_schema.jsonify(modelo)

# Endpoint para buscar modelos por nombre 
@app.route('/models/search', methods=['GET'])
def search_models():
    name_query = request.args.get('name')
    if not name_query:
        abort(400, "Falta el parámetro 'name' en la query")
    
    resultados = Model.query.filter(Model.name.ilike(f"%{name_query}%")).all()
    return models_schema.jsonify(resultados)

# Modificar un objeto (PUT o PATCH)
@app.route('/models/<int:model_id>', methods=['PUT'])
def update_model(model_id):
    modelo = Model.query.get_or_404(model_id)
    data = request.get_json()
    if not data:
        abort(400, "No hay datos para actualizar")

    # Actualizar campos si vienen en JSON
    if 'name' in data:
        modelo.name = data['name']
    if 'url' in data:
        modelo.url = data['url']
    if 'description' in data:
        modelo.description = data['description']

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        abort(500, f"Error al actualizar: {e}")

    return model_schema.jsonify(modelo)

@app.route('/models/<int:model_id>', methods=['DELETE'])
def delete_model(model_id):
    modelo = Model.query.get_or_404(model_id)
    try:
        # Si tiene imagen asociada, borrarla del disco
        if modelo.image_path:
            image_full_path = os.path.join(app.config['UPLOAD_FOLDER'], modelo.image_path)
            if os.path.exists(image_full_path):
                os.remove(image_full_path)

        db.session.delete(modelo)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        abort(500, f"Error al eliminar: {e}")
    return jsonify({"message": f"Modelo {model_id} eliminado correctamente"})

SCREENSHOTS_FOLDER = 'screenshots'
app.config['SCREENSHOTS_FOLDER'] = SCREENSHOTS_FOLDER
if not os.path.exists(SCREENSHOTS_FOLDER):
    os.makedirs(SCREENSHOTS_FOLDER)

@app.route('/upload-screenshot', methods=['POST'])
def upload_screenshot():
    if 'image' not in request.files:
        abort(400, "No se encontró el archivo 'image' en la petición")

    file = request.files['image']

    if file.filename == '':
        abort(400, "No se seleccionó ningún archivo")

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Para evitar colisiones, podrías añadir timestamp o un uuid:
        import time
        timestamp = int(time.time())
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['SCREENSHOTS_FOLDER'], filename)
        file.save(filepath)

        return jsonify({
            "message": "Captura subida correctamente",
            "image_url": f"/screenshots/{filename}"
        })

    else:
        abort(400, "Archivo no permitido")

@app.route('/screenshots/<filename>')
def uploaded_screenshot(filename):
    return send_from_directory(app.config['SCREENSHOTS_FOLDER'], filename)

# Carpeta donde están los modelos .glb
MODELS_FOLDER = 'models'

@app.route('/models/<path:filename>')
def serve_model(filename):
    # Envía el archivo solicitado al cliente
    return send_from_directory(MODELS_FOLDER, filename)

if __name__ == '__main__':
    CORS(app)  # Permite todas las peticiones CORS
    #CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}}) solo desde react
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            print(f"Error al crear tablas: {e}")

    app.run(debug=True, host='0.0.0.0', port=5000)
