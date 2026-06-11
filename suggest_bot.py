import discord
from discord import app_commands
from discord.ui import Button, View
import json, os, string, random, asyncio
from datetime import datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))

SUGGEST_FILE = "suggestions.json"
SCORE_FILE = "scores.json"
SUGGEST_CHANNEL = 1511027051388469478
COLOR = 0x0a2e36

def sid(): return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

def load(f):
    if not os.path.exists(f): return {}
    with open(f, "r", encoding="utf-8") as fp: return json.load(fp)

def save(f, data):
    with open(f, "w", encoding="utf-8") as fp: json.dump(data, fp, indent=2, ensure_ascii=False)

def add_score(uid, a=1):
    d = load(SCORE_FILE)
    d[str(uid)] = d.get(str(uid), 0) + a
    save(SCORE_FILE, d)
    return d[str(uid)]

def get_score(uid):
    return load(SCORE_FILE).get(str(uid), 0)

intents = discord.Intents.default()
intents.message_content = True

# ====================== VOTE VIEW ======================
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

    async def vote_yes(self, i):
        await self._vote(i, "yes")
    async def vote_no(self, i):
        await self._vote(i, "no")
    async def _vote(self, i, t):
        mid = str(i.message.id)
        d = load(SUGGEST_FILE)
        if mid not in d:
            return await i.response.send_message("Not found", ephemeral=True)
        s = d[mid]
        uid = str(i.user.id)
        v = s.setdefault("votes", {})
        if v.get(uid) == t: del v[uid]
        else: v[uid] = t
        s["yes"] = sum(1 for x in v.values() if x == "yes")
        s["no"] = sum(1 for x in v.values() if x == "no")
        save(SUGGEST_FILE, d)
        e = i.message.embeds[0]
        e.set_field_at(1, name="Results so far", value=f"{self.up_e}: {s['yes']}  |  {self.down_e}: {s['no']}", inline=False)
        await i.response.edit_message(embed=e)

# ====================== CONFIRM VIEW ======================
class ConfirmView(View):
    def __init__(self, ctx, target):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.target = target
        self.value = False
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, i, b):
        if i.user.id != self.target.id:
            return await i.response.send_message("Not your button", ephemeral=True)
        self.value = True
        for c in self.children: c.disabled = True
        await i.response.edit_message(view=self)
        self.stop()
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, i, b):
        if i.user.id != self.target.id:
            return await i.response.send_message("Not your button", ephemeral=True)
        self.value = False
        for c in self.children: c.disabled = True
        await i.response.edit_message(view=self)
        self.stop()

# ====================== XO VIEW ======================
class XOButton(Button):
    def __init__(self, r, c):
        super().__init__(label="\u200b", style=discord.ButtonStyle.secondary, custom_id=f"xo_{r}_{c}", row=r)
        self.r, self.c, self.val = r, c, None
    async def callback(self, i):
        v = self.view
        if i.user.id != v.cp: return await i.response.send_message("Not your turn!", ephemeral=True)
        if self.val is not None: return await i.response.send_message("Taken!", ephemeral=True)
        mark = "❌" if v.turn else "⭕"
        self.val = mark; self.label = mark; self.disabled = True
        self.style = discord.ButtonStyle.danger if v.turn else discord.ButtonStyle.success
        v.turn = not v.turn
        ps = list(v.p.keys()); v.cp = ps[1] if v.cp == ps[0] else ps[0]
        w = v.check()
        if w:
            for c in v.children: c.disabled = True
            if w == "tie":
                e = discord.Embed(title="🤝 It's a tie!", color=COLOR)
            else:
                pid = v.p[w]; add_score(pid, 15)
                e = discord.Embed(title=f"🎉 {w} wins!", description=f"<@{pid}> +15 pts", color=COLOR)
            e.set_footer(text="Tic Tac Toe")
            await i.response.edit_message(embed=e, view=v); v.stop()
        else:
            e = discord.Embed(title="Tic Tac Toe", description=f"**<@{v.cp}>**'s turn", color=COLOR)
            await i.response.edit_message(embed=e, view=v)

class XOView(View):
    def __init__(self, p1, p2):
        super().__init__(timeout=120)
        self.p = {"❌": p1, "⭕": p2}; self.turn = True; self.cp = p1
        for r in range(3):
            for c in range(3): self.add_item(XOButton(r, c))
    def check(self):
        b = [[c.val if c.val else "" for c in self.children[r*3:(r+1)*3]] for r in range(3)]
        ls = b + [[b[r][c] for r in range(3)] for c in range(3)] + [[b[i][i] for i in range(3)],[b[i][2-i] for i in range(3)]]
        for l in ls:
            if l[0] and l[0]==l[1]==l[2]: return l[0]
        if all(c.val for c in self.children): return "tie"
        return None

