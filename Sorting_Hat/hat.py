import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# =========================================================
# CONFIG
# =========================================================
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1079764344688095312

HOUSE_ROLE_IDS = {
    "Gryffindor": 1079764344717463579,
    "Hufflepuff": 1079764344717463577,
    "Ravenclaw": 1079764344717463576,
    "Slytherin": 1079764344717463578,
}

EXTRA_ROLE_ID = 1487710450790563890

HOUSE_ORDER = ["Gryffindor", "Hufflepuff", "Ravenclaw", "Slytherin"]

HOUSE_STYLES = {
    "Gryffindor": {
        "color": discord.Color.red(),
        "thumbnail": "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Gryffindor_Crest.png?raw=true",
    },
    "Hufflepuff": {
        "color": discord.Color.gold(),
        "thumbnail": "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Huflepuff_Crest.png?raw=true",
    },
    "Ravenclaw": {
        "color": discord.Color.blue(),
        "thumbnail": "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Ravenclaw_Crest.png?raw=true",
    },
    "Slytherin": {
        "color": discord.Color.green(),
        "thumbnail": "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Slitherin_Crest.png?raw=true",
    },
}

DEFAULT_CREST = "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Hogwarts_Crest.png?raw=true"
ALL_HOUSES_IMAGE = "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/All_Houses.png?raw=true"

sorting_announcement_channels: dict[int, int] = {}
quiz_messages: dict[int, dict[str, int]] = {}
active_sessions: dict[int, dict] = {}

