import uuid

from fastapi import FastAPI, Header, HTTPException

from app import banco, cripto
from app.modelos import NovoCofre, NovoSegredo, NovaSenha

app = FastAPI(title="Cofre de Senhas")


def abrir_cofre(cofre_id: str, senha_mestra: str):
    validar_uuid(cofre_id)
    cofre = banco.buscar_cofre(cofre_id)
    if cofre is None:
        raise HTTPException(status_code=404, detail="cofre nao encontrado")

    chave = cripto.derivar_chave(
        senha_mestra,
        cripto.de_b64(cofre["kdf_sal"]),
        cofre["kdf_iteracoes"],
    )

    if not cripto.senha_mestra_correta(
        chave,
        cofre["verificador_nonce"],
        cofre["verificador_criptograma"],
        cofre["verificador_etiqueta"],
        cofre_id,
    ):
        raise HTTPException(status_code=401, detail="senha-mestra incorreta")

    return chave

def validar_uuid(valor: str):
    try:
        uuid.UUID(valor)
    except ValueError:
        raise HTTPException(status_code=404, detail="identificador invalido")

@app.post("/cofres", status_code=201)
def criar_cofre(dados: NovoCofre):
    cofre_id = str(uuid.uuid4())
    sal = cripto.gerar_sal()
    chave = cripto.derivar_chave(dados.senha_mestra, sal, cripto.ITERACOES_PADRAO)
    nonce, criptograma, etiqueta = cripto.criar_verificador(chave, cofre_id)

    banco.inserir_cofre(
        cofre_id,
        dados.nome,
        cripto.para_b64(sal),
        cripto.ITERACOES_PADRAO,
        nonce,
        criptograma,
        etiqueta,
    )
    return {"cofre_id": cofre_id, "nome": dados.nome}


@app.post("/cofres/{cofre_id}/abrir")
def conferir_senha(cofre_id: str, x_senha_mestra: str = Header(...)):
    abrir_cofre(cofre_id, x_senha_mestra)
    return {"status": "ok"}


@app.post("/cofres/{cofre_id}/segredos", status_code=201)
def criar_segredo(cofre_id: str, dados: NovoSegredo, x_senha_mestra: str = Header(...)):
    chave = abrir_cofre(cofre_id, x_senha_mestra)

    segredo_id = str(uuid.uuid4())
    aad = cripto.montar_aad(cofre_id, segredo_id)
    nonce, criptograma, etiqueta = cripto.cifrar(chave, dados.senha, aad)

    banco.inserir_segredo(
        segredo_id, cofre_id, dados.titulo, dados.usuario, dados.url,
        nonce, criptograma, etiqueta,
    )
    return {"segredo_id": segredo_id, "titulo": dados.titulo}


@app.get("/cofres/{cofre_id}/segredos")
def listar(cofre_id: str, x_senha_mestra: str = Header(...)):
    abrir_cofre(cofre_id, x_senha_mestra)
    return banco.listar_segredos(cofre_id)


@app.get("/cofres/{cofre_id}/segredos/{segredo_id}")
def ler_segredo(cofre_id: str, segredo_id: str, x_senha_mestra: str = Header(...)):
    chave = abrir_cofre(cofre_id, x_senha_mestra)

    segredo = banco.buscar_segredo(segredo_id, cofre_id)
    if segredo is None:
        raise HTTPException(status_code=404, detail="segredo nao encontrado")

    try:
        senha = cripto.decifrar(
            chave,
            segredo["nonce"],
            segredo["criptograma"],
            segredo["etiqueta"],
            cripto.montar_aad(cofre_id, segredo_id),
        )
    except ValueError:
        raise HTTPException(status_code=500, detail="registro adulterado")

    return {
        "id": segredo["id"],
        "titulo": segredo["titulo"],
        "usuario": segredo["usuario"],
        "url": segredo["url"],
        "senha": senha,
    }


@app.put("/cofres/{cofre_id}/segredos/{segredo_id}")
def atualizar(cofre_id: str, segredo_id: str, dados: NovaSenha, x_senha_mestra: str = Header(...)):
    chave = abrir_cofre(cofre_id, x_senha_mestra)

    if banco.buscar_segredo(segredo_id, cofre_id) is None:
        raise HTTPException(status_code=404, detail="segredo nao encontrado")

    aad = cripto.montar_aad(cofre_id, segredo_id)
    nonce, criptograma, etiqueta = cripto.cifrar(chave, dados.senha, aad)
    banco.atualizar_segredo(segredo_id, nonce, criptograma, etiqueta)

    return {"status": "atualizado"}


@app.delete("/cofres/{cofre_id}/segredos/{segredo_id}")
def remover(cofre_id: str, segredo_id: str, x_senha_mestra: str = Header(...)):
    abrir_cofre(cofre_id, x_senha_mestra)

    if banco.buscar_segredo(segredo_id, cofre_id) is None:
        raise HTTPException(status_code=404, detail="segredo nao encontrado")

    banco.remover_segredo(segredo_id, cofre_id)
    return {"status": "removido"}


@app.get("/")
def raiz():
    return {"servico": "Cofre de Senhas", "documentacao": "/docs"}