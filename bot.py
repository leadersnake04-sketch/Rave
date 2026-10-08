import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import asyncio
import os
import json
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

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Historique des conversations par utilisateur (user_id -> liste de messages)
conversations = {}
MAX_HISTORY = 10  # garder les 10 derniers messages par utilisateur

SYSTEM_PROMPT = """Tu es Rave, un bot Discord au caractère de Joker — fou, chaotique, imprévisible mais brillant.
Tu parles en français, de façon familière et décontractée.
Tu utilises des emojis comme 🃏🎭🔥 mais pas trop.
Tu peux être sarcastique, mystérieux, drôle.
Tu réponds de façon courte à moyenne (2-4 phrases max sauf si on te demande quelque chose de long).
Tu es sur le serveur Discord "Maestro".
Tu ne parles jamais de ce que tu es vraiment (une IA), tu joues le personnage du fou du roi.
Si on te demande de jouer de la musique, dis que tu n'es plus un bot musique, tu es maintenant une IA.
Exemple de ton style : "Haha, bonne question mon ami... ou peut-être pas si bonne que ça 🃏"
"""


def footer_text():
    return f"Rave 🃏 • {datetime.now().strftime('%d/%m/%Y à %H:%M')}"


# ─────────────────────────────────────────
# FONCTION APPEL API CLAUDE
# ─────────────────────────────────────────
async def call_claude(user_id: int, user_message: str) -> str:
    if user_id not in conversations:
        conversations[user_id] = []

    conversations[user_id].append({
        "role": "user",
        "content": user_message
    })

    # Garder seulement les derniers messages
    if len(conversations[user_id]) > MAX_HISTORY * 2:
        conversations[user_id] = conversations[user_id][-MAX_HISTORY * 2:]

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    payload = {
        "model": "claude-haiku-4-5",
        "max_tokens": 500,
        "system": SYSTEM_PROMPT,
        "messages": conversations[user_id]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    reply = data["content"][0]["text"]

                    conversations[user_id].append({
                        "role": "assistant",
                        "content": reply
                    })

                    return reply
                else:
                    error = await resp.text()
                    print(f"Erreur API : {resp.status} - {error}")
                    return "Hmm... quelque chose a mal tourné dans ma tête tordue 🃏 Réessaie !"
    except asyncio.TimeoutError:
        return "Trop lent pour moi... ou trop rapide pour toi ? 🃏"
    except Exception as e:
        print(f"Erreur : {e}")
        return "Une erreur mystérieuse... comme moi 🎭"


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
# ON_MESSAGE — Réponse IA quand mentionné
# ─────────────────────────────────────────
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Si Rave est mentionné
    if bot.user in message.mentions:
        # Supprimer la mention du message
        content = message.content.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()

        if not content:
            content = "Bonjour !"

        async with message.channel.typing():
            reply = await call_claude(message.author.id, content)

        embed = discord.Embed(
            description=reply,
            color=RED
        )
        embed.set_author(name="Rave 🃏", icon_url=bot.user.display_avatar.url)
        embed.set_footer(text=f"Demandé par {message.author.display_name} • {footer_text()}")
        await message.reply(embed=embed, mention_author=False)

    await bot.process_commands(message)


# ─────────────────────────────────────────
# /ask — Parler à Rave directement
# ─────────────────────────────────────────
@bot.tree.command(name="ask", description="Parler à Rave l'IA 🃏")
@app_commands.describe(message="Ta question ou message pour Rave")
async def ask(interaction: discord.Interaction, message: str):
    await interaction.response.defer()

    async with interaction.channel.typing():
        reply = await call_claude(interaction.user.id, message)

    embed = discord.Embed(
        description=reply,
        color=RED
    )
    embed.set_author(name="Rave 🃏", icon_url=bot.user.display_avatar.url)
    embed.set_footer(text=f"Demandé par {interaction.user.display_name} • {footer_text()}")
    await interaction.followup.send(embed=embed)


# ─────────────────────────────────────────
# /reset — Réinitialiser la conversation
# ─────────────────────────────────────────
@bot.tree.command(name="reset", description="Réinitialiser ta conversation avec Rave")
async def reset(interaction: discord.Interaction):
    if interaction.user.id in conversations:
        conversations.pop(interaction.user.id)
    embed = discord.Embed(
        description="Conversation effacée... comme si elle n'avait jamais existé 🃏",
        color=GOLD
    )
    embed.set_footer(text=footer_text())
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ─────────────────────────────────────────
# /rave — Infos sur Rave
# ─────────────────────────────────────────
@bot.tree.command(name="rave", description="Qui est Rave ?")
async def rave_info(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🃏 Je suis Rave",
        description=(
            "Le fou du roi de Maestro 🎭\n\n"
            "Je suis une IA au caractère chaotique et imprévisible.\n"
            "Parle moi en me mentionnant `@Rave` ou avec `/ask`.\n\n"
            "Je me souviens de notre conversation jusqu'à ce que tu utilises `/reset` 😈"
        ),
        color=RED
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text=footer_text())
    await interaction.response.send_message(embed=embed)


# ─────────────────────────────────────────
# /8ball — Boule magique
# ─────────────────────────────────────────
@bot.tree.command(name="8ball", description="Pose une question à la boule magique de Rave 🎱")
@app_commands.describe(question="Ta question")
async def eight_ball(interaction: discord.Interaction, question: str):
    await interaction.response.defer()
    prompt = f"L'utilisateur pose cette question à une boule magique : '{question}'. Réponds de façon courte (1-2 phrases), mystérieuse et dans ton style Joker. Ne commence pas par 'La boule dit'."
    reply = await call_claude(interaction.user.id, prompt)
    embed = discord.Embed(
        title="🎱 La boule de Rave a parlé",
        description=f"**Question :** {question}\n\n**Réponse :** {reply}",
        color=RED
    )
    embed.set_footer(text=footer_text())
    await interaction.followup.send(embed=embed)


# ─────────────────────────────────────────
# /roast — Vannes
# ─────────────────────────────────────────
@bot.tree.command(name="roast", description="Rave se moque gentiment de quelqu'un 😈")
@app_commands.describe(membre="La personne à roaster")
async def roast(interaction: discord.Interaction, membre: discord.Member):
    await interaction.response.defer()
    prompt = f"Fais une vanne courte et drôle (2-3 phrases max) sur quelqu'un qui s'appelle '{membre.display_name}'. C'est pour rire, reste gentil mais piquant. Style Joker."
    reply = await call_claude(interaction.user.id, prompt)
    embed = discord.Embed(
        description=f"🎯 {membre.mention} ... {reply}",
        color=RED
    )
    embed.set_author(name="Rave 🃏", icon_url=bot.user.display_avatar.url)
    embed.set_footer(text=footer_text())
    await interaction.followup.send(embed=embed)


# ─────────────────────────────────────────
# /blague — Blague
# ─────────────────────────────────────────
@bot.tree.command(name="blague", description="Rave te sort une blague 🃏")
async def blague(interaction: discord.Interaction):
    await interaction.response.defer()
    reply = await call_claude(interaction.user.id, "Raconte moi une blague courte et drôle en français. Juste la blague, sans introduction.")
    embed = discord.Embed(
        title="🃏 Rave te sort une blague",
        description=reply,
        color=GOLD
    )
    embed.set_footer(text=footer_text())
    await interaction.followup.send(embed=embed)


# ─────────────────────────────────────────
# /conseil — Conseil fou
# ─────────────────────────────────────────
@bot.tree.command(name="conseil", description="Demande un conseil à Rave 🃏")
@app_commands.describe(situation="Ta situation")
async def conseil(interaction: discord.Interaction, situation: str):
    await interaction.response.defer()
    prompt = f"Donne un conseil pour cette situation : '{situation}'. Sois utile mais garde ton style chaotique de Joker. 2-3 phrases max."
    reply = await call_claude(interaction.user.id, prompt)
    embed = discord.Embed(
        title="🃏 Le conseil de Rave",
        description=f"**Situation :** {situation}\n\n**Conseil :** {reply}",
        color=RED
    )
    embed.set_footer(text=footer_text())
    await interaction.followup.send(embed=embed)


# ─────────────────────────────────────────
# ERREURS
# ─────────────────────────────────────────
@bot.tree.error
async def on_err(interaction: discord.Interaction, error):
    try:
        await interaction.response.send_message(f"❌ Erreur : {error}", ephemeral=True)
    except:
        try:
            await interaction.followup.send(f"❌ Erreur : {error}", ephemeral=True)
        except:
            pass


keep_alive()
bot.run(os.getenv("MTUwODk4OTI2MjM1ODY0Mjc5OA.GzE2Yg.0MlGXhDPDYsGzOSm7ejL_pqMHrDu6iXjUI-6_E"))