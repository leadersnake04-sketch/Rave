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

intents = discord.Intents.all()

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


def create_np_embed(track, player):
    embed = discord.Embed(
        title="🃏 En cours de lecture",
        description=f"**[{track.title}]({track.uri})**",
        color=RED
    )
    if hasattr(track, 'artwork') and track.artwork:
        embed.set_thumbnail(url=track.artwork)
    embed.add_field(name="⏱️ Durée", value=format_duration(track.length), inline=True)
    embed.add_field(name="🎤 Artiste", value=getattr(track, 'author', 'Inconnu') or 'Inconnu', inline=True)
    embed.add_field(name="📋 File", value=f"{len(player.queue)} musique(s)", inline=True)
    embed.set_footer(text=footer_text())
    return embed


# ─────────────────────────────────────────
# BOUTONS
# ─────────────────────────────────────────
class MusicControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def get_player(self, interaction):
        return interaction.guild.voice_client

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

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, row=0)
    async def loop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        player = self.get_player(interaction)
        if player:
            if player.queue.mode == wavelink.QueueMode.normal:
                player.queue.mode = wavelink.QueueMode.loop
                await interaction.followup.send("🔂 Répétition piste !", ephemeral=True, delete_after=3)
            elif player.queue.mode == wavelink.QueueMode.loop:
                player.queue.mode = wavelink.QueueMode.loop_all
                await interaction.followup.send("🔁 Répétition file !", ephemeral=True, delete_after=3)
            else:
                player.queue.mode = wavelink.QueueMode.normal
                await interaction.followup.send("➡️ Répétition off !", ephemeral=True, delete_after=3)

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
            await interaction.followup.send("⏹️ Rave déconnecté 🃏", ephemeral=True, delete_after=5)


# ─────────────────────────────────────────
# EVENTS
# ─────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"Rave connecté : {bot.user}")
    await setup_lavalink()
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} commandes synchronisées")
    except Exception as e:
        print(f"Erreur sync : {e}")


async def setup_lavalink():
    host = os.getenv("LAVALINK_HOST", "lavalink-2026-production-f304.up.railway.app")
    password = os.getenv("LAVALINK_PASSWORD", "maestrorave2026")

    node = wavelink.Node(
        uri=f"https://{host}",
        password=password,
    )
    await wavelink.Pool.connect(nodes=[node], client=bot, cache_capacity=100)


@bot.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
    print(f"✅ Lavalink connecté : {payload.node.identifier}")


@bot.event
async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload):
    player: wavelink.Player = payload.player
    if hasattr(player, 'text_channel') and player.text_channel:
        embed = create_np_embed(payload.track, player)
        view = MusicControls()
        await player.text_channel.send(embed=embed, view=view)


@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    player: wavelink.Player = payload.player
    if not player.queue and hasattr(player, 'text_channel') and player.text_channel:
        embed = discord.Embed(
            title="🎵 File terminée",
            description="Plus rien à jouer ! Utilise `/play` 🃏",
            color=RED
        )
        embed.set_footer(text=footer_text())
        await player.text_channel.send(embed=embed)


