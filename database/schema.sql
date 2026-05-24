-- =============================================================================
-- Banco principal do TCC — tcc_monitoramento_urbano
-- Execução: mysql -u root -p < database/schema.sql
-- Schema estendido (fases futuras): database/schema_extended.sql
-- =============================================================================

CREATE DATABASE IF NOT EXISTS tcc_monitoramento_urbano
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE tcc_monitoramento_urbano;

CREATE TABLE IF NOT EXISTS eventos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tipo VARCHAR(100) NOT NULL,
    descricao TEXT,
    criticidade VARCHAR(50),
    latitude DECIMAL(10,7),
    longitude DECIMAL(10,7),
    status VARCHAR(50),
    confiabilidade FLOAT DEFAULT 0,
    fonte VARCHAR(100),
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_eventos_tipo (tipo),
    INDEX idx_eventos_status (status),
    INDEX idx_eventos_criticidade (criticidade),
    INDEX idx_eventos_criado (criado_em)
) ENGINE=InnoDB;

-- Dados iniciais para desenvolvimento e testes do mapa
INSERT INTO eventos (tipo, descricao, criticidade, latitude, longitude, status, confiabilidade, fonte) VALUES
  ('transito', 'Congestionamento intenso na Av. Paulista', 'media', -23.5505200, -46.6333080, 'ativo', 0.65, 'api'),
  ('alagamento', 'Acúmulo de água após chuva forte na Zona Norte', 'alta', -23.5614140, -46.6558810, 'ativo', 0.82, 'sensor'),
  ('incendio', 'Fumaça detectada em área comercial — em análise', 'alta', -23.5429700, -46.6298100, 'em_analise', 0.55, 'manual');
