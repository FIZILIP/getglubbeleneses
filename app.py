from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from flask import send_file
import os
import shutil
import sys
import tempfile
from io import BytesIO
import math
from urllib.request import urlopen
import json

from sqlalchemy import text, func
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from PIL import Image
from license import check_license, activate_license



BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, 
            template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'getclub2024_3ecf593ed43d09a6')

def get_storage_dir():
    custom_dir = os.environ.get("GETCLUB_DATA_DIR")
    if custom_dir:
        return custom_dir
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "GETCLUB")
    return os.path.join(os.path.expanduser("~"), ".getclub")

def is_dir_writable(path):
    try:
        os.makedirs(path, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix="getclub_", dir=path)
        os.close(fd)
        os.unlink(tmp)
        return True
    except Exception:
        return False

def pick_storage_dir():
    preferred = get_storage_dir()
    if is_dir_writable(preferred):
        return preferred
    fallback = os.path.join("/private/tmp", "GETCLUB_Data")
    os.makedirs(fallback, exist_ok=True)
    return fallback

def ensure_local_db(data_dir):
    os.makedirs(data_dir, exist_ok=True)
    target = os.path.join(data_dir, "getclub.db")
    if os.path.exists(target):
        return target
    bundled = os.path.join(BASE_DIR, "getclub.db")
    if os.path.exists(bundled):
        try:
            shutil.copy2(bundled, target)
        except Exception:
            pass
    return target

DATA_DIR = pick_storage_dir()
LOCAL_DB_PATH = ensure_local_db(DATA_DIR)
APP_SETTINGS_PATH = os.path.join(DATA_DIR, "app_settings.json")
APP_SETTINGS_FALLBACK_PATH = os.path.join(BASE_DIR, "app_settings.json")

database_url = os.environ.get('DATABASE_URL')
if database_url:
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + LOCAL_DB_PATH
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(DATA_DIR, 'uploads', 'atletas')
app.config['UPLOAD_FOLDER_COMISSAO'] = os.path.join(DATA_DIR, 'uploads', 'comissao')
app.config['UPLOAD_FOLDER_DOCS'] = os.path.join(DATA_DIR, 'uploads', 'documentos')
app.config['UPLOAD_FOLDER_CLUBE'] = os.path.join(DATA_DIR, 'uploads', 'clube')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER_COMISSAO'], exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER_DOCS'], exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER_CLUBE'], exist_ok=True)

@app.route('/uploads/atletas/<path:filename>')
def serve_foto_atleta(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/uploads/comissao/<path:filename>')
def serve_foto_comissao(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER_COMISSAO'], filename)

@app.route('/uploads/clube/<path:filename>')
def serve_logo_clube(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER_CLUBE'], filename)

def get_logo_clube_filename():
    pasta = app.config['UPLOAD_FOLDER_CLUBE']
    try:
        arquivos = []
        for nome in os.listdir(pasta):
            caminho = os.path.join(pasta, nome)
            if os.path.isfile(caminho) and allowed_file(nome):
                arquivos.append((os.path.getmtime(caminho), nome))
        if arquivos:
            arquivos.sort(reverse=True)
            return arquivos[0][1]
    except Exception:
        pass
    return None

def load_app_settings():
    padrao = {"club_name": "GETCLUB"}
    for caminho in [APP_SETTINGS_PATH, APP_SETTINGS_FALLBACK_PATH]:
        try:
            if os.path.exists(caminho):
                with open(caminho, "r", encoding="utf-8") as f:
                    dados = json.load(f)
                    if isinstance(dados, dict):
                        padrao.update(dados)
                        return padrao
        except Exception:
            continue
    return padrao

def save_app_settings(data):
    atual = load_app_settings()
    atual.update(data or {})
    ok = False
    for caminho in [APP_SETTINGS_PATH, APP_SETTINGS_FALLBACK_PATH]:
        try:
            pasta = os.path.dirname(caminho)
            if pasta:
                os.makedirs(pasta, exist_ok=True)
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(atual, f, ensure_ascii=False, indent=2)
            ok = True
        except Exception:
            continue
    return ok

from models import AvaliacaoFisica, AvaliacaoMental, AvaliacaoTatica, AvaliacaoTecnica, db, User, Atleta, ComissaoTecnica, Compra, GastoMensal, ContaFixa, Inventario, Reuniao, Evento, FichaMedica, Scouting, Patrocinio, Documento, EventoAtleta, Convocatoria, Convocada, EstatisticaJogo

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_foto_file():
    """
    Compatibilidade entre versões de template:
    algumas usam name='foto' e outras name='fotoInput'.
    """
    return request.files.get('foto') or request.files.get('fotoInput')

def salvar_foto_atleta(foto, foto_antiga=None):
    if not foto or not foto.filename:
        return None
    if not allowed_file(foto.filename):
        raise ValueError('Formato de imagem inválido. Use PNG, JPG, JPEG, GIF ou WEBP.')

    filename = secure_filename(f"{datetime.now().timestamp()}_{foto.filename}")
    destino = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    foto.save(destino)

    if foto_antiga and foto_antiga != filename:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], foto_antiga))
        except OSError:
            pass

    return filename

def garantir_colunas_atleta():
    colunas = [
        ("iban", "VARCHAR(34)"),
        ("cartoes_amarelos", "INTEGER DEFAULT 0"),
        ("cartoes_vermelhos", "INTEGER DEFAULT 0"),
        ("jogos_suspensao", "INTEGER DEFAULT 0"),
        ("desempenho_competicoes", "TEXT"),
        ("transferencias", "TEXT"),
        ("redes_sociais", "TEXT"),
    ]
    for nome, tipo in colunas:
        try:
            db.session.execute(text(f"ALTER TABLE atleta ADD COLUMN IF NOT EXISTS {nome} {tipo}"))
            db.session.commit()
        except Exception:
            db.session.rollback()
            try:
                db.session.execute(text(f"ALTER TABLE atleta ADD COLUMN {nome} {tipo}"))
                db.session.commit()
            except Exception:
                db.session.rollback()

def garantir_colunas_permissoes_usuario():
    colunas = [
        ("can_manage_atletas", "BOOLEAN DEFAULT FALSE"),
        ("can_manage_comissao", "BOOLEAN DEFAULT FALSE"),
        ("can_manage_financeiro", "BOOLEAN DEFAULT FALSE"),
        ("can_manage_inventario", "BOOLEAN DEFAULT FALSE"),
        ("can_manage_reunioes", "BOOLEAN DEFAULT FALSE"),
        ("can_manage_medico", "BOOLEAN DEFAULT FALSE"),
        ("can_manage_scouting", "BOOLEAN DEFAULT FALSE"),
        ("can_manage_documentos", "BOOLEAN DEFAULT FALSE"),
    ]
    for nome, tipo in colunas:
        try:
            db.session.execute(text(f"ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS {nome} {tipo}"))
            db.session.commit()
        except Exception:
            db.session.rollback()
            try:
                db.session.execute(text(f"ALTER TABLE user ADD COLUMN {nome} {tipo}"))
                db.session.commit()
            except Exception:
                db.session.rollback()

def garantir_colunas_convocatoria():
    try:
        db.session.execute(text("ALTER TABLE convocatoria ADD COLUMN IF NOT EXISTS treinador VARCHAR(100)"))
        db.session.commit()
    except Exception:
        db.session.rollback()
        try:
            db.session.execute(text("ALTER TABLE convocatoria ADD COLUMN treinador VARCHAR(100)"))
            db.session.commit()
        except Exception:
            db.session.rollback()

PERMISSAO_POR_ENDPOINT = {
    "atletas": "can_manage_atletas",
    "editar_atleta": "can_manage_atletas",
    "deletar_atleta": "can_manage_atletas",
    "registrar_cartao": "can_manage_atletas",
    "editar_suspensao": "can_manage_atletas",
    "cumprir_suspensao": "can_manage_atletas",
    "comissao": "can_manage_comissao",
    "editar_comissao": "can_manage_comissao",
    "deletar_comissao": "can_manage_comissao",
    "compras": "can_manage_financeiro",
    "deletar_compra": "can_manage_financeiro",
    "gastos": "can_manage_financeiro",
    "deletar_gasto": "can_manage_financeiro",
    "contas_fixas": "can_manage_financeiro",
    "toggle_conta_fixa": "can_manage_financeiro",
    "deletar_conta_fixa": "can_manage_financeiro",
    "patrocinios": "can_manage_financeiro",
    "adicionar_patrocinio": "can_manage_financeiro",
    "atualizar_patrocinio": "can_manage_financeiro",
    "deletar_patrocinio": "can_manage_financeiro",
    "inventario": "can_manage_inventario",
    "deletar_item": "can_manage_inventario",
    "reunioes": "can_manage_reunioes",
    "concluir_reuniao": "can_manage_reunioes",
    "deletar_reuniao": "can_manage_reunioes",
    "editar_reuniao": "can_manage_reunioes",
    "calendario": "can_manage_reunioes",
    "adicionar_evento": "can_manage_reunioes",
    "adicionar_reuniao": "can_manage_reunioes",
    "departamento_medico": "can_manage_medico",
    "adicionar_ficha_medica": "can_manage_medico",
    "atualizar_ficha_medica": "can_manage_medico",
    "scouting": "can_manage_scouting",
    "adicionar_scouting": "can_manage_scouting",
    "atualizar_scouting": "can_manage_scouting",
    "documentos": "can_manage_documentos",
    "upload_documento": "can_manage_documentos",
    "download_documento": "can_manage_documentos",
    "deletar_documento": "can_manage_documentos",
    "direcao": "can_manage_reunioes",
    "log_temporada_atletas": "can_manage_atletas",
    "adicionar_evento_atleta": "can_manage_atletas",
    "baixar_relatorio_atleta_pdf": "can_manage_atletas",
    "convocatorias": "can_manage_reunioes",
    "baixar_convocatoria_pdf": "can_manage_reunioes",
}

PERFIS_DIRECAO = {
    "diretor_futebol": {
        "label": "Diretor Futebol",
        "can_manage_atletas": True,
        "can_manage_comissao": True,
        "can_manage_reunioes": True,
        "can_manage_medico": True,
        "can_manage_scouting": True,
        "can_manage_documentos": True,
    },
    "team_manager": {
        "label": "Team Manager",
        "can_manage_atletas": True,
        "can_manage_reunioes": True,
        "can_manage_medico": True,
        "can_manage_documentos": True,
    },
    "supervisor": {
        "label": "Supervisor",
        "can_manage_atletas": True,
        "can_manage_comissao": True,
        "can_manage_financeiro": True,
        "can_manage_inventario": True,
        "can_manage_reunioes": True,
        "can_manage_medico": True,
        "can_manage_scouting": True,
        "can_manage_documentos": True,
    },
    "gerente_marketing": {
        "label": "Gerente Marketing",
        "can_manage_financeiro": True,
        "can_manage_reunioes": True,
        "can_manage_documentos": True,
    },
    "diretor_investidor": {
        "label": "Diretor Investidor",
        "can_manage_financeiro": True,
        "can_manage_reunioes": True,
        "can_manage_documentos": True,
    },
}

