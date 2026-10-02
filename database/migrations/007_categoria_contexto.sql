-- O Data Fusion passou a ter duas dimensões (IA e contexto). A categoria dos
-- dados contextuais que a alimentam deixa de se chamar "clima" — ela também
-- guarda índice de trânsito (contagem de veículos, TomTom) e histórico de
-- alagamento, não só clima.
--
-- No SQLite o mesmo UPDATE roda sozinho no startup
-- (data_fusion_service.migrar_categoria_legada).
UPDATE dados_contextuais SET categoria = 'contexto' WHERE categoria = 'clima';
