import aiosqlite

DB = "data.db"

async def db_init():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users(
            telegram_id INTEGER PRIMARY KEY
        )""")

        await db.execute("""
        CREATE TABLE IF NOT EXISTS periods(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            start_date TEXT,
            end_date TEXT,
            opening_stock_cost INTEGER DEFAULT 0,
            closing_stock_cost INTEGER,
            is_closed INTEGER DEFAULT 0
        )""")

        await db.execute("""
        CREATE TABLE IF NOT EXISTS daily_sales(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            period_id INTEGER,
            date TEXT,
            cash_amount INTEGER DEFAULT 0,
            card_amount INTEGER DEFAULT 0
        )""")

        await db.execute("""
        CREATE TABLE IF NOT EXISTS purchases(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            period_id INTEGER,
            date TEXT,
            total_cost INTEGER,
            note TEXT
        )""")

        await db.execute("""
        CREATE TABLE IF NOT EXISTS expenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            period_id INTEGER,
            date TEXT,
            amount INTEGER,
            note TEXT
        )""")

        await db.execute("""
        CREATE TABLE IF NOT EXISTS reminders(
            telegram_id INTEGER PRIMARY KEY,
            hour INTEGER DEFAULT 21,
            minute INTEGER DEFAULT 0,
            enabled INTEGER DEFAULT 1
        )""")


        await db.commit()

async def get_or_create_user(telegram_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT OR IGNORE INTO users(telegram_id) VALUES(?)", (telegram_id,))
        await db.commit()

async def get_open_period(telegram_id: int):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
            SELECT id, start_date, end_date, opening_stock_cost, closing_stock_cost, is_closed
            FROM periods
            WHERE telegram_id=? AND is_closed=0
            ORDER BY id DESC LIMIT 1
        """, (telegram_id,))
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "start_date": row[1],
            "end_date": row[2],
            "opening_stock_cost": row[3],
            "closing_stock_cost": row[4],
            "is_closed": row[5],
        }

async def create_period(telegram_id: int, start_date: str, end_date: str):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
            INSERT INTO periods(telegram_id, start_date, end_date, opening_stock_cost, is_closed)
            VALUES(?,?,?,?,0)
        """, (telegram_id, start_date, end_date, 0))
        await db.commit()
        return cur.lastrowid

async def set_opening_stock(period_id: int, opening: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE periods SET opening_stock_cost=? WHERE id=?", (opening, period_id))
        await db.commit()

async def add_sale(telegram_id: int, period_id: int, d: str, cash: int, card: int):
    async with aiosqlite.connect(DB) as db:
        # har kunda 1 ta yozuv: bor bo'lsa update
        cur = await db.execute("""
            SELECT id FROM daily_sales WHERE telegram_id=? AND period_id=? AND date=?
        """, (telegram_id, period_id, d))
        row = await cur.fetchone()
        if row:
            await db.execute("""
                UPDATE daily_sales SET cash_amount=?, card_amount=? WHERE id=?
            """, (cash, card, row[0]))
        else:
            await db.execute("""
                INSERT INTO daily_sales(telegram_id, period_id, date, cash_amount, card_amount)
                VALUES(?,?,?,?,?)
            """, (telegram_id, period_id, d, cash, card))
        await db.commit()

async def add_purchase(telegram_id: int, period_id: int, d: str, total_cost: int, note: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
            INSERT INTO purchases(telegram_id, period_id, date, total_cost, note)
            VALUES(?,?,?,?,?)
        """, (telegram_id, period_id, d, total_cost, note))
        await db.commit()

async def add_expense(telegram_id: int, period_id: int, d: str, amount: int, note: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
            INSERT INTO expenses(telegram_id, period_id, date, amount, note)
            VALUES(?,?,?,?,?)
        """, (telegram_id, period_id, d, amount, note))
        await db.commit()

async def close_period(period_id: int, closing: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
            UPDATE periods SET closing_stock_cost=?, is_closed=1 WHERE id=?
        """, (closing, period_id))
        await db.commit()

async def period_totals(telegram_id: int, period_id: int):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
            SELECT COALESCE(SUM(cash_amount),0), COALESCE(SUM(card_amount),0)
            FROM daily_sales WHERE telegram_id=? AND period_id=?
        """, (telegram_id, period_id))
        cash, card = await cur.fetchone()

        cur = await db.execute("""
            SELECT COALESCE(SUM(total_cost),0)
            FROM purchases WHERE telegram_id=? AND period_id=?
        """, (telegram_id, period_id))
        purchases = (await cur.fetchone())[0]

        cur = await db.execute("""
            SELECT COALESCE(SUM(amount),0)
            FROM expenses WHERE telegram_id=? AND period_id=?
        """, (telegram_id, period_id))
        expenses = (await cur.fetchone())[0]

        return {"cash": cash, "card": card, "purchases": purchases, "expenses": expenses}

async def get_reminder(telegram_id: int):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT hour, minute, enabled FROM reminders WHERE telegram_id=?", (telegram_id,))
        row = await cur.fetchone()
        if not row:
            # default 21:00 ON
            await db.execute("INSERT INTO reminders(telegram_id, hour, minute, enabled) VALUES(?,?,?,?)", (telegram_id, 21, 0, 1))
            await db.commit()
            return {"hour": 21, "minute": 0, "enabled": 1}
        return {"hour": row[0], "minute": row[1], "enabled": row[2]}

async def set_reminder(telegram_id: int, hour: int, minute: int, enabled: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
            INSERT INTO reminders(telegram_id, hour, minute, enabled)
            VALUES(?,?,?,?)
            ON CONFLICT(telegram_id) DO UPDATE SET hour=excluded.hour, minute=excluded.minute, enabled=excluded.enabled
        """, (telegram_id, hour, minute, enabled))
        await db.commit()

async def get_reminders(telegram_id: int):
    return await get_reminder(telegram_id)
