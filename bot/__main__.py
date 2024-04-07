from datetime import datetime
import os
import sqlite3

import aiosqlite
from aiosqlite import Connection
import dotenv
import hikari
import lightbulb as lb
from lightbulb.ext import tasks

dotenv.load_dotenv()


bot = lb.BotApp(token=os.environ["TOKEN"], prefix=lb.when_mentioned_or("!"))
tasks.load(bot)


# Register the command to the bot
@bot.command
# Use the command decorator to convert the function into a command
@lb.command("ping", "checks the bot is alive")
# Define the command type(s) that this command implements
@lb.implements(lb.PrefixCommand, lb.SlashCommand)
# Define the command's callback. The callback should take a single argument which will be
# an instance of a subclass of lightbulb.Context when passed in
async def ping(ctx: lb.Context) -> None:
    # Send a message to the channel the command was used in
    await ctx.respond(f"Pong! {ctx.bot.heartbeat_latency:.2f}ms")


@bot.listen(hikari.StartingEvent)
async def on_started(_: hikari.StartingEvent):
    print("connecting to db...")
    conn = await aiosqlite.connect(os.environ["DATABASE_URL"])
    conn.row_factory = sqlite3.Row  # allows us to query rows by col name
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

    bot.d.db = conn


@tasks.task(s=10, auto_start=True, pass_app=True)
async def send_scheduled_messages(app: lb.BotApp):
    await tasks.wait_until_started()
    print(app.d)
    db: Connection = app.d.db
    cur = await db.execute(
        """
        SELECT 
            user_id, channel_id, send_at, msg 
        FROM 
            scheduled_messages
        WHERE send_at <= datetime('now');
    """
    )
    rows = await cur.fetchall()
    for row in rows:
        print(
            "sending message from ",
            row["user_id"],
            "in",
            row["channel_id"],
            "len",
            len(row["msg"]),
        )
        await app.rest.create_message(
            row["channel_id"],
            row["msg"],
            mentions_everyone=True,
            flags=hikari.MessageFlag.URGENT,
        )
        await db.execute(
            """
            DELETE FROM 
                scheduled_messages
            WHERE 
                user_id = :user_id  AND
                channel_id = :channel_id AND
                send_at = :send_at;
            """,
            {
                "user_id": row["user_id"],
                "channel_id": row["channel_id"],
                "send_at": row["send_at"],
            },
        )
        await db.commit()


@lb.add_checks(lb.guild_only)
@lb.add_checks(lb.has_guild_permissions(hikari.Permissions.ADMINISTRATOR))
@bot.command
@lb.option("message", "the message to schedule", required=True)
@lb.option("time", "the time to schedule at (yyyy/mm/dd HH:MM:SS)", required=True)
@lb.option(
    "channel", "the channel to send in", required=True, type=hikari.TextableGuildChannel
)
@lb.command("schedule_message", "Schedule a message to be sent later")
@lb.implements(lb.SlashCommand)
async def schedule_message(ctx: lb.SlashContext):
    print(
        f"{ctx.channel_id}, {ctx.guild_id}, {ctx.options.message}, {ctx.options.time}, {ctx.options.channel}"
    )
    time = datetime.strptime(ctx.options.time, "%Y/%m/%d %H:%M:%S")
    channel: hikari.TextableGuildChannel = ctx.options.channel
    db: Connection = ctx.bot.d.db
    await db.execute(
        """
        INSERT INTO scheduled_messages (user_id, channel_id, send_at, msg) 
        VALUES (:user_id, :channel_id, :send_at, :msg) ;
    """,
        {
            "user_id": ctx.user.id,
            "channel_id": channel.id,
            "send_at": time,
            "msg": ctx.options.message.replace("\\n", "\n"),
        },
    )
    await db.commit()

    await ctx.respond(
        f"{ctx.channel_id}, {ctx.guild_id}, {ctx.options.message}, {ctx.options.time}, {ctx.options.channel}"
    )


@bot.command
@lb.command("view_scheduled_messages", "View your scheduled messages")
@lb.implements(lb.SlashCommand)
async def view_scheduled_messages(ctx: lb.SlashContext):
    db: Connection = ctx.bot.d.db
    cur = await db.execute("""
        SELECT 
            user_id, channel_id, send_at, msg 
        FROM 
            scheduled_messages
        WHERE send_at >= datetime('now');
    """)
    rows = await cur.fetchall()

    msg = ""
    for row in rows:
        time = datetime.strptime(row["send_at"], "%Y-%m-%d %H:%M:%S")
        timestamp = int(time.timestamp())
        msg += f"<#{row['channel_id']}> <t:{timestamp}> (<t:{timestamp}:R>):\n{row['msg']}\n\n"

    await ctx.respond(msg)




@bot.listen(hikari.StoppedEvent)
async def on_stopped(_: hikari.StoppedEvent):
    db: aiosqlite.Connection = bot.d.db
    print("closing db...")
    await db.close()


if __name__ == "__main__":
    import uvloop

    uvloop.install()

    # Run the bot
    # Note that this is blocking meaning no code after this line will run
    # until the bot is shut off
    bot.run()
