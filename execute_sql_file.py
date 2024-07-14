def execute_sql_file(cursor, file_path):
    with open(file_path, 'r') as file:
        sql = file.read()
    cursor.execute(sql)
