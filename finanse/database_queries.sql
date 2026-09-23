-- Daily turnover.
SELECT * FROM daily_turnover ORDER BY date;

-- Top 20 senders.
SELECT gid, out_tx, out_kzt FROM client_turnover ORDER BY out_tiyn DESC LIMIT 20;

-- Top 20 recipients.
SELECT gid, in_tx, in_kzt FROM client_turnover ORDER BY in_tiyn DESC LIMIT 20;

-- Full history of one client; bind :gid as a parameter in Python.
SELECT * FROM transactions WHERE src=:gid OR dst=:gid ORDER BY date, transaction_id;
