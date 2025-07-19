# app.py
import json
from flask import Flask, render_template, abort, request, flash, redirect, url_for, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import os
import random
import string

# --- Configuración Inicial ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'blackbox-super-secret-key-change-this') # Consider changing this in production
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'tienda.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Configuración de Flask-Mail ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'kevincortesa@gmail.com' # Consider using environment variables for production
app.config['MAIL_PASSWORD'] = 'hqya mdba qgyy ozlg' # Consider using environment variables for production
app.config['MAIL_DEFAULT_SENDER'] = ('BLACK BOX', 'kevincortesa@gmail.com')
mail = Mail(app)

# --- Modelos de la Base de Datos ---
class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    precio = db.Column(db.String(50), nullable=False)
    estado = db.Column(db.String(20), nullable=False, default='disponible')
    imagen = db.Column(db.String(200), nullable=True, default='https://placehold.co/400x300/343a40/ffffff?text=Producto')

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(200), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# --- Carga de Datos y Rutas Públicas ---
def cargar_servicios_json():
    try:
        with open('servicios.json', 'r', encoding='utf-8') as f: return json.load(f)
    except: return {}
servicios_data = cargar_servicios_json()

@app.route('/')
def index():
    return render_template('index.html', servicios=servicios_data)

@app.route('/tienda')
def tienda():
    productos = Producto.query.order_by(Producto.id.desc()).all()
    return render_template('tienda.html', productos=productos)

@app.route('/servicio/<string:nombre_servicio>')
def detalle_servicio(nombre_servicio):
    servicio = servicios_data.get(nombre_servicio)
    if not servicio: abort(404)
    return render_template('servicio.html', servicio=servicio, servicios=servicios_data, nombre_servicio=nombre_servicio)

@app.route('/buscar')
def buscar():
    query = request.args.get('q', '').lower()
    if not query: return redirect(url_for('index'))
    resultados = {k: v for k, v in servicios_data.items() if isinstance(v, dict) and (query in v.get('titulo', '').lower() or query in v.get('resumen', '').lower())}
    return render_template('resultados_busqueda.html', query=query, resultados=resultados)

@app.route('/enviar-mensaje', methods=['POST'])
def enviar_mensaje():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        mensaje = request.form.get('mensaje')
        print(f"Nuevo mensaje de: {nombre} ({email}) - Mensaje: {mensaje}")
        flash('¡Gracias por tu mensaje! Te contactaremos pronto.', 'success')
    return redirect(url_for('index') + '#contacto')

# --- Rutas de Autenticación y Administración ---
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if 'user_id' in session: return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        
        if User.query.filter_by(username=username).first():
            flash('El nombre de usuario ya existe.', 'danger')
        elif User.query.filter_by(email=email).first():
            flash('El correo electrónico ya está registrado.', 'danger')
        else:
            verification_code = ''.join(random.choices(string.digits, k=6))
            session['registration_data'] = request.form.to_dict()
            session['verification_code'] = verification_code

            try:
                msg = Message('Tu Código de Verificación - BLACK BOX', recipients=[email])
                msg.body = f'Hola {username},\n\nGracias por registrarte. Tu código de verificación es: {verification_code}\n\nEste código expirará en 10 minutos.\n\nAtentamente,\nEl equipo de BLACK BOX'
                mail.send(msg)
                flash('Te hemos enviado un código de verificación a tu correo.', 'info')
                return redirect(url_for('verificar'))
            except Exception as e:
                flash('No se pudo enviar el correo de verificación. Revisa tus credenciales en app.py.', 'danger')
                print(f"Error al enviar correo: {e}")
            
    return render_template('registro.html')