QUESTIONS = [
    {
        "title": "A Journey Begins",
        "question": (
            "Your Hogwarts letter has finally arrived. With your list of school supplies in hand and a little excitement in your chest, "
            "you begin your first magical journey toward Diagon Alley.\n\n"
            "**How would you choose to travel there?**"
        ),
        "gif": "https://i.pinimg.com/736x/a2/74/a5/a274a5079687f9cf6a2be9907b1a8aea.jpg",
        "options": [
            ("By broom, with the wind rushing past", {"Gryffindor": 4}),
            ("Through the Floo Network", {"Hufflepuff": 4}),
            ("By Apparition, quick and precise", {"Slytherin": 4}),
            ("On the Knight Bus, for the adventure", {"Ravenclaw": 4}),
            ("By Thestral, quiet and mysterious", {"Gryffindor": 1, "Hufflepuff": 1, "Ravenclaw": 1, "Slytherin": 1}),
        ],
    },
    {
        "title": "A Pause at the Leaky Cauldron",
        "question": (
            "Before stepping into the hidden wonders of Diagon Alley, you stop at the Leaky Cauldron. "
            "Behind the counter, magical drinks shimmer in the light.\n\n"
            "**Which one do you choose?**"
        ),
        "gif": "https://64.media.tumblr.com/db2b9bf7554f0791bc09a482d07c0dc6/tumblr_mgfivn4SJ31r5s4n9o1_500.gif",
        "options": [
            ("Pumpkin Juice", {"Hufflepuff": 4}),
            ("Butterbeer", {"Gryffindor": 4}),
            ("Firewhisky", {"Slytherin": 4}),
            ("Gillywater", {"Ravenclaw": 4}),
            ("Moldmead", {"Gryffindor": 2, "Hufflepuff": 2}),
            ("Unicorn Blood", {"Ravenclaw": 2, "Slytherin": 2}),
        ],
    },
    {
        "title": "Wonders of Diagon Alley",
        "question": (
            "Now surrounded by enchanted windows, curious trinkets, and busy witches and wizards, one shop draws your attention more than all the others.\n\n"
            "**Which one do you explore first?**"
        ),
        "gif": "https://i.pinimg.com/originals/8f/22/65/8f2265de44f6726a987551a4991c9ac8.gif",
        "options": [
            ("Madam Malkin's Robes for All Occasions", {"Slytherin": 4}),
            ("Magical Menagerie", {"Hufflepuff": 4}),
            ("Quidditch Quality Supplies", {"Gryffindor": 4}),
            ("Florean Fortescue's Ice Cream Parlour", {"Ravenclaw": 4}),
        ],
    },
    {
        "title": "Shelves of Secrets",
        "question": (
            "Inside Flourish and Blotts, rows upon rows of books stretch in every direction. Some seem charming, others a little dangerous.\n\n"
            "**Which title catches your eye first?**"
        ),
        "gif": "https://i.pinimg.com/originals/d9/41/3c/d9413c51e8b86161213defcb48222cbc.gif",
        "options": [
            ("The Monster Book of Monsters", {"Gryffindor": 4}),
            ("Charm Your Own Cheese", {"Hufflepuff": 4}),
            ("Secrets of the Darkest Art", {"Slytherin": 4}),
            ("Numerology and Grammatica", {"Ravenclaw": 4}),
        ],
    },
    {
        "title": "The Founders' Legacy",
        "question": (
            "As you flip through *Hogwarts: A History*, you come across four famous objects once tied to the founders themselves.\n\n"
            "**Which one would you most like to learn more about?**"
        ),
        "gif": "https://i.pinimg.com/originals/f3/3d/ed/f33ded39f152941fa327d0b67d7504e9.gif",
        "options": [
            ("A sword", {"Gryffindor": 4}),
            ("A cup", {"Hufflepuff": 4}),
            ("A diadem", {"Ravenclaw": 4}),
            ("A locket", {"Slytherin": 4}),
        ],
    },
    {
        "title": "A Magical Purchase",
        "question": (
            "Your shopping continues, and one item stands out as something you would happily spend your last few galleons on.\n\n"
            "**What do you choose?**"
        ),
        "gif": "https://64.media.tumblr.com/33a0b70e874fb81d6d2f46185a3a095b/1923acea026d69a1-2a/s500x750/423179bcefcae45959a7157962bef6bea0ad737e.gif",
        "options": [
            ("A fine broom", {"Gryffindor": 4}),
            ("A wizarding chess set", {"Ravenclaw": 4}),
            ("A Hand of Glory", {"Slytherin": 4}),
            ("A patented daydream charm", {"Hufflepuff": 4}),
        ],
    },
    {
        "title": "Tasty Trolley Treats",
        "question": (
            "Later, aboard the Hogwarts Express, the snack trolley rattles past your compartment, full of strange and delightful sweets.\n\n"
            "**Which treat are you reaching for?**"
        ),
        "gif": "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/anything_from.gif?raw=true",
        "options": [
            ("Chocolate Frog", {"Gryffindor": 4}),
            ("Bertie Bott's Every Flavour Beans", {"Ravenclaw": 4}),
            ("Fizzing Whizzbees", {"Hufflepuff": 4}),
            ("Liquorice Wands", {"Slytherin": 4}),
            ("Treacle Tart", {"Gryffindor": 2, "Hufflepuff": 2}),
            ("Pumpkin Pasty", {"Ravenclaw": 2, "Slytherin": 2}),
        ],
    },
    {
        "title": "Lessons Await",
        "question": (
            "As the train carries you closer to Hogwarts, you imagine the lessons waiting beyond the castle doors.\n\n"
            "**Which subject are you most excited to study?**"
        ),
        "gif": "https://images.gr-assets.com/hostedimages/1589957764ra/29507492.gif",
        "options": [
            ("Defense Against the Dark Arts", {"Gryffindor": 4}),
            ("Charms", {"Ravenclaw": 4}),
            ("Potions", {"Slytherin": 4}),
            ("Transfiguration", {"Gryffindor": 2, "Ravenclaw": 2}),
            ("Herbology", {"Hufflepuff": 4}),
            ("Care for Magical Creatures", {"Hufflepuff": 2, "Slytherin": 2}),
        ],
    },
    {
        "title": "Life at Hogwarts",
        "question": (
            "You picture yourself settled at Hogwarts at last, finding your favorite place within castle life.\n\n"
            "**Where do you think you'll spend the most time?**"
        ),
        "gif": "https://media0.giphy.com/media/v1.Y2lkPTZjMDliOTUyZ2RzZGF1MHBuNWJhZzk2ZjFhc2hkZm13NjZoMmNld2xrc3Bna2JhNCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/XFiImydWEVhNC/source.gif",
        "options": [
            ("At the Quidditch Pitch", {"Gryffindor": 4}),
            ("In the common room with friends", {"Hufflepuff": 4}),
            ("In the library", {"Ravenclaw": 4}),
            ("By the lake", {"Slytherin": 4}),
        ],
    },
    {
        "title": "The Sorting Hat's Whisper",
        "question": (
            "At last, you arrive in the Great Hall. Candles glow overhead, the room quiets, and the Sorting Hat is placed gently on your head.\n\n"
            "**The Sorting Hat will take your choice into account… but it also sees your true nature. Which house would you wish to join?**"
        ),
        "gif": "https://github.com/Maiq-The-Liar/General-Gifs/blob/main/Talking_Hat.gif?raw=true",
        "options": [
            ("Gryffindor", {"Gryffindor": 4}),
            ("Hufflepuff", {"Hufflepuff": 4}),
            ("Ravenclaw", {"Ravenclaw": 4}),
            ("Slytherin", {"Slytherin": 4}),
            ("I will let the hat decide", {"Gryffindor": 1, "Hufflepuff": 1, "Ravenclaw": 1, "Slytherin": 1}),
        ],
    },
]

