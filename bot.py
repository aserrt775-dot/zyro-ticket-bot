import os
import discord

from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv


# =========================================================
# CONFIGURATION
# =========================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

ZYRO_ROLE_NAME = "ZYRO"
STAFF_ROLE_NAME = "Ticket Staff"

TICKET_CATEGORIES = {
    "media": {
        "name": "📷・Media",
        "emoji": "📷",
        "label": "Media"
    },
    "purchase": {
        "name": "🛒・Purchase",
        "emoji": "🛒",
        "label": "Purchase"
    },
    "support": {
        "name": "❓・Support",
        "emoji": "❓",
        "label": "Support"
    },
    "reseller": {
        "name": "💰・Reseller",
        "emoji": "💰",
        "label": "Reseller"
    }
}


# =========================================================
# BOT
# =========================================================

intents = discord.Intents.default()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# CRÉATION DU TICKET
# =========================================================

class TicketView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    async def create_ticket(
        self,
        interaction: discord.Interaction,
        ticket_type: str
    ):

        guild = interaction.guild

        if guild is None:
            await interaction.response.send_message(
                "❌ This can only be used inside a server.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        # -------------------------------------------------
        # RÔLES
        # -------------------------------------------------

        zyro_role = discord.utils.get(
            guild.roles,
            name=ZYRO_ROLE_NAME
        )

        staff_role = discord.utils.get(
            guild.roles,
            name=STAFF_ROLE_NAME
        )

        # Si Ticket Staff n'existe pas, on le crée
        if staff_role is None:
            try:
                staff_role = await guild.create_role(
                    name=STAFF_ROLE_NAME,
                    color=discord.Color.red(),
                    reason="Ticket system"
                )
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ I cannot create the Ticket Staff role.",
                    ephemeral=True
                )
                return

        # -------------------------------------------------
        # CATÉGORIE
        # -------------------------------------------------

        category_info = TICKET_CATEGORIES[ticket_type]

        category = discord.utils.get(
            guild.categories,
            name=category_info["name"]
        )

        if category is None:
            try:
                category = await guild.create_category(
                    category_info["name"],
                    reason="Ticket system"
                )
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ I don't have permission to create ticket categories.",
                    ephemeral=True
                )
                return

        # -------------------------------------------------
        # VÉRIFIER SI LE MEMBRE A DÉJÀ UN TICKET
        # -------------------------------------------------

        existing_ticket = discord.utils.find(
            lambda channel:
                isinstance(channel, discord.TextChannel)
                and channel.topic == f"ticket-owner:{interaction.user.id}",
            guild.text_channels
        )

        if existing_ticket:
            await interaction.followup.send(
                f"❌ You already have an open ticket: {existing_ticket.mention}",
                ephemeral=True
            )
            return

        # -------------------------------------------------
        # PERMISSIONS
        # -------------------------------------------------

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),

            # MEMBRE QUI OUVRE
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            ),

            # TICKET STAFF
            staff_role: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
                manage_messages=True
            ),

            # ZYRO
            # Seulement si le rôle existe
        }

        if zyro_role is not None:
            overwrites[zyro_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
                manage_messages=True
            )

        # BOT
        if guild.me is not None:
            overwrites[guild.me] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True,
                attach_files=True,
                embed_links=True
            )

        # -------------------------------------------------
        # NOM DU TICKET
        # -------------------------------------------------

        username = interaction.user.name.lower()

        username = "".join(
            character
            for character in username
            if character.isalnum() or character in "-_"
        )

        username = username[:20]

        channel_name = (
            f"{category_info['emoji']}-{username}"
        )

        # -------------------------------------------------
        # CRÉATION DU SALON
        # -------------------------------------------------

        try:

            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"ticket-owner:{interaction.user.id}",
                reason=f"Ticket created by {interaction.user}"
            )

        except discord.Forbidden:

            await interaction.followup.send(
                "❌ I don't have permission to create ticket channels.",
                ephemeral=True
            )
            return

        except discord.HTTPException as error:

            await interaction.followup.send(
                f"❌ Discord refused to create the ticket.\n`{error}`",
                ephemeral=True
            )
            return

        # -------------------------------------------------
        # EMBED
        # -------------------------------------------------

        embed = discord.Embed(
            title=f"{category_info['emoji']} {category_info['label']} Ticket",
            description=(
                f"Welcome {interaction.user.mention}!\n\n"
                "Please explain your request and wait for "
                "a member of the staff team to assist you."
            ),
            color=discord.Color.red()
        )

        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )

        embed.add_field(
            name="👤 User",
            value=interaction.user.mention,
            inline=True
        )

        embed.add_field(
            name="📂 Category",
            value=category_info["label"],
            inline=True
        )

        embed.set_footer(
            text="Zyro Ticket System"
        )

        # -------------------------------------------------
        # ENVOYER LE TICKET
        # -------------------------------------------------

        mentions = [
            interaction.user.mention,
            staff_role.mention
        ]

        # Ajoute le rôle ZYRO s'il existe
        if zyro_role is not None:
            mentions.append(zyro_role.mention)

        # Ajoute le propriétaire
        if guild.owner_id:
            mentions.append(f"<@{guild.owner_id}>")

        await ticket_channel.send(
            content=" ".join(mentions),
            embed=embed,
            view=CloseTicketView(),
            allowed_mentions=discord.AllowedMentions(
                users=True,
                roles=True
            )
        )

        # -------------------------------------------------
        # CONFIRMATION
        # -------------------------------------------------

        await interaction.followup.send(
            f"✅ Your ticket has been created: {ticket_channel.mention}",
            ephemeral=True
        )

    # =====================================================
    # BOUTONS
    # =====================================================

    @discord.ui.button(
        label="Media",
        emoji="📷",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_media"
    )
    async def media(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await self.create_ticket(
            interaction,
            "media"
        )

    @discord.ui.button(
        label="Purchase",
        emoji="🛒",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_purchase"
    )
    async def purchase(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await self.create_ticket(
            interaction,
            "purchase"
        )

    @discord.ui.button(
        label="Support",
        emoji="❓",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_support"
    )
    async def support(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await self.create_ticket(
            interaction,
            "support"
        )

    @discord.ui.button(
        label="Reseller",
        emoji="💰",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_reseller"
    )
    async def reseller(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await self.create_ticket(
            interaction,
            "reseller"
        )


# =========================================================
# FERMER UN TICKET
# =========================================================

class CloseTicketView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Ticket",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="close_ticket"
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        channel = interaction.channel
        guild = interaction.guild

        if not isinstance(channel, discord.TextChannel):
            return

        if guild is None:
            return

        # Vérifie que c'est bien un ticket
        if not channel.topic:
            await interaction.response.send_message(
                "❌ This is not a ticket channel.",
                ephemeral=True
            )
            return

        if not channel.topic.startswith("ticket-owner:"):
            await interaction.response.send_message(
                "❌ This is not a ticket channel.",
                ephemeral=True
            )
            return

        # Rôles
        staff_role = discord.utils.get(
            guild.roles,
            name=STAFF_ROLE_NAME
        )

        zyro_role = discord.utils.get(
            guild.roles,
            name=ZYRO_ROLE_NAME
        )

        is_staff = (
            staff_role is not None
            and staff_role in interaction.user.roles
        )

        is_zyro = (
            zyro_role is not None
            and zyro_role in interaction.user.roles
        )

        is_admin = (
            interaction.user.guild_permissions.manage_channels
        )

        if not (is_staff or is_zyro or is_admin):

            await interaction.response.send_message(
                "❌ Only Ticket Staff or ZYRO can close tickets.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "🔒 Closing ticket...",
            ephemeral=True
        )

        await channel.delete(
            reason=f"Ticket closed by {interaction.user}"
        )


# =========================================================
# SETUP TICKETS
# =========================================================

@bot.tree.command(
    name="setup-tickets",
    description="Create the ticket system"
)
@app_commands.default_permissions(administrator=True)
async def setup_tickets(
    interaction: discord.Interaction
):

    guild = interaction.guild

    if guild is None:
        await interaction.response.send_message(
            "❌ This command must be used inside a server.",
            ephemeral=True
        )
        return

    await interaction.response.defer(
        ephemeral=True
    )

    # -------------------------------------------------
    # TICKET STAFF
    # -------------------------------------------------

    staff_role = discord.utils.get(
        guild.roles,
        name=STAFF_ROLE_NAME
    )

    if staff_role is None:

        try:

            staff_role = await guild.create_role(
                name=STAFF_ROLE_NAME,
                color=discord.Color.red(),
                reason="Ticket system"
            )

        except discord.Forbidden:

            await interaction.followup.send(
                "❌ I cannot create the Ticket Staff role.",
                ephemeral=True
            )
            return

    # -------------------------------------------------
    # ZYRO
    # -------------------------------------------------

    zyro_role = discord.utils.get(
        guild.roles,
        name=ZYRO_ROLE_NAME
    )

    # -------------------------------------------------
    # CATÉGORIES
    # -------------------------------------------------

    for key, info in TICKET_CATEGORIES.items():

        category = discord.utils.get(
            guild.categories,
            name=info["name"]
        )

        if category is None:

            try:

                category = await guild.create_category(
                    info["name"],
                    reason="Ticket system"
                )

            except discord.Forbidden:

                await interaction.followup.send(
                    "❌ I cannot create ticket categories.",
                    ephemeral=True
                )
                return

        # ---------------------------------------------
        # PERMISSIONS DE LA CATÉGORIE
        # ---------------------------------------------

        try:

            # @everyone ne voit pas
            await category.set_permissions(
                guild.default_role,
                view_channel=False
            )

            # Ticket Staff
            await category.set_permissions(
                staff_role,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            )

            # ZYRO
            if zyro_role is not None:

                await category.set_permissions(
                    zyro_role,
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True
                )

        except discord.Forbidden:
            pass

    # -------------------------------------------------
    # EMBED PANEL
    # -------------------------------------------------

    embed = discord.Embed(
        title="🎫 Support Tickets",
        description=(
            "Need help? Select a category below to open a ticket.\n\n"
            "📷 **Media**\n"
            "Media-related requests.\n\n"
            "🛒 **Purchase**\n"
            "Purchase and order questions.\n\n"
            "❓ **Support**\n"
            "General support.\n\n"
            "💰 **Reseller**\n"
            "Reseller requests."
        ),
        color=discord.Color.red()
    )

    embed.set_footer(
        text="Zyro Ticket System • Select a category below"
    )

    # -------------------------------------------------
    # PANEL
    # -------------------------------------------------

    await interaction.channel.send(
        embed=embed,
        view=TicketView()
    )

    await interaction.followup.send(
        "✅ Ticket system successfully created!",
        ephemeral=True
    )


# =========================================================
# READY
# =========================================================

@bot.event
async def on_ready():

    print(
        f"✅ Connected as {bot.user}"
    )

    try:
        bot.add_view(TicketView())
        bot.add_view(CloseTicketView())

        synced = await bot.tree.sync()

        print(
            f"✅ {len(synced)} command(s) synchronized"
        )

    except Exception as error:

        print(
            f"❌ Synchronization error: {error}"
        )


# =========================================================
# RENDER KEEP-ALIVE (needed for Render to see a running port)
# =========================================================

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

class RenderHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Zyro ticket bot is running")
    def log_message(self, *args):
        pass

def keep_alive():
    port = int(os.getenv("PORT", "10000"))
    print(f"✅ Heartbeat server on port {port}")
    HTTPServer(("0.0.0.0", port), RenderHandler).serve_forever()

threading.Thread(target=keep_alive, daemon=True).start()


# =========================================================
# START
# =========================================================

if not TOKEN:

    raise RuntimeError(
        "❌ DISCORD_TOKEN is missing from the .env file."
    )

bot.run(TOKEN)