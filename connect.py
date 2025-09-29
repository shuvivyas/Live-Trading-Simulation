import psycopg2

conn = psycopg2.connect(
    dbname="trading",
    user="postgres",
    password="2001",
    host="localhost",
    port="8080"  
)

cursor = conn.cursor()
cursor.execute("SELECT version();")
print(cursor.fetchone())
cursor.close()
conn.close()
print("Connected to PostgreSQL database successfully!")
