-- MySQL/MariaDB compatible migration for matchmaking table
CREATE TABLE matchmaking (
  id INT AUTO_INCREMENT PRIMARY KEY,
  player1_id INT NOT NULL,
  player2_id INT DEFAULT NULL,
  status VARCHAR(20) NOT NULL,
  mode VARCHAR(50) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (player1_id) REFERENCES players(id) ON DELETE CASCADE,
  FOREIGN KEY (player2_id) REFERENCES players(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE INDEX idx_matchmaking_status_mode ON matchmaking(status, mode);
