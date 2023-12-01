CREATE SEQUENCE usuarios_id_seq;

CREATE TABLE usuarios (
    id INTEGER DEFAULT nextval('usuarios_id_seq') PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    data_nascimento DATE
);
