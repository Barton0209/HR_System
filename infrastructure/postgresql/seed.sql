-- infrastructure/postgresql/seed.sql
-- Начальные данные

-- 1. Admin user
INSERT INTO idps.users (username, email, password_hash, is_admin, active, department)
VALUES (
    'admin',
    'admin@example.com',
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',  -- SHA-256 пустой строки (замените)
    true,
    true,
    'Admin'
) ON CONFLICT (username) DO NOTHING;

-- 2. Тестовые пользователи подразделений
INSERT INTO idps.users (username, email, password_hash, is_admin, active, department)
VALUES
    ('op_kingisepp', 'kingisepp@company.ru', 'hash_placeholder', false, true, 'ОП Кингисепп'),
    ('op_sochi', 'sochi@company.ru', 'hash_placeholder', false, true, 'ОП Сочи')
ON CONFLICT (username) DO NOTHING;

-- 3. Тестовые сотрудники
INSERT INTO idps.employees (
    fio, fio_hash, tab_num, position, department, department_category,
    citizenship, birth_date, doc_series, doc_num, phone
)
VALUES
    (
        'Атабеков Бакберген Туйгинбекович',
        MD5('атабеков бакберген туйгинбекович'),
        '12345',
        'Монтажник строительных лесов и подмостей',
        'ОП Кингисепп 2. ЕвроХим',
        'СМУ',
        'КИРГИЗИЯ',
        '21.02.1995',
        'TP',
        '042007676',
        '+7 (999) 123-45-67'
    ),
    (
        'Шералиев Нурмухаммад Фарход Угли',
        MD5('шералиев нурмухаммад фарход угли'),
        '67890',
        'Антикоррозийщик',
        'ОП Кингисепп 2. ЕвроХим',
        'СМУ',
        'УЗБЕКИСТАН',
        '26.10.2006',
        '',
        '0381588',
        '+7 (999) 987-65-43'
    )
ON CONFLICT DO NOTHING;
