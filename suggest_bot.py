import discord
from discord import app_commands
from discord.ui import Button, View
import json, os, string, random
from datetime import datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))

if not os.path.exists("vote_up.gif") or not os.path.exists("vote_down.gif"):
    from gen_emojis import gen
    gen()
DATA_FILE = "suggestions.json"
SUGGEST_CHANNEL = 1511027051388469478

def sid(): return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

def load():
    if not os.path.exists(DATA_FILE): return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f: return json.load(f)

def save(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)

intents = discord.Intents.default()
intents.message_content = True

class VoteView(View):
    def __init__(self, up_e, down_e):
        super().__init__(timeout=None)
        self.up_e = up_e
        self.down_e = down_e
        b_up = Button(emoji=up_e, style=discord.ButtonStyle.success, custom_id="persist_yes")
        b_down = Button(emoji=down_e, style=discord.ButtonStyle.danger, custom_id="persist_no")
        b_up.callback = self.vote_yes
        b_down.callback = self.vote_no
        self.add_item(b_up)
        self.add_item(b_down)

    async def vote_yes(self, interaction):
        await self._vote(interaction, "yes")

    async def vote_no(self, interaction):
        await self._vote(interaction, "no")

    async def _vote(self, interaction, t):
        msg_id = str(interaction.message.id)
        data = load()
        if msg_id not in data:
            return await interaction.response.send_message("Not found", ephemeral=True)
        sug = data[msg_id]
        uid = str(interaction.user.id)
        votes = sug.setdefault("votes", {})
        if votes.get(uid) == t:
            del votes[uid]
        else:
            votes[uid] = t
        sug["yes"] = sum(1 for v in votes.values() if v == "yes")
        sug["no"] = sum(1 for v in votes.values() if v == "no")
        save(data)

        embed = interaction.message.embeds[0]
        embed.set_field_at(1, name="Results so far", value=f"{self.up_e}: {sug['yes']}  |  {self.down_e}: {sug['no']}", inline=False)
        await interaction.response.edit_message(embed=embed)

class SugBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents, activity=discord.Activity(type=discord.ActivityType.watching, name="dev:by_alex"))
        self.tree = app_commands.CommandTree(self)
        self.up_e = "\u2705"
        self.down_e = "\u274c"

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        print(f"Ready as {bot.user}")
        guild = None
        for g in self.guilds:
            for ch in g.channels:
                if ch.id == SUGGEST_CHANNEL:
                    guild = g
                    break
            if guild: break
        if guild and guild.me.guild_permissions.manage_emojis:
            for e in guild.emojis:
                if e.name == "vote_up":
                    self.up_e = e
                if e.name == "vote_down":
                    self.down_e = e
            if not isinstance(self.up_e, discord.Emoji):
                with open("vote_up.gif", "rb") as f:
                    self.up_e = await guild.create_custom_emoji(name="vote_up", image=f.read())
            if not isinstance(self.down_e, discord.Emoji):
                with open("vote_down.gif", "rb") as f:
                    self.down_e = await guild.create_custom_emoji(name="vote_down", image=f.read())
            print(f"Using custom emojis: {self.up_e} / {self.down_e}")
        else:
            print("No manage_emojis permission, using Unicode")
        self.add_view(VoteView(self.up_e, self.down_e))

bot = SugBot()

def make_embed(author, text, sid, up_e, down_e):
    embed = discord.Embed(color=0x0a2e36, timestamp=datetime.now())
    embed.set_author(name=f"Submitter | {author.display_name}", icon_url=author.display_avatar.url)
    embed.set_thumbnail(url=author.display_avatar.url)
    embed.add_field(name="Suggestion", value=text, inline=False)
    embed.add_field(name="Results so far", value=f"{up_e}: 0  |  {down_e}: 0", inline=False)
    embed.set_footer(text=f"User ID: {author.id} | sID: {sid}  \u2022  by_alex")
    return embed

@bot.event
async def on_message(msg):
    if msg.author.bot or msg.channel.id != SUGGEST_CHANNEL or msg.content.startswith("/"):
        return
    if not msg.content.strip() and not msg.attachments:
        return

    _sid = sid()
    text = msg.content if msg.content.strip() else "(no text)"
    embed = make_embed(msg.author, text, _sid, bot.up_e, bot.down_e)

    if msg.attachments:
        img = msg.attachments[0]
        if img.content_type and "image" in img.content_type:
            embed.set_thumbnail(url=img.url)

    await msg.delete()
    view = VoteView(bot.up_e, bot.down_e)
    bot_msg = await msg.channel.send(embed=embed, view=view)
    await bot_msg.create_thread(name=f"Thread for suggestion {_sid}", auto_archive_duration=1440)

    data = load()
    data[str(bot_msg.id)] = {"user_id": msg.author.id, "title": text, "yes": 0, "no": 0, "votes": {}, "sid": _sid}
    save(data)

@bot.tree.command(name="suggest", description="Submit a suggestion")
@app_commands.describe(text="Your suggestion")
async def suggest(interaction: discord.Interaction, text: str):
    _sid = sid()
    embed = make_embed(interaction.user, text, _sid, bot.up_e, bot.down_e)
    view = VoteView(bot.up_e, bot.down_e)
    bot_msg = await interaction.channel.send(embed=embed, view=view)

    data = load()
    data[str(bot_msg.id)] = {"user_id": interaction.user.id, "title": text, "yes": 0, "no": 0, "votes": {}, "sid": _sid}
    save(data)
    await interaction.response.send_message("\u2705", ephemeral=True)

@bot.tree.command(name="stats", description="Suggestion stats")
async def stats(interaction: discord.Interaction):
    data = load()
    total = len(data)
    total_votes = sum(len(s.get("votes", {})) for s in data.values())
    embed = discord.Embed(title="Suggestions Stats", color=0x0a2e36, timestamp=datetime.now())
    embed.add_field(name="Total Suggestions", value=str(total), inline=True)
    embed.add_field(name="Total Votes", value=str(total_votes), inline=True)
    embed.add_field(name="Average", value=f"{round(total_votes/total,1) if total else 0} votes/suggestion", inline=True)
    embed.set_footer(text="dev:by_alex")
    await interaction.response.send_message(embed=embed)

token = os.getenv("TOKEN")
if not token:
    raise RuntimeError("TOKEN environment variable not set")
bot.run(token)
