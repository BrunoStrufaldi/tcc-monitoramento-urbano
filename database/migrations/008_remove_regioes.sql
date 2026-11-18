-- Remove a tabela regioes, que nunca foi usada de fato.
--
-- Nenhum serviço preenchia regiao_id, então essa coluna ficava sempre vazia em
-- eventos, localizacoes e dados_contextuais. Por isso as chaves estrangeiras e
-- as colunas saem primeiro, e a tabela sai por último.
--
-- No SQLite nada precisa ser feito. As colunas antigas podem continuar no
-- arquivo, porque o sistema não lê nem grava mais nelas.
--
-- Reverter significa recriar a tabela e as colunas como estavam no schema.sql
-- antes desta migração. As três regiões fixas não voltam sozinhas.
ALTER TABLE eventos DROP FOREIGN KEY fk_eventos_regiao;
ALTER TABLE eventos DROP COLUMN regiao_id;

ALTER TABLE localizacoes DROP FOREIGN KEY fk_localizacoes_regiao;
ALTER TABLE localizacoes DROP INDEX idx_localizacoes_regiao;
ALTER TABLE localizacoes DROP COLUMN regiao_id;

ALTER TABLE dados_contextuais DROP FOREIGN KEY fk_contexto_regiao;
ALTER TABLE dados_contextuais DROP INDEX idx_contexto_regiao;
ALTER TABLE dados_contextuais DROP COLUMN regiao_id;

DROP TABLE IF EXISTS regioes;
