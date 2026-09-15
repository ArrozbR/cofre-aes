import os

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

supabase: Client = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_KEY"],
)


def inserir_cofre(cofre_id, nome, sal_b64, iteracoes, ver_nonce, ver_cripto, ver_etiqueta):
    supabase.table("cofres").insert({
        "id": cofre_id,
        "nome": nome,
        "kdf_sal": sal_b64,
        "kdf_iteracoes": iteracoes,
        "verificador_nonce": ver_nonce,
        "verificador_criptograma": ver_cripto,
        "verificador_etiqueta": ver_etiqueta,
    }).execute()


def buscar_cofre(cofre_id):
    resposta = supabase.table("cofres").select("*").eq("id", cofre_id).execute()
    return resposta.data[0] if resposta.data else None


def inserir_segredo(segredo_id, cofre_id, titulo, usuario, url, nonce, criptograma, etiqueta):
    supabase.table("segredos").insert({
        "id": segredo_id,
        "cofre_id": cofre_id,
        "titulo": titulo,
        "usuario": usuario,
        "url": url,
        "nonce": nonce,
        "criptograma": criptograma,
        "etiqueta": etiqueta,
    }).execute()


def listar_segredos(cofre_id):
    resposta = supabase.table("segredos").select(
        "id, titulo, usuario, url, criado_em"
    ).eq("cofre_id", cofre_id).execute()
    return resposta.data


def buscar_segredo(segredo_id, cofre_id):
    resposta = supabase.table("segredos").select("*").eq(
        "id", segredo_id
    ).eq("cofre_id", cofre_id).execute()
    return resposta.data[0] if resposta.data else None


def atualizar_segredo(segredo_id, nonce, criptograma, etiqueta):
    supabase.table("segredos").update({
        "nonce": nonce,
        "criptograma": criptograma,
        "etiqueta": etiqueta,
        "atualizado_em": "now()",
    }).eq("id", segredo_id).execute()


def remover_segredo(segredo_id, cofre_id):
    supabase.table("segredos").delete().eq("id", segredo_id).eq("cofre_id", cofre_id).execute()