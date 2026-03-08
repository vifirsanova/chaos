-- Создаём партиции помесячно
DO $$
DECLARE
    start_date DATE := '2026-01-01';
    end_date DATE := '2027-01-01';
    cur_date DATE;
    table_name TEXT;
BEGIN
    cur_date := start_date;
    WHILE cur_date < end_date LOOP
        table_name := 'messages_' || to_char(cur_date, 'YYYY_MM');
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I PARTITION OF messages
            FOR VALUES FROM (%L) TO (%L)',
            table_name,
            cur_date,
            cur_date + INTERVAL '1 month'
        );
        cur_date := cur_date + INTERVAL '1 month';
    END LOOP;
END;
$$;
