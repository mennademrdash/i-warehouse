
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    img TEXT,
    description TEXT,
    price REAL,
    tags TEXT,
    createdAt TEXT,
    quantity INTEGER
);

-
INSERT INTO devices (id, name, img, description, price, tags, createdAt, quantity) VALUES
(1, 'Arduino Uno', 'device1.jpeg', 'عبارة عن لوحة الكترونية قابلة للبرمجة تستخدم كعقل لربط والتحكم في القطع الالكترونيه الاخرى لابتكار مشاريع ذكية و تفاعليه', 450, '["microcontroller", "arduino", "electronics", "diy"]', '2026-07-12T10:00:00.000Z', 50),
(2, 'DC-DC Buck Converter', 'device2.jpeg', 'بياخد كهرباء بجهد عالي وبيقللها لجهد أقل ومستقر تقدر تظبطه وتتحكم فيه يدوياً عن طريق البكرة (المقاومة المتغيرة) عشان تشغل بيه أجهزة بتحتاج فولت معين', 45, '["power", "converter", "voltage-regulator", "electronics"]', '2026-07-12T12:00:00.000Z', 120),
(3, 'PoE Module', 'device3.jpeg', 'وظيفته إنه بياخد كابل النت العادي ويفصل منه البيانات والكهرباء عشان يشغل أجهزة زي كاميرات المراقبة (IP Cameras) بكابل واحد بس من غير ما تحتاج مصدر كهرباء منفصل', 150, '["network", "power", "ethernet", "poe", "security"]', '2026-07-12T13:00:00.000Z', 40),
(4, 'Relay Module', 'device4.jpeg', 'عبارة عن مفتاح إلكتروني بيسمح للوحات البرمجة (زي الأردوينو والـ ESP32) إنها تتحكم في تشغيل أو قفل أجهزة بتسحب كهرباء عالية (زي اللمبات أو المواتير) بأمان تام', 35, '["switch", "control", "smart-home", "automation"]', '2026-07-12T13:11:00.000Z', 150);

