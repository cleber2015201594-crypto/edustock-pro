import streamlit as st
import plotly.express as px
from datetime import datetime, date
import json
import os
import hashlib
import sys

# Tentar importar psycopg2 com fallback
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError as e:
    st.error(f"Erro ao importar psycopg2: {e}")
    PSYCOPG2_AVAILABLE = False

# Configuração da página
st.set_page_config(
    page_title="EduStock Pro",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Conexão com PostgreSQL - Versão mais robusta
@st.cache_resource
def init_connection():
    if not PSYCOPG2_AVAILABLE:
        st.error("psycopg2 não está disponível. Verifique as dependências.")
        return None
        
    try:
        # Primeiro tenta variáveis de ambiente do Render
        db_config = {
            'host': os.environ.get('DB_HOST'),
            'database': os.environ.get('DB_NAME'),
            'user': os.environ.get('DB_USER'),
            'password': os.environ.get('DB_PASSWORD'),
            'port': os.environ.get('DB_PORT', 5432)
        }
        
        # Se não encontrou, tenta secrets do Streamlit
        if not all(db_config.values()):
            try:
                db_config = {
                    'host': st.secrets.get("DB_HOST"),
                    'database': st.secrets.get("DB_NAME"),
                    'user': st.secrets.get("DB_USER"),
                    'password': st.secrets.get("DB_PASSWORD"),
                    'port': st.secrets.get("DB_PORT", 5432)
                }
            except:
                pass
        
        # Verifica se todas as configurações estão presentes
        if not all(db_config.values()):
            st.error("Configuração do banco de dados incompleta.")
            return None
            
        conn = psycopg2.connect(**db_config)
        return conn
        
    except Exception as e:
        st.error(f"❌ Erro ao conectar com PostgreSQL: {e}")
        return None

# Inicialização condicional
if PSYCOPG2_AVAILABLE:
    conn = init_connection()
else:
    conn = None

# Sistema de Autenticação
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

def create_usertable():
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    nivel VARCHAR(20) DEFAULT 'Vendedor',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Erro ao criar tabela de usuários: {e}")
        return False

def add_user(username, password, nivel='Vendedor'):
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO usuarios (username, password, nivel) VALUES (%s, %s, %s)",
                (username, make_hashes(password), nivel)
            )
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Erro ao adicionar usuário: {e}")
        return False

def login_user(username, password):
    if not conn:
        return None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM usuarios WHERE username = %s", (username,))
            user = cur.fetchone()
            if user and check_hashes(password, user['password']):
                return user
            return None
    except Exception as e:
        st.error(f"Erro no login: {e}")
        return None

