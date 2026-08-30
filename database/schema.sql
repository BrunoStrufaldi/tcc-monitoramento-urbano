-- =============================================================================
-- Banco: notificacoes_urbanas
-- Sistema de notificações urbanas em tempo real 
-- =============================================================================

CREATE DATABASE IF NOT EXISTS notificacoes_urbanas
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE notificacoes_urbanas;

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS logs_sistema;
DROP TABLE IF EXISTS notificacoes;
DROP TABLE IF EXISTS dados_contextuais;
DROP TABLE IF EXISTS evidencias_visuais;
DROP TABLE IF EXISTS eventos;
DROP TABLE IF EXISTS localizacoes;
DROP TABLE IF EXISTS fontes_dados;
DROP TABLE IF EXISTS regioes;

SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE regioes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nome VARCHAR(120) NOT NULL,
  codigo VARCHAR(32) UNIQUE,
  descricao TEXT,
  poligono_geojson JSON NULL,
  ativo TINYINT(1) NOT NULL DEFAULT 1,
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  atualizado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_regioes_ativo (ativo)
) ENGINE=InnoDB;

CREATE TABLE fontes_dados (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nome VARCHAR(120) NOT NULL,
  tipo VARCHAR(50) NOT NULL COMMENT 'sensor, api, yolo, data_fusion, manual',
  endpoint VARCHAR(500) NULL,
  descricao TEXT,
  configuracao JSON NULL,
  ativo TINYINT(1) NOT NULL DEFAULT 1,
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  atualizado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_fontes_tipo (tipo),
  INDEX idx_fontes_ativo (ativo)
) ENGINE=InnoDB;

CREATE TABLE localizacoes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  regiao_id INT NULL,
  latitude DOUBLE NOT NULL,
  longitude DOUBLE NOT NULL,
  endereco VARCHAR(255) NULL,
  bairro VARCHAR(120) NULL,
  cidade VARCHAR(120) NULL DEFAULT 'São Paulo',
  cep VARCHAR(12) NULL,
  precisao_metros FLOAT NULL,
  referencia VARCHAR(200) NULL,
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  atualizado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_localizacoes_regiao FOREIGN KEY (regiao_id) REFERENCES regioes(id) ON DELETE SET NULL,
  INDEX idx_localizacoes_coords (latitude, longitude),
  INDEX idx_localizacoes_regiao (regiao_id)
) ENGINE=InnoDB;

CREATE TABLE eventos (
  id INT AUTO_INCREMENT PRIMARY KEY,
  titulo VARCHAR(200) NOT NULL,
  descricao TEXT,
  tipo VARCHAR(50) NOT NULL,
  severidade ENUM('baixa', 'media', 'alta', 'critica') NOT NULL DEFAULT 'media',
  status VARCHAR(30) NOT NULL DEFAULT 'ativo',
  localizacao_id INT NOT NULL,
  regiao_id INT NULL,
  fonte_id INT NULL,
  confianca DECIMAL(5,4) NULL,
  detectado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  resolvido_em DATETIME NULL,
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  atualizado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_eventos_localizacao FOREIGN KEY (localizacao_id) REFERENCES localizacoes(id) ON DELETE RESTRICT,
  CONSTRAINT fk_eventos_regiao FOREIGN KEY (regiao_id) REFERENCES regioes(id) ON DELETE SET NULL,
  CONSTRAINT fk_eventos_fonte FOREIGN KEY (fonte_id) REFERENCES fontes_dados(id) ON DELETE SET NULL,
  INDEX idx_eventos_status (status),
  INDEX idx_eventos_tipo (tipo),
  INDEX idx_eventos_severidade (severidade),
  INDEX idx_eventos_detectado (detectado_em),
  INDEX idx_eventos_localizacao (localizacao_id)
) ENGINE=InnoDB;

CREATE TABLE evidencias_visuais (
  id INT AUTO_INCREMENT PRIMARY KEY,
  evento_id INT NOT NULL,
  fonte_id INT NULL,
  tipo ENUM('imagem', 'video', 'frame', 'thumbnail') NOT NULL DEFAULT 'imagem',
  caminho_arquivo VARCHAR(500) NULL,
  url_externa VARCHAR(500) NULL,
  modelo_ia VARCHAR(80) NULL,
  classe_detectada VARCHAR(80) NULL,
  confianca DECIMAL(5,4) NULL,
  largura_px INT NULL,
  altura_px INT NULL,
  metadados JSON NULL,
  capturado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_evidencias_evento FOREIGN KEY (evento_id) REFERENCES eventos(id) ON DELETE CASCADE,
  CONSTRAINT fk_evidencias_fonte FOREIGN KEY (fonte_id) REFERENCES fontes_dados(id) ON DELETE SET NULL,
  INDEX idx_evidencias_evento (evento_id),
  INDEX idx_evidencias_capturado (capturado_em)
) ENGINE=InnoDB;

