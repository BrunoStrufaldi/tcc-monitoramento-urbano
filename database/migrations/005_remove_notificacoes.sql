-- Remove a funcionalidade de notificações.
--
-- A tabela registrava o disparo de um aviso por canal externo (e-mail, SMS,
-- push, webhook). Nada no sistema jamais a preencheu: o único produtor era o
-- formulário manual do painel, removido junto com as demais ações de
-- operador. O sistema detecta e exibe o evento no painel; avisar terceiros
-- nunca esteve implementado.
--
-- Reverter significa reaplicar o bloco `notificacoes` de schema.sql.
DROP TABLE IF EXISTS notificacoes;
