-- =====================================================================
-- PawPet database schema  (MySQL / MariaDB, XAMPP)           version 1
-- This file is the ONE source of truth for the tables.
--   * Normal use : py setup_database.py   (reads this file, run once)
--   * Manual use : import this whole file in phpMyAdmin (Import tab) on an empty server
-- Plain CREATE TABLE is used on purpose: the tables are created once, by the setup step.
-- The server never creates or alters tables; it only checks that schema_version matches.
-- Dates/times are stored as text (YYYY-MM-DD, HH:MM, YYYY-MM-DD HH:MM:SS) and money as DOUBLE,
-- so the JSON sent to the apps is simple and identical on every engine.
-- =====================================================================
CREATE DATABASE pawpet CHARACTER SET utf8mb4;
USE pawpet;
SET NAMES utf8mb4;

-- Accounts of every role. role = customer | staff | admin
CREATE TABLE users(
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(200) NOT NULL,              -- pbkdf2$iterations$salt$hash
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100),
    phone VARCHAR(30),
    role VARCHAR(20) NOT NULL DEFAULT 'customer',
    active TINYINT NOT NULL DEFAULT 1,
    must_change TINYINT NOT NULL DEFAULT 0,      -- 1 = must choose a new password at next sign-in
    created_at VARCHAR(19) NOT NULL
) ENGINE=InnoDB;

-- Sign-in sessions (bearer tokens)
CREATE TABLE tokens(
    token VARCHAR(64) PRIMARY KEY,
    user_id INT NOT NULL,
    created_at VARCHAR(19) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE pets(
    id INT AUTO_INCREMENT PRIMARY KEY,
    owner_id INT NOT NULL,
    name VARCHAR(60) NOT NULL,
    species VARCHAR(30) NOT NULL,
    breed VARCHAR(60),
    age DOUBLE,
    weight DOUBLE,
    notes VARCHAR(255),
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE products(
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(40) NOT NULL,
    price DOUBLE NOT NULL,
    stock INT NOT NULL DEFAULT 0,
    reorder_level INT NOT NULL DEFAULT 5,
    emoji VARCHAR(8) DEFAULT '🐾'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Every delivery of a product, with its own expiry date
CREATE TABLE batches(
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    batch_no VARCHAR(40),
    qty INT NOT NULL DEFAULT 0,
    expiry_date VARCHAR(10),
    received_at VARCHAR(19) NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE services(
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(255),
    price DOUBLE NOT NULL,
    duration INT NOT NULL DEFAULT 30,            -- minutes
    emoji VARCHAR(8) DEFAULT '🩺'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE vets(
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    specialty VARCHAR(100),
    work_days VARCHAR(20) NOT NULL DEFAULT '0,1,2,3,4',   -- 0 = Monday ... 6 = Sunday
    start_time VARCHAR(5) NOT NULL DEFAULT '09:00',
    end_time VARCHAR(5) NOT NULL DEFAULT '17:00',
    active TINYINT NOT NULL DEFAULT 1
) ENGINE=InnoDB;

-- status = pending | confirmed | completed | cancelled | no_show
CREATE TABLE appointments(
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    pet_id INT NOT NULL,
    service_id INT NOT NULL,
    vet_id INT NOT NULL,
    appt_date VARCHAR(10) NOT NULL,
    appt_time VARCHAR(5) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    notes VARCHAR(500),
    followup_of INT,
    created_at VARCHAR(19) NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES users(id),
    FOREIGN KEY (pet_id) REFERENCES pets(id),
    FOREIGN KEY (service_id) REFERENCES services(id),
    FOREIGN KEY (vet_id) REFERENCES vets(id),
    FOREIGN KEY (followup_of) REFERENCES appointments(id)
) ENGINE=InnoDB;

-- kind = product | service
CREATE TABLE sales(
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT,
    appointment_id INT,
    kind VARCHAR(20) NOT NULL,
    item_name VARCHAR(100) NOT NULL,
    qty INT NOT NULL DEFAULT 1,
    amount DOUBLE NOT NULL,
    created_at VARCHAR(19) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE notifications(
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(120) NOT NULL,
    body VARCHAR(500),
    is_read TINYINT NOT NULL DEFAULT 0,
    created_at VARCHAR(19) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Which version of this schema the database is on (the server refuses to start on a different version)
CREATE TABLE schema_version(
    version INT NOT NULL PRIMARY KEY,
    description VARCHAR(100) NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Indexes for the lookups the apps do all the time
CREATE INDEX idx_vet_day ON appointments(vet_id, appt_date);
CREATE INDEX idx_appt_date_status ON appointments(appt_date, status);
CREATE INDEX idx_appt_customer ON appointments(customer_id);
CREATE INDEX idx_pets_owner ON pets(owner_id);
CREATE INDEX idx_batches_product ON batches(product_id);
CREATE INDEX idx_sales_created ON sales(created_at);
CREATE INDEX idx_notif_user ON notifications(user_id, is_read);
CREATE INDEX idx_tokens_user ON tokens(user_id);

INSERT INTO schema_version(version, description) VALUES (1, 'Initial schema');