CREATE TABLE dados_contextuais (
  id INT AUTO_INCREMENT PRIMARY KEY,
  evento_id INT NULL,
  regiao_id INT NULL,
  fonte_id INT NULL,
  categoria VARCHAR(60) NOT NULL,
  chave VARCHAR(80) NOT NULL,
  valor_texto TEXT NULL,
  valor_numerico DOUBLE NULL,
  unidade VARCHAR(30) NULL,
  coletado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_contexto_evento FOREIGN KEY (evento_id) REFERENCES eventos(id) ON DELETE CASCADE,
  CONSTRAINT fk_contexto_regiao FOREIGN KEY (regiao_id) REFERENCES regioes(id) ON DELETE SET NULL,
  CONSTRAINT fk_contexto_fonte FOREIGN KEY (fonte_id) REFERENCES fontes_dados(id) ON DELETE SET NULL,
  INDEX idx_contexto_evento (evento_id),
  INDEX idx_contexto_regiao (regiao_id),
  INDEX idx_contexto_categoria (categoria),
  INDEX idx_contexto_coletado (coletado_em)
) ENGINE=InnoDB;

CREATE TABLE notificacoes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  evento_id INT NOT NULL,
  canal ENUM('painel', 'push', 'email', 'sms', 'webhook') NOT NULL DEFAULT 'painel',
  destinatario VARCHAR(200) NULL,
  titulo VARCHAR(200) NOT NULL,
  mensagem TEXT NOT NULL,
  status ENUM('pendente', 'enviada', 'falha', 'lida') NOT NULL DEFAULT 'pendente',
  tentativas TINYINT UNSIGNED NOT NULL DEFAULT 0,
  erro_detalhe TEXT NULL,
  agendada_para DATETIME NULL,
  enviada_em DATETIME NULL,
  lida_em DATETIME NULL,
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  atualizado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_notificacoes_evento FOREIGN KEY (evento_id) REFERENCES eventos(id) ON DELETE CASCADE,
  INDEX idx_notificacoes_evento (evento_id),
  INDEX idx_notificacoes_status (status),
  INDEX idx_notificacoes_canal (canal)
) ENGINE=InnoDB;

CREATE TABLE logs_sistema (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  nivel ENUM('DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL') NOT NULL DEFAULT 'INFO',
  modulo VARCHAR(80) NOT NULL,
  mensagem TEXT NOT NULL,
  evento_id INT NULL,
  contexto JSON NULL,
  ip_origem VARCHAR(45) NULL,
  criado_em DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  CONSTRAINT fk_logs_evento FOREIGN KEY (evento_id) REFERENCES eventos(id) ON DELETE SET NULL,
  INDEX idx_logs_nivel (nivel),
  INDEX idx_logs_modulo (modulo),
  INDEX idx_logs_criado (criado_em),
  INDEX idx_logs_evento (evento_id)
) ENGINE=InnoDB;

INSERT INTO regioes (nome, codigo, descricao) VALUES
  ('Centro', 'CENTRO', 'Região central da cidade'),
  ('Zona Norte', 'ZN', 'Bairros da zona norte'),
  ('Zona Sul', 'ZS', 'Bairros da zona sul');

INSERT INTO fontes_dados (nome, tipo, descricao, ativo) VALUES
  ('Painel manual', 'manual', 'Cadastro manual via API', 1),
  ('MotSP YOLO', 'yolo', 'Observações visuais revalidadas no servidor', 1),
  ('Open-Meteo', 'api', 'Clima e qualidade do ar em tempo real', 1);

-- O schema não popula eventos, evidências, contexto ou notificações. Esses
-- registros só podem entrar por uma integração real ou por uma ação auditada.

INSERT INTO logs_sistema (nivel, modulo, mensagem, evento_id, contexto) VALUES
  ('INFO', 'api', 'Schema inicializado sem eventos demonstrativos', NULL, JSON_OBJECT('versao_schema', '2.1'));