# Inicialização do banco de dados
def init_db():
    if not conn:
        return False
        
    try:
        with conn.cursor() as cur:
            # Tabela de escolas
            cur.execute("""
                CREATE TABLE IF NOT EXISTS escolas (
                    id SERIAL PRIMARY KEY,
                    nome VARCHAR(255) NOT NULL,
                    telefone VARCHAR(20),
                    email VARCHAR(255),
                    endereco TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabela de clientes (CPF opcional)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS clientes (
                    id SERIAL PRIMARY KEY,
                    nome VARCHAR(255) NOT NULL,
                    telefone VARCHAR(20),
                    email VARCHAR(255),
                    cpf VARCHAR(14),
                    endereco TEXT,
                    escola_id INTEGER REFERENCES escolas(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabela de produtos
            cur.execute("""
                CREATE TABLE IF NOT EXISTS produtos (
                    id SERIAL PRIMARY KEY,
                    nome VARCHAR(255) NOT NULL,
                    descricao TEXT,
                    preco_custo DECIMAL(10,2),
                    preco_venda DECIMAL(10,2),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabela de estoque
            cur.execute("""
                CREATE TABLE IF NOT EXISTS estoque (
                    id SERIAL PRIMARY KEY,
                    escola_id INTEGER REFERENCES escolas(id),
                    produto_id INTEGER REFERENCES produtos(id),
                    tamanho VARCHAR(5) NOT NULL,
                    quantidade INTEGER DEFAULT 0,
                    UNIQUE(escola_id, produto_id, tamanho)
                )
            """)
            
            # Tabela de pedidos
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pedidos (
                    id SERIAL PRIMARY KEY,
                    cliente_id INTEGER REFERENCES clientes(id),
                    escola_id INTEGER REFERENCES escolas(id),
                    status VARCHAR(50) DEFAULT 'Pendente',
                    total DECIMAL(10,2) DEFAULT 0,
                    desconto DECIMAL(10,2) DEFAULT 0,
                    data_pedido DATE DEFAULT CURRENT_DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabela de itens do pedido
            cur.execute("""
                CREATE TABLE IF NOT EXISTS itens_pedido (
                    id SERIAL PRIMARY KEY,
                    pedido_id INTEGER REFERENCES pedidos(id),
                    produto_id INTEGER REFERENCES produtos(id),
                    tamanho VARCHAR(5) NOT NULL,
                    quantidade INTEGER NOT NULL,
                    preco_unitario DECIMAL(10,2) NOT NULL
                )
            """)
            
            conn.commit()
            return True
            
    except Exception as e:
        st.error(f"❌ Erro ao criar tabelas: {e}")
        return False

# Inicializar banco se conectado
if conn:
    create_usertable()
    init_db()

# Funções do Sistema
def get_escolas():
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM escolas ORDER BY nome")
            return cur.fetchall()
    except Exception as e:
        st.error(f"Erro ao buscar escolas: {e}")
        return []

def add_escola(nome, telefone, email, endereco):
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO escolas (nome, telefone, email, endereco) VALUES (%s, %s, %s, %s)",
                (nome, telefone, email, endereco)
            )
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Erro ao adicionar escola: {e}")
        return False

def get_clientes():
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT c.*, e.nome as escola_nome 
                FROM clientes c 
                LEFT JOIN escolas e ON c.escola_id = e.id 
                ORDER BY c.nome
            """)
            return cur.fetchall()
    except Exception as e:
        st.error(f"Erro ao buscar clientes: {e}")
        return []

def add_cliente(nome, telefone, email, cpf, endereco, escola_id):
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO clientes (nome, telefone, email, cpf, endereco, escola_id) 
                VALUES (%s, %s, %s, %s, %s, %s)""",
                (nome, telefone, email, cpf, endereco, escola_id)
            )
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Erro ao adicionar cliente: {e}")
        return False

def get_produtos():
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM produtos ORDER BY nome")
            return cur.fetchall()
    except Exception as e:
        st.error(f"Erro ao buscar produtos: {e}")
        return []

def add_produto(nome, descricao, preco_custo, preco_venda):
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO produtos (nome, descricao, preco_custo, preco_venda) 
                VALUES (%s, %s, %s, %s)""",
                (nome, descricao, preco_custo, preco_venda)
            )
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Erro ao adicionar produto: {e}")
        return False

def get_estoque(escola_id=None):
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if escola_id:
                cur.execute("""
                    SELECT e.*, p.nome as produto_nome, p.preco_venda, esc.nome as escola_nome
                    FROM estoque e
                    JOIN produtos p ON e.produto_id = p.id
                    JOIN escolas esc ON e.escola_id = esc.id
                    WHERE e.escola_id = %s
                    ORDER BY p.nome, e.tamanho
                """, (escola_id,))
            else:
                cur.execute("""
                    SELECT e.*, p.nome as produto_nome, p.preco_venda, esc.nome as escola_nome
                    FROM estoque e
                    JOIN produtos p ON e.produto_id = p.id
                    JOIN escolas esc ON e.escola_id = esc.id
                    ORDER BY esc.nome, p.nome, e.tamanho
                """)
            return cur.fetchall()
    except Exception as e:
        st.error(f"Erro ao buscar estoque: {e}")
        return []

def update_estoque(escola_id, produto_id, tamanho, quantidade):
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO estoque (escola_id, produto_id, tamanho, quantidade) 
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (escola_id, produto_id, tamanho) 
                DO UPDATE SET quantidade = %s
            """, (escola_id, produto_id, tamanho, quantidade, quantidade))
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Erro ao atualizar estoque: {e}")
        return False

