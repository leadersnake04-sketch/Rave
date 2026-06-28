import discord
from discord import app_commands
from discord.ext import commands
import wavelink
import asyncio
import os
from flask import Flask
from threading import Thread
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────
# KEEP ALIVE
# ─────────────────────────────────────────
app = Flask('')

@app.route('/')
def home():
    return "Rave est en ligne 🃏"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
RED = 0xE74C3C
GOLD = 0xF39C12

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)


def footer_text():
    return f"Rave 🃏 • {datetime.now().strftime('%d/%m/%Y à %H:%M')}"


def fmt_dur(ms):
    if not ms:
        return "∞"
    s = ms // 1000
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def np_embed(track, player):
    em = discord.Embed(
        title="🃏 En cours",
        description=f"**[{track.title}]({track.uri})**",
        color=RED
    )
    if getattr(track, 'artwork', None):
        em.set_thumbnail(url=track.artwork)
    em.add_field(name="⏱️", value=fmt_dur(track.length), inline=True)
    em.add_field(name="🎤", value=getattr(track, 'author', '?') or '?', inline=True)
    em.add_field(name="📋", value=f"{len(player.queue)} en file", inline=True)
    em.set_footer(text=footer_text())
    return em


# ─────────────────────────────────────────
# BOUTONS
# ─────────────────────────────────────────
class Controls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.primary, row=0)
    async def pause(self, i: discord.Interaction, b):
        await i.response.defer()
        p = i.guild.voice_client
        if p:
            await p.pause(not p.paused)
            await i.followup.send("⏸️" if p.paused else "▶️", ephemeral=True, delete_after=2)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, row=0)
    async def skip(self, i: discord.Interaction, b):
        await i.response.defer()
        p = i.guild.voice_client
        if p:
            await p.skip(force=True)
            await i.followup.send("⏭️ Skip !", ephemeral=True, delete_after=2)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, row=0)
    async def shuffle(self, i: discord.Interaction, b):
        await i.response.defer()
        p = i.guild.voice_client
        if p and p.queue:
            p.queue.shuffle()
            await i.followup.send("🔀 Mélangé !", ephemeral=True, delete_after=2)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, row=0)
    async def loop(self, i: discord.Interaction, b):
        await i.response.defer()
        p = i.guild.voice_client
        if p:
            if p.queue.mode == wavelink.QueueMode.normal:
                p.queue.mode = wavelink.QueueMode.loop
                await i.followup.send("🔂 Loop piste", ephemeral=True, delete_after=2)
            elif p.queue.mode == wavelink.QueueMode.loop:
                p.queue.mode = wavelink.QueueMode.loop_all
                await i.followup.send("🔁 Loop file", ephemeral=True, delete_after=2)
            else:
                p.queue.mode = wavelink.QueueMode.normal
                await i.followup.send("➡️ Loop off", ephemeral=True, delete_after=2)

    @discord.ui.button(emoji="🔉", style=discord.ButtonStyle.secondary, row=1)
    async def vol_down(self, i: discord.Interaction, b):
        await i.response.defer()
        p = i.guild.voice_client
        if p:
            v = max(0, p.volume - 10)
            await p.set_volume(v)
            await i.followup.send(f"🔉 {v}%", ephemeral=True, delete_after=2)

    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, row=1)
    async def vol_up(self, i: discord.Interaction, b):
        await i.response.defer()
        p = i.guild.voice_client
        if p:
            v = min(100, p.volume + 10)
            await p.set_volume(v)
            await i.followup.send(f"🔊 {v}%", ephemeral=True, delete_after=2)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, row=1)
    async def stop(self, i: discord.Interaction, b):
        await i.response.defer()
        p = i.guild.voice_client
        if p:
            p.queue.clear()
            await p.stop()
            await p.disconnect()
            await i.followup.send("⏹️ Déconnecté 🃏", ephemeral=True, delete_after=3)


