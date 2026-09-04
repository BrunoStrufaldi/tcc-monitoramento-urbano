-- Painel somente leitura: o sistema não tem operador humano.
--
-- Os eventos, evidências e notificações nascem da detecção automática
-- (app/services/detection_events.py); nenhuma rota cria, altera ou remove
-- esses registros por requisição. Com isso, `logs_sistema.ip_origem` perdeu
-- o sentido: existia para rastrear a origem de uma ação de usuário, nunca
-- chegou a ser preenchida por nenhum código e agora não tem o que rastrear.
--
-- Reverter: ALTER TABLE logs_sistema ADD COLUMN ip_origem VARCHAR(45) NULL AFTER contexto;
ALTER TABLE logs_sistema DROP COLUMN ip_origem;
