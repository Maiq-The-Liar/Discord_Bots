import discord
from discord import app_commands
from discord.ext import commands


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="help",
        description="Learn how the Hogwarts Bot works and see all commands.",
    )
    async def help(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="🪄 Welcome to the Hogwarts System",
            description=(
                "This server features a **fully custom Harry Potter experience**.\n\n"
                "Earn House Points, collect Chocolate Frog Cards, compete in quizzes, "
                "and help your House win the **House Cup** 🏆.\n\n"
                "Everything you do contributes to your progress and your House!"
            ),
            color=0x8B0000,
        )

        # --- Core Gameplay ---
        embed.add_field(
            name="🏆 House Cup",
            value=(
                "• Earn house points through activities\n"
                "• Monthly reset with rewards\n"
                "• Compete for your House to win\n"
                "• Top players earn Galleons 💰"
            ),
            inline=False,
        )

        embed.add_field(
            name="🧠 Quiz System",
            value=(
                "• Answer questions in quiz channels\n"
                "• First correct answer wins\n"
                "• Rewards: **2 House Points + 5 Galleons**\n"
                "• Wrong answers get removed automatically"
            ),
            inline=False,
        )

        embed.add_field(
            name="🍫 Chocolate Frogs",
            value=(
                "• Buy frogs in the shop\n"
                "• Open them to collect famous wizard cards\n"
                "• View your collection in your album\n"
                "• Trade cards with other players"
            ),
            inline=False,
        )

        embed.add_field(
            name="🎂 Birthdays",
            value=(
                "• Set your birthday once\n"
                "• Receive gifts from other members 🎁\n"
            ),
            inline=False,
        )

        embed.add_field(
            name="🧙 Profile System",
            value=(
                "• Custom profile with house, bio, age & pronouns\n"
                "• Track your stats and progress\n"
                "• Show off your Chocolate Frog collection"
            ),
            inline=False,
        )

        # --- Commands Section ---
        embed.add_field(
            name="📜 Commands Overview",
            value=(
                "**👤 Profile**\n"
                "`/profile` – View your profile\n"
                "`/set_profile_bio` – Set your bio\n\n"

                "**🍫 Chocolate Frogs**\n"
                "`/open_chocolate_frog` – Open a frog\n"
                "`/frog_album` – View your collection\n"
                "`/give_card` – Trade cards\n\n"

                "**🧠 Quiz**\n"
                "`/setup_quiz_channel` – (Admin)\n"
                "`/skip_question` – Skip current question\n\n"

                "**🎂 Birthday**\n"
                "`/set_birthday` – Set your birthday\n"

                "**🛒 Shop**\n"
                "`/shop` – View shop\n"
                "`/buy` – Buy items\n\n"

                "**🪄 Misc**\n"
                "`/patronus` – Discover your Patronus"
            ),
            inline=False,
        )

        embed.set_footer(
            text="Tip: Start with /profile and /shop to begin your journey!"
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)