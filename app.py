from flask import  Flask, render_template, request, redirect, url_for, session, Response
import psycopg2
import bcrypt
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
import re, json
import secrets

app = Flask(__name__)

# Gere uma chave secreta aleatória
app.secret_key = secrets.token_hex(16)

# Configurações do banco de dados PostgreSQL
db_params = {
    'dbname': 'proxyusers',
    'user': 'postgres',
    'password': '1234',
    'host': 'localhost',
    'port': '5432'
}


@app.route('/')
def index():
    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        new_username = request.form['new_username']
        new_password = request.form['new_password']
        data_nascimento = request.form['data_nascimento']

        # Converte a data de nascimento para o formato adequado
        data_nascimento = datetime.strptime(data_nascimento, '%Y-%m-%d').date()

        if not verificar_usuario_existente(new_username):
            criar_novo_usuario(new_username, new_password, data_nascimento)
            return render_template('login.html')
        else:
            return "Este nome de usuário já está em uso. Tente outro."
    return render_template('registro.html')


@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    user = verificar_credenciais(username, password)

    if user:
        # Autenticação bem-sucedida
        session['username'] = username
        session['maioridade'] = verificar_maioridade(user[3])

        return render_template('proxy.html', username=username, maioridade = session['maioridade'])
    else:
        # Autenticação falhou
        return "Credenciais inválidas. Tente novamente."




@app.route('/proxy', methods=['GET', 'POST'])
def proxy():

    # Obtenha o nome e maioriade de usuário do formulário
    username = session.get('username')
    maioridade = session.get('maioridade')
    print(username, maioridade)


    # Obtenha a URL de destino a partir do formulário HTML
    target_url = request.args.get('proxy_link')
    
    if not target_url:
        return "Por favor, forneça uma URL de destino."

    # Se a solicitação for um redirecionamento interno do proxy, pegue o URL real
    if 'internal_redirect' in request.args:
        target_url = request.args['internal_redirect']

    # Faça uma solicitação para o servidor de destino
    response = requests.get(target_url)

    # Analise o conteúdo HTML da resposta
    soup = BeautifulSoup(response.text, 'html.parser')

    # Modifique todos os links (tags <a>) para passar pelo proxy
    for tag in soup.find_all('a', href=True):
        href = tag['href']
        absolute_url = urljoin(target_url, href)
        proxy_url = urljoin(request.base_url, '/proxy')
        tag['href'] = f"{proxy_url}?proxy_link={absolute_url}"


    final = add_cabecario(str(soup), username=username)

    if maioridade == False:
        final = substituir_palavras_proibidas(final, 'censura.json')
        print('entrou')





    return Response(final, content_type='text/html; charset=utf-8')


# Função para verificar se um usuário já existe no banco de dados
def verificar_usuario_existente(username):
    try:
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return user is not None
    except Exception as e:
        print(e)
        return False


# Função para criar um novo usuário no banco de dados
def criar_novo_usuario(username, password, data_nascimento):
    try:
        # Gerar um hash de senha
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        hashed_password = hashed_password.decode('utf8')

        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()
        cursor.execute(f"INSERT INTO usuarios (username, password, data_nascimento) VALUES (%s, %s, %s)", (username, hashed_password, data_nascimento))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(e)


# Função para verificar as credenciais do usuário no banco de dados
def verificar_credenciais(username, password):
    try:
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and bcrypt.checkpw(password.encode('utf-8'), user[2].encode('utf-8')):
            return user
        else:
            return None
    except Exception as e:
        print(e)
        return None
    

#Função para verificar se é maior de idade
def verificar_maioridade(data_nascimento):
    # Obter a data atual
    data_atual = datetime.now()

    # Calcular a idade da pessoa
    idade = data_atual.year - data_nascimento.year - ((data_atual.month, data_atual.day) < (data_nascimento.month, data_nascimento.day))

    # Verificar se a pessoa é maior de idade
    if idade >= 18:
        return True
    else:
        return False
    
#Função para aicionar cabeçario
def add_cabecario(texto, username):
    try:
        indice_body = texto.find('<body')  # Procura a posição de "<body" na string
        if indice_body != -1:  # Se "<body" for encontrado
            indice_fim_body = texto.find('>', indice_body)  # Encontra o ">" após "<body"
            if indice_fim_body != -1:
                indice_fim_body += 1  # Ajusta para incluir o ">"

                # Adiciona a nova string após "</body>"
                texto_modificado = texto[:indice_fim_body] + f"<p>Logado como: {username}</p><p><a href='http://127.0.0.1:5000/'>Sair</a></p>" + texto[indice_fim_body:]
                return texto_modificado
            else:
                print("Erro: '>' não encontrado após '<body'.")
        else:
            print("Erro: '<body' não encontrado na string.")
    except Exception as e:
        print(f"Ocorreu um erro: {e}")
    return texto  # Retorna a string original se algo der errado


def substituir_palavras_proibidas(html_str, arquivo_json):
    with open(arquivo_json, 'r') as file:
        dados_json = json.load(file)
        palavras_proibidas = dados_json.get("palavras_proibidas", [])

    for palavra in palavras_proibidas:
        # Usando regex para encontrar a palavra proibida, ignorando maiúsculas/minúsculas
        regex = re.compile(r'\b' + re.escape(palavra) + r'\b', re.IGNORECASE)
        # Substituir a palavra proibida por asteriscos
        html_str = regex.sub('****', html_str)

    return html_str



if __name__ == '__main__':
    app.run(debug=True)
