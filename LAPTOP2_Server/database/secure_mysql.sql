-- Run ONCE in phpMyAdmin (SQL tab) or:  C:\xampp\mysql\bin\mysql -u root < secure_mysql.sql
-- 1) a dedicated database user for PawPet (change the password below FIRST!)
CREATE USER IF NOT EXISTS 'pawpet'@'localhost' IDENTIFIED BY 'CHANGE-THIS-PASSWORD-123';
GRANT ALL PRIVILEGES ON pawpet.* TO 'pawpet'@'localhost';
-- 2) a password for root (XAMPP ships with none). Change it, and remember it!
ALTER USER 'root'@'localhost' IDENTIFIED BY 'CHANGE-THIS-ROOT-PASSWORD-456';
FLUSH PRIVILEGES;
-- Then start the server with these set (cmd), so it no longer uses root:
--   set PAWPET_DB_USER=pawpet
--   set PAWPET_DB_PASSWORD=CHANGE-THIS-PASSWORD-123
--   py app.py
-- NOTE: the database is created by  py setup_database.py  - run it ONCE as root with the root password:
--   set PAWPET_DB_USER=root & set PAWPET_DB_PASSWORD=CHANGE-THIS-ROOT-PASSWORD-456 & py setup_database.py
-- then start the server with the 'pawpet' user (settings above).
-- Also keep MySQL private: in C:\xampp\mysql\bin\my.ini under [mysqld] add   bind-address=127.0.0.1