# =========================================================
# DISCORD SETUP
# =========================================================
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True


def member_has_house(member: discord.Member) -> bool:
    house_role_ids = set(HOUSE_ROLE_IDS.values())
    return any(role.id in house_role_ids for role in member.roles)


def resolve_house(scores: dict[str, int]) -> str:
    max_score = max(scores.values())
    for house in HOUSE_ORDER:
        if scores[house] == max_score:
            return house
    return "Gryffindor"


async def assign_house_role(guild: discord.Guild, member: discord.Member, house_name: str) -> bool:
    house_role = guild.get_role(HOUSE_ROLE_IDS[house_name])
    extra_role = guild.get_role(EXTRA_ROLE_ID)

    if house_role is None:
        return False

    roles_to_add = [house_role]

    if extra_role is not None:
        roles_to_add.append(extra_role)

    await member.add_roles(*roles_to_add, reason="Housing quiz result")

    return True


def make_base_embed(title: str, description: str, bot_user: discord.ClientUser | None) -> discord.Embed:
    embed = discord.Embed(title=title, description=description)
    #if bot_user:
    #    embed.set_author(name=bot_user.name, icon_url=bot_user.display_avatar.url)
    embed.set_thumbnail(url=DEFAULT_CREST)
    return embed


def make_house_embed(
    title: str,
    description: str,
    house_name: str,
    bot_user: discord.ClientUser | None,
) -> discord.Embed:
    style = HOUSE_STYLES.get(house_name, {})
    embed = discord.Embed(
        title=title,
        description=description,
        color=style.get("color", discord.Color.blurple()),
    )
    #if bot_user:
    #    embed.set_author(name=bot_user.name, icon_url=bot_user.display_avatar.url)
    if style.get("thumbnail"):
        embed.set_thumbnail(url=style["thumbnail"])
    return embed


def build_question_embed(index: int, qdata: dict, bot_user: discord.ClientUser | None) -> discord.Embed:
    embed = make_base_embed(
        title=f"{qdata['title']}  •  {index + 1}/{len(QUESTIONS)}",
        description=qdata["question"],
        bot_user=bot_user,
    )
    if qdata.get("gif"):
        embed.set_image(url=qdata["gif"])
    embed.set_footer(text="Choose using the buttons below.")
    return embed