def criar_pedido(cliente_id, escola_id, itens, desconto=0):
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            # Calcula total
            total = sum(item['quantidade'] * item['preco_unitario'] for item in itens) - desconto
            
            # Cria pedido
            cur.execute("""
                INSERT INTO pedidos (cliente_id, escola_id, total, desconto) 
                VALUES (%s, %s, %s, %s) RETURNING id
            """, (cliente_id, escola_id, total, desconto))
            pedido_id = cur.fetchone()[0]
            
            # Adiciona itens
            for item in itens:
                cur.execute("""
                    INSERT INTO itens_pedido (pedido_id, produto_id, tamanho, quantidade, preco_unitario)
                    VALUES (%s, %s, %s, %s, %s)
                """, (pedido_id, item['produto_id'], item['tamanho'], item['quantidade'], item['preco_unitario']))
                
                # Atualiza estoque
                cur.execute("""
                    UPDATE estoque 
                    SET quantidade = quantidade - %s 
                    WHERE escola_id = %s AND produto_id = %s AND tamanho = %s
                """, (item['quantidade'], escola_id, item['produto_id'], item['tamanho']))
            
            conn.commit()
            return pedido_id
    except Exception as e:
        st.error(f"Erro ao criar pedido: {e}")
        return None

def get_pedidos():
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT p.*, c.nome as cliente_nome, e.nome as escola_nome
                FROM pedidos p
                JOIN clientes c ON p.cliente_id = c.id
                JOIN escolas e ON p.escola_id = e.id
                ORDER BY p.created_at DESC
            """)
            return cur.fetchall()
    except Exception as e:
        st.error(f"Erro ao buscar pedidos: {e}")
        return []

# Funções para gráficos sem pandas
def prepare_pie_chart_data(data, value_col, name_col):
    """Prepara dados para gráfico de pizza"""
    values = [item[value_col] for item in data]
    names = [item[name_col] for item in data]
    return names, values

def prepare_line_chart_data(data, x_col, y_col):
    """Prepara dados para gráfico de linha"""
    x = [item[x_col] for item in data]
    y = [float(item[y_col]) for item in data]
    return x, y

def prepare_bar_chart_data(data, x_col, y_col, color_col=None):
    """Prepara dados para gráfico de barras"""
    x = [item[x_col] for item in data]
    y = [item[y_col] for item in data]
    color = [item[color_col] for item in data] if color_col else None
    return x, y, color

# Interface de Login
def show_login():
    st.markdown("""
        <style>
        .main {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .login-container {
            background: white;
            padding: 2rem;
            border-radius: 10px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
            width: 400px;
        }
        </style>
    """, unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.title("🏫 Login Sistema")
        
        username = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        
        if st.button("Entrar"):
            user = login_user(username, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos")
        
        st.markdown('</div>', unsafe_allow_html=True)

# Interface Principal
def main():
    st.markdown("""
        <style>
        .main-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 2rem;
            border-radius: 10px;
            color: white;
            margin-bottom: 2rem;
        }
        .metric-card {
            background: white;
            padding: 1.5rem;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border-left: 4px solid #667eea;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("""
        <div class="main-header">
            <h1>🏫 EduStock Pro - Sistema de Gestão Escolar</h1>
            <p>Controle completo de estoque, pedidos e clientes</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Menu de Navegação
    menu = ["Dashboard", "Gestão de Escolas", "Gestão de Clientes", "Produtos e Estoque", "Pedidos", "Relatórios"]
    choice = st.selectbox("Navegação", menu, key='nav')
    
    if choice == "Dashboard":
        show_dashboard()
    elif choice == "Gestão de Escolas":
        show_escolas_management()
    elif choice == "Gestão de Clientes":
        show_clientes_management()
    elif choice == "Produtos e Estoque":
        show_estoque_management()
    elif choice == "Pedidos":
        show_pedidos_management()
    elif choice == "Relatórios":
        show_reports()

def show_dashboard():
    if not conn:
        st.error("⚠️ Banco de dados não conectado. Algumas informações podem não estar disponíveis.")
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM clientes")
                total_clientes = cur.fetchone()[0]
            st.markdown(f"""
                <div class="metric-card">
                    <h3>👥 Total Clientes</h3>
                    <h2>{total_clientes}</h2>
                </div>
            """, unsafe_allow_html=True)
        except:
            st.markdown("""
                <div class="metric-card">
                    <h3>👥 Total Clientes</h3>
                    <h2>0</h2>
                </div>
            """, unsafe_allow_html=True)
    
    with col2:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM escolas")
                total_escolas = cur.fetchone()[0]
            st.markdown(f"""
                <div class="metric-card">
                    <h3>🏫 Total Escolas</h3>
                    <h2>{total_escolas}</h2>
                </div>
            """, unsafe_allow_html=True)
        except:
            st.markdown("""
                <div class="metric-card">
                    <h3>🏫 Total Escolas</h3>
                    <h2>0</h2>
                </div>
            """, unsafe_allow_html=True)
    
    with col3:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM pedidos WHERE status = 'Pendente'")
                pedidos_pendentes = cur.fetchone()[0]
            st.markdown(f"""
                <div class="metric-card">
                    <h3>📦 Pedidos Pendentes</h3>
                    <h2>{pedidos_pendentes}</h2>
                </div>
            """, unsafe_allow_html=True)
        except:
            st.markdown("""
                <div class="metric-card">
                    <h3>📦 Pedidos Pendentes</h3>
                    <h2>0</h2>
                </div>
            """, unsafe_allow_html=True)
    
    with col4:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT SUM(total) FROM pedidos WHERE data_pedido = CURRENT_DATE")
                result = cur.fetchone()[0]
                faturamento_hoje = result if result else 0
            st.markdown(f"""
                <div class="metric-card">
                    <h3>💰 Faturamento Hoje</h3>
                    <h2>R$ {faturamento_hoje:,.2f}</h2>
                </div>
            """, unsafe_allow_html=True)
        except:
            st.markdown("""
                <div class="metric-card">
                    <h3>💰 Faturamento Hoje</h3>
                    <h2>R$ 0,00</h2>
                </div>
            """, unsafe_allow_html=True)
    
    # Gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Pedidos por Status")
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT status, COUNT(*) as count 
                    FROM pedidos 
                    GROUP BY status
                """)
                data = cur.fetchall()
            if data:
                names, values = prepare_pie_chart_data(data, 'count', 'status')
                fig = px.pie(values=values, names=names, hole=0.3)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Nenhum dado disponível para o gráfico")
        except Exception as e:
            st.error(f"Erro ao carregar gráfico: {e}")
    
    with col2:
        st.subheader("Faturamento Mensal")
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT DATE_TRUNC('month', data_pedido) as mes, 
                           SUM(total) as total 
                    FROM pedidos 
                    GROUP BY mes 
                    ORDER BY mes
                """)
                data = cur.fetchall()
            if data:
                x, y = prepare_line_chart_data(data, 'mes', 'total')
                fig = px.line(x=x, y=y, title='Evolução do Faturamento')
                fig.update_layout(xaxis_title='Mês', yaxis_title='Total (R$)')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Nenhum dado disponível para o gráfico")
        except Exception as e:
            st.error(f"Erro ao carregar gráfico: {e}")

