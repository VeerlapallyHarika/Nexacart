import sqlite3

conn = sqlite3.connect('data/nexacart.db')
cursor = conn.cursor()
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='decision_traces'")
print("Table SQL:", cursor.fetchall())
cursor.execute("PRAGMA index_list('decision_traces')")
print("Indexes:", cursor.fetchall())