# ─────────────────────────────────────────
# SETUP LAVALINK
# ─────────────────────────────────────────
async def setup_lavalink():
    await bot.wait_until_ready()
    await asyncio.sleep(1)

    host = os.getenv("LAVALINK_HOST", "lavalink-2026-production-f304.up.railway.app")
    password = os.getenv("LAVALINK_PASSWORD", "maestrorave2026")

    node = wavelink.Node(
        uri=f"https://{host}",
        password=password,
    )
    try:
        await wavelink.Pool.connect(nodes=[node], client=bot, cache_capacity=100)
        print(f"✅ Lavalink connecté : {host}")
    except Exception as e:
        print(f"❌ Erreur Lavalink : {e}")


@bot.event
async def on_ready():
    print(f"Rave connecté : {bot.user}")
    bot.loop.create_task(setup_lavalink())
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} commandes synchronisées")
    except Exception as e:
        print(f"Erreur sync : {e}")


@bot.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
    print(f"✅ Node prêt : {payload.node.identifier}")


@bot.event
async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload):
    p = payload.player
    if hasattr(p, 'text_channel') and p.text_channel:
        await p.text_channel.send(embed=np_embed(payload.track, p), view=Controls())


@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    p = payload.player
    if not p.queue and hasattr(p, 'text_channel') and p.text_channel:
        em = discord.Embed(title="🎵 File terminée", description="Utilise `/play` pour continuer 🃏", color=RED)
        em.set_footer(text=footer_text())
        await p.text_channel.send(embed=em)


# ─────────────────────────────────────────
# HELPER CONNEXION
# ─────────────────────────────────────────
async def get_player(interaction: discord.Interaction) -> wavelink.Player | None:
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send("❌ Rejoins un salon vocal !", ephemeral=True)
        return None

    channel = interaction.user.voice.channel
    player: wavelink.Player = interaction.guild.voice_client

    if not player:
        try:
            player = await channel.connect(cls=wavelink.Player, deaf=True, timeout=60.0)
        except Exception as e:
            await interaction.followup.send(f"❌ Erreur connexion : `{e}`", ephemeral=True)
            return None
    elif player.channel.id != channel.id:
        try:
            await player.move_to(channel, timeout=60.0)
        except Exception as e:
            await interaction.followup.send(f"❌ Erreur déplacement : `{e}`", ephemeral=True)
            return None

    player.text_channel = interaction.channel
    return player


# ─────────────────────────────────────────
# /play
# ─────────────────────────────────────────
@bot.tree.command(name="play", description="Jouer une musique ou playlist")
@app_commands.describe(recherche="Lien ou nom (YouTube, SoundCloud...)")
async def play(interaction: discord.Interaction, recherche: str):
    await interaction.response.defer()

    player = await get_player(interaction)
    if not player:
        return

    player.autoplay = wavelink.AutoPlayMode.partial

    msg = await interaction.followup.send(embed=discord.Embed(
        title="🔍 Recherche...", description=f"**{recherche}**", color=GOLD))

    try:
        tracks = await wavelink.Playable.search(recherche)
        if not tracks:
            await msg.edit(embed=discord.Embed(title="❌ Rien trouvé", description=f"**{recherche}**", color=RED))
            return

        if isinstance(tracks, wavelink.Playlist):
            count = 0
            for t in tracks:
                await player.queue.put_wait(t)
                count += 1
            if not player.playing:
                await player.play(player.queue.get())
            await msg.edit(embed=discord.Embed(
                title="➕ Playlist ajoutée",
                description=f"**{tracks.name}** — {count} musiques 🃏",
                color=GOLD
            ))
        else:
            track = tracks[0]
            if player.playing:
                await player.queue.put_wait(track)
                em = discord.Embed(title="➕ En file", description=f"**[{track.title}]({track.uri})**", color=GOLD)
                if getattr(track, 'artwork', None):
                    em.set_thumbnail(url=track.artwork)
                em.add_field(name="⏱️", value=fmt_dur(track.length), inline=True)
                em.add_field(name="📋 Position", value=f"#{len(player.queue)}", inline=True)
                em.set_footer(text=footer_text())
                await msg.edit(embed=em)
            else:
                await player.play(track)
                await msg.delete()

    except Exception as e:
        await msg.edit(embed=discord.Embed(title="❌ Erreur", description=f"`{e}`", color=RED))
        print(f"Erreur play : {e}")