def show_escolas_management():
    st.header("🏫 Gestão de Escolas")
    
    tab1, tab2 = st.tabs(["Cadastrar Escola", "Lista de Escolas"])
    
    with tab1:
        with st.form("cadastro_escola"):
            nome = st.text_input("Nome da Escola*")
            telefone = st.text_input("Telefone")
            email = st.text_input("Email")
            endereco = st.text_area("Endereço")
            
            if st.form_submit_button("Cadastrar Escola"):
                if nome:
                    if add_escola(nome, telefone, email, endereco):
                        st.success("Escola cadastrada com sucesso!")
                        st.rerun()
                    else:
                        st.error("Erro ao cadastrar escola")
                else:
                    st.error("Nome é obrigatório")
    
    with tab2:
        escolas = get_escolas()
        if escolas:
            for escola in escolas:
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.write(f"**{escola['nome']}**")
                    st.write(f"📞 {escola['telefone']} | 📧 {escola['email']}")
                with col2:
                    st.write(f"🏠 {escola['endereco']}")
                with col3:
                    if st.button("Excluir", key=f"del_esc_{escola['id']}"):
                        try:
                            with conn.cursor() as cur:
                                cur.execute("DELETE FROM escolas WHERE id = %s", (escola['id'],))
                                conn.commit()
                            st.success("Escola excluída com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao excluir escola: {e}")
        else:
            st.info("Nenhuma escola cadastrada")