# ====================== RPS VIEW ======================
class RPSView(View):
    def __init__(self, uid):
        super().__init__(timeout=120); self.uid = uid; self.c = None
    @discord.ui.button(emoji="🪨", style=discord.ButtonStyle.secondary)
    async def rock(self, i, b): await self._p(i, "rock")
    @discord.ui.button(emoji="📄", style=discord.ButtonStyle.secondary)
    async def paper(self, i, b): await self._p(i, "paper")
    @discord.ui.button(emoji="✂️", style=discord.ButtonStyle.secondary)
    async def scissors(self, i, b): await self._p(i, "scissors")
    async def _p(self, i, ch):
        if i.user.id != self.uid: return await i.response.send_message("Not your game", ephemeral=True)
        self.c = ch
        for c in self.children: c.disabled = True
        bc = random.choice(["rock","paper","scissors"])
        em = {"rock":"🪨","paper":"📄","scissors":"✂️"}
        w = {"rock":"scissors","scissors":"paper","paper":"rock"}
        r = "It's a tie!"
        if w[ch] == bc: r = "You win! +5 pts"; add_score(i.user.id, 5)
        elif ch != bc: r = "Bot wins!"
        e = discord.Embed(title="Rock Paper Scissors", color=COLOR)
        e.add_field(name="You", value=f"{em[ch]} {ch}", inline=True)
        e.add_field(name="Bot", value=f"{em[bc]} {bc}", inline=True)
        e.add_field(name="Result", value=r, inline=False)
        e.set_footer(text=f"Score: {get_score(i.user.id)}")
        await i.response.edit_message(embed=e, view=self); self.stop()

# ====================== GAME SELECT ======================
class GameSelect(discord.ui.Select):
    def __init__(self):
        opts = [
            discord.SelectOption(label="Rock Paper Scissors", emoji="🪨", value="rps", desc="vs bot"),
            discord.SelectOption(label="Coin Flip", emoji="🪙", value="coinflip", desc="Heads or tails"),
            discord.SelectOption(label="Dice Roll", emoji="🎲", value="dice", desc="Roll a dice"),
            discord.SelectOption(label="Slots", emoji="🎰", value="slots", desc="Slot machine"),
            discord.SelectOption(label="Trivia", emoji="🧠", value="trivia", desc="Quiz question"),
            discord.SelectOption(label="Fast Type", emoji="⌨️", value="fasttype", desc="Speed typing"),
            discord.SelectOption(label="Roulette", emoji="🎡", value="roulette", desc="Red/black/green"),
            discord.SelectOption(label="Tic Tac Toe", emoji="❌", value="xo", desc="2 player"),
        ]
        super().__init__(placeholder="Choose a game...", min_values=1, max_values=1, options=opts)
    async def callback(self, i):
        cmds = {"rps":rps,"coinflip":coinflip,"dice":dice,"slots":slots,"trivia":trivia,"fasttype":fasttype,"roulette":roulette,"xo":xo}
        c = cmds.get(self.values[0])
        if c: await c.callback(i)

# ====================== CLIENT ======================
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
        self.add_view(VoteView(self.up_e, self.down_e))

bot = SugBot()

def make_embed(author, text, sid, ue, de):
    e = discord.Embed(color=COLOR, timestamp=datetime.now())
    e.set_author(name=f"Submitter | {author.display_name}", icon_url=author.display_avatar.url)
    e.set_thumbnail(url=author.display_avatar.url)
    e.add_field(name="Suggestion", value=text, inline=False)
    e.add_field(name="Results so far", value=f"{ue}: 0  |  {de}: 0", inline=False)
    e.set_footer(text=f"User ID: {author.id} | sID: {sid}  \u2022  by_alex")
    return e

