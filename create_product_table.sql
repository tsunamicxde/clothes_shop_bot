CREATE TABLE IF NOT EXISTS product (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    parse_name TEXT NOT NULL,
    parent_category TEXT NOT NULL,
    min_price REAL,
    count_of_reviews INTEGER
);