def show_clientes_management():
    st.header("👥 Gestão de Clientes")
    
    tab1, tab2 = st.tabs(["Cadastrar Cliente", "Lista de Clientes"])
    
    with tab1:
        with st.form("cadastro_cliente"):
            nome = st.text_input("Nome Completo*")
            telefone = st.text_input("Telefone")
            email = st.text_input("Email")
            cpf = st.text_input("CPF (opcional)")  # CPF não é mais obrigatório
            endereco = st.text_area("Endereço")
            
            escolas = get_escolas()
            if escolas:
                escola_opcoes = {e['nome']: e['id'] for e in escolas}
                escola_selecionada = st.selectbox("Escola", list(escola_opcoes.keys()))
            else:
                st.warning("Cadastre uma escola primeiro")
                escola_opcoes = {}
                escola_selecionada = None
            
            if st.form_submit_button("Cadastrar Cliente"):
                if nome and escola_selecionada:  # Apenas nome e escola são obrigatórios
                    escola_id = escola_opcoes[escola_selecionada]
                    if add_cliente(nome, telefone, email, cpf, endereco, escola_id):
                        st.success("Cliente cadastrada com sucesso!")
                        st.rerun()
                    else:
                        st.error("Erro ao cadastrar cliente")
                else:
                    st.error("Nome e Escola são obrigatórios")
    
    with tab2:
        clientes = get_clientes()
        if clientes:
            for cliente in clientes:
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.write(f"**{cliente['nome']}**")
                    st.write(f"📞 {cliente['telefone']} | 📧 {cliente['email']}")
                    st.write(f"🎓 {cliente['escola_nome']}")
                with col2:
                    st.write(f"📍 {cliente['endereco']}")
                    st.write(f"🔢 CPF: {cliente['cpf'] or 'Não informado'}")
                with col3:
                    if st.button("Excluir", key=f"del_cli_{cliente['id']}"):
                        try:
                            with conn.cursor() as cur:
                                cur.execute("DELETE FROM clientes WHERE id = %s", (cliente['id'],))
                                conn.commit()
                            st.success("Cliente excluído com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao excluir cliente: {e}")
        else:
            st.info("Nenhum cliente cadastrado")