# ====================== SUGGEST EVENTS ======================
@bot.event
async def on_message(msg):
    if msg.author.bot or msg.channel.id != SUGGEST_CHANNEL or msg.content.startswith("/"):
        return
    if not msg.content.strip() and not msg.attachments:
        return
    _s = sid()
    t = msg.content if msg.content.strip() else "(no text)"
    e = make_embed(msg.author, t, _s, bot.up_e, bot.down_e)
    if msg.attachments:
        im = msg.attachments[0]
        if im.content_type and "image" in im.content_type:
            e.set_thumbnail(url=im.url)
    await msg.delete()
    v = VoteView(bot.up_e, bot.down_e)
    bm = await msg.channel.send(embed=e, view=v)
    await bm.create_thread(name=f"Thread for suggestion {_s}", auto_archive_duration=1440)
    d = load(SUGGEST_FILE)
    d[str(bm.id)] = {"user_id": msg.author.id, "title": t, "yes": 0, "no": 0, "votes": {}, "sid": _s}
    save(SUGGEST_FILE, d)

# ====================== SUGGEST COMMANDS ======================
@bot.tree.command(name="suggest", description="Submit a suggestion")
@app_commands.describe(text="Your suggestion")
async def suggest(i: discord.Interaction, text: str):
    _s = sid()
    e = make_embed(i.user, text, _s, bot.up_e, bot.down_e)
    v = VoteView(bot.up_e, bot.down_e)
    bm = await i.channel.send(embed=e, view=v)
    d = load(SUGGEST_FILE)
    d[str(bm.id)] = {"user_id": i.user.id, "title": text, "yes": 0, "no": 0, "votes": {}, "sid": _s}
    save(SUGGEST_FILE, d)
    await i.response.send_message("\u2705", ephemeral=True)

@bot.tree.command(name="stats", description="Suggestion stats")
async def stats(i: discord.Interaction):
    d = load(SUGGEST_FILE)
    t = len(d); tv = sum(len(s.get("votes",{})) for s in d.values())
    e = discord.Embed(title="Suggestions Stats", color=COLOR, timestamp=datetime.now())
    e.add_field(name="Total Suggestions", value=str(t), inline=True)
    e.add_field(name="Total Votes", value=str(tv), inline=True)
    e.add_field(name="Average", value=f"{round(tv/t,1) if t else 0} votes/suggestion", inline=True)
    e.set_footer(text="dev:by_alex")
    await i.response.send_message(embed=e)

# ====================== GAMES ======================

@bot.tree.command(name="play", description="Open the game menu")
async def play(i: discord.Interaction):
    e = discord.Embed(title="🎮 Game Menu", description="Select a game from the dropdown below!", color=COLOR)
    e.set_footer(text=f"Score: {get_score(i.user.id)}")
    await i.response.send_message(embed=e, view=__import__('discord.ui').View().add_item(GameSelect()))

@bot.tree.command(name="rps", description="Rock Paper Scissors vs bot")
async def rps(i: discord.Interaction):
    e = discord.Embed(title="Rock Paper Scissors", description="Choose your move!", color=COLOR)
    e.set_footer(text=f"Score: {get_score(i.user.id)}")
    await i.response.send_message(embed=e, view=RPSView(i.user.id))

@bot.tree.command(name="coinflip", description="Flip a coin")
@app_commands.describe(bet="Heads or tails")
@app_commands.choices(bet=[app_commands.Choice(n="Heads",v="heads"),app_commands.Choice(n="Tails",v="tails")])
async def coinflip(i: discord.Interaction, bet: str):
    r = random.choice(["heads","tails"])
    w = bet == r
    if w: add_score(i.user.id, 3)
    e = discord.Embed(title="🪙 Coin Flip", color=COLOR)
    e.add_field(name="Your bet", value=bet.capitalize(), inline=True)
    e.add_field(name="Result", value=r.capitalize(), inline=True)
    e.add_field(name="Outcome", value="You won! 🎉 +3 pts" if w else "You lost! 😢", inline=False)
    e.set_footer(text=f"Score: {get_score(i.user.id)}")
    await i.response.send_message(embed=e)

@bot.tree.command(name="dice", description="Roll a dice")
@app_commands.describe(sides="Number of sides (default: 6)")
async def dice(i: discord.Interaction, sides: int = 6):
    r = random.randint(1, sides)
    add_score(i.user.id, 1)
    de = {1:"1️⃣",2:"2️⃣",3:"3️⃣",4:"4️⃣",5:"5️⃣",6:"6️⃣"}
    e = discord.Embed(title="🎲 Dice Roll", description=f"You rolled **{r}** {de.get(r,'🎲')}", color=COLOR)
    e.set_footer(text=f"Score: {get_score(i.user.id)}")
    await i.response.send_message(embed=e)

