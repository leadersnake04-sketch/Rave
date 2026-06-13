import discord
from discord import app_commands
from discord.ext import commands
import wavelink
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

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)


def footer_text():
    return f"Rave 🃏 • {datetime.now().strftime('%d/%m/%Y à %H:%M')}"


def format_duration(ms):
    if not ms:
        return "∞"
    seconds = ms // 1000
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def create_now_playing_embed(track, player):
    embed = discord.Embed(
        title="🃏 En cours de lecture",
        description=f"**[{track.title}]({track.uri})**",
        color=RED
    )
    if hasattr(track, 'artwork') and track.artwork:
        embed.set_thumbnail(url=track.artwork)
    embed.add_field(name="⏱️ Durée", value=format_duration(track.length), inline=True)
    embed.add_field(name="🎤 Artiste", value=track.author or "Inconnu", inline=True)
    loop_emoji = "🔁" if player.queue.mode == wavelink.QueueMode.loop_all else "🔂" if player.queue.mode == wavelink.QueueMode.loop else "➡️"
    embed.add_field(name=f"{loop_emoji} Mode", value=str(player.queue.mode).split('.')[-1], inline=True)
    embed.add_field(name="📋 File d'attente", value=f"{len(player.queue)} musique(s)", inline=True)
    embed.add_field(name="🔊 Volume", value=f"{player.volume}%", inline=True)
    embed.set_footer(text=footer_text())
    return embed


# ─────────────────────────────────────────
# BOUTONS DE CONTRÔLE
# ─────────────────────────────────────────
class MusicControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def get_player(self, interaction):
        return wavelink.Pool.get_node().get_player(interaction.guild.id)

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary, row=0)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        player = self.get_player(interaction)
        if player:
            await player.seek(0)
            await interaction.followup.send("⏮️ Retour au début !", ephemeral=True, delete_after=3)

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.primary, row=0)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        player = self.get_player(interaction)
        if player:
            await player.pause(not player.paused)
            etat = "⏸️ En pause !" if player.paused else "▶️ Reprise !"
            await interaction.followup.send(etat, ephemeral=True, delete_after=3)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, row=0)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        player = self.get_player(interaction)
        if player:
            await player.skip(force=True)
            await interaction.followup.send("⏭️ Skippé !", ephemeral=True, delete_after=3)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, row=0)
    async def shuffle_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        player = self.get_player(interaction)
        if player and player.queue:
            player.queue.shuffle()
            await interaction.followup.send("🔀 File mélangée !", ephemeral=True, delete_after=3)
        else:
            await interaction.followup.send("❌ File vide !", ephemeral=True, delete_after=3)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, row=0)
    async def loop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        player = self.get_player(interaction)
        if player:
            if player.queue.mode == wavelink.QueueMode.normal:
                player.queue.mode = wavelink.QueueMode.loop
                await interaction.followup.send("🔂 Répétition de la piste !", ephemeral=True, delete_after=3)
            elif player.queue.mode == wavelink.QueueMode.loop:
                player.queue.mode = wavelink.QueueMode.loop_all
                await interaction.followup.send("🔁 Répétition de la file !", ephemeral=True, delete_after=3)
            else:
                player.queue.mode = wavelink.QueueMode.normal
                await interaction.followup.send("➡️ Répétition désactivée !", ephemeral=True, delete_after=3)

    @discord.ui.button(emoji="🔉", style=discord.ButtonStyle.secondary, row=1)
    async def volume_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        player = self.get_player(interaction)
        if player:
            vol = max(0, player.volume - 10)
            await player.set_volume(vol)
            await interaction.followup.send(f"🔉 Volume : **{vol}%**", ephemeral=True, delete_after=3)

    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, row=1)
    async def volume_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        player = self.get_player(interaction)
        if player:
            vol = min(100, player.volume + 10)
            await player.set_volume(vol)
            await interaction.followup.send(f"🔊 Volume : **{vol}%**", ephemeral=True, delete_after=3)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, row=1)
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        player = self.get_player(interaction)
        if player:
            player.queue.clear()
            await player.stop()
            await player.disconnect()
            await interaction.followup.send("⏹️ Rave a quitté le vocal 🃏", ephemeral=True, delete_after=5)


# ─────────────────────────────────────────
# READY + CONNEXION LAVALINK
# ─────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"Rave connecté : {bot.user}")
    await connect_lavalink()
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} commandes synchronisées")
    except Exception as e:
        print(f"Erreur sync : {e}")


async def connect_lavalink():
    host = os.getenv("LAVALINK_HOST", "lavalink-2026-production-f304.up.railway.app")
    port = int(os.getenv("LAVALINK_PORT", 443))
    password = os.getenv("LAVALINK_PASSWORD", "maestrorave2026")

    node = wavelink.Node(
        uri=f"https://{host}:{port}",
        password=password
    )
    await wavelink.Pool.connect(nodes=[node], client=bot)
    print(f"Lavalink connecté : {host}")


