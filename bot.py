import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import os
import random
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
BLACK = 0x1a1a1a

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

queues = {}
current_tracks = {}
loop_modes = {}
volumes = {}


def footer_text():
    return f"Rave 🃏 • {datetime.now().strftime('%d/%m/%Y à %H:%M')}"


def format_duration(seconds):
    if not seconds:
        return "∞"
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def get_queue(guild_id):
    if guild_id not in queues:
        queues[guild_id] = []
    return queues[guild_id]


# ─────────────────────────────────────────
# SOURCE AUDIO
# ─────────────────────────────────────────
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.webpage_url = data.get('webpage_url')
        self.thumbnail = data.get('thumbnail')
        self.duration = data.get('duration', 0)
        self.uploader = data.get('uploader', 'Inconnu')

    @classmethod
    async def from_url(cls, url, *, stream=True, volume=0.5):
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            return [cls(discord.FFmpegPCMAudio(e['url'], **FFMPEG_OPTIONS), data=e, volume=volume)
                    for e in data['entries'] if e]
        return cls(discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS), data=data, volume=volume)


# ─────────────────────────────────────────
# LECTURE SUIVANTE
# ─────────────────────────────────────────
async def play_next(guild, voice_client, text_channel):
    guild_id = guild.id
    queue = get_queue(guild_id)
    loop_mode = loop_modes.get(guild_id, "none")

    if loop_mode == "one" and guild_id in current_tracks:
        track = current_tracks[guild_id]
        try:
            source = await YTDLSource.from_url(track.webpage_url, stream=True, volume=volumes.get(guild_id, 0.5))
            if isinstance(source, list):
                source = source[0]
            voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(
                play_next(guild, voice_client, text_channel), bot.loop))
            current_tracks[guild_id] = source
        except:
            pass
        return

    if loop_mode == "all" and guild_id in current_tracks:
        queue.append(current_tracks[guild_id].webpage_url)

    if not queue:
        current_tracks.pop(guild_id, None)
        embed = discord.Embed(
            title="🎵 File d'attente terminée",
            description="Plus rien à jouer... Ajoute des musiques avec `/play` 🃏",
            color=RED
        )
        embed.set_footer(text=footer_text())
        await text_channel.send(embed=embed)
        return

    url = queue.pop(0)
    try:
        source = await YTDLSource.from_url(url, stream=True, volume=volumes.get(guild_id, 0.5))
        if isinstance(source, list):
            source = source[0]
        current_tracks[guild_id] = source
        voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(
            play_next(guild, voice_client, text_channel), bot.loop))
        embed = create_now_playing_embed(source, guild_id)
        view = MusicControls(guild_id, text_channel)
        await text_channel.send(embed=embed, view=view)
    except Exception as e:
        await text_channel.send(f"❌ Erreur lors de la lecture : {e}")


def create_now_playing_embed(source, guild_id):
    loop_mode = loop_modes.get(guild_id, "none")
    loop_emoji = "🔁" if loop_mode == "all" else "🔂" if loop_mode == "one" else "➡️"
    queue = get_queue(guild_id)
    embed = discord.Embed(
        title="🃏 En cours de lecture",
        description=f"**[{source.title}]({source.webpage_url})**",
        color=RED
    )
    if source.thumbnail:
        embed.set_thumbnail(url=source.thumbnail)
    embed.add_field(name="⏱️ Durée", value=format_duration(source.duration), inline=True)
    embed.add_field(name="🎤 Artiste", value=source.uploader, inline=True)
    embed.add_field(name=f"{loop_emoji} Mode", value=loop_mode.capitalize(), inline=True)
    embed.add_field(name="📋 File d'attente", value=f"{len(queue)} musique(s)", inline=True)
    embed.set_footer(text=footer_text())
    return embed


