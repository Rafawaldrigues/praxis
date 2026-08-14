-- Migração v3 do IA ADV
-- Rode isso no banco DEPOIS da migracao_v2.sql.

-- Cliente: soft delete (nunca apaga de verdade, só desativa)
ALTER TABLE cliente ADD COLUMN IF NOT EXISTS ativo BOOLEAN NOT NULL DEFAULT TRUE;

-- Processo: valor da causa (usado no módulo financeiro)
ALTER TABLE processo ADD COLUMN IF NOT EXISTS valor_causa NUMERIC(14,2);

-- Agenda: prazos, audiências e outros compromissos ligados a um processo
CREATE TABLE IF NOT EXISTS compromisso (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    processo_id UUID NOT NULL REFERENCES processo(id),
    tipo VARCHAR(30) NOT NULL,       -- 'audiencia', 'prazo', 'reuniao', 'outro'
    descricao TEXT,
    data_hora TIMESTAMP NOT NULL,
    concluido BOOLEAN NOT NULL DEFAULT FALSE,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Financeiro: lançamentos de honorários/custas por processo e/ou cliente
CREATE TABLE IF NOT EXISTS financeiro (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    escritorio_id UUID NOT NULL REFERENCES escritorio(id),
    processo_id UUID REFERENCES processo(id),
    cliente_id UUID REFERENCES cliente(id),
    tipo VARCHAR(20) NOT NULL,        -- 'receita' ou 'despesa'
    descricao VARCHAR(255) NOT NULL,
    valor NUMERIC(14,2) NOT NULL,
    status VARCHAR(20) NOT NULL,      -- 'pendente' ou 'pago'
    vencimento DATE,
    pago_em TIMESTAMP,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_compromisso_data ON compromisso (data_hora);
CREATE INDEX IF NOT EXISTS idx_financeiro_escritorio ON financeiro (escritorio_id);
