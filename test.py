import asyncio
import os
import dotenv

import aiosqlite
import sqlite3


dotenv.load_dotenv()


async def main():
    conn = await aiosqlite.connect(os.environ["DATABASE_URL"])
    conn.row_factory = sqlite3.Row
    await conn.execute(
        """\
CREATE TABLE IF NOT EXISTS scheduled_messages(
    user_id BITINT NOT NULL,
    channel_id BIGINT NOT NULL,
    send_at TIMESTAMP NOT NULL,
    msg TEXT,

    PRIMARY KEY(user_id, channel_id, send_at)
);
"""
    )

    cur = await conn.execute("SELECT * FROM scheduled_messages;")
    rows = await cur.fetchall()
    for row in rows:
        # print(row["user_id"])
        print(row.keys())
        for key in row.keys():
            print(row[key], type(row[key]))

    await conn.close()


asyncio.run(main())
