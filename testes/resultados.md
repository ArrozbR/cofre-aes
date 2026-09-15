# Roteiro de verificação — resultados observados

Ambiente: FastAPI + Uvicorn em `127.0.0.1:8000`, PostgreSQL gerenciado pelo Supabase (região São Paulo).
Cofre utilizado nos testes: `4444df29-3ad2-43fe-bfb8-17d97237cdcb`, senha-mestra `pipoca123`.

Todas as requisições foram executadas pela interface `/docs` gerada pelo FastAPI. As capturas
correspondentes estão em `evidencias/`.

---

## Teste 1 — Nonces distintos

**Procedimento.** Foram cadastrados dois segredos no mesmo cofre, `Servidor A`
(`838fa527-3887-4f1d-99b0-01b8f734493b`) e `Servidor B`
(`f701f713-31ec-4d76-aa64-61eca9c46e50`), ambos protegendo a senha idêntica `mesma-senha-123`.
Em seguida a tabela foi consultada no SQL Editor do Supabase:

```sql
select titulo, nonce, criptograma from public.segredos;
```

**Resultado observado.** Os dois registros apresentaram nonce e criptograma completamente
distintos, sem qualquer semelhança entre si, ainda que a senha protegida seja a mesma:

| titulo | nonce (início) | criptograma (início) |
|---|---|---|
| Servidor A | `fTsPUPJJLCoWP2I…` | `SlwBOgSDewbIAu7yzuL…` |
| Servidor B | `jW5FCqRrmzwPDF…` | `FsApIw+84OemoaZNOV…` |

**Interpretação.** Confirma que o nonce é sorteado com `get_random_bytes(12)` imediatamente antes
de cada operação de cifragem, e não reaproveitado. Consequência prática: um invasor com acesso de
leitura à tabela não consegue sequer determinar que os dois registros protegem a mesma senha —
informação que, isoladamente, já teria valor para ele.

---

## Teste 2 — Senha-mestra incorreta

**Procedimento.** Requisição a `POST /cofres/{cofre_id}/abrir` com o identificador correto do cofre
e o cabeçalho `X-Senha-Mestra: 123`.

**Resultado observado.** Resposta **401**, com o corpo:

```json
{ "detail": "senha-mestra incorreta" }
```

Nenhum conteúdo do cofre ou dos segredos foi devolvido.

**Interpretação.** O servidor não armazena a senha-mestra nem qualquer forma de hash dela para
comparação. A rejeição decorre da própria criptografia: a chave derivada a partir de `123` não
consegue decifrar o verificador `cofre-ok` gravado no registro do cofre, a etiqueta não confere, e
`senha_mestra_correta` devolve `False`. A ausência da senha correta é detectada como falha
criptográfica, não como divergência de credencial.

---

## Teste 3 — O que o invasor enxerga

**Procedimento.** Consulta direta à tabela, executada no SQL Editor com a permissão ampla concedida
pelas políticas de RLS do laboratório — situação equivalente à de um invasor que obteve cópia
integral do banco:

```sql
select titulo, usuario, nonce, criptograma, etiqueta from public.segredos;
```

**Resultado observado.** Três registros retornados. Nenhuma senha legível em qualquer coluna: os
campos `nonce`, `criptograma` e `etiqueta` contêm exclusivamente cadeias em Base64 sem significado
aparente. Os únicos dados inteligíveis são os metadados deliberadamente mantidos em claro
(`titulo`, `usuario`, `url`).

**Interpretação.** Demonstra que a proteção do conteúdo vem da cifragem no nível da aplicação, e
não da política de acesso ao banco. Mesmo com acesso total de leitura, o invasor obtém apenas a
informação de quais sistemas a equipe acessa — exposição residual assumida como decisão de projeto
e declarada nas limitações do README.

---

## Teste 4 — Registro adulterado

**Procedimento.** Alteração manual de um caractere do criptograma diretamente no banco, seguida de
tentativa de leitura pela API com a senha-mestra **correta**:

```sql
update public.segredos
set criptograma = 'X' || substring(criptograma from 2)
where id = 'a3f7a81c-d46f-48f6-a5b5-a98fe93b925e';
```

**Resultado observado.** Resposta **500**, com o corpo:

```json
{ "detail": "registro adulterado" }
```

Nenhum texto claro foi devolvido. A alteração é visível na comparação entre as consultas dos
Testes 3 e 1: o criptograma do segredo `Servidor de producao` passou de `eKnuNDadrB8BMpDbC…` para
`XKnuNDadrB8BMpDbC…`.

**Interpretação.** A etiqueta de autenticação foi recalculada sobre o criptograma recebido e não
coincidiu com a armazenada. O `decrypt_and_verify` abortou a operação antes de devolver qualquer
byte, lançando `ValueError`. A exceção foi capturada explicitamente na camada da API e convertida
em 500 — comportamento previsto, e não falha não tratada. A alternativa, sem a verificação do GCM,
seria devolver bytes corrompidos que a aplicação trataria como se fossem a senha verdadeira.

Note a distinção de códigos: senha-mestra errada produz 401, dado adulterado produz 500. Só é
possível chegar ao 500 depois que o verificador do cofre foi aprovado, ou seja, com a chave
comprovadamente correta.

---

## Teste 5 — Troca de criptogramas entre registros

**Procedimento.** Os três campos criptográficos do segredo `Servidor A` foram copiados sobre o
registro do segredo `Servidor B`, ambos do mesmo cofre e cifrados com a mesma chave:

```sql
update public.segredos
set nonce = (select nonce from public.segredos where titulo = 'Servidor A'),
    criptograma = (select criptograma from public.segredos where titulo = 'Servidor A'),
    etiqueta = (select etiqueta from public.segredos where titulo = 'Servidor A')
where titulo = 'Servidor B';
```

Em seguida, leitura de `Servidor B` pela API com a senha-mestra correta.

**Resultado observado.** Resposta **500**, com o corpo:

```json
{ "detail": "registro adulterado" }
```

**Interpretação.** Este é o teste que isola o efeito do AAD. Diferentemente do Teste 4, aqui nada
foi corrompido: o criptograma é legítimo, a etiqueta corresponde a ele, e a chave derivada é a
mesma que os produziu. A leitura ainda assim é recusada porque o AAD gravado no lacre é
`{cofre_id}|838fa527-3887-4f1d-99b0-01b8f734493b`, enquanto a API, ao ler pelo identificador do
`Servidor B`, monta `{cofre_id}|f701f713-31ec-4d76-aa64-61eca9c46e50`. A divergência no dado
associado altera o cálculo da etiqueta e a verificação falha.

Sem o AAD, este ataque teria sucesso: um invasor com acesso de escrita, mas sem a senha-mestra,
faria a aplicação exibir a senha do servidor de produção no lugar da senha do servidor de testes.
A confidencialidade permaneceria intacta e o sistema, ainda assim, teria sido manipulado. O AAD
amarra cada criptograma ao registro em que foi gerado.

---

## Síntese

| Teste | Propriedade verificada | Resultado |
|---|---|---|
| 1 | Nonce único por operação de cifragem | Confirmado |
| 2 | Confidencialidade sob senha-mestra incorreta (401) | Confirmado |
| 3 | Ilegibilidade sob acesso direto ao banco | Confirmado |
| 4 | Integridade: detecção de adulteração (500) | Confirmado |
| 5 | Vinculação do criptograma ao registro via AAD (500) | Confirmado |
