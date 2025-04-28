from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta_aqui'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data/reservas.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Modelos
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    admin = db.Column(db.Boolean, default=False)

class Barraca(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    capacidade = db.Column(db.Integer, nullable=False)
    preco_diaria = db.Column(db.Float, nullable=False)
    disponivel = db.Column(db.Boolean, default=True)

class Reserva(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_nome = db.Column(db.String(100), nullable=False)
    cliente_email = db.Column(db.String(100), nullable=False)
    cliente_telefone = db.Column(db.String(20), nullable=False)
    barraca_id = db.Column(db.Integer, db.ForeignKey('barraca.id'), nullable=False)
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date, nullable=False)
    adultos = db.Column(db.Integer, nullable=False)
    criancas = db.Column(db.Integer, default=0)
    valor_total = db.Column(db.Float, nullable=False)
    valor_pago = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default='pendente')  # pendente, confirmada, cancelada
    data_reserva = db.Column(db.DateTime, default=datetime.utcnow)
    
    barraca = db.relationship('Barraca', backref='reservas')

class Pagamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reserva_id = db.Column(db.Integer, db.ForeignKey('reserva.id'), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data_pagamento = db.Column(db.DateTime, default=datetime.utcnow)
    metodo = db.Column(db.String(50), nullable=False)
    observacoes = db.Column(db.Text)
    
    reserva = db.relationship('Reserva', backref='pagamentos')

# Rotas
@app.route('/')
def index():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    reservas = Reserva.query.order_by(Reserva.data_reserva.desc()).limit(5).all()
    barracas_disponiveis = Barraca.query.filter_by(disponivel=True).count()
    return render_template('index.html', reservas=reservas, barracas_disponiveis=barracas_disponiveis)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        
        usuario = Usuario.query.filter_by(email=email).first()
        
        if usuario and check_password_hash(usuario.senha, senha):
            session['usuario_id'] = usuario.id
            session['usuario_nome'] = usuario.nome
            session['usuario_admin'] = usuario.admin
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Email ou senha incorretos', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você foi desconectado', 'info')
    return redirect(url_for('login'))

@app.route('/reservas')
def listar_reservas():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    reservas = Reserva.query.order_by(Reserva.data_inicio).all()
    return render_template('reservas.html', reservas=reservas)

@app.route('/reservas/nova', methods=['GET', 'POST'])
def nova_reserva():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Processar formulário de reserva
        cliente_nome = request.form['cliente_nome']
        cliente_email = request.form['cliente_email']
        cliente_telefone = request.form['cliente_telefone']
        barraca_id = request.form['barraca_id']
        data_inicio = datetime.strptime(request.form['data_inicio'], '%Y-%m-%d').date()
        data_fim = datetime.strptime(request.form['data_fim'], '%Y-%m-%d').date()
        adultos = int(request.form['adultos'])
        criancas = int(request.form['criancas'])
        
        # Calcular valor total (simplificado)
        barraca = Barraca.query.get(barraca_id)
        dias = (data_fim - data_inicio).days
        valor_total = barraca.preco_diaria * dias * (adultos + criancas * 0.5)  # Criança paga metade
        
        # Criar reserva
        reserva = Reserva(
            cliente_nome=cliente_nome,
            cliente_email=cliente_email,
            cliente_telefone=cliente_telefone,
            barraca_id=barraca_id,
            data_inicio=data_inicio,
            data_fim=data_fim,
            adultos=adultos,
            criancas=criancas,
            valor_total=valor_total
        )
        
        # Marcar barraca como indisponível
        barraca.disponivel = False
        
        db.session.add(reserva)
        db.session.commit()
        
        flash('Reserva criada com sucesso!', 'success')
        return redirect(url_for('listar_reservas'))
    
    barracas = Barraca.query.filter_by(disponivel=True).all()
    return render_template('nova_reserva.html', barracas=barracas)

@app.route('/estoque')
def estoque():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    barracas = Barraca.query.all()
    return render_template('estoque.html', barracas=barracas)

@app.route('/pagamentos/<int:reserva_id>', methods=['GET', 'POST'])
def pagamentos(reserva_id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    reserva = Reserva.query.get_or_404(reserva_id)
    
    if request.method == 'POST':
        valor = float(request.form['valor'])
        metodo = request.form['metodo']
        observacoes = request.form.get('observacoes', '')
        
        pagamento = Pagamento(
            reserva_id=reserva_id,
            valor=valor,
            metodo=metodo,
            observacoes=observacoes
        )
        
        reserva.valor_pago += valor
        
        if reserva.valor_pago >= reserva.valor_total:
            reserva.status = 'confirmada'
        
        db.session.add(pagamento)
        db.session.commit()
        
        flash('Pagamento registrado com sucesso!', 'success')
        return redirect(url_for('pagamentos', reserva_id=reserva_id))
    
    return render_template('pagamentos.html', reserva=reserva)

@app.route('/usuarios')
def usuarios():
    if 'usuario_id' not in session or not session.get('usuario_admin'):
        flash('Acesso não autorizado', 'danger')
        return redirect(url_for('index'))
    
    usuarios = Usuario.query.all()
    return render_template('usuarios.html', usuarios=usuarios)

# Função para carregar dados iniciais
def carregar_dados_iniciais():
    # Verificar se já existem usuários
    if not Usuario.query.first():
        admin = Usuario(
            nome='Administrador',
            email='admin@acampamento.com',
            senha=generate_password_hash('admin123'),
            admin=True
        )
        db.session.add(admin)
        db.session.commit()
    
    # Carregar barracas baseadas nos dados da planilha
    if not Barraca.query.first():
        barracas = [
            Barraca(codigo='GA001974', tipo='Familiar', capacidade=4, preco_diaria=150.0),
            Barraca(codigo='P-JAS007', tipo='Individual', capacidade=1, preco_diaria=80.0),
            Barraca(codigo='VXA', tipo='Luxo', capacidade=2, preco_diaria=200.0)
        ]
        db.session.add_all(barracas)
        db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        # Criar banco de dados se não existir
        if not os.path.exists('data/reservas.db'):
            db.create_all()
            carregar_dados_iniciais()
    
    app.run(debug=True)