@bot.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
    print(f"Node Lavalink prêt : {payload.node.identifier}")


@bot.event
async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload):
    player = payload.player
    if player and hasattr(player, 'text_channel') and player.text_channel:
        embed = create_now_playing_embed(payload.track, player)
        view = MusicControls()
        await player.text_channel.send(embed=embed, view=view)


@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    player = payload.player
    if player and not player.queue and hasattr(player, 'text_channel') and player.text_channel:
        embed = discord.Embed(
            title="🎵 File d'attente terminée",
            description="Plus rien à jouer... Ajoute des musiques avec `/play` 🃏",
            color=RED
        )
        embed.set_footer(text=footer_text())
        await player.text_channel.send(embed=embed)


# ─────────────────────────────────────────
# /play
# ─────────────────────────────────────────
@bot.tree.command(name="play", description="Jouer une musique ou une playlist")
@app_commands.describe(recherche="Lien ou nom (YouTube, Spotify, SoundCloud)")
async def play(interaction: discord.Interaction, recherche: str):
    await interaction.response.defer()

    if not interaction.user.voice:
        await interaction.followup.send("❌ T'es pas dans un salon vocal !", ephemeral=True)
        return

    channel = interaction.user.voice.channel
    player = interaction.guild.voice_client

    if player is None:
        player = await channel.connect(cls=wavelink.Player)
    elif player.channel != channel:
        await player.move_to(channel)

    player.text_channel = interaction.channel
    player.autoplay = wavelink.AutoPlayMode.partial

    embed = discord.Embed(
        title="🔍 Chargement...",
        description=f"Recherche de : **{recherche}**",
        color=GOLD
    )
    embed.set_footer(text=footer_text())
    msg = await interaction.followup.send(embed=embed)

    try:
        tracks = await wavelink.Playable.search(recherche)

        if not tracks:
            await msg.edit(embed=discord.Embed(
                title="❌ Aucun résultat",
                description=f"Impossible de trouver : **{recherche}**",
                color=RED
            ))
            return

        if isinstance(tracks, wavelink.Playlist):
            for track in tracks:
                await player.queue.put_wait(track)
            embed = discord.Embed(
                title="➕ Playlist ajoutée",
                description=f"**{tracks.name}** — {len(tracks)} musiques ajoutées 🃏",
                color=GOLD
            )
            embed.set_footer(text=footer_text())
            await msg.edit(embed=embed)
        else:
            track = tracks[0]
            if player.playing:
                await player.queue.put_wait(track)
                embed = discord.Embed(
                    title="➕ Ajouté à la file",
                    description=f"**[{track.title}]({track.uri})**",
                    color=GOLD
                )
                if hasattr(track, 'artwork') and track.artwork:
                    embed.set_thumbnail(url=track.artwork)
                embed.add_field(name="⏱️ Durée", value=format_duration(track.length), inline=True)
                embed.add_field(name="📋 Position", value=f"#{len(player.queue)}", inline=True)
                embed.set_footer(text=footer_text())
                await msg.edit(embed=embed)
            else:
                await player.play(track)
                await msg.delete()

    except Exception as e:
        await msg.edit(embed=discord.Embed(
            title="❌ Erreur",
            description=f"Impossible de charger : `{str(e)}`",
            color=RED
        ))


# ─────────────────────────────────────────
# /search
# ─────────────────────────────────────────
@bot.tree.command(name="search", description="Rechercher une musique parmi 5 résultats")
@app_commands.describe(recherche="Nom de la musique")
async def search(interaction: discord.Interaction, recherche: str):
    await interaction.response.defer()
    try:
        tracks = await wavelink.Playable.search(f"ytsearch:{recherche}")
        tracks = tracks[:5]

        embed = discord.Embed(title=f"🔍 Résultats : {recherche}", color=RED)
        for i, track in enumerate(tracks, 1):
            embed.add_field(
                name=f"{i}. {track.title[:80]}",
                value=f"⏱️ {format_duration(track.length)} • 👤 {track.author or 'Inconnu'}",
                inline=False
            )
        embed.set_footer(text=footer_text())

        view = SearchResults(tracks, interaction)
        await interaction.followup.send(embed=embed, view=view)
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)