def show_estoque_management():
    st.header("📦 Gestão de Produtos e Estoque")
    
    tab1, tab2, tab3 = st.tabs(["Cadastrar Produto", "Gerenciar Estoque", "Consulta Estoque"])
    
    with tab1:
        with st.form("cadastro_produto"):
            nome = st.text_input("Nome do Produto*")
            descricao = st.text_area("Descrição")
            preco_custo = st.number_input("Preço de Custo", min_value=0.0, step=0.01, value=0.0)
            preco_venda = st.number_input("Preço de Venda", min_value=0.0, step=0.01, value=0.0)
            
            if st.form_submit_button("Cadastrar Produto"):
                if nome:
                    if add_produto(nome, descricao, preco_custo, preco_venda):
                        st.success("Produto cadastrado com sucesso!")
                        st.rerun()
                    else:
                        st.error("Erro ao cadastrar produto")
                else:
                    st.error("Nome é obrigatório")
    
    with tab2:
        with st.form("gerenciar_estoque"):
            escolas = get_escolas()
            produtos = get_produtos()
            tamanhos = ['2', '4', '6', '8', '10', '12', 'pp', 'p', 'm', 'g', 'gg']
            
            if escolas and produtos:
                escola_selecionada = st.selectbox("Escola", escolas, format_func=lambda x: x['nome'])
                produto_selecionado = st.selectbox("Produto", produtos, format_func=lambda x: x['nome'])
                tamanho_selecionado = st.selectbox("Tamanho", tamanhos)
                quantidade = st.number_input("Quantidade", min_value=0, step=1, value=0)
                
                if st.form_submit_button("Atualizar Estoque"):
                    if update_estoque(escola_selecionada['id'], produto_selecionado['id'], 
                                 tamanho_selecionado, quantidade):
                        st.success("Estoque atualizado com sucesso!")
                    else:
                        st.error("Erro ao atualizar estoque")
            else:
                st.warning("Cadastre escolas e produtos primeiro")
    
    with tab3:
        estoque = get_estoque()
        if estoque:
            st.subheader("Estoque por Escola")
            # Agrupar por escola para melhor visualização
            escolas_estoque = {}
            for item in estoque:
                escola_nome = item['escola_nome']
                if escola_nome not in escolas_estoque:
                    escolas_estoque[escola_nome] = []
                escolas_estoque[escola_nome].append(item)
            
            for escola_nome, itens in escolas_estoque.items():
                with st.expander(f"🏫 {escola_nome}"):
                    for item in itens:
                        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                        with col1:
                            st.write(f"**{item['produto_nome']}**")
                        with col2:
                            st.write(f"Tamanho: {item['tamanho']}")
                        with col3:
                            st.write(f"Preço: R$ {item['preco_venda']:.2f}")
                        with col4:
                            cor = "red" if item['quantidade'] == 0 else "orange" if item['quantidade'] < 10 else "green"
                            st.markdown(f"<span style='color: {cor}; font-weight: bold;'>Qtd: {item['quantidade']}</span>", 
                                      unsafe_allow_html=True)
        else:
            st.info("Nenhum item em estoque")