# ─────────────────────────────────────────
# /play
# ─────────────────────────────────────────
@bot.tree.command(name="play", description="Jouer une musique ou playlist")
@app_commands.describe(recherche="Lien ou nom (YouTube, SoundCloud...)")
async def play(interaction: discord.Interaction, recherche: str):
    await interaction.response.defer()

    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send("❌ Rejoins un salon vocal d'abord !", ephemeral=True)
        return

    channel = interaction.user.voice.channel
    player: wavelink.Player = interaction.guild.voice_client

    if not player:
        try:
            player = await channel.connect(cls=wavelink.Player, deaf=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Impossible de rejoindre le vocal : {e}", ephemeral=True)
            return
    elif player.channel.id != channel.id:
        await player.move_to(channel)

    player.text_channel = interaction.channel
    player.autoplay = wavelink.AutoPlayMode.partial

    msg = await interaction.followup.send(embed=discord.Embed(
        title="🔍 Chargement...",
        description=f"Recherche : **{recherche}**",
        color=GOLD
    ))

    try:
        tracks = await wavelink.Playable.search(recherche)

        if not tracks:
            await msg.edit(embed=discord.Embed(
                title="❌ Aucun résultat",
                description=f"Rien trouvé pour : **{recherche}**",
                color=RED
            ))
            return

        if isinstance(tracks, wavelink.Playlist):
            added = 0
            for track in tracks:
                await player.queue.put_wait(track)
                added += 1
            if not player.playing:
                await player.play(player.queue.get())
            embed = discord.Embed(
                title="➕ Playlist ajoutée",
                description=f"**{tracks.name}** — {added} musiques 🃏",
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
                embed.add_field(name="⏱️", value=format_duration(track.length), inline=True)
                embed.add_field(name="📋 Position", value=f"#{len(player.queue)}", inline=True)
                embed.set_footer(text=footer_text())
                await msg.edit(embed=embed)
            else:
                await player.play(track)
                await msg.delete()

    except Exception as e:
        await msg.edit(embed=discord.Embed(
            title="❌ Erreur",
            description=f"`{str(e)}`",
            color=RED
        ))
        print(f"Erreur play : {e}")


# ─────────────────────────────────────────
# /search
# ─────────────────────────────────────────
@bot.tree.command(name="search", description="Rechercher parmi 5 résultats")
@app_commands.describe(recherche="Nom de la musique")
async def search(interaction: discord.Interaction, recherche: str):
    await interaction.response.defer()
    try:
        tracks = await wavelink.Playable.search(f"ytsearch:{recherche}")
        tracks = tracks[:5]
        if not tracks:
            await interaction.followup.send("❌ Aucun résultat !", ephemeral=True)
            return
        embed = discord.Embed(title=f"🔍 {recherche}", color=RED)
        for i, t in enumerate(tracks, 1):
            embed.add_field(
                name=f"{i}. {t.title[:80]}",
                value=f"⏱️ {format_duration(t.length)} • 👤 {getattr(t, 'author', 'Inconnu') or 'Inconnu'}",
                inline=False
            )
        embed.set_footer(text=footer_text())
        view = SearchView(tracks, interaction)
        await interaction.followup.send(embed=embed, view=view)
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)


class SearchView(discord.ui.View):
    def __init__(self, tracks, interaction):
        super().__init__(timeout=30)
        self.tracks = tracks
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
        select.callback = self.select_cb
        self.add_item(select)

    async def select_cb(self, interaction: discord.Interaction):
        idx = int(interaction.data['values'][0])
        track = self.tracks[idx]
        await interaction.response.defer()
        await play.callback(interaction, track.uri or track.title)


# ─────────────────────────────────────────
# /queue
# ─────────────────────────────────────────
@bot.tree.command(name="queue", description="Voir la file d'attente")
async def queue_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    player: wavelink.Player = interaction.guild.voice_client
    embed = discord.Embed(title="📋 File d'attente", color=RED)
    if player and player.current:
        embed.add_field(
            name="🃏 En cours",
            value=f"**[{player.current.title}]({player.current.uri})**\n⏱️ {format_duration(player.current.length)}",
            inline=False
        )
    if player and player.queue:
        txt = "\n".join([f"`{i}.` {t.title[:60]}" for i, t in enumerate(list(player.queue)[:10], 1)])
        if len(player.queue) > 10:
            txt += f"\n*...et {len(player.queue) - 10} autres*"
        embed.add_field(name=f"📋 À venir ({len(player.queue)})", value=txt, inline=False)
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
    player: wavelink.Player = interaction.guild.voice_client
    if player and player.current:
        embed = create_np_embed(player.current, player)
        await interaction.followup.send(embed=embed, view=MusicControls())
    else:
        await interaction.followup.send("❌ Rien en cours !", ephemeral=True)


# ─────────────────────────────────────────
# /skip
# ─────────────────────────────────────────
@bot.tree.command(name="skip", description="Passer à la suivante")
async def skip(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    player: wavelink.Player = interaction.guild.voice_client
    if player and player.playing:
        await player.skip(force=True)
        await interaction.followup.send("⏭️ Skippé !", ephemeral=True)
    else:
        await interaction.followup.send("❌ Rien en cours !", ephemeral=True)


# ─────────────────────────────────────────
# /stop
# ─────────────────────────────────────────
@bot.tree.command(name="stop", description="Arrêter et déconnecter Rave")
async def stop(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    player: wavelink.Player = interaction.guild.voice_client
    if player:
        player.queue.clear()
        await player.stop()
        await player.disconnect()
        await interaction.followup.send("⏹️ Rave déconnecté 🃏", ephemeral=True)
    else:
        await interaction.followup.send("❌ Rave n'est pas connecté !", ephemeral=True)


# ─────────────────────────────────────────
# /pause
# ─────────────────────────────────────────
@bot.tree.command(name="pause", description="Pause ou reprendre")
async def pause(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    player: wavelink.Player = interaction.guild.voice_client
    if player:
        await player.pause(not player.paused)
        await interaction.followup.send("⏸️ Pause !" if player.paused else "▶️ Reprise !", ephemeral=True)


# ─────────────────────────────────────────
# /volume
# ─────────────────────────────────────────
@bot.tree.command(name="volume", description="Changer le volume (0-100)")
@app_commands.describe(niveau="Volume entre 0 et 100")
async def volume_cmd(interaction: discord.Interaction, niveau: int):
    await interaction.response.defer(ephemeral=True)
    if not 0 <= niveau <= 100:
        await interaction.followup.send("❌ Entre 0 et 100 !", ephemeral=True)
        return
    player: wavelink.Player = interaction.guild.voice_client
    if player:
        await player.set_volume(niveau)
        await interaction.followup.send(f"🔊 Volume : **{niveau}%**", ephemeral=True)


# ─────────────────────────────────────────
# /loop
# ─────────────────────────────────────────
@bot.tree.command(name="loop", description="Mode de répétition")
@app_commands.choices(mode=[
    app_commands.Choice(name="➡️ Désactivé", value="none"),
    app_commands.Choice(name="🔂 Piste", value="one"),
    app_commands.Choice(name="🔁 File", value="all"),
])
async def loop_cmd(interaction: discord.Interaction, mode: str):
    await interaction.response.defer(ephemeral=True)
    player: wavelink.Player = interaction.guild.voice_client
    if player:
        modes = {"none": wavelink.QueueMode.normal, "one": wavelink.QueueMode.loop, "all": wavelink.QueueMode.loop_all}
        player.queue.mode = modes[mode]
        emojis = {"none": "➡️", "one": "🔂", "all": "🔁"}
        await interaction.followup.send(f"{emojis[mode]} Mode : **{mode}**", ephemeral=True)


# ─────────────────────────────────────────
# /shuffle
# ─────────────────────────────────────────
@bot.tree.command(name="shuffle", description="Mélanger la file")
async def shuffle_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    player: wavelink.Player = interaction.guild.voice_client
    if player and player.queue:
        player.queue.shuffle()
        await interaction.followup.send("🔀 File mélangée !", ephemeral=True)
    else:
        await interaction.followup.send("❌ File vide !", ephemeral=True)


# ─────────────────────────────────────────
# /remove
# ─────────────────────────────────────────
@bot.tree.command(name="remove", description="Supprimer une musique de la file")
@app_commands.describe(position="Position dans la file")
async def remove(interaction: discord.Interaction, position: int):
    await interaction.response.defer(ephemeral=True)
    player: wavelink.Player = interaction.guild.voice_client
    if player and 1 <= position <= len(player.queue):
        del player.queue[position - 1]
        await interaction.followup.send(f"🗑️ Musique #{position} supprimée !", ephemeral=True)
    else:
        await interaction.followup.send("❌ Position invalide !", ephemeral=True)


# ─────────────────────────────────────────
# /clearqueue
# ─────────────────────────────────────────
@bot.tree.command(name="clearqueue", description="Vider la file")
async def clearqueue(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    player: wavelink.Player = interaction.guild.voice_client
    if player:
        player.queue.clear()
    await interaction.followup.send("🗑️ File vidée !", ephemeral=True)


# ─────────────────────────────────────────
# /jump
# ─────────────────────────────────────────
@bot.tree.command(name="jump", description="Sauter à une position")
@app_commands.describe(position="Position dans la file")
async def jump(interaction: discord.Interaction, position: int):
    await interaction.response.defer(ephemeral=True)
    player: wavelink.Player = interaction.guild.voice_client
    if player and 1 <= position <= len(player.queue):
        for _ in range(position - 1):
            player.queue.get()
        await player.skip(force=True)
        await interaction.followup.send(f"⏩ Saut position **{position}** !", ephemeral=True)
    else:
        await interaction.followup.send("❌ Position invalide !", ephemeral=True)


# ─────────────────────────────────────────
# ERREURS
# ─────────────────────────────────────────
@bot.tree.error
async def on_error(interaction: discord.Interaction, error):
    try:
        await interaction.response.send_message(f"❌ Erreur : {error}", ephemeral=True)
    except:
        try:
            await interaction.followup.send(f"❌ Erreur : {error}", ephemeral=True)
        except:
            pass


keep_alive()
bot.run(os.getenv("TOKEN"))