# ─────────────────────────────────────────
# /search
# ─────────────────────────────────────────
@bot.tree.command(name="search", description="Chercher parmi 5 résultats")
@app_commands.describe(recherche="Nom de la musique")
async def search(interaction: discord.Interaction, recherche: str):
    await interaction.response.defer()
    try:
        tracks = await wavelink.Playable.search(f"ytsearch:{recherche}")
        tracks = tracks[:5]
        if not tracks:
            await interaction.followup.send("❌ Rien trouvé !", ephemeral=True)
            return
        em = discord.Embed(title=f"🔍 {recherche}", color=RED)
        for i, t in enumerate(tracks, 1):
            em.add_field(name=f"{i}. {t.title[:80]}", value=f"⏱️ {fmt_dur(t.length)}", inline=False)
        em.set_footer(text=footer_text())

        class SV(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)
                sel = discord.ui.Select(placeholder="Choisis...", options=[
                    discord.SelectOption(label=t.title[:100], value=str(i)) for i, t in enumerate(tracks)
                ])
                sel.callback = self.cb
                self.add_item(sel)

            async def cb(self, i2: discord.Interaction):
                idx = int(i2.data['values'][0])
                t = tracks[idx]
                await i2.response.defer()
                await play.callback(i2, t.uri or t.title)

        await interaction.followup.send(embed=em, view=SV())
    except Exception as e:
        await interaction.followup.send(f"❌ {e}", ephemeral=True)


# ─────────────────────────────────────────
# /queue
# ─────────────────────────────────────────
@bot.tree.command(name="queue", description="Voir la file d'attente")
async def queue_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    p: wavelink.Player = interaction.guild.voice_client
    em = discord.Embed(title="📋 File d'attente", color=RED)
    if p and p.current:
        em.add_field(name="🃏 En cours", value=f"**{p.current.title}**\n⏱️ {fmt_dur(p.current.length)}", inline=False)
    if p and p.queue:
        txt = "\n".join([f"`{i}.` {t.title[:60]}" for i, t in enumerate(list(p.queue)[:10], 1)])
        if len(p.queue) > 10:
            txt += f"\n*+{len(p.queue)-10} autres*"
        em.add_field(name=f"📋 À venir ({len(p.queue)})", value=txt, inline=False)
    else:
        em.add_field(name="📋", value="File vide !", inline=False)
    em.set_footer(text=footer_text())
    await interaction.followup.send(embed=em, ephemeral=True)


# ─────────────────────────────────────────
# /nowplaying
# ─────────────────────────────────────────
@bot.tree.command(name="nowplaying", description="Musique en cours")
async def nowplaying(interaction: discord.Interaction):
    await interaction.response.defer()
    p: wavelink.Player = interaction.guild.voice_client
    if p and p.current:
        await interaction.followup.send(embed=np_embed(p.current, p), view=Controls())
    else:
        await interaction.followup.send("❌ Rien en cours !", ephemeral=True)


