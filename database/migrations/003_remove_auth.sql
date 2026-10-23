-- Migração destrutiva: remove login e usuários.
-- O sistema não tem mais operador, os eventos vêm da detecção automática.
--
-- A tabela auditoria_acoes depende de usuarios, por isso é apagada primeiro.
--
-- Reverter significa reaplicar 001_security.sql; os dados não voltam.
DROP TABLE IF EXISTS auditoria_acoes;
DROP TABLE IF EXISTS usuarios;
