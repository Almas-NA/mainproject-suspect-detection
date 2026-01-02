import mysql.connector

# ====================== DB CONFIG ======================
config = {
    'user': 'root',
    'password': '',
    'host': 'localhost',
    'database': 'suspect',
}

# ====================== DB FUNCTIONS ======================

def insert_record(query, data):
    cnx = mysql.connector.connect(**config)
    crsr = cnx.cursor()
    crsr.execute(query, data)
    cnx.commit()
    crsr.close()
    cnx.close()

def update_record(query, data):
    cnx = mysql.connector.connect(**config)
    cursor = cnx.cursor()
    cursor.execute(query, data)
    cnx.commit()
    cursor.close()
    cnx.close()
    return True

def select_record(query, data):
    cnx = mysql.connector.connect(**config)
    cursor = cnx.cursor()
    cursor.execute(query, data)
    row = cursor.fetchone()
    cursor.close()
    cnx.close()
    return row

def select_records(query, data):
    cnx = mysql.connector.connect(**config)
    cursor = cnx.cursor()
    cursor.execute(query, data)
    rows = cursor.fetchall()
    cursor.close()
    cnx.close()
    return rows

def count_records(query):
    cnx = mysql.connector.connect(**config)
    cursor = cnx.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    cnx.close()
    return len(rows)
