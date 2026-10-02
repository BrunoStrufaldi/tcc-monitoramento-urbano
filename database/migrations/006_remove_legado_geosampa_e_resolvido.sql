-- Remove duas sobras sem produtor.
--
-- `ocorrencias_externas` rastreava registros já importados do GeoSampa/Defesa
-- Civil quando esses datasets disparavam evento. Essa fonte saiu do escopo e
-- nada mais grava na tabela.
--
-- `eventos.resolvido_em` (e o status `resolvido`) nunca é atribuído: um evento
-- vive no máximo GX_EVENTO_JANELA_MINUTOS após a última detecção e então é
-- apagado (services/event_retention.py), não "resolvido".
--
-- Reverter significa reaplicar a migração 002 e recriar a coluna.
DROP TABLE IF EXISTS ocorrencias_externas;
ALTER TABLE eventos DROP COLUMN resolvido_em;
