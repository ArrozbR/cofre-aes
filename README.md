# Cofre de Senhas Corporativo

API que armazena credenciais compartilhadas em PostgreSQL de modo que, mesmo diante de uma cópia
integral do banco, nenhuma senha possa ser lida sem a senha-mestra da equipe. A proteção combina
derivação de chave com PBKDF2 e cifragem autenticada com AES-256-GCM.

Projeto de laboratório da disciplina Criptografia Aplicada — Módulo 3, Criptografia Simétrica.
Pontifícia Universidade Católica de Goiás, Escola Politécnica.

## Identificação

| | |
|---|---|
| Aluno | Pedro Blamires Cordeiro |
| Matrícula | 2024.1.0028.0229-4 |
| Curso | Ciência da Computação |
| Disciplina | Criptografia Aplicada — 2026.2-CMP2195/C02 |
| Entrega | Atividade 03 — Cofre AES (individual) |

## Instalação e execução

Requer Python 3.10 ou superior e uma conta no Supabase.

**1. Clonar e preparar o ambiente**

```bash
git clone https://github.com/USUARIO/REPOSITORIO.git
cd cofre-aes
python -m venv .venv
```

Ativação do ambiente virtual:

| Sistema | Comando |
|---|---|
| Windows (PowerShell) | `.venv\Scripts\Activate.ps1` |
| Windows (Prompt) | `.venv\Scripts\activate.bat` |
| Linux e macOS | `source .venv/bin/activate` |

**2. Instalar as dependências**

```bash
pip install -r requirements.txt
```

**3. Preparar o banco**

Crie um projeto no Supabase e execute o conteúdo de `sql/esquema.sql` no SQL Editor. O script cria
as tabelas `cofres` e `segredos`, o índice de apoio e as políticas de acesso.

**4. Configurar as credenciais**

Copie `.env.exemplo` para `.env` e preencha com os valores do próprio projeto, obtidos em
Project Settings → API:

```
SUPABASE_URL=https://xxxxxxxx.supabase.co
SUPABASE_KEY=eyJhbGciOi...
```

O arquivo `.env` está listado no `.gitignore` e não deve ser versionado.

**5. Executar**

```bash
uvicorn app.main:app --reload
```

A documentação interativa fica disponível em `http://127.0.0.1:8000/docs`, permitindo executar
todas as rotas sem cliente adicional.

## Rotas

A senha-mestra é transmitida no cabeçalho `X-Senha-Mestra` em todas as rotas, exceto na criação do
cofre. O uso de cabeçalho, em vez do corpo ou da URL, evita que a senha apareça em registros de
servidor e no histórico do navegador.

| Método e rota | Descrição |
|---|---|
| `POST /cofres` | Cria o cofre: sorteia o sal, deriva a chave, grava o verificador. |
| `POST /cofres/{id}/abrir` | Confere a senha-mestra contra o verificador. |
| `POST /cofres/{id}/segredos` | Cifra e grava uma credencial. |
| `GET /cofres/{id}/segredos` | Lista os metadados dos segredos. Nunca devolve senhas. |
| `GET /cofres/{id}/segredos/{sid}` | Decifra e devolve a senha solicitada. |
| `PUT /cofres/{id}/segredos/{sid}` | Substitui a senha, com novo nonce. |
| `DELETE /cofres/{id}/segredos/{sid}` | Remove o registro. |

### Exemplo de requisição

Gravação de uma credencial:

```http
POST /cofres/4444df29-3ad2-43fe-bfb8-17d97237cdcb/segredos
X-Senha-Mestra: pipoca123
Content-Type: application/json

{
  "titulo": "Servidor de producao",
  "usuario": "admin",
  "url": "https://prod.exemplo.com",
  "senha": "S3nh@-do-Banco!"
}
```

Resposta `201 Created`:

```json
{
  "segredo_id": "a3f7a81c-d46f-48f6-a5b5-a98fe93b925e",
  "titulo": "Servidor de producao"
}
```

Leitura posterior da mesma credencial, em `GET /cofres/{id}/segredos/{sid}`, devolve `200 OK`:

```json
{
  "id": "a3f7a81c-d46f-48f6-a5b5-a98fe93b925e",
  "titulo": "Servidor de producao",
  "usuario": "admin",
  "url": "https://prod.exemplo.com",
  "senha": "S3nh@-do-Banco!"
}
```

### Códigos de resposta

| Código | Situação |
|---|---|
| 200 | Leitura ou atualização bem-sucedida. |
| 201 | Cofre ou segredo criado. |
| 401 | Verificador falhou: senha-mestra incorreta. |
| 404 | Cofre ou segredo inexistente, ou identificador fora do formato UUID. |
| 422 | Formato da requisição inválido (gerado pelo FastAPI). |
| 500 | Verificador aprovado, mas a etiqueta do segredo falhou: registro adulterado. |

A separação entre 401 e 500 é o que torna o verificador necessário. Ambas as situações produzem o
mesmo `ValueError` na biblioteca; é a tentativa prévia de decifrar a frase `cofre-ok` que permite
distinguir chave incorreta de dado corrompido.

