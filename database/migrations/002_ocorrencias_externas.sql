-- Migração aditiva: não remove nem modifica dados existentes.
-- Rastreia registros já processados de fontes externas (GeoSampa/Defesa
-- Civil) para não duplicar evento a cada nova consulta ao mesmo dataset.
CREATE TABLE IF NOT EXISTS ocorrencias_externas (
  id INT AUTO_INCREMENT PRIMARY KEY,
  fonte VARCHAR(60) NOT NULL,
  identificador_externo VARCHAR(80) NOT NULL,
  evento_id INT NULL,
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_ocorrencias_externas_fonte_identificador (fonte, identificador_externo),
  CONSTRAINT fk_ocorrencias_externas_evento FOREIGN KEY (evento_id) REFERENCES eventos(id) ON DELETE SET NULL,
  INDEX idx_ocorrencias_externas_evento (evento_id)
);