# ─────────────────────────────────────────
# BOUTONS DE CONTRÔLE
# ─────────────────────────────────────────
class MusicControls(discord.ui.View):
    def __init__(self, guild_id, text_channel):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.text_channel = text_channel

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary, row=0)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
        await interaction.followup.send("⏮️ Retour au début de la piste !", ephemeral=True, delete_after=3)

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.primary, row=0)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        if vc:
            if vc.is_playing():
                vc.pause()
                await interaction.followup.send("⏸️ En pause !", ephemeral=True, delete_after=3)
            elif vc.is_paused():
                vc.resume()
                await interaction.followup.send("▶️ Reprise !", ephemeral=True, delete_after=3)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, row=0)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.followup.send("⏭️ Skippé !", ephemeral=True, delete_after=3)
        else:
            await interaction.followup.send("❌ Rien en cours !", ephemeral=True, delete_after=3)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, row=0)
    async def shuffle_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        queue = get_queue(self.guild_id)
        if queue:
            random.shuffle(queue)
            await interaction.followup.send("🔀 File mélangée !", ephemeral=True, delete_after=3)
        else:
            await interaction.followup.send("❌ File vide !", ephemeral=True, delete_after=3)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, row=0)
    async def loop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        current = loop_modes.get(self.guild_id, "none")
        if current == "none":
            loop_modes[self.guild_id] = "one"
            await interaction.followup.send("🔂 Répétition de la piste !", ephemeral=True, delete_after=3)
        elif current == "one":
            loop_modes[self.guild_id] = "all"
            await interaction.followup.send("🔁 Répétition de la file !", ephemeral=True, delete_after=3)
        else:
            loop_modes[self.guild_id] = "none"
            await interaction.followup.send("➡️ Répétition désactivée !", ephemeral=True, delete_after=3)

    @discord.ui.button(emoji="🔉", style=discord.ButtonStyle.secondary, row=1)
    async def volume_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        vol = max(0.0, volumes.get(self.guild_id, 0.5) - 0.1)
        volumes[self.guild_id] = vol
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = vol
        await interaction.followup.send(f"🔉 Volume : **{int(vol * 100)}%**", ephemeral=True, delete_after=3)

    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, row=1)
    async def volume_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        vol = min(1.0, volumes.get(self.guild_id, 0.5) + 0.1)
        volumes[self.guild_id] = vol
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = vol
        await interaction.followup.send(f"🔊 Volume : **{int(vol * 100)}%**", ephemeral=True, delete_after=3)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, row=1)
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        guild_id = interaction.guild.id
        vc = interaction.guild.voice_client
        if vc:
            queues[guild_id] = []
            loop_modes[guild_id] = "none"
            current_tracks.pop(guild_id, None)
            vc.stop()
            await vc.disconnect()
        await interaction.followup.send("⏹️ Musique arrêtée, Rave déconnecté !", ephemeral=True, delete_after=5)


# ─────────────────────────────────────────
# READY
# ─────────────────────────────────────────
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Rave connecté : {bot.user}")
        print(f"{len(synced)} commandes synchronisées")
    except Exception as e:
        print(f"Erreur sync : {e}")


# ─────────────────────────────────────────
# /play
# ─────────────────────────────────────────
@bot.tree.command(name="play", description="Jouer une musique ou une playlist")
@app_commands.describe(recherche="Lien ou nom de la musique (YouTube, Spotify, SoundCloud)")
async def play(interaction: discord.Interaction, recherche: str):
    await interaction.response.defer()

    if not interaction.user.voice:
        await interaction.followup.send("❌ T'es pas dans un salon vocal !", ephemeral=True)
        return

    channel = interaction.user.voice.channel
    vc = interaction.guild.voice_client

    if vc is None:
        vc = await channel.connect()
    elif vc.channel != channel:
        await vc.move_to(channel)

    guild_id = interaction.guild.id
    queue = get_queue(guild_id)

    embed = discord.Embed(
        title="🔍 Chargement...",
        description=f"Recherche de : **{recherche}**",
        color=GOLD
    )
    embed.set_footer(text=footer_text())
    msg = await interaction.followup.send(embed=embed)

    try:
        sources = await YTDLSource.from_url(recherche, stream=True, volume=volumes.get(guild_id, 0.5))
        if not isinstance(sources, list):
            sources = [sources]

        if vc.is_playing() or vc.is_paused():
            for source in sources:
                queue.append(source.webpage_url)
            if len(sources) == 1:
                embed = discord.Embed(
                    title="➕ Ajouté à la file",
                    description=f"**[{sources[0].title}]({sources[0].webpage_url})**",
                    color=GOLD
                )
                embed.add_field(name="📋 Position", value=f"#{len(queue)}", inline=True)
                embed.add_field(name="⏱️ Durée", value=format_duration(sources[0].duration), inline=True)
                if sources[0].thumbnail:
                    embed.set_thumbnail(url=sources[0].thumbnail)
            else:
                embed = discord.Embed(
                    title="➕ Playlist ajoutée",
                    description=f"**{len(sources)} musiques** ajoutées à la file ! 🃏",
                    color=GOLD
                )
            embed.set_footer(text=footer_text())
            await msg.edit(embed=embed)
        else:
            source = sources[0]
            for s in sources[1:]:
                queue.append(s.webpage_url)
            current_tracks[guild_id] = source
            vc.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(
                play_next(interaction.guild, vc, interaction.channel), bot.loop))
            embed = create_now_playing_embed(source, guild_id)
            view = MusicControls(guild_id, interaction.channel)
            await msg.edit(embed=embed, view=view)
            if len(sources) > 1:
                await interaction.channel.send(
                    f"🃏 **{len(sources) - 1} musiques supplémentaires** ajoutées à la file !")

    except Exception as e:
        embed = discord.Embed(
            title="❌ Erreur",
            description=f"Impossible de charger : `{str(e)}`",
            color=RED
        )
        embed.set_footer(text=footer_text())
        await msg.edit(embed=embed)