## Parâmetros criptográficos

| Parâmetro | Valor | Justificativa |
|---|---|---|
| Função de derivação | PBKDF2 com HMAC-SHA-256 | Padronizada e disponível na PyCryptodome. O módulo de hash é informado explicitamente (`hmac_hash_module=SHA256`); sem esse parâmetro a biblioteca adota SHA-1 por padrão. |
| Chave derivada | 32 bytes | Exigência do AES-256. |
| Sal | 16 bytes aleatórios, um por cofre, armazenado em claro | Impede que duas equipes com a mesma senha-mestra produzam a mesma chave, e inviabiliza o pré-cálculo de chaves para senhas comuns aplicável a todos os cofres de uma vez. |
| Iterações | 210 000, registradas por cofre | Torna a derivação deliberadamente lenta. O usuário legítimo paga o custo uma vez por sessão; o atacante paga a cada tentativa. Armazenar o valor por cofre permite elevar o padrão no futuro sem impedir a abertura de cofres antigos. |
| Cifra | AES-256 em modo GCM | Oferece confidencialidade e integridade na mesma operação, dispensa preenchimento e detecta adulteração antes de devolver texto claro. |
| Nonce | 12 bytes, sorteado a cada cifragem | Tamanho recomendado para o GCM. É gerado imediatamente antes de cada operação, inclusive nas atualizações: repetir um nonce com a mesma chave permitiria recuperar o texto claro por cancelamento do fluxo de chave. |
| AAD | `{cofre_id}\|{segredo_id}` | Vincula cada criptograma ao registro em que foi gerado. O verificador do cofre usa apenas `{cofre_id}`, por não haver segredo associado a ele. |

A senha-mestra e a chave derivada existem apenas durante o processamento de cada requisição. Não
são gravadas em banco, arquivo, log ou cache entre requisições.

## O que fica em claro no banco

Os campos `titulo`, `usuario` e `url` são armazenados sem cifragem, de modo deliberado: permitem
listar o conteúdo do cofre sem exigir a decifragem de cada registro. O custo dessa escolha é que um
invasor de posse do banco descobre quais sistemas a equipe acessa, embora não as senhas. A rota de
listagem nomeia explicitamente as colunas devolvidas, sem `select("*")`, de modo que nonce,
criptograma e etiqueta jamais trafeguem em respostas que não precisam deles.

## Limitações

As limitações abaixo são fronteiras deliberadas de escopo, não defeitos pendentes de correção.

**Servidor de aplicação comprometido durante o uso.** A senha-mestra transita pela memória do
servidor a cada requisição. Um invasor com execução de código no servidor em operação consegue
interceptá-la, e a proteção do cofre é contornada. O modelo protege o dado em repouso, não o
processo em execução.

**Senha-mestra fraca ou divulgada.** A segurança do cofre é a segurança dessa senha. As 210 000
iterações do PBKDF2 encarecem a busca exaustiva, mas não compensam uma senha previsível nem
qualquer forma de divulgação pela equipe.

**Ausência de auditoria.** O sistema não registra quem leu qual credencial e quando. Um acesso
legítimo e um acesso indevido feito com a senha-mestra correta são indistinguíveis.

**Ausência de controle de acesso por usuário.** Não há usuários individuais: quem conhece a
senha-mestra tem acesso a todos os segredos do cofre. Não é possível conceder acesso parcial nem
revogar o acesso de uma pessoa sem trocar a senha e recifrar todo o conteúdo.

**Políticas de acesso permissivas no banco.** As políticas de RLS liberam leitura e escrita a
qualquer portador da chave pública do projeto. A escolha é intencional e serve ao propósito
didático de simular o cenário do invasor com cópia do banco, conforme demonstrado no Teste 3. Em
produção, as tabelas seriam acessadas apenas pelo servidor, com credenciais restritas — ainda que a
proteção do conteúdo continuasse vindo da cifragem, e não da política de acesso.

## Estrutura

```
cofre-aes/
├── app/
│   ├── __init__.py
│   ├── main.py        rotas e códigos de resposta
│   ├── cripto.py      PBKDF2, AES-GCM, verificador
│   ├── banco.py       acesso ao Supabase
│   └── modelos.py     validação das requisições
├── sql/
│   └── esquema.sql
├── testes/
│   ├── resultados.md
│   └── evidencias/
├── .env.exemplo
├── .gitignore
├── requirements.txt
└── README.md
```

Nenhuma operação criptográfica ocorre em `banco.py`, e nenhuma chamada ao Supabase ocorre em
`main.py`. A separação mantém a lógica criptográfica auditável de forma isolada.

## Referências

Câmara, D. *Introdução à Criptografia*. PyCryptodome, documentação oficial:
`https://pycryptodome.readthedocs.io`. NIST SP 800-38D, *Recommendation for Block Cipher Modes of
Operation: Galois/Counter Mode (GCM) and GMAC*. NIST SP 800-132, *Recommendation for Password-Based
Key Derivation*. OWASP, *Password Storage Cheat Sheet*.
