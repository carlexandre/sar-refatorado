"""Fixed schema whitelist for untrusted legacy databases."""

SELECTS = {
    "grupos": "SELECT * FROM grupos",
    "links": "SELECT * FROM links",
    "faturas_cadastradas": "SELECT * FROM faturas_cadastradas",
    "itens_fatura": "SELECT * FROM itens_fatura",
    "itens_fatura_grupo": "SELECT * FROM itens_fatura_grupo",
    "agendamentos": "SELECT * FROM agendamentos",
    "historico_relatorios": "SELECT * FROM historico_relatorios",
}
INSERTS = {
    "grupos": "INSERT INTO grupos(id,nome,parent_id,email_contato,fatura_para,cnpj,cep,endereco,numero,cidade,uf) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
    "links": "INSERT INTO links(id,grupo_id,nome_instituicao,host_id,item_down_id,item_up_id,capacidade_str,email_contato) VALUES (?,?,?,?,?,?,?,?)",
    "faturas_cadastradas": "INSERT INTO faturas_cadastradas(link_id,fatura_para,cnpj,cep,endereco,numero,cidade,uf,email_contato) VALUES (?,?,?,?,?,?,?,?,?)",
    "itens_fatura": "INSERT INTO itens_fatura(id,link_id,descricao,quantidade,valor_unitario) VALUES (?,?,?,?,?)",
    "itens_fatura_grupo": "INSERT INTO itens_fatura_grupo(id,grupo_id,descricao,quantidade,valor_unitario) VALUES (?,?,?,?,?)",
    "agendamentos": "INSERT INTO agendamentos(id,link_ids,dia_envio,horario,incluir_fatura,fatura_num_prefixo,fatura_venc_dia,ativo,periodo_modo,data_inicio,data_fim,grupo_id,owner_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
}