def aplicar_perfil_direcao(usuario, perfil):
    usuario.cargo_direcao = perfil if perfil in PERFIS_DIRECAO else None
    campos = [
        "can_manage_atletas",
        "can_manage_comissao",
        "can_manage_financeiro",
        "can_manage_inventario",
        "can_manage_reunioes",
        "can_manage_medico",
        "can_manage_scouting",
        "can_manage_documentos",
    ]
    for campo in campos:
        setattr(usuario, campo, False)
    if perfil in PERFIS_DIRECAO:
        for campo, valor in PERFIS_DIRECAO[perfil].items():
            if campo.startswith("can_manage_"):
                setattr(usuario, campo, valor)

def usuario_tem_permissao(permissao):
    if not current_user.is_authenticated:
        return False
    if current_user.is_admin:
        return True
    return bool(getattr(current_user, permissao, False))

def atleta_esta_apta(atleta):
    if (atleta.jogos_suspensao or 0) > 0:
        return False
    for ficha in atleta.fichas_medicas:
        if ficha.status == 'em_tratamento':
            return False
    return True

def _pdf_escape(texto):
    return texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

def gerar_pdf_simples(linhas):
    texto_pdf = "BT /F1 11 Tf 50 800 Td 14 TL "
    first = True
    for linha in linhas:
        safe = _pdf_escape(linha)
        if first:
            texto_pdf += f"({safe}) Tj "
            first = False
        else:
            texto_pdf += f"T* ({safe}) Tj "
    texto_pdf += "ET"
    stream = texto_pdf.encode("latin-1", errors="replace")

    objs = []
    objs.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objs.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objs.append(b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>endobj\n")
    objs.append(b"4 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")
    objs.append(f"5 0 obj<< /Length {len(stream)} >>stream\n".encode("latin-1") + stream + b"\nendstream endobj\n")

    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for obj in objs:
        offsets.append(len(pdf))
        pdf += obj
    xref_pos = len(pdf)
    pdf += f"xref\n0 {len(offsets)}\n".encode("latin-1")
    pdf += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        pdf += f"{off:010d} 00000 n \n".encode("latin-1")
    pdf += f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode("latin-1")
    return pdf

def carregar_foto_atleta(atleta):
    if not atleta.foto:
        return None
    try:
        path = os.path.join(app.config['UPLOAD_FOLDER'], atleta.foto)
        img = Image.open(path).convert("RGB")
        return img
    except Exception:
        return None

@app.context_processor
def inject_permissions():
    return {
        "usuario_tem_permissao": usuario_tem_permissao,
        "PERFIS_DIRECAO": PERFIS_DIRECAO
    }

@app.context_processor
def utility_processor():
    from datetime import datetime
    settings = load_app_settings()
    club_name     = (settings.get("club_name")     or "GETCLUB").strip()
    club_subtitulo= (settings.get("club_subtitulo") or "Painel Central de Gestão do Clube").strip()
    club_meta     = (settings.get("club_meta")      or "").strip()
    club_logo_filename = get_logo_clube_filename()
    club_logo_url = url_for('serve_logo_clube', filename=club_logo_filename) if club_logo_filename else None
    return {
        'now': datetime.now,
        'club_display_name': club_name,
        'club_subtitulo': club_subtitulo,
        'club_meta': club_meta,
        'club_logo_url': club_logo_url
    }

@app.before_request
def verificar_permissao_modulo():
    if not current_user.is_authenticated:
        return
    if current_user.is_admin:
        return
    endpoint = request.endpoint
    if not endpoint:
        return
    permissao = PERMISSAO_POR_ENDPOINT.get(endpoint)
    if permissao and not usuario_tem_permissao(permissao):
        flash("Você não tem permissão para acessar este módulo.", "error")
        return redirect(url_for("index"))

@app.before_request
def verificar_permissao_modulo():
    if not current_user.is_authenticated:
        return
    if current_user.is_admin:
        return
    endpoint = request.endpoint
    if not endpoint:
        return
    permissao = PERMISSAO_POR_ENDPOINT.get(endpoint)
    if permissao and not usuario_tem_permissao(permissao):
        flash("Você não tem permissão para acessar este módulo.", "error")
        return redirect(url_for("index"))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== ROTAS PRINCIPAIS ====================
@app.route('/')
@login_required
def index():
    mes_atual = datetime.now().strftime('%Y-%m')
    total_gastos = db.session.query(func.coalesce(func.sum(GastoMensal.valor), 0.0)).filter_by(mes=mes_atual).scalar() or 0
    total_compras_mes = db.session.query(func.coalesce(func.sum(Compra.total), 0.0)).filter(
        Compra.data_compra >= datetime.now().date().replace(day=1)
    ).scalar() or 0
    total_patrocinios_ativos = db.session.query(func.coalesce(func.sum(Patrocinio.valor_aporte), 0.0)).filter_by(status='ativo').scalar() or 0
    total_contas_fixas_ativas = db.session.query(func.coalesce(func.sum(ContaFixa.valor), 0.0)).filter(ContaFixa.status.in_(['ativo', 'ativa'])).scalar() or 0
    num_atletas = Atleta.query.count()
    num_reunioes = Reuniao.query.filter(Reuniao.data >= datetime.now().date()).count()
    atletas_recentes = Atleta.query.order_by(Atleta.id.desc()).limit(5).all()

    atletas_lesionados = FichaMedica.query.filter_by(status='em_tratamento').count()
    atletas_suspensos = Atleta.query.filter(Atleta.jogos_suspensao > 0).count()
    atletas_em_observacao = Scouting.query.filter_by(status='ativo').count()
    total_documentos = Documento.query.count()
    total_itens_inventario = db.session.query(func.coalesce(func.sum(Inventario.quantidade), 0)).scalar() or 0

    proximas_reunioes = Reuniao.query.filter(Reuniao.data >= datetime.now().date()).order_by(Reuniao.data.asc()).limit(5).all()
    eventos_calendario = Evento.query.filter(Evento.data >= datetime.now().date()).order_by(Evento.data.asc()).limit(5).all()
    convocatorias_recentes = Convocatoria.query.order_by(Convocatoria.data_jogo.desc()).limit(5).all()
    fichas_medicas_recentes = FichaMedica.query.order_by(FichaMedica.created_at.desc()).limit(5).all()

    club_logo_filename = get_logo_clube_filename()
    club_logo_url = url_for('serve_logo_clube', filename=club_logo_filename) if club_logo_filename else None

    return render_template(
        'index.html',
        total_gastos=total_gastos,
        total_compras_mes=total_compras_mes,
        total_patrocinios_ativos=total_patrocinios_ativos,
        total_contas_fixas_ativas=total_contas_fixas_ativas,
        num_atletas=num_atletas,
        num_reunioes=num_reunioes,
        atletas=atletas_recentes,
        atletas_lesionados=atletas_lesionados,
        atletas_suspensos=atletas_suspensos,
        atletas_em_observacao=atletas_em_observacao,
        total_documentos=total_documentos,
        total_itens_inventario=total_itens_inventario,
        proximas_reunioes=proximas_reunioes,
        eventos_calendario=eventos_calendario,
        convocatorias_recentes=convocatorias_recentes,
        fichas_medicas_recentes=fichas_medicas_recentes,
        club_logo_url=club_logo_url
    )

@app.route('/clube/logo', methods=['POST'])
@login_required
def upload_logo_clube():
    try:
        logo = request.files.get('logo_clube')
        if not logo or not logo.filename:
            flash('Selecione uma imagem para o logo do clube.', 'error')
            return redirect(url_for('index'))
        if not allowed_file(logo.filename):
            flash('Formato inválido. Use PNG, JPG, JPEG, GIF ou WEBP.', 'error')
            return redirect(url_for('index'))

        nome = secure_filename(logo.filename)
        ext = nome.rsplit('.', 1)[1].lower()
        novo_nome = f"club_logo_{int(datetime.now().timestamp())}.{ext}"
        destino = os.path.join(app.config['UPLOAD_FOLDER_CLUBE'], novo_nome)
        logo.save(destino)

        # Limpa logos antigos para manter apenas o atual.
        for antigo in os.listdir(app.config['UPLOAD_FOLDER_CLUBE']):
            if antigo != novo_nome:
                antigo_path = os.path.join(app.config['UPLOAD_FOLDER_CLUBE'], antigo)
                if os.path.isfile(antigo_path):
                    try:
                        os.remove(antigo_path)
                    except Exception:
                        pass

        flash('Logo do clube atualizada com sucesso.', 'success')
    except Exception as e:
        flash(f'Erro ao enviar logo do clube: {str(e)}', 'error')
    return redirect(url_for('index'))

@app.route('/clube/nome', methods=['POST'])
@login_required
def update_nome_clube():
    nome      = (request.form.get('club_name')      or '').strip()
    subtitulo = (request.form.get('club_subtitulo') or '').strip()
    meta      = (request.form.get('club_meta')      or '').strip()
    if not nome:
        flash('O nome do clube não pode ficar vazio.', 'error')
        return redirect(request.referrer or url_for('index'))
    ok = save_app_settings({
        "club_name":      nome[:80],
        "club_subtitulo": subtitulo[:120],
        "club_meta":      meta[:200],
    })
    if ok:
        flash('Informações do clube atualizadas com sucesso.', 'success')
    else:
        flash('Não foi possível salvar. Verifique permissões de escrita.', 'error')
    return redirect(request.referrer or url_for('index'))

@app.before_request
def verificar_licenca():
    """Bloqueia o acesso se o trial expirou e não há key ativada."""
    rotas_livres = {'ativar_licenca', 'static'}
    if request.endpoint in rotas_livres:
        return
    status, mensagem, dias = check_license()
    if status == 'need_key':
        return redirect(url_for('ativar_licenca'))

@app.route('/ativar', methods=['GET', 'POST'])
def ativar_licenca():
    from license import check_license, activate_license
    status, mensagem, dias = check_license()
    # Se já está ativa ou em trial, redirecionar
    if status == 'ok' and request.method == 'GET':
        return redirect(url_for('login'))
    
    erro = None
    sucesso = None
    if request.method == 'POST':
        key = request.form.get('key', '').strip()
        ok, msg = activate_license(key)
        if ok:
            sucesso = msg
        else:
            erro = msg
    
    return render_template('ativar_licenca.html', erro=erro, sucesso=sucesso, mensagem=mensagem)

@app.route('/atleta/novo', methods=['GET', 'POST'])
@login_required
def atleta_form():
    if request.method == 'POST':
        try:
            # Coletar dados do formulário
            atleta = Atleta(
                nome=request.form.get('nomeCompleto'),
                data_nascimento=datetime.strptime(request.form.get('dataNasc'), '%Y-%m-%d').date() if request.form.get('dataNasc') else None,
                posicao=request.form.get('posicao'),
                numero=request.form.get('numeroCamisa'),
                altura=float(request.form.get('altura')) if request.form.get('altura') else None,
                peso=float(request.form.get('peso')) if request.form.get('peso') else None,
                telefone=request.form.get('telefone'),
                email=request.form.get('email'),
                endereco=request.form.get('endereco'),
                categoria=request.form.get('categoria'),
                salario=float(request.form.get('salario') or 0),
                premios=float(request.form.get('premios') or 0),
                contrato_inicio=datetime.strptime(request.form.get('contratoInicio'), '%Y-%m-%d').date() if request.form.get('contratoInicio') else None,
                contrato_fim=datetime.strptime(request.form.get('contratoFim'), '%Y-%m-%d').date() if request.form.get('contratoFim') else None,
                status=request.form.get('statusAtleta', 'ativo'),
                cartoes_amarelos=int(request.form.get('cartoesAmarelos') or 0),
                cartoes_vermelhos=int(request.form.get('cartoesVermelhos') or 0),
                jogos_suspensao=int(request.form.get('suspensoes') or 0)
            )
            
            # Salvar foto se houver
            foto = get_foto_file()
            if foto and foto.filename:
                filename = salvar_foto_atleta(foto)
                atleta.foto = filename
            
            db.session.add(atleta)
            db.session.commit()
            flash(f'Atleta {atleta.nome} cadastrado com sucesso!', 'success')
            return redirect(url_for('atletas'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao salvar: {str(e)}', 'error')
    
    return render_template('atleta_form.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Usuário ou senha inválidos', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ==================== ROTAS PARA USUÁRIOS ====================
@app.route('/usuarios')
@login_required
def usuarios():
    if not current_user.is_admin:
        flash('Acesso restrito a administradores!', 'error')
        return redirect(url_for('index'))
    
    todos_usuarios = User.query.all()
    return render_template('usuarios.html', usuarios=todos_usuarios)

@app.route('/criar-usuario', methods=['POST'])
@login_required
def criar_usuario():
    if not current_user.is_admin:
        flash('Acesso negado!', 'error')
        return redirect(url_for('usuarios'))
    
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    is_admin = request.form.get('is_admin') == '1'
    perfil_direcao = request.form.get('perfil_direcao') or None
    
    if User.query.filter_by(username=username).first():
        flash(f'Usuário {username} já existe!', 'warning')
        return redirect(url_for('usuarios'))
    
    if User.query.filter_by(email=email).first():
        flash(f'Email {email} já cadastrado!', 'warning')
        return redirect(url_for('usuarios'))
    
    try:
        novo = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            is_admin=is_admin,
            can_manage_atletas=is_admin,
            can_manage_comissao=is_admin,
            can_manage_financeiro=is_admin,
            can_manage_inventario=is_admin,
            can_manage_reunioes=is_admin,
            can_manage_medico=is_admin,
            can_manage_scouting=is_admin,
            can_manage_documentos=is_admin,
            cargo_direcao=None
        )
        if not is_admin and perfil_direcao:
            aplicar_perfil_direcao(novo, perfil_direcao)
        db.session.add(novo)
        db.session.commit()
        flash(f'Usuário {username} criado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar usuário: {str(e)}', 'error')
    
    return redirect(url_for('usuarios'))

@app.route('/deletar-usuario/<int:id>')
@login_required
def deletar_usuario(id):
    if not current_user.is_admin:
        flash('Acesso negado!', 'error')
        return redirect(url_for('usuarios'))
    
    if id == current_user.id:
        flash('Você não pode deletar seu próprio usuário!', 'warning')
        return redirect(url_for('usuarios'))
    
    usuario = User.query.get_or_404(id)
    nome = usuario.username
    db.session.delete(usuario)
    db.session.commit()
    
    flash(f'Usuário {nome} removido com sucesso!', 'success')
    return redirect(url_for('usuarios'))

@app.route('/permissoes')
@login_required
def permissoes():
    if not current_user.is_admin:
        flash('Acesso restrito a administradores!', 'error')
        return redirect(url_for('index'))
    todos_usuarios = User.query.order_by(User.username.asc()).all()
    return render_template('permissoes.html', usuarios=todos_usuarios)

@app.route('/permissoes/atualizar/<int:id>', methods=['POST'])
@login_required
def atualizar_permissoes(id):
    if not current_user.is_admin:
        flash('Acesso negado!', 'error')
        return redirect(url_for('index'))

    usuario = User.query.get_or_404(id)
    try:
        novo_admin = request.form.get('is_admin') == 'on'
        perfil_direcao = request.form.get('perfil_direcao') or None
        usuario.is_admin = novo_admin
        if novo_admin:
            usuario.can_manage_atletas = True
            usuario.can_manage_comissao = True
            usuario.can_manage_financeiro = True
            usuario.can_manage_inventario = True
            usuario.can_manage_reunioes = True
            usuario.can_manage_medico = True
            usuario.can_manage_scouting = True
            usuario.can_manage_documentos = True
            usuario.cargo_direcao = None
        elif perfil_direcao in PERFIS_DIRECAO:
            aplicar_perfil_direcao(usuario, perfil_direcao)
        else:
            usuario.cargo_direcao = None
            usuario.can_manage_atletas = request.form.get('can_manage_atletas') == 'on'
            usuario.can_manage_comissao = request.form.get('can_manage_comissao') == 'on'
            usuario.can_manage_financeiro = request.form.get('can_manage_financeiro') == 'on'
            usuario.can_manage_inventario = request.form.get('can_manage_inventario') == 'on'
            usuario.can_manage_reunioes = request.form.get('can_manage_reunioes') == 'on'
            usuario.can_manage_medico = request.form.get('can_manage_medico') == 'on'
            usuario.can_manage_scouting = request.form.get('can_manage_scouting') == 'on'
            usuario.can_manage_documentos = request.form.get('can_manage_documentos') == 'on'
        db.session.commit()
        flash(f'Permissões de {usuario.username} atualizadas!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar permissões: {str(e)}', 'error')
    return redirect(url_for('permissoes'))

# ==================== ROTAS PARA ATLETAS ====================
@app.route('/atletas', methods=['GET', 'POST'])
@login_required
def atletas():
    if request.method == 'POST':
        try:
            nome = request.form.get('nome', '').strip()
            if not nome:
                flash('Nome do atleta é obrigatório!', 'error')
                return redirect(url_for('atletas'))
            
            foto_path = None
            if 'foto' in request.files:
                foto = request.files['foto']
                if foto and foto.filename:
                    foto_path = salvar_foto_atleta(foto)
            
            atleta = Atleta(
                nome=nome,
                data_nascimento=datetime.strptime(request.form['data_nascimento'], '%Y-%m-%d').date() if request.form.get('data_nascimento') else datetime.now().date(),
                posicao=request.form.get('posicao') or None,
                numero=request.form.get('numero') or None,
                altura=float(request.form['altura']) if request.form.get('altura') else None,
                peso=float(request.form['peso']) if request.form.get('peso') else None,
                telefone=request.form.get('telefone') or None,
                email=request.form.get('email') or None,
                iban=request.form.get('iban') or None,
                endereco=request.form.get('endereco') or None,
                categoria=request.form.get('categoria') or None,
                salario=float(request.form.get('salario') or 0),
                premios=float(request.form.get('premios') or 0),
                contrato_inicio=datetime.strptime(request.form.get('contrato_inicio'), '%Y-%m-%d').date() if request.form.get('contrato_inicio') else None,
                contrato_fim=datetime.strptime(request.form.get('contrato_fim'), '%Y-%m-%d').date() if request.form.get('contrato_fim') else None,
                status=request.form.get('status') or 'ativo',
                cartoes_amarelos=int(request.form.get('cartoes_amarelos') or 0),
                cartoes_vermelhos=int(request.form.get('cartoes_vermelhos') or 0),
                jogos_suspensao=int(request.form.get('jogos_suspensao') or 0),
                foto=foto_path
            )
            db.session.add(atleta)
            db.session.commit()
            flash(f'Atleta {nome} cadastrado com sucesso!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar atleta: {str(e)}', 'error')
        return redirect(url_for('atletas'))
    
    atletas_list = Atleta.query.all()
    return render_template('atletas.html', atletas=atletas_list)

@app.route('/atletas/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_atleta(id):
    atleta = Atleta.query.get_or_404(id)

    def _to_int(value, default=0):
        try:
            if value is None:
                return default
            if isinstance(value, str):
                value = value.strip().replace(",", ".")
                if not value:
                    return default
            return int(float(value))
        except Exception:
            return default

    def _to_float(value, default=0.0):
        try:
            if value is None:
                return default
            if isinstance(value, str):
                value = value.strip().replace(",", ".")
                if not value:
                    return default
            return float(value)
        except Exception:
            return default

    def _parse_json(value, default):
        try:
            if value is None:
                return default
            if isinstance(value, (list, dict)):
                return value
            txt = str(value).strip()
            if not txt:
                return default
            return json.loads(txt)
        except Exception:
            return default

    def _coerce_date(value):
        if value is None:
            return None
        if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(raw, fmt).date()
                except Exception:
                    continue
        return None

    def _safe_date_str(value):
        d = _coerce_date(value)
        return d.strftime("%d/%m/%Y") if d else ""
    
    if request.method == 'POST':
        try:
            atleta.nome = request.form.get('nome', '').strip()
            atleta.data_nascimento = datetime.strptime(request.form.get('data_nascimento'), '%Y-%m-%d').date() if request.form.get('data_nascimento') else atleta.data_nascimento
            atleta.posicao = request.form.get('posicao') or None
            atleta.numero = request.form.get('numero') or None
            atleta.altura = _to_float(request.form.get('altura'), None)
            atleta.peso = _to_float(request.form.get('peso'), None)
            atleta.telefone = request.form.get('telefone') or None
            atleta.email = request.form.get('email') or None
            atleta.iban = request.form.get('iban') or None
            atleta.categoria = request.form.get('categoria') or None
            atleta.endereco = request.form.get('endereco') or None
            atleta.status = request.form.get('status') or atleta.status or 'ativo'
            atleta.cartoes_amarelos = _to_int(request.form.get('cartoes_amarelos'), 0)
            atleta.cartoes_vermelhos = _to_int(request.form.get('cartoes_vermelhos'), 0)
            atleta.jogos_suspensao = _to_int(request.form.get('jogos_suspensao'), 0)
            atleta.salario = _to_float(request.form.get('salario'), 0)
            atleta.premios = _to_float(request.form.get('premios'), 0)
            atleta.contrato_inicio = datetime.strptime(request.form.get('contrato_inicio'), '%Y-%m-%d').date() if request.form.get('contrato_inicio') else None
            atleta.contrato_fim = datetime.strptime(request.form.get('contrato_fim'), '%Y-%m-%d').date() if request.form.get('contrato_fim') else None
            desempenho_bruto = request.form.get('desempenho_competicoes') or '[]'
            atleta.desempenho_competicoes = desempenho_bruto or None
            atleta.transferencias = request.form.get('transferencias') or None
            atleta.redes_sociais = request.form.get('redes_sociais') or None

            # Sincroniza a aba de desempenho com a tabela oficial de estatísticas de jogo
            linhas = _parse_json(desempenho_bruto, [])

            existentes = {j.id: j for j in EstatisticaJogo.query.filter_by(atleta_id=atleta.id).all()}
            ids_mantidos = set()
            suspensoes_automaticas = 0
            vermelhos_desempenho = 0

            for linha in linhas:
                if isinstance(linha, dict):
                    jogo_id = linha.get('id')
                    data_jogo_raw = (linha.get('data_jogo') or '').strip()
                    temporada = (linha.get('temporada') or '').strip()
                    adversario = (linha.get('competicao') or '').strip()
                    minutos = _to_int(linha.get('minutos'), 0)
                    jogos = _to_int(linha.get('jogos'), 1)
                    gols = _to_int(linha.get('gols'), 0)
                    assist = _to_int(linha.get('assistencias'), 0)
                    amarelos = _to_int(linha.get('amarelos'), 0)
                    vermelhos = _to_int(linha.get('vermelhos'), 0)
                    finalizacoes = _to_int(linha.get('finalizacoes'), 0)
                    passes_certos = _to_int(linha.get('passes_certos'), 0)
                    passes_errados = _to_int(linha.get('passes_errados'), 0)
                    desarmes = _to_int(linha.get('desarmes'), 0)
                    faltas_cometidas = _to_int(linha.get('faltas_cometidas'), 0)
                    faltas_sofridas = _to_int(linha.get('faltas_sofridas'), 0)
                    nota_jogo = _to_float(linha.get('nota_jogo'), 0)
                    suspensao_jogos = _to_int(linha.get('suspensao_jogos'), 0)
                elif isinstance(linha, list):
                    jogo_id = None
                    data_jogo_raw = ''
                    temporada = (linha[0] if len(linha) > 0 else '')
                    adversario = (linha[1] if len(linha) > 1 else '')
                    minutos = _to_int(linha[2] if len(linha) > 2 else 0, 0)
                    jogos = _to_int(linha[3] if len(linha) > 3 else 1, 1)
                    gols = _to_int(linha[6] if len(linha) > 6 else 0, 0)
                    assist = _to_int(linha[7] if len(linha) > 7 else 0, 0)
                    amarelos = _to_int(linha[8] if len(linha) > 8 else 0, 0)
                    vermelhos = _to_int(linha[9] if len(linha) > 9 else 0, 0)
                    finalizacoes = 0
                    passes_certos = 0
                    passes_errados = 0
                    desarmes = 0
                    faltas_cometidas = 0
                    faltas_sofridas = 0
                    nota_jogo = 0
                    suspensao_jogos = 0
                else:
                    continue

                temporada = temporada or f"{datetime.now().year}/{datetime.now().year + 1}"

                data_jogo = datetime.now().date()
                if data_jogo_raw:
                    try:
                        if '/' in data_jogo_raw:
                            data_jogo = datetime.strptime(data_jogo_raw, '%d/%m/%Y').date()
                        else:
                            data_jogo = datetime.strptime(data_jogo_raw, '%Y-%m-%d').date()
                    except Exception:
                        data_jogo = datetime.now().date()

                if jogo_id and jogo_id in existentes:
                    jogo = existentes[jogo_id]
                    ids_mantidos.add(jogo_id)
                else:
                    jogo = EstatisticaJogo(
                        atleta_id=atleta.id,
                        data_jogo=datetime.now().date(),
                        temporada=temporada,
                    )
                    db.session.add(jogo)

                jogo.temporada = temporada
                jogo.data_jogo = data_jogo
                jogo.adversario = adversario
                jogo.minutos_jogados = max(0, minutos)
                jogo.gols = max(0, gols)
                jogo.assistencias = max(0, assist)
                jogo.cartoes_amarelos = max(0, amarelos)
                jogo.cartoes_vermelhos = max(0, vermelhos)
                jogo.finalizacoes = max(0, finalizacoes)
                jogo.passes_certos = max(0, passes_certos)
                jogo.passes_errados = max(0, passes_errados)
                jogo.desarmes = max(0, desarmes)
                jogo.faltas_cometidas = max(0, faltas_cometidas)
                jogo.faltas_sofridas = max(0, faltas_sofridas)
                jogo.nota_jogo = max(0, nota_jogo)
                jogo.observacao = jogo.observacao or ''
                if vermelhos > 0:
                    vermelhos_desempenho += max(0, vermelhos)
                    suspensoes_automaticas += max(1, suspensao_jogos)

            for jogo_id, jogo in existentes.items():
                if jogo_id not in ids_mantidos:
                    db.session.delete(jogo)

            suspensao_manual = _to_int(request.form.get('jogos_suspensao'), 0)
            vermelhos_total = max(0, atleta.cartoes_vermelhos or 0, vermelhos_desempenho)
            suspensao_por_vermelho = 1 if vermelhos_total > 0 else 0
            atleta.jogos_suspensao = max(0, suspensao_manual, suspensoes_automaticas, suspensao_por_vermelho)

            foto = get_foto_file()
            if foto and foto.filename:
                filename = salvar_foto_atleta(foto, atleta.foto)
                atleta.foto = filename
            
            db.session.commit()
            flash(f'Atleta {atleta.nome} atualizado!', 'success')
            return redirect(url_for('editar_atleta', id=atleta.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'error')

    # Normaliza datas para evitar erro de template em bases antigas com texto em campos de data.
    atleta.data_nascimento = _coerce_date(atleta.data_nascimento)
    atleta.contrato_inicio = _coerce_date(atleta.contrato_inicio)
    atleta.contrato_fim = _coerce_date(atleta.contrato_fim)

    jogos_desempenho = EstatisticaJogo.query.filter_by(atleta_id=atleta.id).order_by(EstatisticaJogo.data_jogo.desc()).all()
    desempenho_competicoes = [
        {
            'id': j.id,
            'data_jogo': _safe_date_str(j.data_jogo),
            'temporada': j.temporada or '',
            'competicao': j.adversario or '',
            'minutos': j.minutos_jogados or 0,
            'jogos': 1,
            'titulares': 0,
            'substituicoes': 0,
            'gols': j.gols or 0,
            'assistencias': j.assistencias or 0,
            'amarelos': j.cartoes_amarelos or 0,
            'vermelhos': j.cartoes_vermelhos or 0,
            'finalizacoes': j.finalizacoes or 0,
            'passes_certos': j.passes_certos or 0,
            'passes_errados': j.passes_errados or 0,
            'desarmes': j.desarmes or 0,
            'faltas_cometidas': j.faltas_cometidas or 0,
            'faltas_sofridas': j.faltas_sofridas or 0,
            'nota_jogo': j.nota_jogo or 0,
            'suspensao_jogos': 1 if (j.cartoes_vermelhos or 0) > 0 else 0,
        }
        for j in jogos_desempenho
    ]

    if not desempenho_competicoes and atleta.desempenho_competicoes:
        try:
            desempenho_competicoes = json.loads(atleta.desempenho_competicoes)
        except Exception:
            desempenho_competicoes = []

    transferencias = []
    redes_sociais = {}
    transferencias = _parse_json(atleta.transferencias, [])
    redes_sociais = _parse_json(atleta.redes_sociais, {})

    return render_template(
        'editar_atleta.html',
        atleta=atleta,
        desempenho_competicoes=desempenho_competicoes,
        transferencias=transferencias,
        redes_sociais=redes_sociais
    )

@app.route('/atletas/editar/<int:id>/foto', methods=['POST'])
@login_required
def editar_foto_atleta(id):
    atleta = Atleta.query.get_or_404(id)
    try:
        foto = get_foto_file()
        if not foto or not foto.filename:
            return jsonify({'ok': False, 'error': 'Selecione uma imagem.'}), 400

        filename = salvar_foto_atleta(foto, atleta.foto)
        atleta.foto = filename
        db.session.commit()

        foto_url = url_for('serve_foto_atleta', filename=filename, v=int(datetime.now().timestamp()))
        return jsonify({'ok': True, 'foto': filename, 'foto_url': foto_url})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 400

@app.route('/atletas/relatorio/pdf/<int:id>')
@login_required
def baixar_relatorio_atleta_pdf(id):
    try:
        atleta = Atleta.query.get_or_404(id)
        estatisticas = (
            EstatisticaJogo.query
            .filter_by(atleta_id=atleta.id)
            .order_by(EstatisticaJogo.data_jogo.desc(), EstatisticaJogo.id.desc())
            .all()
        )

        total_jogos = len(estatisticas)
        total_gols = sum((e.gols or 0) for e in estatisticas)
        total_assist = sum((e.assistencias or 0) for e in estatisticas)
        total_min = sum((e.minutos_jogados or 0) for e in estatisticas)
        total_am = sum((e.cartoes_amarelos or 0) for e in estatisticas)
        total_vm = sum((e.cartoes_vermelhos or 0) for e in estatisticas)

        idade_txt = "-"
        if atleta.data_nascimento:
            idade = int((datetime.now().date() - atleta.data_nascimento).days / 365.25)
            idade_txt = f"{idade} anos"

        temporadas = {}
        for e in estatisticas:
            temporada = e.temporada or "Sem temporada"
            if temporada not in temporadas:
                temporadas[temporada] = {"gols": 0, "assist": 0}
            temporadas[temporada]["gols"] += (e.gols or 0)
            temporadas[temporada]["assist"] += (e.assistencias or 0)

        temporadas_labels = list(temporadas.keys())[:8]
        gols_temp = [temporadas[t]["gols"] for t in temporadas_labels]
        assist_temp = [temporadas[t]["assist"] for t in temporadas_labels]

        arquivo = BytesIO()
        with PdfPages(arquivo) as pdf:
            fig = plt.figure(figsize=(8.27, 11.69))
            fig.patch.set_facecolor("white")

            y = 0.96
            fig.text(0.07, y, "US 1919 Genève-Ville - Relatório Individual de Desempenho", fontsize=18, weight="bold", color="#111827")
            y -= 0.035
            fig.text(0.07, y, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", fontsize=9, color="#6b7280")

            y -= 0.05
            fig.text(0.07, y, f"Atleta: {atleta.nome}", fontsize=14, weight="bold", color="#111827")
            y -= 0.028
            fig.text(
                0.07,
                y,
                f"Posição: {atleta.posicao or '-'} | Nº: {atleta.numero or '-'} | Idade: {idade_txt} | Categoria: {atleta.categoria or '-'}",
                fontsize=10,
                color="#374151",
            )
            y -= 0.022
            fig.text(
                0.07,
                y,
                f"Status: {atleta.status or '-'} | Contrato até: {atleta.contrato_fim.strftime('%d/%m/%Y') if atleta.contrato_fim else '-'}",
                fontsize=10,
                color="#374151",
            )

            y -= 0.05
            fig.text(0.07, y, "Resumo Estatístico", fontsize=12, weight="bold", color="#111827")
            y -= 0.032
            fig.text(0.08, y, f"Jogos: {total_jogos}", fontsize=11)
            fig.text(0.28, y, f"Gols: {total_gols}", fontsize=11)
            fig.text(0.45, y, f"Assistências: {total_assist}", fontsize=11)
            fig.text(0.67, y, f"Minutos: {total_min}", fontsize=11)
            y -= 0.026
            fig.text(0.08, y, f"Cartões Amarelos: {total_am}", fontsize=10, color="#92400e")
            fig.text(0.35, y, f"Cartões Vermelhos: {total_vm}", fontsize=10, color="#991b1b")
            fig.text(0.62, y, f"Suspensão Atual: {atleta.jogos_suspensao or 0}", fontsize=10, color="#4b5563")

            ax = fig.add_axes([0.09, 0.40, 0.82, 0.25])
            if temporadas_labels:
                x = range(len(temporadas_labels))
                ax.bar([i - 0.2 for i in x], gols_temp, width=0.4, label="Gols", color="#6c2bd9")
                ax.bar([i + 0.2 for i in x], assist_temp, width=0.4, label="Assistências", color="#10b981")
                ax.set_xticks(list(x))
                ax.set_xticklabels(temporadas_labels, rotation=20, ha="right", fontsize=8)
                ax.set_title("Produção Ofensiva por Temporada", fontsize=11, pad=12)
                ax.grid(axis="y", alpha=0.2)
                ax.legend(fontsize=8)
            else:
                ax.text(0.5, 0.5, "Sem dados de desempenho para exibir gráfico.", ha="center", va="center", fontsize=10)
                ax.axis("off")

            y_table = 0.32
            fig.text(0.07, y_table, "Últimos Jogos", fontsize=12, weight="bold", color="#111827")
            y_table -= 0.02
            fig.text(0.07, y_table, "Data      Adversário                  G  A  Min  CA  CV  Nota", fontsize=9, family="monospace", color="#6b7280")
            y_table -= 0.017

            for e in estatisticas[:12]:
                data_str = e.data_jogo.strftime("%d/%m/%y") if e.data_jogo else "--/--/--"
                adv = (e.adversario or "-")[:24].ljust(24)
                linha = (
                    f"{data_str}  {adv}  "
                    f"{(e.gols or 0):>1}  {(e.assistencias or 0):>1}  {(e.minutos_jogados or 0):>3}  "
                    f"{(e.cartoes_amarelos or 0):>2}  {(e.cartoes_vermelhos or 0):>2}  {(e.nota_jogo or 0):>4.1f}"
                )
                fig.text(0.07, y_table, linha, fontsize=8.8, family="monospace", color="#111827")
                y_table -= 0.016
                if y_table < 0.06:
                    break

            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)

        arquivo.seek(0)
        nome_arquivo = f"relatorio_desempenho_{atleta.nome.replace(' ', '_')}.pdf"
        return send_file(arquivo, mimetype="application/pdf", as_attachment=True, download_name=nome_arquivo)
    except Exception as e:
        linhas = [
            "US 1919 Genève-Ville - Relatório de Desempenho",
            f"Atleta: {id}",
            f"Erro na geração avançada: {str(e)}",
            "Foi gerado um relatório simplificado para não interromper o fluxo.",
        ]
        pdf_bytes = gerar_pdf_simples(linhas)
        return send_file(BytesIO(pdf_bytes), mimetype="application/pdf", as_attachment=True, download_name=f"relatorio_atleta_{id}.pdf")

@app.route('/atletas/deletar/<int:id>')
@login_required
def deletar_atleta(id):
    atleta = Atleta.query.get_or_404(id)
    nome = atleta.nome
    
    # Remove fichas médicas vinculadas
    FichaMedica.query.filter_by(atleta_id=id).delete()
    # Remove estatísticas e vínculos de convocação para evitar bloqueio por FK
    EstatisticaJogo.query.filter_by(atleta_id=id).delete()
    Convocada.query.filter_by(atleta_id=id).delete()
    
    if atleta.foto:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], atleta.foto))
        except:
            pass
    
    db.session.delete(atleta)
    db.session.commit()
    flash(f'Atleta {nome} removido!', 'success')
    return redirect(url_for('atletas'))

@app.route('/atletas/cartao/<int:id>', methods=['POST'])
@login_required
def registrar_cartao(id):
    atleta = Atleta.query.get_or_404(id)
    tipo = (request.form.get('tipo_cartao') or '').strip().lower()

    try:
        atleta.cartoes_amarelos = atleta.cartoes_amarelos or 0
        atleta.cartoes_vermelhos = atleta.cartoes_vermelhos or 0
        atleta.jogos_suspensao = atleta.jogos_suspensao or 0

        if tipo == 'amarelo':
            atleta.cartoes_amarelos += 1
            if atleta.cartoes_amarelos % 5 == 0:
                atleta.jogos_suspensao += 1
                flash(f'{atleta.nome}: 5 amarelos acumulados. Suspensão automática de 1 jogo.', 'warning')
            else:
                flash(f'Cartão amarelo registado para {atleta.nome}.', 'success')
        elif tipo == 'vermelho':
            jogos = int(request.form.get('jogos_suspensao_vermelho') or 1)
            jogos = max(1, jogos)
            atleta.cartoes_vermelhos += 1
            atleta.jogos_suspensao += jogos
            flash(f'Cartão vermelho registado para {atleta.nome}. Suspensão: {jogos} jogo(s).', 'warning')
        else:
            flash('Tipo de cartão inválido.', 'error')
            return redirect(url_for('atletas'))

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao registar cartão: {str(e)}', 'error')

    return redirect(url_for('atletas'))

@app.route('/atletas/suspensao/<int:id>', methods=['POST'])
@login_required
def editar_suspensao(id):
    atleta = Atleta.query.get_or_404(id)
    try:
        jogos = int(request.form.get('jogos_suspensao') or 0)
        atleta.jogos_suspensao = max(0, jogos)
        db.session.commit()
        flash(f'Suspensão de {atleta.nome} atualizada para {atleta.jogos_suspensao} jogo(s).', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar suspensão: {str(e)}', 'error')
    return redirect(url_for('atletas'))

@app.route('/atletas/cumprir-suspensao/<int:id>', methods=['POST'])
@login_required
def cumprir_suspensao(id):
    atleta = Atleta.query.get_or_404(id)
    try:
        atual = atleta.jogos_suspensao or 0
        atleta.jogos_suspensao = max(0, atual - 1)
        db.session.commit()
        flash(f'{atleta.nome}: 1 jogo de suspensão cumprido.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar suspensão: {str(e)}', 'error')
    return redirect(url_for('atletas'))

@app.route('/atletas/log-temporada')
@login_required
def log_temporada_atletas():
    atletas = Atleta.query.order_by(Atleta.nome.asc()).all()
    eventos = EventoAtleta.query.order_by(EventoAtleta.data_evento.desc(), EventoAtleta.id.desc()).all()
    return render_template('log_temporada_atletas.html', atletas=atletas, eventos=eventos)

@app.route('/atletas/log-temporada/adicionar', methods=['POST'])
@login_required
def adicionar_evento_atleta():
    try:
        evento = EventoAtleta(
            atleta_id=int(request.form['atleta_id']),
            data_evento=datetime.strptime(request.form['data_evento'], '%Y-%m-%d').date() if request.form.get('data_evento') else datetime.now().date(),
            tipo=request.form['tipo'],
            titulo=request.form['titulo'],
            descricao=request.form.get('descricao', ''),
            created_by=current_user.username
        )
        db.session.add(evento)
        db.session.commit()
        flash('Evento adicionado ao log da atleta!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao adicionar evento: {str(e)}', 'error')
    return redirect(url_for('log_temporada_atletas'))

@app.route('/convocatorias', methods=['GET', 'POST'])
@login_required
def convocatorias():
    if request.method == 'POST':
        try:
            titulo = request.form.get('titulo', '').strip()
            if not titulo:
                flash('Título da convocatória é obrigatório.', 'error')
                return redirect(url_for('convocatorias'))

            convocatoria = Convocatoria(
                titulo=titulo,
                adversario=request.form.get('adversario', '').strip() or None,
                treinador=request.form.get('treinador', '').strip() or None,
                data_jogo=datetime.strptime(request.form['data_jogo'], '%Y-%m-%d').date() if request.form.get('data_jogo') else datetime.now().date(),
                observacoes=request.form.get('observacoes', ''),
                created_by=current_user.username
            )
            db.session.add(convocatoria)
            db.session.flush()

            atletas_ids = request.form.getlist('atletas_ids')
            for atleta_id in atletas_ids:
                db.session.add(Convocada(convocatoria_id=convocatoria.id, atleta_id=int(atleta_id)))

            db.session.commit()
            flash('Convocatória criada com sucesso!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar convocatória: {str(e)}', 'error')
        return redirect(url_for('convocatorias'))

    atletas = Atleta.query.order_by(Atleta.nome.asc()).all()
    aptas = [a for a in atletas if atleta_esta_apta(a)]
    indisponiveis = [a for a in atletas if not atleta_esta_apta(a)]
    convocatorias_list = Convocatoria.query.order_by(Convocatoria.data_jogo.desc(), Convocatoria.id.desc()).all()
    categorias = sorted(set(a.categoria for a in aptas if a.categoria))
    return render_template(
        'convocatorias.html',
        aptas=aptas,
        indisponiveis=indisponiveis,
        convocatorias=convocatorias_list,
        categorias=categorias
    )

@app.route('/convocatorias/pdf/<int:id>')
@login_required
def baixar_convocatoria_pdf(id):
    convocatoria = Convocatoria.query.get_or_404(id)
    convocadas = [j.atleta for j in convocatoria.jogadoras if j.atleta]

    arquivo = BytesIO()
    with PdfPages(arquivo) as pdf:
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.patch.set_facecolor("white")
        y = 0.96
        fig.text(0.08, y, "US 1919 Genève-Ville - Convocatória Oficial", fontsize=16, weight="bold")
        y -= 0.04
        fig.text(0.08, y, f"Titulo: {convocatoria.titulo}", fontsize=11)
        y -= 0.025
        fig.text(0.08, y, f"Adversario: {convocatoria.adversario or '-'}", fontsize=11)
        y -= 0.025
        data_jogo = convocatoria.data_jogo.strftime('%d/%m/%Y') if convocatoria.data_jogo else '-'
        fig.text(0.08, y, f"Data do Jogo: {data_jogo}", fontsize=11)
        y -= 0.025
        fig.text(0.08, y, f"Treinador: {convocatoria.treinador or '-'}", fontsize=11)
        y -= 0.04
        fig.text(0.08, y, "Jogadoras Convocadas:", fontsize=12, weight="bold")
        y -= 0.03

        if convocadas:
            for idx, atleta in enumerate(convocadas, start=1):
                fig.text(0.1, y, f"{idx}. {atleta.nome}", fontsize=10)
                y -= 0.022
                if y < 0.08:
                    break
        else:
            fig.text(0.1, y, "Nenhuma jogadora convocada.", fontsize=10)
            y -= 0.022

        if convocatoria.observacoes:
            y -= 0.02
            fig.text(0.08, y, "Observacoes:", fontsize=11, weight="bold")
            y -= 0.025
            fig.text(0.1, y, convocatoria.observacoes[:2500], fontsize=9, wrap=True)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        if convocadas:
            cols = 3
            rows = math.ceil(len(convocadas) / cols)
            fig2, axs = plt.subplots(rows, cols, figsize=(8.27, 11.69))
            fig2.suptitle("Jogadoras Convocadas - Fotos", fontsize=14, weight="bold")
            axs = axs.flatten() if hasattr(axs, "flatten") else [axs]
            for ax in axs:
                ax.axis("off")
            for i, atleta in enumerate(convocadas):
                ax = axs[i]
                foto = carregar_foto_atleta(atleta)
                if foto is not None:
                    ax.imshow(foto)
                else:
                    ax.text(0.5, 0.5, "Sem foto", ha="center", va="center", fontsize=9)
                    ax.set_facecolor("#f2f2f2")
                ax.set_title(atleta.nome, fontsize=9)
                ax.axis("off")
            pdf.savefig(fig2, bbox_inches="tight")
            plt.close(fig2)

    arquivo.seek(0)
    nome_arquivo = f"convocatoria_{convocatoria.id}.pdf"
    return send_file(arquivo, mimetype="application/pdf", as_attachment=True, download_name=nome_arquivo)

# ==================== ROTAS PARA COMISSÃO TÉCNICA ====================
@app.route('/comissao', methods=['GET', 'POST'])
@login_required
def comissao():
    if request.method == 'POST':
        try:
            foto_path = None
            if 'foto' in request.files:
                foto = request.files['foto']
                if foto and foto.filename and allowed_file(foto.filename):
                    filename = secure_filename(f"{datetime.now().timestamp()}_{foto.filename}")
                    foto.save(os.path.join(app.config['UPLOAD_FOLDER_COMISSAO'], filename))
                    foto_path = filename
            
            membro = ComissaoTecnica(
                nome=request.form['nome'],
                cargo=request.form['cargo'],
                especialidade=request.form.get('especialidade', ''),
                telefone=request.form.get('telefone', ''),
                email=request.form.get('email', ''),
                data_contratacao=datetime.strptime(request.form['data_contratacao'], '%Y-%m-%d').date() if request.form.get('data_contratacao') else datetime.now().date(),
                foto=foto_path
            )
            db.session.add(membro)
            db.session.commit()
            flash(f'Membro {membro.nome} cadastrado!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'error')
        return redirect(url_for('comissao'))
    
    comissao_list = ComissaoTecnica.query.all()
    return render_template('comissao.html', comissao=comissao_list)

@app.route('/comissao/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_comissao(id):
    membro = ComissaoTecnica.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            membro.nome = request.form['nome']
            membro.cargo = request.form['cargo']
            membro.especialidade = request.form.get('especialidade', '')
            membro.telefone = request.form.get('telefone', '')
            membro.email = request.form.get('email', '')
            membro.data_contratacao = datetime.strptime(request.form['data_contratacao'], '%Y-%m-%d').date() if request.form.get('data_contratacao') else membro.data_contratacao
            
            if 'foto' in request.files:
                foto = request.files['foto']
                if foto and foto.filename and allowed_file(foto.filename):
                    if membro.foto:
                        try:
                            os.remove(os.path.join(app.config['UPLOAD_FOLDER_COMISSAO'], membro.foto))
                        except:
                            pass
                    filename = secure_filename(f"{datetime.now().timestamp()}_{foto.filename}")
                    foto.save(os.path.join(app.config['UPLOAD_FOLDER_COMISSAO'], filename))
                    membro.foto = filename
            
            db.session.commit()
            flash(f'{membro.nome} atualizado!', 'success')
            return redirect(url_for('comissao'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'error')
    
    return render_template('editar_comissao.html', membro=membro)

@app.route('/comissao/deletar/<int:id>')
@login_required
def deletar_comissao(id):
    membro = ComissaoTecnica.query.get_or_404(id)
    nome = membro.nome
    db.session.delete(membro)
    db.session.commit()
    flash(f'Membro {nome} removido!', 'success')
    return redirect(url_for('comissao'))

# ==================== ROTAS PARA COMPRAS ====================
@app.route('/compras', methods=['GET', 'POST'])
@login_required
def compras():
    if request.method == 'POST':
        try:
            compra = Compra(
                item=request.form['item'],
                quantidade=int(request.form['quantidade']),
                valor_unitario=float(request.form['valor_unitario']),
                total=float(request.form['quantidade']) * float(request.form['valor_unitario']),
                data_compra=datetime.strptime(request.form['data_compra'], '%Y-%m-%d').date() if request.form.get('data_compra') else datetime.now().date(),
                fornecedor=request.form.get('fornecedor'),
                categoria=request.form.get('categoria', 'Geral')
            )
            db.session.add(compra)
            db.session.commit()
            flash('Compra registrada!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'error')
        return redirect(url_for('compras'))
    
    compras_list = Compra.query.all()
    total_gastos = sum(c.total for c in compras_list if c.total)
    return render_template('compras.html', compras=compras_list, total_gastos=total_gastos)

@app.route('/compras/deletar/<int:id>')
@login_required
def deletar_compra(id):
    compra = Compra.query.get_or_404(id)
    db.session.delete(compra)
    db.session.commit()
    flash('Compra removida!', 'success')
    return redirect(url_for('compras'))

# ==================== ROTAS PARA GASTOS ====================
@app.route('/gastos', methods=['GET', 'POST'])
@login_required
def gastos():
    if request.method == 'POST':
        try:
            gasto = GastoMensal(
                mes=request.form['mes'],
                categoria=request.form['categoria'],
                valor=float(request.form['valor']),
                descricao=request.form.get('descricao', ''),
                data_pagamento=datetime.strptime(request.form['data_pagamento'], '%Y-%m-%d').date() if request.form.get('data_pagamento') else datetime.now().date()
            )
            db.session.add(gasto)
            db.session.commit()
            flash('Gasto registrado!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'error')
        return redirect(url_for('gastos'))
    
    gastos_list = GastoMensal.query.all()
    return render_template('gastos.html', gastos=gastos_list)

@app.route('/gastos/deletar/<int:id>')
@login_required
def deletar_gasto(id):
    gasto = GastoMensal.query.get_or_404(id)
    db.session.delete(gasto)
    db.session.commit()
    flash('Gasto removido com sucesso!', 'success')
    return redirect(url_for('gastos'))

# ==================== ROTAS PARA CONTAS FIXAS ====================
@app.route('/contas_fixas', methods=['GET', 'POST'])
@login_required
def contas_fixas():
    if request.method == 'POST':
        try:
            conta = ContaFixa(
                descricao=request.form['descricao'],
                valor=float(request.form['valor']),
                data_vencimento=int(request.form['dia_vencimento']),
                categoria=request.form.get('categoria', 'Outros'),
                status='ativa'
            )
            db.session.add(conta)
            db.session.commit()
            flash('Conta fixa cadastrada com sucesso!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar conta: {str(e)}', 'error')
        return redirect(url_for('contas_fixas'))
    
    contas_list = ContaFixa.query.all()
    total_mensal = sum(conta.valor for conta in contas_list if conta.status == 'ativa')
    
    return render_template('contas_fixas.html', contas=contas_list, total_mensal=total_mensal)

@app.route('/contas_fixas/toggle/<int:id>')
@login_required
def toggle_conta_fixa(id):
    conta = ContaFixa.query.get_or_404(id)
    conta.status = 'inativa' if conta.status == 'ativa' else 'ativa'
    db.session.commit()
    flash(f'Status da conta alterado para {conta.status}!', 'success')
    return redirect(url_for('contas_fixas'))

@app.route('/contas_fixas/deletar/<int:id>')
@login_required
def deletar_conta_fixa(id):
    conta = ContaFixa.query.get_or_404(id)
    db.session.delete(conta)
    db.session.commit()
    flash('Conta removida com sucesso!', 'success')
    return redirect(url_for('contas_fixas'))

# ==================== ANÁLISE DE DESEMPENHO ====================

@app.route('/analise/desempenho')
@login_required
def analise_desempenho():
    """Dashboard de análise de desempenho"""
    atletas = Atleta.query.order_by(Atleta.nome.asc()).all()
    
    # Calcular médias por atleta
    desempenho_atletas = []
    for atleta in atletas:
        # Buscar últimas avaliações
        avaliacao_tec = AvaliacaoTecnica.query.filter_by(atleta_id=atleta.id).order_by(AvaliacaoTecnica.data_avaliacao.desc()).first()
        avaliacao_tat = AvaliacaoTatica.query.filter_by(atleta_id=atleta.id).order_by(AvaliacaoTatica.data_avaliacao.desc()).first()
        avaliacao_fis = AvaliacaoFisica.query.filter_by(atleta_id=atleta.id).order_by(AvaliacaoFisica.data_avaliacao.desc()).first()
        avaliacao_men = AvaliacaoMental.query.filter_by(atleta_id=atleta.id).order_by(AvaliacaoMental.data_avaliacao.desc()).first()
        
        # Calcular média geral
        medias = []
        if avaliacao_tec:
            medias.append(avaliacao_tec.overall)
        if avaliacao_tat:
            medias.append(avaliacao_tat.overall)
        if avaliacao_fis:
            medias.append(avaliacao_fis.overall)
        if avaliacao_men:
            medias.append(avaliacao_men.overall)
        
        media_geral = sum(medias) / len(medias) if medias else 0
        
        desempenho_atletas.append({
            'atleta': atleta,
            'tecnica': avaliacao_tec.overall if avaliacao_tec else 0,
            'tatica': avaliacao_tat.overall if avaliacao_tat else 0,
            'fisica': avaliacao_fis.overall if avaliacao_fis else 0,
            'mental': avaliacao_men.overall if avaliacao_men else 0,
            'media_geral': media_geral,
            'ultima_avaliacao': avaliacao_tec.data_avaliacao if avaliacao_tec else None
        })
    
    # Ordenar por média geral
    desempenho_atletas.sort(key=lambda x: x['media_geral'], reverse=True)
    
    return render_template('analise_desempenho.html', atletas=desempenho_atletas)

@app.route('/analise/avaliar/<int:atleta_id>', methods=['GET', 'POST'])
@login_required
def avaliar_atleta(atleta_id):
    atleta = Atleta.query.get_or_404(atleta_id)
    
    if request.method == 'POST':
        temporada = request.form.get('temporada')
        observador = current_user.username
        
        try:
            # Salvar Avaliação Técnica
            avaliacao_tec = AvaliacaoTecnica(
                atleta_id=atleta_id,
                temporada=temporada,
                first_touch=int(request.form.get('first_touch', 3)),
                passing=int(request.form.get('passing', 3)),
                dribbling=int(request.form.get('dribbling', 3)),
                shooting=int(request.form.get('shooting', 3)),
                crossing=int(request.form.get('crossing', 3)),
                overall=float(request.form.get('tec_overall', 3)),
                observador=observador,
                notas=request.form.get('notas_tec', '')
            )
            db.session.add(avaliacao_tec)
            
            # Salvar Avaliação Tática
            avaliacao_tat = AvaliacaoTatica(
                atleta_id=atleta_id,
                temporada=temporada,
                positioning=int(request.form.get('positioning', 3)),
                decision_making=int(request.form.get('decision_making', 3)),
                off_ball_movement=int(request.form.get('off_ball_movement', 3)),
                pressing=int(request.form.get('pressing', 3)),
                team_structure=int(request.form.get('team_structure', 3)),
                overall=float(request.form.get('tat_overall', 3)),
                observador=observador,
                notas=request.form.get('notas_tat', '')
            )
            db.session.add(avaliacao_tat)
            
            # Salvar Avaliação Física
            avaliacao_fis = AvaliacaoFisica(
                atleta_id=atleta_id,
                temporada=temporada,
                acceleration=int(request.form.get('acceleration', 3)),
                strength=int(request.form.get('strength', 3)),
                agility=int(request.form.get('agility', 3)),
                stamina=int(request.form.get('stamina', 3)),
                overall=float(request.form.get('fis_overall', 3)),
                observador=observador,
                notas=request.form.get('notas_fis', '')
            )
            db.session.add(avaliacao_fis)
            
            # Salvar Avaliação Mental
            avaliacao_men = AvaliacaoMental(
                atleta_id=atleta_id,
                temporada=temporada,
                concentration=int(request.form.get('concentration', 3)),
                competitiveness=int(request.form.get('competitiveness', 3)),
                confidence=int(request.form.get('confidence', 3)),
                coachability=int(request.form.get('coachability', 3)),
                leadership=int(request.form.get('leadership', 3)),
                overall=float(request.form.get('men_overall', 3)),
                observador=observador,
                notas=request.form.get('notas_men', '')
            )
            db.session.add(avaliacao_men)
            
            db.session.commit()
            flash(f'Avaliação de {atleta.nome} registrada com sucesso!', 'success')
            return redirect(url_for('analise_desempenho'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao salvar avaliação: {str(e)}', 'error')
    
    return render_template('avaliar_atleta.html', atleta=atleta)

@app.route('/analise/estatisticas/<int:atleta_id>')
@login_required
def estatisticas_atleta(atleta_id):
    atleta = Atleta.query.get_or_404(atleta_id)
    
    # Buscar estatísticas por temporada
    temporadas = db.session.query(EstatisticaJogo.temporada).distinct().all()
    
    estatisticas = {}
    for t in temporadas:
        temporada = t[0]
        jogos = EstatisticaJogo.query.filter_by(atleta_id=atleta_id, temporada=temporada).all()
        
        total = {
            'jogos': len(jogos),
            'gols': sum(j.gols for j in jogos),
            'assistencias': sum(j.assistencias for j in jogos),
            'minutos': sum(j.minutos_jogados for j in jogos),
            'media_nota': sum(j.nota_jogo for j in jogos) / len(jogos) if jogos else 0
        }
        estatisticas[temporada] = {
            'jogos': jogos,
            'total': total
        }
    
    return render_template('estatisticas_atleta.html', atleta=atleta, estatisticas=estatisticas)

@app.route('/analise/adicionar_estatistica/<int:atleta_id>', methods=['POST'])
@login_required
def adicionar_estatistica_jogo(atleta_id):
    try:
        estatistica = EstatisticaJogo( # pyright: ignore[reportUndefinedVariable]
            atleta_id=atleta_id,
            data_jogo=datetime.strptime(request.form['data_jogo'], '%Y-%m-%d').date(),
            temporada=request.form['temporada'],
            adversario=request.form.get('adversario', ''),
            minutos_jogados=int(request.form.get('minutos_jogados', 0)),
            gols=int(request.form.get('gols', 0)),
            assistencias=int(request.form.get('assistencias', 0)),
            cartoes_amarelos=int(request.form.get('cartoes_amarelos', 0)),
            cartoes_vermelhos=int(request.form.get('cartoes_vermelhos', 0)),
            finalizacoes=int(request.form.get('finalizacoes', 0)),
            passes_certos=int(request.form.get('passes_certos', 0)),
            passes_errados=int(request.form.get('passes_errados', 0)),
            desarmes=int(request.form.get('desarmes', 0)),
            faltas_cometidas=int(request.form.get('faltas_cometidas', 0)),
            faltas_sofridas=int(request.form.get('faltas_sofridas', 0)),
            nota_jogo=float(request.form.get('nota_jogo', 0)),
            observacao=request.form.get('observacao', '')
        )
        db.session.add(estatistica)
        db.session.commit()
        flash('Estatística de jogo adicionada!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {str(e)}', 'error')
    
    return redirect(url_for('editar_atleta', id=atleta_id, tab='desempenho'))

@app.route('/analise/deletar_estatistica/<int:estatistica_id>', methods=['POST'])
@login_required
def deletar_estatistica_jogo(estatistica_id):
    estatistica = EstatisticaJogo.query.get_or_404(estatistica_id)
    atleta_id = estatistica.atleta_id
    try:
        db.session.delete(estatistica)
        db.session.commit()
        flash('Jogo removido do histórico.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao remover jogo: {str(e)}', 'error')
    return redirect(url_for('editar_atleta', id=atleta_id, tab='desempenho'))

# ==================== ROTAS PARA INVENTÁRIO ====================
@app.route('/inventario', methods=['GET', 'POST'])
@login_required
def inventario():
    if request.method == 'POST':
        try:
            item = Inventario(
                nome=request.form['nome'],
                categoria=request.form.get('categoria', 'Geral'),
                quantidade=int(request.form.get('quantidade', 1)),
                localizacao=request.form.get('localizacao', ''),
                data_aquisicao=datetime.strptime(request.form['data_aquisicao'], '%Y-%m-%d').date() if request.form.get('data_aquisicao') else datetime.now().date(),
                valor_aquisicao=float(request.form.get('valor_aquisicao', 0)),
                status=request.form.get('status', 'bom')
            )
            db.session.add(item)
            db.session.commit()
            flash('Item adicionado ao inventário!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'error')
        return redirect(url_for('inventario'))
    
    inventario_list = Inventario.query.all()
    return render_template('inventario.html', inventario=inventario_list)

@app.route('/inventario/deletar/<int:id>')
@login_required
def deletar_item(id):
    item = Inventario.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    flash('Item removido!', 'success')
    return redirect(url_for('inventario'))

# ==================== ROTAS PARA REUNIÕES ====================
@app.route('/reunioes', methods=['GET', 'POST'])
@login_required
def reunioes():
    if request.method == 'POST':
        try:
            reuniao = Reuniao(
                titulo=request.form['titulo'],
                data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(),
                hora=request.form['hora'],
                local=request.form.get('local', ''),
                pauta=request.form['pauta'],
                participantes=request.form.get('participantes', ''),
                status='agendada'
            )
            db.session.add(reuniao)
            db.session.commit()
            
            # Criar também no calendário
            evento = Evento(
                titulo=request.form['titulo'],
                data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(),
                tipo='Reunião',
                descricao=request.form.get('pauta', '')
            )
            db.session.add(evento)
            db.session.commit()
            
            flash('Reunião agendada e adicionada ao calendário!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'error')
        return redirect(url_for('reunioes'))
    
    reunioes_list = Reuniao.query.all()
    return render_template('reunioes.html', reunioes=reunioes_list)

@app.route('/reunioes/concluir/<int:id>')
@login_required
def concluir_reuniao(id):
    reuniao = Reuniao.query.get_or_404(id)
    reuniao.status = 'concluída'
    
    # Atualizar o evento no calendário
    evento = Evento.query.filter_by(
        titulo=reuniao.titulo,
        data=reuniao.data,
        tipo='Reunião'
    ).first()
    if evento:
        evento.descricao = '✅ CONCLUÍDA - ' + (evento.descricao or '')
    
    db.session.commit()
    flash('Reunião concluída!', 'success')
    return redirect(url_for('reunioes'))

@app.route('/reunioes/deletar/<int:id>')
@login_required
def deletar_reuniao(id):
    reuniao = Reuniao.query.get_or_404(id)
    
    # Remover também do calendário
    evento = Evento.query.filter_by(
        titulo=reuniao.titulo,
        data=reuniao.data,
        tipo='Reunião'
    ).first()
    if evento:
        db.session.delete(evento)
    
    db.session.delete(reuniao)
    db.session.commit()
    flash('Reunião removida do calendário!', 'success')
    return redirect(url_for('reunioes'))

@app.route('/reunioes/editar/<int:id>', methods=['POST'])
@login_required
def editar_reuniao(id):
    reuniao = Reuniao.query.get_or_404(id)
    try:
        reuniao.titulo = request.form['titulo']
        reuniao.data = datetime.strptime(request.form['data'], '%Y-%m-%d').date()
        reuniao.hora = request.form['hora']
        reuniao.local = request.form.get('local', '')
        reuniao.pauta = request.form['pauta']
        reuniao.participantes = request.form.get('participantes', '')
        db.session.commit()
        flash('Reunião atualizada!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {str(e)}', 'error')
    return redirect(url_for('reunioes'))

# ==================== ROTAS PARA CALENDÁRIO ====================
@app.route('/calendario')
@login_required
def calendario():
    import json as _json
    eventos = Evento.query.all()
    reunioes = Reuniao.query.all()
    cores = {'Jogo':'#EF4444','Treino':'#10B981','Reuniao':'#F59E0B','Evento Social':'#8B5CF6'}
    ev = []
    for e in eventos:
        cor = cores.get(e.tipo,'#6366f1')
        ev.append({'id':f'e_{e.id}','title':e.titulo,'start':e.data.isoformat(),'type':e.tipo,'description':e.descricao or '','backgroundColor':cor,'borderColor':cor,'textColor':'#FFFFFF'})
    for r in reunioes:
        cor = '#F59E0B' if r.status == 'agendada' else '#10B981'
        ev.append({'id':f'r_{r.id}','title':f'Reuniao: {r.titulo}','start':r.data.isoformat(),'type':'Reuniao','description':r.pauta[:200] if r.pauta else '','status':r.status,'hora':r.hora or '','local':r.local or '','backgroundColor':cor,'borderColor':cor,'textColor':'#FFFFFF'})
    return render_template('calendario.html', eventos=eventos, eventos_json=_json.dumps(ev))

@app.route('/calendario/adicionar', methods=['POST'])
@login_required
def adicionar_evento():
    try:
        evento = Evento(
            titulo=request.form['titulo'],
            data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(),
            tipo=request.form['tipo'],
            descricao=request.form.get('descricao', '')
        )
        db.session.add(evento)
        db.session.commit()
        flash('Evento adicionado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro: {str(e)}', 'error')
    return redirect(url_for('calendario'))  # Redireciona para o calendário

# ==================== ROTAS PARA DEPARTAMENTO MÉDICO ====================
@app.route('/departamento_medico')
@login_required
def departamento_medico():
    fichas = FichaMedica.query.all()
    atletas = Atleta.query.filter_by(status='ativo').all()
    return render_template('departamento_medico.html', fichas=fichas, atletas=atletas)

@app.route('/departamento_medico/adicionar', methods=['POST'])
@login_required
def adicionar_ficha_medica():
    try:
        ficha = FichaMedica(
            atleta_id=int(request.form['atleta_id']),
            tipo_lesao=request.form.get('tipo_lesao'),
            data_lesao=datetime.strptime(request.form['data_lesao'], '%Y-%m-%d').date() if request.form.get('data_lesao') else None,
            data_retorno_previsto=datetime.strptime(request.form['data_retorno_previsto'], '%Y-%m-%d').date() if request.form.get('data_retorno_previsto') else None,
            gravidade=request.form.get('gravidade'),
            medico_responsavel=request.form.get('medico_responsavel'),
            diagnostico=request.form.get('diagnostico'),
            tratamento=request.form.get('tratamento'),
            observacoes=request.form.get('observacoes')
        )
        db.session.add(ficha)
        db.session.commit()
        flash('Ficha médica criada com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {str(e)}', 'error')
    return redirect(url_for('departamento_medico'))

@app.route('/departamento_medico/atualizar/<int:id>', methods=['POST'])
@login_required
def atualizar_ficha_medica(id):
    ficha = FichaMedica.query.get_or_404(id)
    try:
        ficha.status = request.form['status']
        if request.form['status'] == 'recuperado':
            ficha.data_retorno_efetivo = datetime.now().date()
        ficha.observacoes = request.form.get('observacoes', ficha.observacoes)
        db.session.commit()
        flash('Ficha médica atualizada!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {str(e)}', 'error')
    return redirect(url_for('departamento_medico'))

# ==================== ROTAS PARA SCOUTING ====================
@app.route('/scouting')
@login_required
def scouting():
    jogadores = Scouting.query.all()
    return render_template('scouting.html', jogadores=jogadores)

@app.route('/scouting/adicionar', methods=['POST'])
@login_required
def adicionar_scouting():
    try:
        jogador = Scouting(
            nome_jogador=request.form['nome_jogador'],
            clube_atual=request.form.get('clube_atual'),
            posicao=request.form.get('posicao'),
            data_nascimento=datetime.strptime(request.form['data_nascimento'], '%Y-%m-%d').date() if request.form.get('data_nascimento') else None,
            nacionalidade=request.form.get('nacionalidade'),
            altura=float(request.form['altura']) if request.form.get('altura') else None,
            peso=float(request.form['peso']) if request.form.get('peso') else None,
            pe_dominante=request.form.get('pe_dominante'),
            valor_estimado=float(request.form['valor_estimado']) if request.form.get('valor_estimado') else None,
            contrato_ate=datetime.strptime(request.form['contrato_ate'], '%Y-%m-%d').date() if request.form.get('contrato_ate') else None,
            nota_tecnica=int(request.form['nota_tecnica']) if request.form.get('nota_tecnica') else None,
            nota_fisica=int(request.form['nota_fisica']) if request.form.get('nota_fisica') else None,
            nota_tatica=int(request.form['nota_tatica']) if request.form.get('nota_tatica') else None,
            nota_mental=int(request.form['nota_mental']) if request.form.get('nota_mental') else None,
            partida_observada=request.form.get('partida_observada'),
            data_observacao=datetime.strptime(request.form['data_observacao'], '%Y-%m-%d').date() if request.form.get('data_observacao') else None,
            campeonato=request.form.get('campeonato'),
            observador=request.form.get('observador'),
            pontos_fortes=request.form.get('pontos_fortes'),
            pontos_fracos=request.form.get('pontos_fracos'),
            resumo=request.form.get('resumo'),
            indicacao=request.form.get('indicacao'),
            video_url=request.form.get('video_url')
        )
        db.session.add(jogador)
        db.session.commit()
        flash('Jogador adicionado ao scouting!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {str(e)}', 'error')
    return redirect(url_for('scouting'))

@app.route('/scouting/atualizar/<int:id>', methods=['POST'])
@login_required
def atualizar_scouting(id):
    jogador = Scouting.query.get_or_404(id)
    try:
        jogador.status = request.form['status']
        jogador.indicacao = request.form.get('indicacao', jogador.indicacao)
        db.session.commit()
        flash('Status atualizado!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {str(e)}', 'error')
    return redirect(url_for('scouting'))

# ==================== CRIAR ADMIN ====================
def create_admin():
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@getclub.com',
                password=generate_password_hash('getclub123'),
                is_admin=True,
                can_manage_atletas=True,
                can_manage_comissao=True,
                can_manage_financeiro=True,
                can_manage_inventario=True,
                can_manage_reunioes=True,
                can_manage_medico=True,
                can_manage_scouting=True,
                can_manage_documentos=True
            )
            db.session.add(admin)
        else:
            admin.is_admin = True
            admin.can_manage_atletas = True
            admin.can_manage_comissao = True
            admin.can_manage_financeiro = True
            admin.can_manage_inventario = True
            admin.can_manage_reunioes = True
            admin.can_manage_medico = True
            admin.can_manage_scouting = True
            admin.can_manage_documentos = True
            admin.cargo_direcao = None
        db.session.commit()
        print("✅ Usuário admin configurado com permissões completas!")

@app.route('/direcao')
@login_required
def direcao():
    if not current_user.is_admin:
        flash('Acesso restrito a administradores!', 'error')
        return redirect(url_for('index'))
    direcao_usuarios = User.query.filter(User.cargo_direcao.isnot(None)).order_by(User.username.asc()).all()
    return render_template('direcao.html', usuarios=direcao_usuarios, perfis=PERFIS_DIRECAO)

# ==================== INICIAR APP ====================

@app.route('/adicionar_reuniao', methods=['POST'])
@login_required
def adicionar_reuniao():
    try:
        reuniao = Reuniao(
            titulo=request.form['titulo'],
            data=datetime.strptime(request.form['data'], '%Y-%m-%d').date(),
            hora=request.form['hora'],
            local=request.form.get('local', ''),
            pauta=request.form['pauta'],
            participantes=request.form.get('participantes', ''),
            status='agendada'
        )
        db.session.add(reuniao)
        db.session.commit()
        flash('Reunião agendada com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao agendar reunião: {str(e)}', 'error')
    return redirect(url_for('reunioes'))

# ==================== ROTAS PARA PATROCÍNIOS ====================
@app.route('/patrocinios')
@login_required
def patrocinios():
    patrocinios_list = Patrocinio.query.all()
    total_aportes = sum(p.valor_aporte for p in patrocinios_list if p.status == 'ativo')
    return render_template('patrocinios.html', patrocinios=patrocinios_list, total_aportes=total_aportes)

@app.route('/patrocinios/adicionar', methods=['POST'])
@login_required
def adicionar_patrocinio():
    try:
        patrocinio = Patrocinio(
            nome_patrocinador=request.form['nome_patrocinador'],
            valor_aporte=float(request.form['valor_aporte']),
            data_inicio=datetime.strptime(request.form['data_inicio'], '%Y-%m-%d').date() if request.form.get('data_inicio') else None,
            data_fim=datetime.strptime(request.form['data_fim'], '%Y-%m-%d').date() if request.form.get('data_fim') else None,
            tipo=request.form.get('tipo'),
            descricao=request.form.get('descricao'),
            contato=request.form.get('contato'),
            status=request.form.get('status', 'ativo')
        )
        db.session.add(patrocinio)
        db.session.commit()
        flash(f'Patrocínio de {patrocinio.nome_patrocinador} cadastrado!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {str(e)}', 'error')
    return redirect(url_for('patrocinios'))

@app.route('/patrocinios/atualizar/<int:id>', methods=['POST'])
@login_required
def atualizar_patrocinio(id):
    patrocinio = Patrocinio.query.get_or_404(id)
    try:
        patrocinio.status = request.form['status']
        db.session.commit()
        flash('Status atualizado!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {str(e)}', 'error')
    return redirect(url_for('patrocinios'))

@app.route('/patrocinios/deletar/<int:id>')
@login_required
def deletar_patrocinio(id):
    patrocinio = Patrocinio.query.get_or_404(id)
    nome = patrocinio.nome_patrocinador
    db.session.delete(patrocinio)
    db.session.commit()
    flash(f'Patrocínio de {nome} removido!', 'success')
    return redirect(url_for('patrocinios'))

# ==================== ROTAS PARA DOCUMENTOS ====================
@app.route('/documentos')
@login_required
def documentos():
    categoria_filtro = request.args.get('categoria', 'todos')
    if categoria_filtro == 'todos':
        docs = Documento.query.order_by(Documento.data_upload.desc()).all()
    else:
        docs = Documento.query.filter_by(categoria=categoria_filtro).order_by(Documento.data_upload.desc()).all()
    
    categorias = ['Contratos', 'Fichas de Inscrição', 'Comprovativos de Pagamento', 'Sumários', 'Facturas']
    return render_template('documentos.html', documentos=docs, categorias=categorias, categoria_ativa=categoria_filtro)

@app.route('/documentos/upload', methods=['POST'])
@login_required
def upload_documento():
    try:
        if 'arquivo' not in request.files:
            flash('Nenhum arquivo enviado!', 'error')
            return redirect(url_for('documentos'))
        
        arquivo = request.files['arquivo']
        if arquivo.filename == '':
            flash('Nenhum arquivo selecionado!', 'error')
            return redirect(url_for('documentos'))
        
        if arquivo:
            filename = secure_filename(f"{datetime.now().timestamp()}_{arquivo.filename}")
            arquivo.save(os.path.join(app.config['UPLOAD_FOLDER_DOCS'], filename))
            
            doc = Documento(
                nome=request.form['nome'],
                categoria=request.form['categoria'],
                arquivo=filename,
                descricao=request.form.get('descricao', ''),
                uploaded_by=current_user.username
            )
            db.session.add(doc)
            db.session.commit()
            flash('Documento carregado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {str(e)}', 'error')
    return redirect(url_for('documentos'))

@app.route('/documentos/download/<int:id>')
@login_required
def download_documento(id):
    doc = Documento.query.get_or_404(id)
    caminho = os.path.join(app.config['UPLOAD_FOLDER_DOCS'], doc.arquivo)
    return send_file(caminho, as_attachment=True, download_name=doc.arquivo)

@app.route('/documentos/deletar/<int:id>')
@login_required
def deletar_documento(id):
    doc = Documento.query.get_or_404(id)
    try:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER_DOCS'], doc.arquivo))
    except:
        pass
    db.session.delete(doc)
    db.session.commit()
    flash('Documento removido!', 'success')
    return redirect(url_for('documentos'))

# Criar tabelas ao iniciar
with app.app_context():
    db.create_all()
    garantir_colunas_atleta()
    garantir_colunas_permissoes_usuario()
    garantir_colunas_convocatoria()
    try:
        db.session.execute(text("ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS cargo_direcao VARCHAR(50)"))
        db.session.commit()
    except Exception:
        db.session.rollback()
        try:
            db.session.execute(text("ALTER TABLE user ADD COLUMN cargo_direcao VARCHAR(50)"))
            db.session.commit()
        except Exception:
            db.session.rollback()
    create_admin()

@app.route('/api/eventos')
@login_required
def api_eventos():
    """Retorna todos os eventos em formato JSON para o calendário"""
    eventos = Evento.query.all()
    reunioes = Reuniao.query.all()
    
    eventos_lista = []
    
    # Adicionar eventos do calendário
    for evento in eventos:
        eventos_lista.append({
            'id': f'evento_{evento.id}',
            'title': evento.titulo,
            'start': evento.data.isoformat(),
            'type': evento.tipo,
            'description': evento.descricao or '',
            'backgroundColor': get_cor_por_tipo(evento.tipo),
            'borderColor': get_cor_por_tipo(evento.tipo),
            'textColor': '#FFFFFF'
        })
    
    # Adicionar reuniões
    for reuniao in reunioes:
        cor = '#F59E0B' if reuniao.status == 'agendada' else '#10B981'
        eventos_lista.append({
            'id': f'reuniao_{reuniao.id}',
            'title': f'📋 {reuniao.titulo}',
            'start': reuniao.data.isoformat(),
            'type': 'Reunião',
            'description': reuniao.pauta[:200] if reuniao.pauta else '',
            'status': reuniao.status,
            'hora': reuniao.hora,
            'local': reuniao.local,
            'backgroundColor': cor,
            'borderColor': cor,
            'textColor': '#FFFFFF'
        })
    
    return jsonify(eventos_lista)

def get_cor_por_tipo(tipo):
    """Retorna a cor baseada no tipo de evento"""
    cores = {
        'Jogo': '#EF4444',      # Vermelho
        'Treino': '#10B981',     # Verde
        'Reunião': '#F59E0B',    # Laranja
        'Evento Social': '#8B5CF6'  # Roxo
    }
    return cores.get(tipo, '#3B82F6')  # Azul padrão
    
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5003))
    app.run(debug=False, host='0.0.0.0', port=port)
