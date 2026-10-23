-- Remove as notificações.
--
-- A tabela era para avisos por e-mail, SMS ou push, mas isso nunca foi
-- implementado e nada gravava nela.
--
-- Reverter significa reaplicar o bloco notificacoes de schema.sql.
DROP TABLE IF EXISTS notificacoes;