class SearchResults(discord.ui.View):
    def __init__(self, tracks, interaction):
        super().__init__(timeout=30)
        self.tracks = tracks
        self.original_interaction = interaction
        select = discord.ui.Select(
            placeholder="Choisis une musique...",
            options=[
                discord.SelectOption(
                    label=t.title[:100],
                    value=str(i),
                    description=f"⏱️ {format_duration(t.length)}"
                ) for i, t in enumerate(tracks)
            ]
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        idx = int(interaction.data['values'][0])
        track = self.tracks[idx]
        await play.callback(interaction, track.uri)


# ─────────────────────────────────────────
# /queue
# ─────────────────────────────────────────
@bot.tree.command(name="queue", description="Voir la file d'attente")
async def queue_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    player = interaction.guild.voice_client
    embed = discord.Embed(title="📋 File d'attente", color=RED)

    if player and player.current:
        embed.add_field(
            name="🃏 En cours",
            value=f"**[{player.current.title}]({player.current.uri})**\n⏱️ {format_duration(player.current.length)}",
            inline=False
        )

    if player and player.queue:
        queue_text = "\n".join([f"`{i}.` {t.title[:60]}" for i, t in enumerate(list(player.queue)[:10], 1)])
        if len(player.queue) > 10:
            queue_text += f"\n*...et {len(player.queue) - 10} autres*"
        embed.add_field(name=f"📋 À venir ({len(player.queue)})", value=queue_text, inline=False)
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
    player = interaction.guild.voice_client
    if player and player.current:
        embed = create_now_playing_embed(player.current, player)
        view = MusicControls()
        await interaction.followup.send(embed=embed, view=view)
    else:
        await interaction.followup.send("❌ Rien en cours !", ephemeral=True)


# ─────────────────────────────────────────
# /skip
# ─────────────────────────────────────────
@bot.tree.command(name="skip", description="Passer à la musique suivante")
async def skip(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    player = interaction.guild.voice_client
    if player and player.playing:
        await player.skip(force=True)
        await interaction.followup.send("⏭️ Skippé !", ephemeral=True)
    else:
        await interaction.followup.send("❌ Rien en cours !", ephemeral=True)


# ─────────────────────────────────────────
# /stop
# ─────────────────────────────────────────
@bot.tree.command(name="stop", description="Arrêter la musique et déconnecter Rave")
async def stop(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    player = interaction.guild.voice_client
    if player:
        player.queue.clear()
        await player.stop()
        await player.disconnect()
        await interaction.followup.send("⏹️ Rave a quitté le vocal 🃏", ephemeral=True)
    else:
        await interaction.followup.send("❌ Rave n'est pas dans un vocal !", ephemeral=True)


# ─────────────────────────────────────────
# /pause
# ─────────────────────────────────────────
@bot.tree.command(name="pause", description="Mettre en pause ou reprendre")
async def pause(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    player = interaction.guild.voice_client
    if player:
        await player.pause(not player.paused)
        etat = "⏸️ En pause !" if player.paused else "▶️ Reprise !"
        await interaction.followup.send(etat, ephemeral=True)
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
    player = interaction.guild.voice_client
    if player:
        await player.set_volume(niveau)
        await interaction.followup.send(f"🔊 Volume réglé à **{niveau}%** !", ephemeral=True)


# ─────────────────────────────────────────
# /loop
# ─────────────────────────────────────────
@bot.tree.command(name="loop", description="Changer le mode de répétition")
@app_commands.choices(mode=[
    app_commands.Choice(name="➡️ Désactivé", value="none"),
    app_commands.Choice(name="🔂 Répéter la piste", value="one"),
    app_commands.Choice(name="🔁 Répéter la file", value="all"),
])
async def loop_cmd(interaction: discord.Interaction, mode: str):
    await interaction.response.defer(ephemeral=True)
    player = interaction.guild.voice_client
    if player:
        modes = {
            "none": wavelink.QueueMode.normal,
            "one": wavelink.QueueMode.loop,
            "all": wavelink.QueueMode.loop_all
        }
        player.queue.mode = modes[mode]
        emojis = {"none": "➡️", "one": "🔂", "all": "🔁"}
        await interaction.followup.send(f"{emojis[mode]} Mode : **{mode}** !", ephemeral=True)


# ─────────────────────────────────────────
# /shuffle
# ─────────────────────────────────────────
@bot.tree.command(name="shuffle", description="Mélanger la file d'attente")
async def shuffle_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    player = interaction.guild.voice_client
    if player and player.queue:
        player.queue.shuffle()
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
    player = interaction.guild.voice_client
    if player and 1 <= position <= len(player.queue):
        del player.queue[position - 1]
        await interaction.followup.send(f"🗑️ Musique #{position} supprimée !", ephemeral=True)
    else:
        await interaction.followup.send("❌ Position invalide !", ephemeral=True)


# ─────────────────────────────────────────
# /clearqueue
# ─────────────────────────────────────────
@bot.tree.command(name="clearqueue", description="Vider la file d'attente")
async def clearqueue(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    player = interaction.guild.voice_client
    if player:
        player.queue.clear()
    await interaction.followup.send("🗑️ File vidée !", ephemeral=True)


# ─────────────────────────────────────────
# /jump
# ─────────────────────────────────────────
@bot.tree.command(name="jump", description="Sauter à une position dans la file")
@app_commands.describe(position="Position dans la file d'attente")
async def jump(interaction: discord.Interaction, position: int):
    await interaction.response.defer(ephemeral=True)
    player = interaction.guild.voice_client
    if player and 1 <= position <= len(player.queue):
        for _ in range(position - 1):
            player.queue.get()
        await player.skip(force=True)
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