# ─────────────────────────────────────────
# /skip
# ─────────────────────────────────────────
@bot.tree.command(name="skip", description="Passer à la suivante")
async def skip(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    p: wavelink.Player = interaction.guild.voice_client
    if p and p.playing:
        await p.skip(force=True)
        await interaction.followup.send("⏭️ Skip !", ephemeral=True)
    else:
        await interaction.followup.send("❌ Rien en cours !", ephemeral=True)


# ─────────────────────────────────────────
# /stop
# ─────────────────────────────────────────
@bot.tree.command(name="stop", description="Stopper et déconnecter")
async def stop(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    p: wavelink.Player = interaction.guild.voice_client
    if p:
        p.queue.clear()
        await p.stop()
        await p.disconnect()
        await interaction.followup.send("⏹️ Déconnecté 🃏", ephemeral=True)


# ─────────────────────────────────────────
# /pause
# ─────────────────────────────────────────
@bot.tree.command(name="pause", description="Pause / Reprendre")
async def pause(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    p: wavelink.Player = interaction.guild.voice_client
    if p:
        await p.pause(not p.paused)
        await interaction.followup.send("⏸️" if p.paused else "▶️", ephemeral=True)


# ─────────────────────────────────────────
# /volume
# ─────────────────────────────────────────
@bot.tree.command(name="volume", description="Volume 0-100")
@app_commands.describe(niveau="Niveau entre 0 et 100")
async def volume(interaction: discord.Interaction, niveau: int):
    await interaction.response.defer(ephemeral=True)
    if not 0 <= niveau <= 100:
        await interaction.followup.send("❌ Entre 0 et 100 !", ephemeral=True)
        return
    p: wavelink.Player = interaction.guild.voice_client
    if p:
        await p.set_volume(niveau)
        await interaction.followup.send(f"🔊 {niveau}%", ephemeral=True)


# ─────────────────────────────────────────
# /loop
# ─────────────────────────────────────────
@bot.tree.command(name="loop", description="Mode répétition")
@app_commands.choices(mode=[
    app_commands.Choice(name="➡️ Off", value="none"),
    app_commands.Choice(name="🔂 Piste", value="one"),
    app_commands.Choice(name="🔁 File", value="all"),
])
async def loop(interaction: discord.Interaction, mode: str):
    await interaction.response.defer(ephemeral=True)
    p: wavelink.Player = interaction.guild.voice_client
    if p:
        m = {"none": wavelink.QueueMode.normal, "one": wavelink.QueueMode.loop, "all": wavelink.QueueMode.loop_all}
        p.queue.mode = m[mode]
        e = {"none": "➡️", "one": "🔂", "all": "🔁"}
        await interaction.followup.send(f"{e[mode]} Mode : **{mode}**", ephemeral=True)


# ─────────────────────────────────────────
# /shuffle
# ─────────────────────────────────────────
@bot.tree.command(name="shuffle", description="Mélanger la file")
async def shuffle(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    p: wavelink.Player = interaction.guild.voice_client
    if p and p.queue:
        p.queue.shuffle()
        await interaction.followup.send("🔀 Mélangé !", ephemeral=True)
    else:
        await interaction.followup.send("❌ File vide !", ephemeral=True)


# ─────────────────────────────────────────
# /remove
# ─────────────────────────────────────────
@bot.tree.command(name="remove", description="Supprimer une musique de la file")
@app_commands.describe(position="Position dans la file")
async def remove(interaction: discord.Interaction, position: int):
    await interaction.response.defer(ephemeral=True)
    p: wavelink.Player = interaction.guild.voice_client
    if p and 1 <= position <= len(p.queue):
        del p.queue[position - 1]
        await interaction.followup.send(f"🗑️ #{position} supprimé !", ephemeral=True)
    else:
        await interaction.followup.send("❌ Position invalide !", ephemeral=True)


# ─────────────────────────────────────────
# /clearqueue
# ─────────────────────────────────────────
@bot.tree.command(name="clearqueue", description="Vider la file")
async def clearqueue(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    p: wavelink.Player = interaction.guild.voice_client
    if p:
        p.queue.clear()
    await interaction.followup.send("🗑️ File vidée !", ephemeral=True)


# ─────────────────────────────────────────
# /jump
# ─────────────────────────────────────────
@bot.tree.command(name="jump", description="Sauter à une position")
@app_commands.describe(position="Position dans la file")
async def jump(interaction: discord.Interaction, position: int):
    await interaction.response.defer(ephemeral=True)
    p: wavelink.Player = interaction.guild.voice_client
    if p and 1 <= position <= len(p.queue):
        for _ in range(position - 1):
            p.queue.get()
        await p.skip(force=True)
        await interaction.followup.send(f"⏩ Position **{position}** !", ephemeral=True)
    else:
        await interaction.followup.send("❌ Position invalide !", ephemeral=True)


# ─────────────────────────────────────────
# ERREURS
# ─────────────────────────────────────────
@bot.tree.error
async def on_err(interaction: discord.Interaction, error):
    msg = f"❌ Erreur : {error}"
    try:
        await interaction.response.send_message(msg, ephemeral=True)
    except:
        try:
            await interaction.followup.send(msg, ephemeral=True)
        except:
            pass


keep_alive()
bot.run(os.getenv("TOKEN"))