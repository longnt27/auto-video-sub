CREATE ROLE app LOGIN PASSWORD 'app';
CREATE DATABASE auto_video_sub OWNER app;

CREATE ROLE temporal LOGIN PASSWORD 'temporal' CREATEDB;
CREATE DATABASE temporal OWNER temporal;
CREATE DATABASE temporal_visibility OWNER temporal;
