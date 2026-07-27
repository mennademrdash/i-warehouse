import Database from "better-sqlite3";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const dbPath = path.join(__dirname, "devices.db");

const db = new Database(dbPath);

function initDB() {
  db.exec(`
    CREATE TABLE IF NOT EXISTS devices (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      img TEXT,
      description TEXT,
      price REAL,
      tags TEXT,
      createdAt TEXT,
      quantity INTEGER
    )
  `);
}

initDB();

export function createDevice({
  name,
  img,
  description,
  price,
  tags,
  quantity,
}) {
  const stmt = db.prepare(`
    INSERT INTO devices (name, img, description, price, tags, createdAt, quantity)
    VALUES (@name, @img, @description, @price, @tags, @createdAt, @quantity)
  `);

  const result = stmt.run({
    name,
    img: img ?? null,
    description: description ?? null,
    price: price ?? 0,
    tags: JSON.stringify(tags ?? []),
    createdAt: new Date().toISOString(),
    quantity: quantity ?? 0,
  });

  return getDeviceById(result.lastInsertRowid);
}

export function getAllDevices() {
  const rows = db.prepare("SELECT * FROM devices").all();
  return rows.map((row) => ({
    ...row,
    tags: row.tags ? JSON.parse(row.tags) : [],
  }));
}

export function getDeviceById(id) {
  const row = db.prepare("SELECT * FROM devices WHERE id = ?").get(id);
  if (!row) return null;
  return {
    ...row,
    tags: row.tags ? JSON.parse(row.tags) : [],
  };
}

export function updateDevice(id, updates) {
  const existing = getDeviceById(id);
  if (!existing) return null;

  const merged = {
    name: updates.name ?? existing.name,
    img: updates.img ?? existing.img,
    description: updates.description ?? existing.description,
    price: updates.price ?? existing.price,
    tags: JSON.stringify(updates.tags ?? existing.tags),
    quantity: updates.quantity ?? existing.quantity,
    id,
  };

  db.prepare(
    `
    UPDATE devices
    SET name = @name,
        img = @img,
        description = @description,
        price = @price,
        tags = @tags,
        quantity = @quantity
    WHERE id = @id
  `,
  ).run(merged);

  return getDeviceById(id);
}

export function deleteDevice(id) {
  const result = db.prepare("DELETE FROM devices WHERE id = ?").run(id);
  return result.changes > 0; // true لو اتحذف فعلاً، false لو مكانش موجود أصلاً
}

export function closeDB() {
  db.close();
}
