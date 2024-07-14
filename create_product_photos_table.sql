CREATE TABLE IF NOT EXISTS product_photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    photo BLOB,
    FOREIGN KEY (product_id) REFERENCES product (id)
);