@app.route('/verificar', methods=['GET', 'POST'])
def verificar():
    if 'registration_data' not in session or 'verification_code' not in session:
        return redirect(url_for('registro'))

    if request.method == 'POST':
        user_code = request.form.get('code')
        if user_code == session['verification_code']:
            data = session['registration_data']
            new_user = User(
                username=data['username'], 
                email=data['email'],
                full_name=data.get('full_name', ''),
                address=data.get('address'),
                city=data.get('city'),
                phone=data.get('phone')
            )
            new_user.set_password(data['password'])
            db.session.add(new_user)
            db.session.commit()

            session.pop('registration_data', None)
            session.pop('verification_code', None)

            flash('¡Cuenta verificada! Ahora puedes iniciar sesión.', 'success')
            return redirect(url_for('login'))
        else:
            flash('El código de verificación es incorrecto. Inténtalo de nuevo.', 'danger')

    return render_template('verificar.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session: return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            flash(f'¡Bienvenido de nuevo, {user.username}!', 'success')
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('tienda'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado la sesión.', 'info')
    return redirect(url_for('index'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if 'user_id' in session and session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username, is_admin=True).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = True
            flash('Inicio de sesión de administrador exitoso.', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Credenciales de administrador incorrectas.', 'danger')
    return render_template('admin_login.html')

@app.route('/admin')
def admin_dashboard():
    if not session.get('is_admin'): return redirect(url_for('admin_login'))
    productos = Producto.query.order_by(Producto.id.desc()).all()
    usuarios = User.query.all()
    return render_template('admin_dashboard.html', productos=productos, usuarios=usuarios)

@app.route('/admin/producto/nuevo', methods=['GET', 'POST'])
def nuevo_producto():
    if not session.get('is_admin'): return redirect(url_for('admin_login'))
    if request.method == 'POST':
        nuevo = Producto(nombre=request.form['nombre'], descripcion=request.form['descripcion'], precio=request.form['precio'], estado=request.form['estado'], imagen=request.form.get('imagen') or None)
        db.session.add(nuevo)
        db.session.commit()
        flash('Producto añadido con éxito.', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_form_producto.html', titulo="Añadir Nuevo Producto")

@app.route('/admin/producto/editar/<int:id>', methods=['GET', 'POST'])
def editar_producto(id):
    if not session.get('is_admin'): return redirect(url_for('admin_login'))
    producto = Producto.query.get_or_404(id)
    if request.method == 'POST':
        producto.nombre, producto.descripcion, producto.precio, producto.estado, producto.imagen = request.form['nombre'], request.form['descripcion'], request.form['precio'], request.form['estado'], request.form.get('imagen') or None
        db.session.commit()
        flash('Producto actualizado con éxito.', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_form_producto.html', titulo="Editar Producto", producto=producto)

@app.route('/admin/producto/eliminar/<int:id>', methods=['POST'])
def eliminar_producto(id):
    if not session.get('is_admin'): return redirect(url_for('admin_login'))
    producto = Producto.query.get_or_404(id)
    db.session.delete(producto)
    db.session.commit()
    flash('Producto eliminado con éxito.', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/user/promote/<int:id>', methods=['POST'])
def promover_usuario(id):
    if not session.get('is_admin'): return redirect(url_for('admin_login'))
    user_to_promote = User.query.get_or_404(id)
    user_to_promote.is_admin = True
    db.session.commit()
    flash(f'El usuario {user_to_promote.username} ahora es administrador.', 'success')
    return redirect(url_for('admin_dashboard'))

# --- Chatbot Evelyn ---
@app.route('/chatbot', methods=['POST'])
def chatbot():
    data = request.json
    user_message = (data.get('message') or '').lower()
    payload = data.get('payload')
    response_text = "No estoy segura de entender. ¿Puedes intentar con una de las opciones? Con gusto te ayudaré."
    quick_replies = [
        {'title': 'Nuestros Servicios', 'payload': 'SHOW_SERVICES'},
        {'title': 'Horario y Ubicación', 'payload': 'SHOW_INFO'},
        {'title': 'Hablar con un técnico', 'payload': 'CONTACT_HUMAN'},
    ]
    if payload == 'GET_STARTED':
        response_text = "¡Hola! Soy Evelyn, tu asistente virtual de BLACK BOX. Estoy aquí para ayudarte. ¿Qué te gustaría saber?"
    elif payload == 'SHOW_SERVICES':
        response_text = "¡Perfecto! Nos especializamos en varios dispositivos. Selecciona una categoría para ver más detalles:"
        quick_replies = [{'title': s.get('titulo', k), 'payload': f'SERVICE_{k}'} for k, s in servicios_data.items()]
    elif payload and payload.startswith('SERVICE_'):
        service_key = payload.replace('SERVICE_', '')
        service = servicios_data.get(service_key)
        if service:
            response_text = f"Para {service.get('titulo', 'este servicio')}, algunas de nuestras soluciones son: {', '.join(service.get('soluciones', [])[:3])} y mucho más. ¿Quieres ver todos los detalles en su página?"
            quick_replies = [
                {'title': f"Sí, ir a la página", 'payload': f"OPEN_PAGE_/servicio/{service_key}"},
                {'title': 'Ver otros servicios', 'payload': 'SHOW_SERVICES'},
                {'title': 'Menú principal', 'payload': 'GET_STARTED'},
            ]
    elif payload == 'SHOW_INFO':
        response_text = "Atendemos de Lunes a Sábado de 9:30 AM a 7:00 PM en el Local 204 del C.C. Opera, en el centro de Medellín. ¡Te esperamos!"
    elif payload == 'CONTACT_HUMAN':
        response_text = "¡Claro! Para una atención personalizada, lo mejor es chatear directamente con un técnico por WhatsApp."
        quick_replies = [{'title': 'Abrir WhatsApp', 'payload': 'OPEN_LINK_https://wa.me/573019320359'}]
    elif "gracias" in user_message or "adios" in user_message:
        response_text = "¡Con mucho gusto! Estoy aquí si necesitas algo más. ¡Que tengas un excelente día!"
        quick_replies = []
    
    return jsonify({'response': response_text, 'quick_replies': quick_replies})

@app.errorhandler(404)
def pagina_no_encontrada(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(is_admin=True).first():
            print("No se encontró ningún administrador. Creando cuenta de admin por defecto...")
            admin_user = User(username='admin', email='admin@blackbox.com', is_admin=True, full_name='Administrador')
            # Generar una contraseña segura y aleatoria para el administrador por defecto
            default_admin_password = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=24))
            admin_user.set_password(default_admin_password)
            print(f"Usuario 'admin' creado con contraseña: {default_admin_password}. ¡CAMBIA ESTA CONTRASEÑA INMEDIATAMENTE!")
            db.session.add(admin_user)
            db.session.commit()
            print("Usuario 'admin' con contraseña 'admin123' creado.")
    app.run(debug=True)