def show_pedidos_management():
    st.header("📦 Gestão de Pedidos")
    
    tab1, tab2 = st.tabs(["Novo Pedido", "Histórico de Pedidos"])
    
    with tab1:
        with st.form("novo_pedido"):
            clientes = get_clientes()
            produtos = get_produtos()
            escolas = get_escolas()
            tamanhos = ['2', '4', '6', '8', '10', '12', 'pp', 'p', 'm', 'g', 'gg']
            
            if clientes and produtos and escolas:
                cliente_selecionado = st.selectbox("Cliente", clientes, format_func=lambda x: x['nome'])
                escola_selecionada = st.selectbox("Escola", escolas, format_func=lambda x: x['nome'])
                desconto = st.number_input("Desconto (R$)", min_value=0.0, step=0.01, value=0.0)
                
                st.subheader("Itens do Pedido")
                col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
                
                with col1:
                    produto = st.selectbox("Produto", produtos, format_func=lambda x: x['nome'], key='produto_pedido')
                with col2:
                    tamanho = st.selectbox("Tamanho", tamanhos, key='tamanho_pedido')
                with col3:
                    quantidade = st.number_input("Quantidade", min_value=1, step=1, value=1, key='quantidade_pedido')
                with col4:
                    preco_unitario = st.number_input("Preço Unitário", min_value=0.0, step=0.01, 
                                                   value=float(produto['preco_venda']) if produto else 0.0, 
                                                   key='preco_pedido')
                
                if st.form_submit_button("Criar Pedido"):
                    itens = [{
                        'produto_id': produto['id'],
                        'tamanho': tamanho,
                        'quantidade': quantidade,
                        'preco_unitario': preco_unitario
                    }]
                    
                    pedido_id = criar_pedido(cliente_selecionado['id'], escola_selecionada['id'], itens, desconto)
                    if pedido_id:
                        st.success(f"Pedido #{pedido_id} criado com sucesso!")
                    else:
                        st.error("Erro ao criar pedido")
            else:
                st.warning("Cadastre clientes, produtos e escolas primeiro")
    
    with tab2:
        pedidos = get_pedidos()
        if pedidos:
            for pedido in pedidos:
                with st.expander(f"Pedido #{pedido['id']} - {pedido['cliente_nome']} - R$ {pedido['total']:.2f}"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.write(f"**Cliente:** {pedido['cliente_nome']}")
                        st.write(f"**Escola:** {pedido['escola_nome']}")
                    with col2:
                        st.write(f"**Status:** {pedido['status']}")
                        st.write(f"**Data:** {pedido['data_pedido']}")
                    with col3:
                        st.write(f"**Total:** R$ {pedido['total']:.2f}")
                        st.write(f"**Desconto:** R$ {pedido['desconto']:.2f}")
                    
                    if st.button("Excluir Pedido", key=f"del_ped_{pedido['id']}"):
                        try:
                            with conn.cursor() as cur:
                                cur.execute("DELETE FROM pedidos WHERE id = %s", (pedido['id'],))
                                conn.commit()
                            st.success("Pedido excluído com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao excluir pedido: {e}")
        else:
            st.info("Nenhum pedido cadastrado")

def show_reports():
    st.header("📊 Relatórios e Análises")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Estoque por Escola")
        estoque = get_estoque()
        if estoque:
            x, y, color = prepare_bar_chart_data(estoque, 'escola_nome', 'quantidade', 'produto_nome')
            fig = px.bar(x=x, y=y, color=color, title="Estoque por Escola")
            fig.update_layout(xaxis_title='Escola', yaxis_title='Quantidade', showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nenhum dado disponível para o gráfico")
    
    with col2:
        st.subheader("Top Produtos")
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT p.nome, SUM(i.quantidade) as total_vendido
                    FROM itens_pedido i
                    JOIN produtos p ON i.produto_id = p.id
                    GROUP BY p.id, p.nome
                    ORDER BY total_vendido DESC
                    LIMIT 10
                """)
                data = cur.fetchall()
            if data:
                names, values = prepare_pie_chart_data(data, 'total_vendido', 'nome')
                fig = px.pie(values=values, names=names, title="Top Produtos Vendidos")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Nenhum dado disponível para o gráfico")
        except Exception as e:
            st.error(f"Erro ao carregar gráfico: {e}")

# Verificação de login
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    show_login()
else:
    # Botão de logout no canto superior direito
    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("🚪 Sair"):
            st.session_state.logged_in = False
            st.rerun()
    
    # Status da conexão
    if conn:
        st.sidebar.success("✅ Conectado ao PostgreSQL")
    else:
        st.sidebar.error("❌ Banco não conectado")
    
    main()

# Criar usuário admin padrão se não existir
try:
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM usuarios WHERE username = 'admin'")
            if cur.fetchone()[0] == 0:
                add_user('admin', 'admin123', 'Admin')
                st.sidebar.info("Usuário admin criado: admin / admin123")
except Exception as e:
    st.sidebar.error(f"Erro ao criar usuário admin: {e}")
