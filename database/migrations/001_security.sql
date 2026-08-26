-- Migração aditiva: não remove nem modifica dados existentes.
CREATE TABLE IF NOT EXISTS usuarios (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nome_usuario VARCHAR(64) NOT NULL UNIQUE,
  senha_hash VARCHAR(512) NOT NULL,
  perfil VARCHAR(20) NOT NULL DEFAULT 'operador',
  ativo BOOLEAN NOT NULL DEFAULT TRUE,
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  atualizado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auditoria_acoes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  usuario_id INT NULL,
  acao VARCHAR(120) NOT NULL,
  evento_id INT NULL,
  resultado VARCHAR(20) NOT NULL,
  detalhes JSON NULL,
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX ix_auditoria_usuario (usuario_id),
  INDEX ix_auditoria_evento (evento_id),
  CONSTRAINT fk_auditoria_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
);
