-- Remove duas coisas que não são mais usadas.
--
-- A tabela ocorrencias_externas era do GeoSampa, que saiu do projeto.
--
-- A coluna eventos.resolvido_em (e o status resolvido) nunca era preenchida:
-- o evento é apagado quando passa o tempo, em vez de ser marcado como resolvido.
--
-- Reverter significa reaplicar a migração 002 e recriar a coluna.
DROP TABLE IF EXISTS ocorrencias_externas;
ALTER TABLE eventos DROP COLUMN resolvido_em;