class AnswerButton(discord.ui.Button):
    def __init__(self, label: str, score_map: dict[str, int], option_index: int):
        super().__init__(
            label=label,
            style=discord.ButtonStyle.primary,
            custom_id=f"quiz_answer_{option_index}",
        )
        self.score_map = score_map

    async def callback(self, interaction: discord.Interaction) -> None:
        user_id = interaction.user.id
        session = active_sessions.get(user_id)

        if session is None:
            await interaction.response.send_message(
                "This quiz session is no longer active. Please click the start button again.",
                ephemeral=True,
            )
            return

        for house, points in self.score_map.items():
            session["scores"][house] += points

        session["question_index"] += 1

        if session["question_index"] >= len(QUESTIONS):
            guild = interaction.guild or bot.get_guild(session["guild_id"])
            if guild is None:
                active_sessions.pop(user_id, None)
                await interaction.response.edit_message(
                    content="I couldn't find the server anymore. Please try again later.",
                    embed=None,
                    view=None,
                )
                return

            member = guild.get_member(user_id)
            if member is None:
                active_sessions.pop(user_id, None)
                await interaction.response.edit_message(
                    content="I couldn't find your member profile in the server anymore.",
                    embed=None,
                    view=None,
                )
                return

            if member_has_house(member):
                active_sessions.pop(user_id, None)
                await interaction.response.edit_message(
                    content="You already have a house role, so the quiz has been closed.",
                    embed=None,
                    view=None,
                )
                return

            winning_house = resolve_house(session["scores"])
            success = await assign_house_role(guild, member, winning_house)
            final_scores = session["scores"].copy()
            active_sessions.pop(user_id, None)

            if not success:
                await interaction.response.edit_message(
                    content=(
                        f"Your house is **{winning_house}**, but I couldn't assign the role.\n"
                        f"Please make sure the role exists and the bot's role is above the house roles."
                    ),
                    embed=None,
                    view=None,
                )
                return

            result_embed = make_house_embed(
                title="🎓 The Sorting Hat Has Decided",
                description=f"Your place at Hogwarts is **{winning_house}**!",
                house_name=winning_house,
                bot_user=bot.user,
            )
            result_embed.add_field(
                name="Final scores",
                value="\n".join(f"**{house}:** {final_scores[house]}" for house in HOUSE_ORDER),
                inline=False,
            )
            result_embed.set_footer(text="Wear your house colors proudly.")

            await interaction.response.edit_message(embed=result_embed, content=None, view=None)

            announce_channel_id = sorting_announcement_channels.get(guild.id)
            if announce_channel_id is not None:
                channel = guild.get_channel(announce_channel_id)
                if channel is not None:
                    try:
                        announcement_embed = make_house_embed(
                            title="✨ A New Student Has Been Sorted ✨",
                            description=f"{member.mention} has been placed into **{winning_house}**!",
                            house_name=winning_house,
                            bot_user=bot.user,
                        )
                        announcement_embed.set_footer(text="Another witch or wizard has found their house.")
                        await channel.send(embed=announcement_embed)
                    except discord.Forbidden:
                        pass
            return

        next_q = QUESTIONS[session["question_index"]]
        view = QuestionView(next_q["options"])
        embed = build_question_embed(session["question_index"], next_q, bot.user)
        await interaction.response.edit_message(embeds=[embed], content=None, view=view)


class QuestionView(discord.ui.View):
    def __init__(self, options: list[tuple[str, dict[str, int]]]):
        super().__init__(timeout=600)
        for idx, (label, score_map) in enumerate(options):
            self.add_item(AnswerButton(label, score_map, idx))


class StartHousingQuizButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Start Housing Quiz",
            style=discord.ButtonStyle.success,
            custom_id="start_housing_quiz_button",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.defer()
            return

        member = interaction.guild.get_member(interaction.user.id)
        if member is None:
            await interaction.response.defer()
            return

        if member_has_house(member):
            await interaction.response.send_message(
                "You already have a Hogwarts house role.",
                ephemeral=True,
            )
            return

        active_sessions[member.id] = {
            "guild_id": interaction.guild.id,
            "scores": {house: 0 for house in HOUSE_ORDER},
            "question_index": 0,
        }

        intro_embed = make_base_embed(
            title="🕯️ Welcome to Hogwarts",
            description=(
                "Your journey is about to begin.\n\n"
                "Answer the questions below and let the Sorting Hat discover where you belong."
            ),
            bot_user=bot.user,
        )
        intro_embed.add_field(
            name="How it works",
            value="Choose the answer that feels most like you. Your result will be revealed at the end.",
            inline=False,
        )
        intro_embed.set_footer(text="The Sorting Hat is listening...")

        first_question = QUESTIONS[0]
        question_embed = build_question_embed(0, first_question, bot.user)
        view = QuestionView(first_question["options"])

        await interaction.response.send_message(
            embeds=[intro_embed, question_embed],
            view=view,
            ephemeral=True,
        )


class StartHousingQuizView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(StartHousingQuizButton())


class HousingBot(commands.Bot):
    async def setup_hook(self) -> None:
        self.add_view(StartHousingQuizView())
        guild = discord.Object(id=GUILD_ID)
        synced = await self.tree.sync(guild=guild)
        print(f"Synced {len(synced)} guild command(s) to server {GUILD_ID}")


