-- Migração destrutiva: remove a camada de autenticação.
-- O sistema não tem mais login, perfis (operador/administrador) nem trilha
-- por usuário — os eventos nascem da detecção automática, não de operador
-- humano. O registro de sistema que sobrou vive em `logs_sistema`.
--
-- Ordem obrigatória: `auditoria_acoes` tem FK para `usuarios`
-- (fk_auditoria_usuario), então é dropada primeiro.
--
-- Reverter significa reaplicar 001_security.sql; os dados não voltam.
DROP TABLE IF EXISTS auditoria_acoes;
DROP TABLE IF EXISTS usuarios;