@bot.tree.command(name="slots", description="Play the slot machine")
async def slots(i: discord.Interaction):
    em = ["🍒","🍋","🍊","🍇","💎","7️⃣","⭐"]
    r1,r2,r3 = random.choices(em, k=3)
    w = r1==r2==r3
    if w: add_score(i.user.id, 20)
    else: add_score(i.user.id, -1)
    e = discord.Embed(title="🎰 Slot Machine", color=COLOR)
    e.add_field(name="Result", value=f"`[ {r1} | {r2} | {r3} ]`", inline=False)
    if w: e.add_field(name="JACKPOT!", value="You won 20 points! 🎉", inline=False)
    e.set_footer(text=f"Score: {get_score(i.user.id)}")
    await i.response.send_message(embed=e)

@bot.tree.command(name="guess", description="Guess a number between 1-100")
async def guess(i: discord.Interaction):
    n = random.randint(1, 100)
    e = discord.Embed(title="🔢 Guess the Number", description="I'm thinking of a number 1-100. Guess in chat!", color=COLOR)
    e.set_footer(text="5 attempts")
    await i.response.send_message(embed=e)
    def ck(m): return m.author.id==i.user.id and m.channel.id==i.channel.id and m.content.isdigit()
    for a in range(5,0,-1):
        try:
            m = await bot.wait_for("message", check=ck, timeout=60)
            g = int(m.content)
            if g<1 or g>100: await m.reply("1-100 only!"); continue
            if g==n:
                e = discord.Embed(title="🎉 Correct!", description=f"The number was **{n}**! {6-a} attempt(s)", color=COLOR)
                add_score(i.user.id, 10)
                e.set_footer(text=f"Score: {get_score(i.user.id)}"); await m.reply(embed=e); return
            await m.reply("⬆️ Higher!" if g<n else "⬇️ Lower!")
        except asyncio.TimeoutError:
            e = discord.Embed(title="⏰ Time's up!", description=f"The number was **{n}**", color=COLOR)
            await i.followup.send(embed=e); return
    e = discord.Embed(title="❌ Out of attempts!", description=f"The number was **{n}**", color=COLOR)
    await i.channel.send(embed=e)

tq = [{"q":"Capital of France?","a":["Paris"]},{"q":"Red Planet?","a":["Mars"]},{"q":"Largest ocean?","a":["Pacific","Pacific Ocean"]},{"q":"WWII ended?","a":["1945"]},{"q":"Fastest land animal?","a":["Cheetah"]},{"q":"Adult human bones?","a":["206"]},{"q":"Square root of 144?","a":["12"]},{"q":"Element 'Fe'?","a":["Iron"]},{"q":"Tallest mountain?","a":["Everest","Mount Everest"]}]

@bot.tree.command(name="trivia", description="Answer a trivia question")
async def trivia(i: discord.Interaction):
    q = random.choice(tq)
    e = discord.Embed(title="🧠 Trivia", description=q["q"], color=COLOR)
    e.set_footer(text="Answer in chat! (20s)")
    await i.response.send_message(embed=e)
    def ck(m): return m.author.id==i.user.id and m.channel.id==i.channel.id
    try:
        m = await bot.wait_for("message", check=ck, timeout=20)
        if m.content.strip().lower() in [a.lower() for a in q["a"]]:
            e = discord.Embed(title="✅ Correct!", description="+5 pts", color=COLOR)
            add_score(i.user.id, 5)
        else:
            e = discord.Embed(title="❌ Wrong!", description=f"Answer: **{q['a'][0]}**", color=COLOR)
        e.set_footer(text=f"Score: {get_score(i.user.id)}"); await m.reply(embed=e)
    except asyncio.TimeoutError:
        e = discord.Embed(title="⏰ Time's up!", description=f"Answer: **{q['a'][0]}**", color=COLOR)
        await i.followup.send(embed=e)

@bot.tree.command(name="fasttype", description="Type the sentence as fast as you can")
async def fasttype(i: discord.Interaction):
    texts = ["The quick brown fox jumps over the lazy dog","Python is a powerful language","Discord bots are fun to create","Coding is a superpower","Practice makes perfect"]
    t = random.choice(texts)
    e = discord.Embed(title="⌨️ Fast Type", description=f"Type this:\n```{t}```", color=COLOR)
    e.set_footer(text="15 seconds!")
    await i.response.send_message(embed=e)
    def ck(m): return m.author.id==i.user.id and m.channel.id==i.channel.id
    try:
        s = datetime.now()
        m = await bot.wait_for("message", check=ck, timeout=15)
        el = (datetime.now()-s).total_seconds()
        if m.content.strip().lower()==t.lower():
            pts = max(1, int(10-el))
            add_score(i.user.id, pts)
            e = discord.Embed(title="✅ Perfect!", description=f"Time: {el:.1f}s\n+{pts} pts", color=COLOR)
        else:
            e = discord.Embed(title="❌ Wrong!", description="Typo :(", color=COLOR)
        e.set_footer(text=f"Score: {get_score(i.user.id)}"); await m.reply(embed=e)
    except asyncio.TimeoutError:
        e = discord.Embed(title="⏰ Time's up!", color=COLOR); await i.followup.send(embed=e)

