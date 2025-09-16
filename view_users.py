from database.connection import get_db_cursor, close_db

conn, cur = get_db_cursor()
cur.execute("SELECT * FROM users;")
rows = cur.fetchall()
for row in rows:
    print(row)
close_db(conn, cur)
