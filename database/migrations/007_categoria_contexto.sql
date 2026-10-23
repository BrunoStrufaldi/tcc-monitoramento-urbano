-- A categoria "clima" dos dados contextuais passa a se chamar "contexto",
-- porque ela também guarda dados de trânsito e o histórico de alagamento.
--
-- No SQLite essa troca é feita sozinha quando o sistema inicia.
UPDATE dados_contextuais SET categoria = 'contexto' WHERE categoria = 'clima';
