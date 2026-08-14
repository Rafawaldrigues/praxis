-- Migração v2 do IA ADV
-- Rode isso no seu banco (psql, DBeaver, pgAdmin) antes de usar a versão nova do app.

-- Cliente: idade e whatsapp (separado do telefone, ex: telefone fixo x celular/whatsapp)
ALTER TABLE cliente ADD COLUMN IF NOT EXISTS idade INTEGER;
ALTER TABLE cliente ADD COLUMN IF NOT EXISTS whatsapp VARCHAR(20);

-- Documentos anexados a um processo (PDF, foto, etc). Guardamos o arquivo
-- direto no banco (BYTEA) pra não depender de storage externo no MVP.
CREATE TABLE IF NOT EXISTS documento_processo (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    processo_id UUID NOT NULL REFERENCES processo(id),
    usuario_id UUID REFERENCES usuario(id),
    nome_arquivo VARCHAR(255) NOT NULL,
    tipo VARCHAR(20) NOT NULL,          -- 'pdf', 'foto', 'outro'
    conteudo BYTEA NOT NULL,
    tamanho_bytes INTEGER,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Comentários internos em um processo (equipe conversando sobre o caso)
CREATE TABLE IF NOT EXISTS comentario_processo (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    processo_id UUID NOT NULL REFERENCES processo(id),
    usuario_id UUID REFERENCES usuario(id),
    texto TEXT NOT NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Índices simples para busca mais rápida por nome/CPF-CNPJ/número de processo
CREATE INDEX IF NOT EXISTS idx_cliente_nome ON cliente (nome);
CREATE INDEX IF NOT EXISTS idx_cliente_cpf_cnpj ON cliente (cpf_cnpj);
CREATE INDEX IF NOT EXISTS idx_processo_numero_cnj ON processo (numero_cnj);

-- OBS sobre usuario.perfil: não precisa de migração, é só um VARCHAR livre.
-- A partir de agora o app usa dois valores por convenção:
--   'lider'    -> vê e gerencia tudo do escritório
--   'advogado' -> só vê os processos atribuídos a ele
-- Se você já tem usuários com perfil 'admin' (criados antes dessa versão),
-- rode isto pra migrar eles pra 'lider':
UPDATE usuario SET perfil = 'lider' WHERE perfil = 'admin';