bot = HousingBot(command_prefix="!", intents=intents)


@bot.event
async def on_ready() -> None:
    if bot.user:
        print(f"Logged in as {bot.user} (ID: {bot.user.id})")


@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.default_permissions(administrator=True)
@app_commands.command(name="sethousingquiz", description="Post the housing quiz start embed in this channel.")
async def sethousingquiz(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used in a server.",
            ephemeral=True,
        )
        return

    embed = make_base_embed(
        title="✨ The Hogwarts Housing Quiz ✨",
        description=(
            "Your letter has arrived.\n\n"
            "Click the button below to begin your journey to Hogwarts. "
            "The quiz will open as a private message in this channel that only you can see."
        ),
        bot_user=bot.user,
    )
    embed.add_field(
        name="What happens next?",
        value=(
            "• The quiz opens privately for you in this channel\n"
            "• Your answers shape your result\n"
            "• At the end, you receive your Hogwarts house role"
        ),
        inline=False,
    )
    embed.set_image(url=ALL_HOUSES_IMAGE)
    embed.set_footer(text="Already have a house role? Then the button will do nothing.")

    message = await interaction.channel.send(embed=embed, view=StartHousingQuizView())
    quiz_messages[interaction.guild.id] = {
        "channel_id": interaction.channel.id,
        "message_id": message.id,
    }

    await interaction.response.send_message(
        "Housing quiz embed created in this channel.",
        ephemeral=True,
    )


@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.default_permissions(administrator=True)
@app_commands.command(name="removehousingquiz", description="Remove the currently tracked housing quiz message.")
async def removehousingquiz(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used in a server.",
            ephemeral=True,
        )
        return

    data = quiz_messages.get(interaction.guild.id)
    if not data:
        await interaction.response.send_message(
            "No tracked housing quiz message is currently set.",
            ephemeral=True,
        )
        return

    channel = interaction.guild.get_channel(data["channel_id"])
    if channel is None:
        quiz_messages.pop(interaction.guild.id, None)
        await interaction.response.send_message(
            "The stored quiz channel no longer exists. I cleared the saved quiz reference.",
            ephemeral=True,
        )
        return

    try:
        message = await channel.fetch_message(data["message_id"])
        await message.delete()
    except discord.NotFound:
        pass
    except discord.Forbidden:
        await interaction.response.send_message(
            "I found the quiz message, but I don't have permission to delete it.",
            ephemeral=True,
        )
        return

    quiz_messages.pop(interaction.guild.id, None)
    await interaction.response.send_message(
        "The housing quiz message has been removed.",
        ephemeral=True,
    )


@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.default_permissions(administrator=True)
@app_commands.command(name="addsortingannouncement", description="Set this channel as the public sorting announcement channel.")
async def addsortingannouncement(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used in a server.",
            ephemeral=True,
        )
        return

    sorting_announcement_channels[interaction.guild.id] = interaction.channel.id
    await interaction.response.send_message(
        f"Sorting announcements will now be posted in {interaction.channel.mention}.",
        ephemeral=True,
    )


@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.default_permissions(administrator=True)
@app_commands.command(name="removesortingannouncement", description="Disable public sorting announcements for this server.")
async def removesortingannouncement(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used in a server.",
            ephemeral=True,
        )
        return

    if interaction.guild.id not in sorting_announcement_channels:
        await interaction.response.send_message(
            "No sorting announcement channel is currently set.",
            ephemeral=True,
        )
        return

    sorting_announcement_channels.pop(interaction.guild.id, None)
    await interaction.response.send_message(
        "Sorting announcements have been disabled.",
        ephemeral=True,
    )


bot.tree.add_command(sethousingquiz)
bot.tree.add_command(removehousingquiz)
bot.tree.add_command(addsortingannouncement)
bot.tree.add_command(removesortingannouncement)

# =========================================================
# MAIN
# =========================================================
def main() -> None:
    if not TOKEN:
        raise RuntimeError(
            'DISCORD_TOKEN is not set. Run:\nexport DISCORD_TOKEN="your_token_here"'
        )

    bot.run(TOKEN)


if __name__ == "__main__":
    main()