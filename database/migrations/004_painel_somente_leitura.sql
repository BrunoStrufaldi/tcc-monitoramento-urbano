-- Painel somente leitura: o sistema não tem operador.
--
-- Nenhuma rota cria, altera ou remove eventos, então a coluna
-- logs_sistema.ip_origem não tem mais uso. Ela também nunca foi preenchida.
--
-- Reverter: ALTER TABLE logs_sistema ADD COLUMN ip_origem VARCHAR(45) NULL AFTER contexto;
ALTER TABLE logs_sistema DROP COLUMN ip_origem;
