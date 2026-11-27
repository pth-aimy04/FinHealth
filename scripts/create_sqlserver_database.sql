-- Run in SSMS on your own SQL Server instance with database-creation permission.
-- Existing databases are preserved. Migrations and financial restore run from Python.
USE master;
GO
IF DB_ID(N'finhealth_db') IS NULL
BEGIN
    CREATE DATABASE [finhealth_db];
END;
GO