# ─────────────────────────────────────────
# /search
# ─────────────────────────────────────────
@bot.tree.command(name="search", description="Rechercher une musique parmi 5 résultats")
@app_commands.describe(recherche="Nom de la musique")
async def search(interaction: discord.Interaction, recherche: str):
    await interaction.response.defer()
    try:
        search_opts = {**YTDL_OPTIONS, 'noplaylist': True}
        with yt_dlp.YoutubeDL(search_opts) as ydl:
            data = await asyncio.get_event_loop().run_in_executor(
                None, lambda: ydl.extract_info(f"ytsearch5:{recherche}", download=False))
        entries = data.get('entries', [])[:5]
        embed = discord.Embed(title=f"🔍 Résultats : {recherche}", color=RED)
        for i, entry in enumerate(entries, 1):
            embed.add_field(
                name=f"{i}. {entry.get('title', 'Inconnu')[:80]}",
                value=f"⏱️ {format_duration(entry.get('duration', 0))} • 👤 {entry.get('uploader', 'Inconnu')}",
                inline=False
            )
        embed.set_footer(text=footer_text())
        view = SearchResults(entries, interaction)
        await interaction.followup.send(embed=embed, view=view)
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)


class SearchResults(discord.ui.View):
    def __init__(self, entries, interaction):
        super().__init__(timeout=30)
        self.entries = entries
        self.original_interaction = interaction
        select = discord.ui.Select(
            placeholder="Choisis une musique...",
            options=[
                discord.SelectOption(
                    label=e.get('title', 'Inconnu')[:100],
                    value=str(i),
                    description=f"⏱️ {format_duration(e.get('duration', 0))}"
                ) for i, e in enumerate(entries)
            ]
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        idx = int(interaction.data['values'][0])
        entry = self.entries[idx]
        url = entry.get('webpage_url') or entry.get('url')
        await play.callback(interaction, url)


# ─────────────────────────────────────────
# /queue
# ─────────────────────────────────────────
@bot.tree.command(name="queue", description="Voir la file d'attente")
async def queue_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild.id
    queue = get_queue(guild_id)
    current = current_tracks.get(guild_id)
    embed = discord.Embed(title="📋 File d'attente", color=RED)
    if current:
        embed.add_field(
            name="🃏 En cours",
            value=f"**[{current.title}]({current.webpage_url})**\n⏱️ {format_duration(current.duration)}",
            inline=False
        )
    if queue:
        queue_text = "\n".join([f"`{i}.` {url[:60]}..." for i, url in enumerate(queue[:10], 1)])
        if len(queue) > 10:
            queue_text += f"\n*...et {len(queue) - 10} autres*"
        embed.add_field(name=f"📋 À venir ({len(queue)})", value=queue_text, inline=False)
    else:
        embed.add_field(name="📋 À venir", value="File vide !", inline=False)
    embed.set_footer(text=footer_text())
    await interaction.followup.send(embed=embed, ephemeral=True)


# ─────────────────────────────────────────
# /nowplaying
# ─────────────────────────────────────────
@bot.tree.command(name="nowplaying", description="Voir la musique en cours")
async def nowplaying(interaction: discord.Interaction):
    await interaction.response.defer()
    current = current_tracks.get(interaction.guild.id)
    if current:
        embed = create_now_playing_embed(current, interaction.guild.id)
        view = MusicControls(interaction.guild.id, interaction.channel)
        await interaction.followup.send(embed=embed, view=view)
    else:
        await interaction.followup.send("❌ Rien en cours !", ephemeral=True)


# ─────────────────────────────────────────
# /skip
# ─────────────────────────────────────────
@bot.tree.command(name="skip", description="Passer à la musique suivante")
async def skip(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    vc = interaction.guild.voice_client
    if vc and (vc.is_playing() or vc.is_paused()):
        vc.stop()
        await interaction.followup.send("⏭️ Skippé !", ephemeral=True)
    else:
        await interaction.followup.send("❌ Rien en cours !", ephemeral=True)


# ─────────────────────────────────────────
# /stop
# ─────────────────────────────────────────
@bot.tree.command(name="stop", description="Arrêter la musique et déconnecter Rave")
async def stop(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild.id
    vc = interaction.guild.voice_client
    if vc:
        queues[guild_id] = []
        loop_modes[guild_id] = "none"
        current_tracks.pop(guild_id, None)
        vc.stop()
        await vc.disconnect()
        await interaction.followup.send("⏹️ Rave a quitté le vocal 🃏", ephemeral=True)
    else:
        await interaction.followup.send("❌ Rave n'est pas dans un vocal !", ephemeral=True)


# ─────────────────────────────────────────
# /pause
# ─────────────────────────────────────────
@bot.tree.command(name="pause", description="Mettre en pause ou reprendre la musique")
async def pause(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    vc = interaction.guild.voice_client
    if vc:
        if vc.is_playing():
            vc.pause()
            await interaction.followup.send("⏸️ En pause !", ephemeral=True)
        elif vc.is_paused():
            vc.resume()
            await interaction.followup.send("▶️ Reprise !", ephemeral=True)
    else:
        await interaction.followup.send("❌ Rave n'est pas dans un vocal !", ephemeral=True)


# ─────────────────────────────────────────
# /volume
# ─────────────────────────────────────────
@bot.tree.command(name="volume", description="Changer le volume (0-100)")
@app_commands.describe(niveau="Volume entre 0 et 100")
async def volume_cmd(interaction: discord.Interaction, niveau: int):
    await interaction.response.defer(ephemeral=True)
    if not 0 <= niveau <= 100:
        await interaction.followup.send("❌ Volume entre 0 et 100 !", ephemeral=True)
        return
    guild_id = interaction.guild.id
    vol = niveau / 100
    volumes[guild_id] = vol
    vc = interaction.guild.voice_client
    if vc and vc.source:
        vc.source.volume = vol
    await interaction.followup.send(f"🔊 Volume réglé à **{niveau}%** !", ephemeral=True)


# ─────────────────────────────────────────
# /loop
# ─────────────────────────────────────────
@bot.tree.command(name="loop", description="Changer le mode de répétition")
@app_commands.choices(mode=[
    app_commands.Choice(name="Désactivé", value="none"),
    app_commands.Choice(name="🔂 Répéter la piste", value="one"),
    app_commands.Choice(name="🔁 Répéter la file", value="all"),
])
async def loop_cmd(interaction: discord.Interaction, mode: str):
    await interaction.response.defer(ephemeral=True)
    loop_modes[interaction.guild.id] = mode
    emojis = {"none": "➡️", "one": "🔂", "all": "🔁"}
    await interaction.followup.send(f"{emojis[mode]} Mode : **{mode}** !", ephemeral=True)


# ─────────────────────────────────────────
# /shuffle
# ─────────────────────────────────────────
@bot.tree.command(name="shuffle", description="Mélanger la file d'attente")
async def shuffle_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    queue = get_queue(interaction.guild.id)
    if queue:
        random.shuffle(queue)
        await interaction.followup.send("🔀 File mélangée !", ephemeral=True)
    else:
        await interaction.followup.send("❌ File vide !", ephemeral=True)


# ─────────────────────────────────────────
# /remove
# ─────────────────────────────────────────
@bot.tree.command(name="remove", description="Supprimer une musique de la file")
@app_commands.describe(position="Position dans la file d'attente")
async def remove(interaction: discord.Interaction, position: int):
    await interaction.response.defer(ephemeral=True)
    queue = get_queue(interaction.guild.id)
    if 1 <= position <= len(queue):
        queue.pop(position - 1)
        await interaction.followup.send(f"🗑️ Musique #{position} supprimée !", ephemeral=True)
    else:
        await interaction.followup.send("❌ Position invalide !", ephemeral=True)


# ─────────────────────────────────────────
# /clearqueue
# ─────────────────────────────────────────
@bot.tree.command(name="clearqueue", description="Vider la file d'attente")
async def clearqueue(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    queues[interaction.guild.id] = []
    await interaction.followup.send("🗑️ File vidée !", ephemeral=True)


# ─────────────────────────────────────────
# /jump
# ─────────────────────────────────────────
@bot.tree.command(name="jump", description="Sauter à une position dans la file")
@app_commands.describe(position="Position dans la file d'attente")
async def jump(interaction: discord.Interaction, position: int):
    await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild.id
    queue = get_queue(guild_id)
    if 1 <= position <= len(queue):
        queues[guild_id] = queue[position - 1:]
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
        await interaction.followup.send(f"⏩ Saut à la position **{position}** !", ephemeral=True)
    else:
        await interaction.followup.send("❌ Position invalide !", ephemeral=True)


# ─────────────────────────────────────────
# ERREURS
# ─────────────────────────────────────────
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    try:
        await interaction.response.send_message(f"❌ Erreur : {error}", ephemeral=True)
    except:
        try:
            await interaction.followup.send(f"❌ Erreur : {error}", ephemeral=True)
        except:
            pass


keep_alive()
bot.run(os.getenv("TOKEN"))