@bot.tree.command(name="roulette", description="Spin the roulette wheel")
@app_commands.describe(bet="Choose red, black, or green")
@app_commands.choices(bet=[app_commands.Choice(n="Red 🔴",v="red"),app_commands.Choice(n="Black ⚫",v="black"),app_commands.Choice(n="Green 🟢",v="green")])
async def roulette(i: discord.Interaction, bet: str):
    cs = {"red":["🔴",1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36],"black":["⚫",2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35],"green":["🟢",0]}
    rn = random.randint(0,36)
    rc = "green"
    for c,v in cs.items():
        if rn in v[1:]: rc=c; break
    w = bet==rc
    pts = {bet: 2 if bet!="green" else 14, "red":-2,"black":-2,"green":-2}[bet] if w else -2
    if bet!="green": pts = 2 if w else -2
    elif bet=="green": pts = 14 if w else -2
    pts = (2 if bet!="green" else 14) if w else -2
    add_score(i.user.id, pts)
    e = discord.Embed(title="🎰 Roulette", color=COLOR)
    e.add_field(name="Your bet", value=bet.capitalize(), inline=True)
    e.add_field(name="Result", value=f"{rn} {cs[rc][0]}", inline=True)
    e.add_field(name="Outcome", value=f"Won {pts} pts! 🎉" if w else f"Lost {abs(pts)} pts", inline=False)
    e.set_footer(text=f"Score: {get_score(i.user.id)}")
    await i.response.send_message(embed=e)

@bot.tree.command(name="xo", description="Play Tic Tac Toe with someone")
@app_commands.describe(opponent="Your opponent")
async def xo(i: discord.Interaction, opponent: discord.Member):
    if opponent.id==i.user.id: return await i.response.send_message("Can't play yourself!", ephemeral=True)
    if opponent.bot: return await i.response.send_message("Can't play bots!", ephemeral=True)
    e = discord.Embed(title="Tic Tac Toe", description=f"<@{opponent.id}> accept?", color=COLOR)
    v = ConfirmView(i, opponent)
    await i.response.send_message(embed=e, view=v); await v.wait()
    if v.value:
        e = discord.Embed(title="Tic Tac Toe", description=f"**<@{i.user.id}>**'s turn (❌)", color=COLOR)
        await i.edit_original_response(embed=e, view=XOView(i.user.id, opponent.id))
    else:
        e = discord.Embed(title="Declined ❌", color=COLOR); await i.edit_original_response(embed=e, view=None)

@bot.tree.command(name="lb", description="Leaderboard top players")
@app_commands.describe(page="Page number")
async def lb(i: discord.Interaction, page: int = 1):
    d = load(SCORE_FILE)
    if not d: return await i.response.send_message(embed=discord.Embed(title="🏆 Leaderboard", description="No players yet!", color=COLOR))
    sp = sorted(d.items(), key=lambda x: x[1], reverse=True)
    pp = 10; tp = (len(sp)+pp-1)//pp; pg = max(1, min(page, tp))
    ch = sp[(pg-1)*pp:pg*pp]
    e = discord.Embed(title="🏆 Leaderboard", color=COLOR)
    for idx,(uid,s) in enumerate(ch, start=(pg-1)*pp+1):
        m = {1:"🥇",2:"🥈",3:"🥉"}.get(idx, f"{idx}.")
        try:
            u = await bot.fetch_user(int(uid)); nm = u.display_name
        except: nm = uid
        e.add_field(name=f"{m} {nm}", value=f"{s} pts", inline=False)
    e.set_footer(text=f"Page {pg}/{tp}")
    await i.response.send_message(embed=e)

@bot.tree.command(name="score", description="Check your score")
async def score(i: discord.Interaction):
    s = get_score(i.user.id)
    e = discord.Embed(title="📊 Your Score", description=f"**{s}** points", color=COLOR)
    await i.response.send_message(embed=e)

token = os.getenv("TOKEN")
if not token: raise RuntimeError("TOKEN environment variable not set")
bot.run(token)
